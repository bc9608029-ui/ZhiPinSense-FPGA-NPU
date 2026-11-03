// Continuous joint stress test — BASELINE DIAGNOSTIC build.
//
// This file is behavior-equivalent to v1's continuous_joint_stress.cpp: the
// reset frequency, Tensor allocation pattern, Session call shape, frame order,
// comparison logic and error handling are all unchanged.  The ONLY additions
// are (a) per-phase steady_clock timing, (b) /proc/self/status VmRSS sampling,
// and (c) resource-allocation counters — none of which alter what the FPGA/NPU
// path executes.  The pure statistics live in latency_diag.hpp.
//
// Nine phases are timed per NPU frame and reported independently in
// LATENCY_PHASE_* lines (count/p50/p95/p99/max/gt_5ms/gt_10ms/gt_100ms):
//   reset, dequantize, input_prepare, forward_submit, wait_ready,
//   output_to_host, output_read, forward_legacy, total_inference.
// forward_legacy_ms = submit + wait + to_host + read, so it stays one-to-one
// comparable with the v1 single forward_ms number (board logs: 425/604/937 ms).
//
// gnu++17.  Official iCraft 3.39 APIs only.

#include <icraft-backends/zg330backend/zg330backend.h>
#include <icraft-backends/hostbackend/backend.h>
#include <icraft-xir/core/network.h>
#include <icraft-xrt/core/device.h>
#include <icraft-xrt/core/session.h>
#include <icraft-xrt/core/tensor.h>
#include <icraft-xrt/dev/host_device.h>
#include <icraft-xrt/dev/zg330_device.h>

#include "pl_ddr_register_map.hpp"
#include "iq_source.hpp"
#include "latency_diag.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace {

// ---- frozen FPGA-side constants (reused from fpga_npu_joint_smoke.cpp) ----
constexpr std::size_t kFrameCount = 19;                 // frames per FPGA task
constexpr std::size_t kFrameLength = 1024;              // samples per frame
constexpr std::size_t kIqFileBytes = kFrameCount * kFrameLength * 4;        // 77824
constexpr std::size_t kTensorFrameBytes = 5 * kFrameLength;                 // 5120
constexpr std::size_t kTensorFileBytes = kFrameCount * kTensorFrameBytes;   // 97280
constexpr std::size_t kIqOffset = 0;
constexpr std::size_t kTensorOffset = kIqFileBytes;                         // 77824
constexpr std::size_t kAllocationBytes = kIqFileBytes + kTensorFileBytes;   // 175104

// ---- frozen NPU-side constants (reused from npu_realtime.cpp) ----
constexpr std::size_t kIqSamples = 2 * kFrameLength;        // 2048 int8 (I,Q)
constexpr std::size_t kPhysicalSamples = 3 * kFrameLength;  // 3072 int8 (power,lag1_re,lag1_im)
constexpr float kIqScale = 1.0f / 127.0f;
constexpr float kPhysicalScale = 2.0f / 127.0f;
constexpr const char* kDeviceUrl = "axi://zg330aiu?npu=0x40000000&dma=0x80000000";
constexpr std::uint64_t kRegBaseDefault = 0x400c0000ULL;
constexpr const char* kClasses[8] = {"BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"};
constexpr std::chrono::milliseconds kReadyTimeout{10000};
constexpr std::chrono::seconds kFpgaDeadline{10};
constexpr int kFirstFrame = 7;   // validated NPU frame range
constexpr int kLastFrame = 18;

using ZG330Backend = icraft::xrt::zg330::ZG330Backend;
using HostBackend = icraft::xrt::HostBackend;
using Clock = std::chrono::steady_clock;

double ms_between(Clock::time_point a, Clock::time_point b) {
    return std::chrono::duration<double, std::milli>(b - a).count();
}

// ---- small helpers (reused verbatim from the verified programs) ----

std::uint64_t parse_u64(const char* text) {
    std::size_t consumed = 0;
    const auto value = std::stoull(text, &consumed, 0);
    if (text[consumed] != '\0') {
        throw std::invalid_argument(std::string("invalid integer: ") + text);
    }
    return value;
}

std::vector<char> read_exact(const std::string& path, std::size_t expected_size) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) throw std::runtime_error("cannot open input file: " + path);
    const auto size = static_cast<std::size_t>(stream.tellg());
    if (size != expected_size) {
        throw std::runtime_error("input size is " + std::to_string(size) +
                                 ", expected " + std::to_string(expected_size) +
                                 " for " + path);
    }
    stream.seekg(0);
    std::vector<char> data(size);
    stream.read(data.data(), static_cast<std::streamsize>(size));
    if (!stream) throw std::runtime_error("failed to read input file: " + path);
    return data;
}

std::vector<int64_t> shape_of(const icraft::xir::Value& value) {
    std::vector<int64_t> result;
    for (const auto dim : value.tensorType()->shape) result.push_back(dim);
    return result;
}

bool same_shape(const std::vector<int64_t>& a, std::initializer_list<int64_t> b) {
    return a == std::vector<int64_t>(b);
}

void dequantize(const char* frame, std::vector<float>& iq, std::vector<float>& physical) {
    const int8_t* iq_int8 = reinterpret_cast<const int8_t*>(frame);
    const int8_t* physical_int8 = reinterpret_cast<const int8_t*>(frame + kIqSamples);
    for (std::size_t i = 0; i < kIqSamples; ++i) iq[i] = static_cast<float>(iq_int8[i]) * kIqScale;
    for (std::size_t i = 0; i < kPhysicalSamples; ++i) physical[i] = static_cast<float>(physical_int8[i]) * kPhysicalScale;
}

icraft::xrt::Tensor make_fp32_input(const icraft::xir::Value& value, const float* source,
                                    std::size_t element_count, const icraft::xrt::MemRegion& region,
                                    latency_diag::ResourceCounters& counters) {
    const auto dtype = value.tensorType();
    if (!dtype->element_dtype.getStorageType().isFP32()) {
        throw std::runtime_error("compiled input storage is not FP32");
    }
    auto tensor = icraft::xrt::Tensor(value).mallocOn(region);
    ++counters.input_allocations;
    tensor.write(0, const_cast<char*>(reinterpret_cast<const char*>(source)), element_count * sizeof(float));
    return tensor;
}

std::vector<icraft::xrt::Tensor> make_inputs(const icraft::xir::Network& network,
                                             const std::vector<float>& iq,
                                             const std::vector<float>& physical,
                                             const icraft::xrt::MemRegion& region,
                                             latency_diag::ResourceCounters& counters) {
    std::vector<icraft::xrt::Tensor> inputs;
    inputs.reserve(2);
    for (std::size_t i = 0; i < network.inputs().size(); ++i) {
        const auto value = network.inputs()[i];
        const auto shape = shape_of(value);
        if (same_shape(shape, {1, 2, 1024})) inputs.push_back(make_fp32_input(value, iq.data(), kIqSamples, region, counters));
        else if (same_shape(shape, {1, 3, 1024})) inputs.push_back(make_fp32_input(value, physical.data(), kPhysicalSamples, region, counters));
        else throw std::runtime_error("unexpected compiled input shape");
    }
    return inputs;
}

std::size_t argmax(const std::vector<float>& v) {
    return static_cast<std::size_t>(std::distance(v.begin(), std::max_element(v.begin(), v.end())));
}

// reference_argmax.txt: "frame_id,argmax_id,argmax_class,ood,ground_truth"
std::map<int, int> load_reference_argmax(const std::string& path) {
    std::ifstream stream(path);
    if (!stream) throw std::runtime_error("cannot open reference file " + path);
    std::map<int, int> ref;
    std::string line;
    bool header = true;
    while (std::getline(stream, line)) {
        if (line.empty()) continue;
        if (header) { header = false; continue; }
        std::stringstream ss(line);
        std::string cell;
        std::vector<std::string> cols;
        while (std::getline(ss, cell, ',')) cols.push_back(cell);
        if (cols.size() < 4) continue;
        if (cols[3] != "1") ref[std::stoi(cols[0])] = std::stoi(cols[1]);
    }
    return ref;
}

double mean(const std::vector<double>& v) {
    if (v.empty()) return 0.0;
    double s = 0.0;
    for (double x : v) s += x;
    return s / static_cast<double>(v.size());
}
double maximum(const std::vector<double>& v) {
    if (v.empty()) return 0.0;
    return *std::max_element(v.begin(), v.end());
}

// Read the VmRSS value from /proc/self/status.  Returns -1 when unavailable.
// This is AUXILIARY evidence only: the iCraft device memory pool may not be
// reflected in Linux VmRSS, so a flat RSS never proves there is no runtime
// resource reclamation by itself.
long long read_vm_rss_kb() {
    std::ifstream f("/proc/self/status");
    if (!f) return -1;
    std::stringstream ss;
    ss << f.rdbuf();
    return latency_diag::parse_vm_rss_kb(ss.str());
}

// RAII guard that closes a ZG330 Device exactly once on every path.  Close
// failure is captured into *err rather than propagated out of a destructor.
struct DeviceGuard {
    icraft::xrt::Device dev;
    std::string* err;
    bool closed = false;
    DeviceGuard(icraft::xrt::Device d, std::string* e) : dev(std::move(d)), err(e) {}
    DeviceGuard(const DeviceGuard&) = delete;
    DeviceGuard& operator=(const DeviceGuard&) = delete;
    void close_now() {
        if (closed) return;
        closed = true;
        try { icraft::xrt::Device::Close(dev); }
        catch (const std::exception& e) {
            if (err && err->empty()) *err = std::string("Device::Close failed: ") + e.what();
        }
    }
    ~DeviceGuard() { close_now(); }
};

// RAII guard that frees a MemChunk exactly once, before Device::Close, on every
// path.  free() failure is captured into *err rather than thrown.
struct MemChunkGuard {
    icraft::xrt::MemChunk chunk;
    std::string* err;
    bool freed = false;
    MemChunkGuard(icraft::xrt::MemChunk c, std::string* e) : chunk(std::move(c)), err(e) {}
    MemChunkGuard(const MemChunkGuard&) = delete;
    MemChunkGuard& operator=(const MemChunkGuard&) = delete;
    void free_now() {
        if (freed) return;
        freed = true;
        try { chunk.free(); }
        catch (const std::exception& e) {
            if (err && err->empty()) *err = std::string("MemChunk::free failed: ") + e.what();
        }
    }
    ~MemChunkGuard() { free_now(); }
};

// ---- options ----

struct Options {
    std::string model, raw, iq, expected_tensor, reference;
    std::string device_url = kDeviceUrl;
    std::uint64_t reg_base = kRegBaseDefault;
    int cycles = 1;         // joint cycles (smoke=1, basic=10, stress=100)
    int first = kFirstFrame;
    int last = kLastFrame;  // NPU frame range, inclusive
};

Options parse_args(int argc, char** argv) {
    Options opt;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        auto next = [&](const char* name) -> std::string {
            if (i + 1 >= argc) throw std::runtime_error(std::string("missing value for ") + name);
            return argv[++i];
        };
        if (a == "--model") opt.model = next("--model");
        else if (a == "--raw") opt.raw = next("--raw");
        else if (a == "--iq") opt.iq = next("--iq");
        else if (a == "--expected-tensor") opt.expected_tensor = next("--expected-tensor");
        else if (a == "--reference") opt.reference = next("--reference");
        else if (a == "--device-url") opt.device_url = next("--device-url");
        else if (a == "--reg-base") opt.reg_base = parse_u64(next("--reg-base").c_str());
        else if (a == "--cycles") opt.cycles = std::stoi(next("--cycles"));
        else if (a == "--first") opt.first = std::stoi(next("--first"));
        else if (a == "--last") opt.last = std::stoi(next("--last"));
        else throw std::runtime_error("unknown argument: " + a);
    }
    if (opt.model.empty() || opt.raw.empty() || opt.iq.empty() ||
        opt.expected_tensor.empty() || opt.reference.empty()) {
        throw std::runtime_error("--model/--raw/--iq/--expected-tensor/--reference are required");
    }
    if (opt.reg_base > 0xffff'ffffULL || (opt.reg_base & 3u) != 0) {
        throw std::runtime_error("register base must be an aligned 32-bit address");
    }
    if (opt.cycles < 1) throw std::runtime_error("--cycles must be >= 1");
    if (opt.last < opt.first) throw std::runtime_error("--last must be >= --first");
    return opt;
}

// One NPU frame on the persistent Session, split into timed phases:
//   submit  = session.forward(inputs)
//   wait    = waitForReady(kReadyTimeout)
//   to_host = outputs[0].to(HostDevice::MemRegion())
//   read    = host.read(...)
// forward_ms stays the single end-to-end number (== v1's forward_ms) for the
// STRESS_SUMMARY average/max; forward_legacy_ms() = submit+wait+to_host+read is
// the newly exposed per-phase counterpart.  The Device::reset(1) re-arm between
// frames is done by the caller, exactly as in v1.
struct NpuOut {
    std::vector<float> logits;
    bool timed_out = false;
    bool errored = false;
    std::string err;
    double forward_ms = -1.0;
    double forward_submit_ms = 0.0;
    double wait_ready_ms = 0.0;
    double output_to_host_ms = 0.0;
    double output_read_ms = 0.0;

    double forward_legacy_ms() const {
        return forward_submit_ms + wait_ready_ms + output_to_host_ms + output_read_ms;
    }
};

NpuOut forward_once(icraft::xrt::Session& session,
                    const std::vector<icraft::xrt::Tensor>& inputs,
                    latency_diag::ResourceCounters& counters) {
    NpuOut out;
    const auto t0 = Clock::now();
    try {
        auto outputs = session.forward(inputs);
        const auto t1 = Clock::now();
        out.forward_submit_ms = ms_between(t0, t1);
        if (outputs.size() != 1) throw std::runtime_error("unexpected output count");
        const bool ready = outputs[0].waitForReady(kReadyTimeout);
        const auto t2 = Clock::now();
        out.wait_ready_ms = ms_between(t1, t2);

        // Inlined read_fp32_logits (identical logic to v1, split for timing).
        std::vector<char> bytes(outputs[0].dtype().bytes());
        auto host = outputs[0].to(icraft::xrt::HostDevice::MemRegion());
        ++counters.output_host_conversions;
        const auto t3 = Clock::now();
        out.output_to_host_ms = ms_between(t2, t3);
        host.read(bytes.data(), 0, bytes.size());
        const auto t4 = Clock::now();
        out.output_read_ms = ms_between(t3, t4);
        if (bytes.size() != 8 * sizeof(float)) throw std::runtime_error("unexpected logits size");
        std::vector<float> logits(8);
        std::memcpy(logits.data(), bytes.data(), bytes.size());
        out.logits = std::move(logits);

        out.forward_ms = ms_between(t0, Clock::now());
        out.timed_out = !ready;
    } catch (const std::exception& e) {
        out.errored = true;
        out.err = e.what();
    }
    return out;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options opt = parse_args(argc, argv);

        const auto iq_bytes = read_exact(opt.iq, kIqFileBytes);
        const auto expected = read_exact(opt.expected_tensor, kTensorFileBytes);
        const std::map<int, int> ref = load_reference_argmax(opt.reference);

        const int npu_frames_per_cycle = opt.last - opt.first + 1;

        // ---------------- open Device once, allocate chunk once ----------------
        std::string close_err, free_err;
        DeviceGuard dev_guard{ icraft::xrt::Device::Open(opt.device_url), &close_err };
        auto zg = dev_guard.dev.cast<icraft::xrt::ZG330Device>();
        auto& regs = zg.defaultRegRegion();

        MemChunkGuard chunk_guard{
            zg.defaultMemRegion().malloc(kAllocationBytes, false, 64), &free_err };
        const auto& chunk = chunk_guard.chunk;
        const std::uint64_t chunk_addr = chunk->begin.addr();
        const std::uint64_t tensor_addr = chunk_addr + kTensorOffset;
        if (chunk_addr > 0xffff'ffffULL || tensor_addr > 0xffff'ffffULL) {
            throw std::runtime_error("allocated PL-DDR address does not fit User_Ddr_*[31:0]");
        }
        if ((chunk_addr & 63u) != 0 || (tensor_addr & 63u) != 0) {
            throw std::runtime_error("runtime returned a non-64-byte-aligned MemChunk");
        }

        const auto write_reg = [&](std::uint64_t offset, std::uint32_t value) {
            regs.write(opt.reg_base + offset, value, false);
        };
        const auto read_reg = [&](std::uint64_t offset) {
            return static_cast<std::uint32_t>(regs.read(opt.reg_base + offset, false));
        };

        const std::uint32_t version0 = read_reg(pl_ddr_regs::VERSION);
        if (version0 != pl_ddr_regs::VERSION_VALUE) {
            std::ostringstream text;
            text << std::hex << version0;
            throw std::runtime_error("PL register VERSION mismatch at startup: got 0x" + text.str());
        }
        std::cout << "STRESS_SETUP device_open=1 chunk=0x" << std::hex << chunk_addr
                  << " tensor_addr=0x" << tensor_addr << std::dec
                  << " version=0x" << std::hex << version0 << std::dec << '\n';

        // ---------------- load network once, create+apply session once ---------
        auto network = icraft::xir::Network::CreateFromJsonFile(opt.model);
        network.lazyLoadParamsFromFile(opt.raw);
        if (network.inputs().size() != 2 || network.outputs().size() != 1) {
            throw std::runtime_error("compiled network must have exactly two inputs and one output");
        }
        auto session = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
            network, { dev_guard.dev, icraft::xrt::HostDevice::Default() });
        session.apply();

        // ---------------- IQ source (frozen file, loop replay) ----------------
        FileIqSource source(iq_bytes, kFrameCount, /*loop=*/true);

        // ---------------- joint loop ------------------------------------------
        int npu_matched = 0, npu_compared = 0;
        int delay_matched = 0, delay_compared = 0;
        int timeout = 0, error = 0;
        int fpga_mismatch_cycles = 0;
        int version_fail = 0;
        int completed_cycles = 0;
        int previous_ref_id = -1;
        bool first_npu = true;
        std::vector<double> fpga_ms_all, forward_ms_all;

        latency_diag::ResourceCounters counters;
        std::vector<latency_diag::FrameTiming> frame_timings;
        frame_timings.reserve(static_cast<std::size_t>(opt.cycles) *
                              static_cast<std::size_t>(npu_frames_per_cycle));

        std::vector<char> iq_block(kIqFileBytes);
        std::vector<char> tensor(kTensorFileBytes);
        std::vector<float> iq_fp(kIqSamples), phys_fp(kPhysicalSamples);

        const long long rss_start_kb = read_vm_rss_kb();
        const auto total_t0 = std::chrono::steady_clock::now();

        for (int c = 0; c < opt.cycles; ++c) {
            // Health check at the top of the cycle: the previous cycle's NPU
            // reset(1) calls must NOT have clobbered the PL-DDR registers.
            const std::uint32_t version_pre = read_reg(pl_ddr_regs::VERSION);
            if (version_pre != pl_ddr_regs::VERSION_VALUE) ++version_fail;

            // ---- 1) gather 19 full frames from the IQ source (byte-exact) ----
            for (int f = 0; f < static_cast<int>(kFrameCount); ++f) {
                iq::Frame fr;
                if (!source.next(fr)) {
                    throw std::runtime_error("IQ source ended mid-cycle (loop replay must not end)");
                }
                if (fr.short_frame) {
                    // Contract: a partial frame is never silently fed to the FPGA.
                    throw std::runtime_error("IQ source produced a short frame; refusing to feed FPGA");
                }
                std::memcpy(iq_block.data() + static_cast<std::size_t>(f) * iq::kFrameBytes,
                            fr.iq, iq::kFrameBytes);
            }

            // ---- 2) FPGA: write IQ, clear tensor, configure, START, poll, read ----
            {
                std::vector<char> zeros(kTensorFileBytes, 0);
                chunk.write(kIqOffset, iq_block.data(), iq_block.size());
                chunk.write(kTensorOffset, zeros.data(), zeros.size());

                // Re-configure ALL PL control registers every cycle; never rely
                // on register state surviving the previous cycle's reset(1).
                write_reg(pl_ddr_regs::CONTROL, pl_ddr_regs::CONTROL_CLEAR);
                write_reg(pl_ddr_regs::IQ_BASE, static_cast<std::uint32_t>(chunk_addr));
                write_reg(pl_ddr_regs::IQ_BYTES, static_cast<std::uint32_t>(kIqFileBytes));
                write_reg(pl_ddr_regs::TENSOR_BASE, static_cast<std::uint32_t>(tensor_addr));
                write_reg(pl_ddr_regs::TENSOR_BYTES, static_cast<std::uint32_t>(kTensorFileBytes));
                write_reg(pl_ddr_regs::FRAME_COUNT, static_cast<std::uint32_t>(kFrameCount));
                write_reg(pl_ddr_regs::CONTROL, pl_ddr_regs::CONTROL_START);

                const auto t0 = std::chrono::steady_clock::now();
                std::uint32_t status = 0;
                const auto deadline = std::chrono::steady_clock::now() + kFpgaDeadline;
                while (std::chrono::steady_clock::now() < deadline) {
                    status = read_reg(pl_ddr_regs::STATUS);
                    if (status & (pl_ddr_regs::STATUS_DONE | pl_ddr_regs::STATUS_ERROR)) break;
                    std::this_thread::sleep_for(std::chrono::milliseconds(1));
                }
                const double fpga_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
                fpga_ms_all.push_back(fpga_ms);

                const std::uint32_t iq_accepted = read_reg(pl_ddr_regs::IQ_ACCEPTED);
                const std::uint32_t tensor_accepted = read_reg(pl_ddr_regs::TENSOR_ACCEPTED);

                bool fpga_ok = true;
                if ((status & pl_ddr_regs::STATUS_DONE) == 0) {
                    ++error;
                    std::cout << "STRESS_CYCLE id=" << c << " result=FPGA_TIMEOUT status=0x" << std::hex << status << std::dec << '\n';
                    fpga_ok = false;
                } else if (status & pl_ddr_regs::STATUS_ERROR) {
                    const auto code = read_reg(pl_ddr_regs::ERROR_CODE);
                    ++error;
                    std::cout << "STRESS_CYCLE id=" << c << " result=FPGA_ERROR code=" << code << '\n';
                    fpga_ok = false;
                } else if (iq_accepted != kFrameCount * kFrameLength ||
                           tensor_accepted != kFrameCount * kFrameLength) {
                    ++error;
                    std::cout << "STRESS_CYCLE id=" << c << " result=FPGA_COUNTER iq_accepted=" << iq_accepted
                              << " tensor_accepted=" << tensor_accepted << '\n';
                    fpga_ok = false;
                }

                std::size_t mismatch = 0;
                if (fpga_ok) {
                    chunk.read(tensor.data(), kTensorOffset, tensor.size());
                    for (std::size_t i = 0; i < kTensorFileBytes; ++i) {
                        if (tensor[i] != expected[i]) ++mismatch;
                    }
                    if (mismatch != 0) ++fpga_mismatch_cycles;
                }

                std::cout << "STRESS_CYCLE id=" << c
                          << " version_pre=0x" << std::hex << version_pre << std::dec
                          << " fpga_status=0x" << std::hex << status << std::dec
                          << " iq_accepted=" << iq_accepted
                          << " tensor_accepted=" << tensor_accepted
                          << " mismatch=" << mismatch
                          << " fpga_ms=" << std::fixed << std::setprecision(3) << fpga_ms
                          << '\n';

                if (!fpga_ok) {
                    // A failed FPGA cycle has no valid tensor for NPU; abort the
                    // run rather than infer on stale/garbage data.
                    break;
                }
            }

            // ---- 3) NPU: frames first..last on the persistent Session ----
            for (int f = opt.first; f <= opt.last; ++f) {
                latency_diag::FrameTiming timing;
                timing.cycle = c;
                timing.frame = f;
                const auto t_frame = Clock::now();

                dequantize(tensor.data() + static_cast<std::size_t>(f) * kTensorFrameBytes, iq_fp, phys_fp);
                const auto t_deq = Clock::now();
                timing.dequantize_ms = ms_between(t_frame, t_deq);

                const auto inputs = make_inputs(network, iq_fp, phys_fp,
                                                icraft::xrt::HostDevice::MemRegion(), counters);
                const auto t_input = Clock::now();
                timing.input_prepare_ms = ms_between(t_deq, t_input);

                // re-arm + PL-health check around reset(1) (read-only VERSION).
                if (!first_npu) {
                    const auto t_reset0 = Clock::now();
                    const std::uint32_t vb = read_reg(pl_ddr_regs::VERSION);
                    dev_guard.dev.reset(1);
                    const std::uint32_t va = read_reg(pl_ddr_regs::VERSION);
                    if (vb != pl_ddr_regs::VERSION_VALUE || va != pl_ddr_regs::VERSION_VALUE) ++version_fail;
                    const auto t_reset1 = Clock::now();
                    timing.reset_ms = ms_between(t_reset0, t_reset1);
                } else {
                    first_npu = false;
                    timing.reset_ms = 0.0;
                }

                const NpuOut out = forward_once(session, inputs, counters);
                const auto t_end = Clock::now();
                timing.forward_submit_ms = out.forward_submit_ms;
                timing.wait_ready_ms = out.wait_ready_ms;
                timing.output_to_host_ms = out.output_to_host_ms;
                timing.output_read_ms = out.output_read_ms;
                timing.total_ms = ms_between(t_frame, t_end);

                const bool has_ref = ref.count(f) != 0;
                const int ref_id = has_ref ? ref.at(f) : -1;

                std::cout << "STRESS_NPU cycle=" << c << " frame=" << f;
                if (out.errored) {
                    ++error;
                    std::cout << " pred=-1 ref=" << ref_id << " result=ERROR err=" << out.err;
                } else if (out.timed_out) {
                    ++timeout;
                    const long pred = out.logits.empty() ? -1 : static_cast<long>(argmax(out.logits));
                    std::cout << " pred=" << pred << " ref=" << ref_id << " result=TIMEOUT";
                } else {
                    const long pred = static_cast<long>(argmax(out.logits));
                    std::string result = "NO_REF";
                    if (has_ref) {
                        ++npu_compared;
                        if (pred == ref_id) { ++npu_matched; result = "MATCH"; }
                        else result = "MISMATCH";
                    }
                    char delay = '-';
                    // A repeated class in adjacent inputs is not evidence of stale
                    // output.  Count the delay diagnostic only when the previous
                    // input had a different expected class, across cycle boundary
                    // 18 -> 7 included.
                    if (has_ref && previous_ref_id >= 0 && previous_ref_id != ref_id) {
                        ++delay_compared;
                        if (pred == previous_ref_id) { ++delay_matched; delay = 'y'; }
                        else delay = 'n';
                    }
                    std::cout << " pred=" << pred << "(" << kClasses[pred] << ")"
                              << " ref=" << ref_id << "(" << (has_ref ? kClasses[ref_id] : "-") << ")"
                              << " result=" << result << " delay=" << delay;
                    if (has_ref) previous_ref_id = ref_id;
                }
                if (out.forward_ms >= 0.0) forward_ms_all.push_back(out.forward_ms);
                std::cout << " forward=" << std::fixed << std::setprecision(3) << out.forward_ms << '\n';

                // Per-frame latency record (every frame, including the first of
                // each cycle and any slow frame, is captured; only an errored
                // frame — which threw and thus has no complete timing — is not).
                if (!out.errored) {
                    frame_timings.push_back(timing);
                    std::cout << "LATENCY_FRAME cycle=" << c << " frame=" << f
                              << " reset=" << std::fixed << std::setprecision(3) << timing.reset_ms
                              << " dequantize=" << timing.dequantize_ms
                              << " input_prepare=" << timing.input_prepare_ms
                              << " submit=" << timing.forward_submit_ms
                              << " wait=" << timing.wait_ready_ms
                              << " to_host=" << timing.output_to_host_ms
                              << " read=" << timing.output_read_ms
                              << " forward_legacy=" << timing.forward_legacy_ms()
                              << " total=" << timing.total_ms
                              << '\n';
                }
            }

            // Health check after this cycle's reset(1) calls.
            const std::uint32_t version_post = read_reg(pl_ddr_regs::VERSION);
            if (version_post != pl_ddr_regs::VERSION_VALUE) ++version_fail;
            if (version_post != version_pre) {
                std::cout << "STRESS_VHEALTH id=" << c << " version_changed=0x"
                          << std::hex << version_pre << "->0x" << version_post << std::dec << '\n';
            }
            ++completed_cycles;   // FPGA + NPU both ran this cycle
        }

        const long long rss_end_kb = read_vm_rss_kb();
        const double total_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - total_t0).count();

        // ---------------- per-phase latency statistics ----------------
        const latency_diag::PhaseStats ps = latency_diag::compute_phase_stats(frame_timings);
        const auto dump_phase = [](const char* name, const latency_diag::PercentileStats& s) {
            std::cout << "LATENCY_PHASE " << name
                      << " count=" << s.count
                      << " p50=" << std::fixed << std::setprecision(3) << s.p50_ms
                      << " p95=" << s.p95_ms
                      << " p99=" << s.p99_ms
                      << " max=" << s.max_ms
                      << " gt_5ms=" << s.gt_5ms
                      << " gt_10ms=" << s.gt_10ms
                      << " gt_100ms=" << s.gt_100ms
                      << '\n';
        };
        dump_phase("reset", ps.reset);
        dump_phase("dequantize", ps.dequantize);
        dump_phase("input_prepare", ps.input_prepare);
        dump_phase("forward_submit", ps.forward_submit);
        dump_phase("wait_ready", ps.wait_ready);
        dump_phase("output_to_host", ps.output_to_host);
        dump_phase("output_read", ps.output_read);
        dump_phase("forward_legacy", ps.forward_legacy);
        dump_phase("total_inference", ps.total_inference);

        // ---------------- summary + throughput ----------------
        const int cycles_done = completed_cycles;
        const int npu_frames_done = cycles_done * npu_frames_per_cycle;
        std::cout << "STRESS_SUMMARY cycles=" << cycles_done
                  << " npu_frames=" << npu_frames_done
                  << " match=" << npu_matched << "/" << npu_compared
                  << " delay_shift=" << delay_matched << "/" << delay_compared
                  << " timeout=" << timeout << " error=" << error
                  << " fpga_mismatch_cycles=" << fpga_mismatch_cycles
                  << " version_fail=" << version_fail;
        if (!fpga_ms_all.empty()) {
            std::cout << " fpga_avg=" << std::fixed << std::setprecision(3) << mean(fpga_ms_all)
                      << " fpga_max=" << maximum(fpga_ms_all);
        }
        if (!forward_ms_all.empty()) {
            std::cout << " npu_avg=" << std::fixed << std::setprecision(3) << mean(forward_ms_all)
                      << " npu_max=" << maximum(forward_ms_all);
        }
        std::cout << '\n';

        std::cout << "LATENCY_SUMMARY rss_start_kb=" << rss_start_kb
                  << " rss_end_kb=" << rss_end_kb
                  << " input_allocations=" << counters.input_allocations
                  << " output_host_conversions=" << counters.output_host_conversions
                  << " frames_recorded=" << frame_timings.size()
                  << '\n';

        if (total_ms > 0.0) {
            std::cout << "STRESS_THROUGHPUT total_ms=" << std::fixed << std::setprecision(1) << total_ms
                      << " cycles_per_sec=" << std::setprecision(3) << (cycles_done * 1000.0 / total_ms)
                      << " npu_frames_per_sec=" << (npu_frames_done * 1000.0 / total_ms)
                      << " iq_samples_per_sec=" << std::setprecision(1) << (cycles_done * kFrameCount * kFrameLength * 1000.0 / total_ms)
                      << '\n';
        }

        const bool correctness_pass = (npu_matched == npu_compared &&
                                       npu_compared == npu_frames_done &&
                                       delay_matched == 0 &&
                                       timeout == 0 && error == 0 &&
                                       fpga_mismatch_cycles == 0 &&
                                       version_fail == 0);
        std::cout << (correctness_pass ? "STRESS_RESULT=PASS" : "STRESS_RESULT=FAIL") << '\n';

        // Free the chunk and close the device (guards run on every path).  Any
        // deferred free/close error is surfaced rather than swallowed.
        chunk_guard.free_now();
        dev_guard.close_now();
        if (!free_err.empty()) { std::cerr << "STRESS_ERROR: " << free_err << '\n'; return 1; }
        if (!close_err.empty()) { std::cerr << "STRESS_ERROR: " << close_err << '\n'; return 1; }

        // ---- auto spike-reproduction gate ----
        // The baseline's job is to REPRODUCE the board spike (>=1 frame with
        // forward_legacy > 100 ms).  If none is found, the diagnostic condition
        // does not hold: return non-zero and explicitly forbid running the fixed
        // tests.  Every slow frame's (cycle, frame) is listed so it can be
        // checked against the original pattern (frame=7, every 6 cycles).
        const latency_diag::SpikeDetection spikes =
            latency_diag::detect_spikes(frame_timings, /*spike_threshold_ms=*/100.0);
        for (const auto& k : spikes.slow_frames) {
            std::cout << "BASELINE_SPIKE_FRAME cycle=" << k.cycle << " frame=" << k.frame << '\n';
        }
        std::cout << "BASELINE_SPIKE_REPRODUCED=" << (spikes.reproduced ? "YES" : "NO") << '\n';

        if (!correctness_pass) {
            std::cerr << "BASELINE_CORRECTNESS_FAIL: correctness gate failed; spike data is not trustworthy.\n";
            return 1;
        }
        if (!spikes.reproduced) {
            std::cerr << "BASELINE_NO_SPIKE: no forward_legacy>100ms frame observed; "
                         "STOP — do not run the fixed tests until the spike is reproduced.\n";
            return 1;
        }
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "STRESS_SETUP_ERROR: " << e.what() << '\n';
        std::cerr << "STRESS_RESULT=FAIL\n";
        return 1;
    }
}
