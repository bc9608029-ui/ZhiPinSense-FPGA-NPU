// FPGA -> NPU joint correctness closed-loop smoke test.
//
// Data flow exercised end-to-end in ONE board program:
//
//   frozen IQ (iq_input.bin, 77824 B)
//     -> Linux host MemChunk (dynamic PL-DDR address, 64 B aligned)
//     -> PL DDR (User_Ddr_*)
//     -> FPGA Mandatory Core (START + poll DONE)
//     -> 97280 B 5-plane SInt8 tensor read back to Linux host memory
//     -> byte-compare vs frozen expected_tensor_plddr.bin (mismatch != 0 => STOP)
//     -> per-frame NPU inference (frames 7..18, exp4 Device reopen lifecycle)
//     -> dequantize iq x 1/127, physical x 2/127 -> FP32
//     -> argmax vs frozen reference_argmax.txt
//
// PHASE A reuses VERBATIM the board-verified PL-DDR + Mandatory Core data-path
// smoke (pl_ddr_mandatory_core_smoke.cpp) and its register map
// (pl_ddr_register_map.hpp / pl_ddr_mandatory_core_regs.sv).  No /dev/mem, no
// custom driver, no hardcoded DDR address: the buffer address comes from
// Device::defaultMemRegion().malloc(..., 64) at run time.
//
// PHASE B reuses the exp4 lifecycle from the NPU diagnostic harness
// (npu_diag.cpp): per frame Device::Open -> Session/Tensor -> forward/wait/read
// -> destroy -> Device::Close, RAII-guarded.  exp4 has been board-run three
// times, each run 12/12 MATCH (frames 7-18), timeout=0, error=0, no one-frame
// delay -- the earlier delay_shift=1/11 was a false positive (frames 8 and 9
// both reference 7/OFDM, so frame 9's correct argmax coincides with frame 8's
// reference).  This lifecycle is correctness-verified but NOT real-time
// (per-frame Device/Session setup overhead), so REALTIME_NOT_YET_VALIDATED is
// still emitted.
//
// FROZEN (never touched here): six Mandatory Core RTL, Golden, frozen IQ, model
// (model.json/model.raw/ONNX/best.pt), bitstream, AI_Mate.edif, FMSH patch,
// verified hardware capture, tensor values/layout.  No re-synthesis, no model
// recompile, no SDR, no Device::reset/setOpWait/private FPGA register writes.
//
// gnu++17.  Official iCraft 3.39 APIs only (Device / defaultRegRegion /
// defaultMemRegion / MemChunk / ZG330Backend / HostBackend / Session).

#include <icraft-backends/zg330backend/zg330backend.h>
#include <icraft-backends/hostbackend/backend.h>
#include <icraft-xir/core/network.h>
#include <icraft-xrt/core/device.h>
#include <icraft-xrt/core/session.h>
#include <icraft-xrt/core/tensor.h>
#include <icraft-xrt/dev/host_device.h>
#include <icraft-xrt/dev/zg330_device.h>

#include "pl_ddr_register_map.hpp"

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

// ---- Frozen data-path constants (reused from pl_ddr_mandatory_core_smoke.cpp)
constexpr std::size_t kFrameCount = 19;
constexpr std::size_t kFrameLength = 1024;
constexpr std::size_t kIqFileBytes = kFrameCount * kFrameLength * 4;       // 77824
constexpr std::size_t kTensorFrameBytes = 5 * kFrameLength;                // 5120
constexpr std::size_t kTensorFileBytes = kFrameCount * kTensorFrameBytes;  // 97280
constexpr std::size_t kIqOffset = 0;
constexpr std::size_t kTensorOffset = kIqFileBytes;                        // 77824
constexpr std::size_t kAllocationBytes = kIqFileBytes + kTensorFileBytes;  // 175104

// ---- Frozen NPU-side constants (reused from npu_diag.cpp)
constexpr std::size_t kFrameBytes = kTensorFrameBytes;                     // 5120
constexpr std::size_t kIqSamples = 2 * kFrameLength;                       // 2048 int8
constexpr std::size_t kPhysicalSamples = 3 * kFrameLength;                 // 3072 int8
constexpr float kIqScale = 1.0f / 127.0f;
constexpr float kPhysicalScale = 2.0f / 127.0f;
constexpr const char* kDeviceUrl = "axi://zg330aiu?npu=0x40000000&dma=0x80000000";
constexpr std::uint64_t kRegBaseDefault = 0x400c0000ULL;
constexpr const char* kClasses[8] = {"BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"};
constexpr std::chrono::milliseconds kReadyTimeout{10000};
constexpr std::chrono::seconds kFpgaDeadline{10};

using ZG330Backend = icraft::xrt::zg330::ZG330Backend;
using HostBackend = icraft::xrt::HostBackend;

// ---- small helpers (reused verbatim where noted)

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
                                    std::size_t element_count, const icraft::xrt::MemRegion& region) {
    const auto dtype = value.tensorType();
    if (!dtype->element_dtype.getStorageType().isFP32()) {
        throw std::runtime_error("compiled input storage is not FP32");
    }
    auto tensor = icraft::xrt::Tensor(value).mallocOn(region);
    tensor.write(0, const_cast<char*>(reinterpret_cast<const char*>(source)), element_count * sizeof(float));
    return tensor;
}

std::vector<icraft::xrt::Tensor> make_inputs(const icraft::xir::Network& network,
                                             const std::vector<float>& iq,
                                             const std::vector<float>& physical,
                                             const icraft::xrt::MemRegion& region) {
    std::vector<icraft::xrt::Tensor> inputs;
    inputs.reserve(2);
    for (std::size_t i = 0; i < network.inputs().size(); ++i) {
        const auto value = network.inputs()[i];
        const auto shape = shape_of(value);
        if (same_shape(shape, {1, 2, 1024})) inputs.push_back(make_fp32_input(value, iq.data(), kIqSamples, region));
        else if (same_shape(shape, {1, 3, 1024})) inputs.push_back(make_fp32_input(value, physical.data(), kPhysicalSamples, region));
        else throw std::runtime_error("unexpected compiled input shape");
    }
    return inputs;
}

std::vector<float> read_fp32_logits(const icraft::xrt::Tensor& tensor) {
    std::vector<char> bytes(tensor.dtype().bytes());
    auto host = tensor.to(icraft::xrt::HostDevice::MemRegion());
    host.read(bytes.data(), 0, bytes.size());
    if (bytes.size() != 8 * sizeof(float)) throw std::runtime_error("unexpected logits size");
    std::vector<float> logits(8);
    std::memcpy(logits.data(), bytes.data(), bytes.size());
    return logits;
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

// forward + waitForReady + read.  Returns timed_out=true when waitForReady timed
// out.  Throws on structural errors (wrong output count / size).
struct Fwd { std::vector<float> logits; bool timed_out; double ms; };
Fwd forward_read(icraft::xrt::Session& session, const std::vector<icraft::xrt::Tensor>& inputs) {
    const auto t0 = std::chrono::steady_clock::now();
    const auto outputs = session.forward(inputs);
    if (outputs.size() != 1) throw std::runtime_error("unexpected output count");
    const bool ready = outputs[0].waitForReady(kReadyTimeout);
    const auto logits = read_fp32_logits(outputs[0]);
    const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
    return {logits, !ready, ms};
}

// RAII guard that closes a ZG330 Device exactly once on scope exit, on every
// path (normal return, timeout, or exception).  Close failure is captured into
// *err rather than propagated out of a destructor.
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

// RAII guard that frees a MemChunk exactly once, on every path (normal return
// or exception), BEFORE Device::Close.  free() failure is captured into *err
// rather than propagated out of a destructor.  A destructor must never free
// twice and must never throw during stack unwinding.
struct MemChunkGuard {
    icraft::xrt::MemChunk chunk;
    std::string* err;
    bool freed = false;

    MemChunkGuard(icraft::xrt::MemChunk c, std::string* e) : chunk(std::move(c)), err(e) {}
    MemChunkGuard(const MemChunkGuard&) = delete;
    MemChunkGuard& operator=(const MemChunkGuard&) = delete;

    void free_now() {
        if (freed) return;
        freed = true;   // single attempt; do not retry from the destructor
        try {
            chunk.free();
        } catch (const std::exception& e) {
            if (err && err->empty()) *err = std::string("MemChunk::free failed: ") + e.what();
        }
    }
    ~MemChunkGuard() { free_now(); }
};

// ---- Phase A: FPGA Mandatory Core (PL DDR) -> host memory, byte-exact compare.

struct PhaseAResult {
    std::uint32_t version = 0;
    std::uint32_t status = 0;
    std::uint32_t iq_accepted = 0;
    std::uint32_t tensor_accepted = 0;
    std::uint64_t chunk_addr = 0;
    std::uint64_t tensor_addr = 0;
    std::size_t mismatch = 0;
    std::string error;      // genuine Phase A failure (address/register/timeout/counter/...)
    std::string free_err;   // MemChunk::free() failure (recorded, not swallowed)
    std::string close_err;  // Device::Close() failure (recorded, not swallowed)
};

PhaseAResult run_phase_a(const std::string& device_url, std::uint64_t reg_base,
                         std::vector<char>& iq, const std::vector<char>& expected) {
    PhaseAResult r;

    // Device::Open itself: if it throws here the DeviceGuard is never
    // constructed, so no Device::Close is attempted (requirement 7).  From this
    // point the device is open and is closed exactly once on every later path.
    DeviceGuard dev_guard{ icraft::xrt::Device::Open(device_url), &r.close_err };

    try {
        auto fpai_device = dev_guard.dev.cast<icraft::xrt::ZG330Device>();
        auto& regs = fpai_device.defaultRegRegion();

        // Inner scope: the MemChunk lives here.  All MemChunk / Region / register
        // access is confined to this scope, before the chunk leaves scope and
        // before Device::Close.  A MemChunkGuard frees the chunk exactly once on
        // every path (explicit free_now() on success; destructor fallback on
        // exception), recording any free() failure into r.free_err.
        {
            // Official adder_demo MemChunk allocation pattern; no /dev/mem, no
            // separately invented DMA.  Dynamic run-time physical address, 64 B
            // aligned (requested, then asserted, then checked by hardware [5:0]==0).
            MemChunkGuard chunk_guard{
                fpai_device.defaultMemRegion().malloc(kAllocationBytes, false, 64),
                &r.free_err
            };
            const auto& chunk = chunk_guard.chunk;

            const std::uint64_t chunk_addr = chunk->begin.addr();
            const std::uint64_t tensor_addr = chunk_addr + kTensorOffset;
            if (chunk_addr > 0xffff'ffffULL || tensor_addr > 0xffff'ffffULL) {
                throw std::runtime_error("allocated PL-DDR address does not fit User_Ddr_*[31:0]");
            }
            if ((chunk_addr & 63u) != 0 || (tensor_addr & 63u) != 0) {
                throw std::runtime_error("runtime returned a non-64-byte-aligned MemChunk");
            }

            std::vector<char> zeros(kTensorFileBytes, 0);
            chunk.write(kIqOffset, iq.data(), iq.size());
            chunk.write(kTensorOffset, zeros.data(), zeros.size());

            const auto write_reg = [&](std::uint64_t offset, std::uint32_t value) {
                regs.write(reg_base + offset, value, false);
            };
            const auto read_reg = [&](std::uint64_t offset) {
                return static_cast<std::uint32_t>(regs.read(reg_base + offset, false));
            };

            r.version = read_reg(pl_ddr_regs::VERSION);
            if (r.version != pl_ddr_regs::VERSION_VALUE) {
                std::ostringstream text;
                text << std::hex << r.version;
                throw std::runtime_error("PL register VERSION mismatch: got 0x" + text.str());
            }

            write_reg(pl_ddr_regs::CONTROL, pl_ddr_regs::CONTROL_CLEAR);
            write_reg(pl_ddr_regs::IQ_BASE, static_cast<std::uint32_t>(chunk_addr));
            write_reg(pl_ddr_regs::IQ_BYTES, static_cast<std::uint32_t>(kIqFileBytes));
            write_reg(pl_ddr_regs::TENSOR_BASE, static_cast<std::uint32_t>(tensor_addr));
            write_reg(pl_ddr_regs::TENSOR_BYTES, static_cast<std::uint32_t>(kTensorFileBytes));
            write_reg(pl_ddr_regs::FRAME_COUNT, static_cast<std::uint32_t>(kFrameCount));
            write_reg(pl_ddr_regs::CONTROL, pl_ddr_regs::CONTROL_START);

            std::uint32_t status = 0;
            const auto deadline = std::chrono::steady_clock::now() + kFpgaDeadline;
            while (std::chrono::steady_clock::now() < deadline) {
                status = read_reg(pl_ddr_regs::STATUS);
                if (status & (pl_ddr_regs::STATUS_DONE | pl_ddr_regs::STATUS_ERROR)) break;
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
            if ((status & pl_ddr_regs::STATUS_DONE) == 0) {
                throw std::runtime_error("timeout waiting for PL-DDR operation DONE");
            }
            if (status & pl_ddr_regs::STATUS_ERROR) {
                const auto code = read_reg(pl_ddr_regs::ERROR_CODE);
                throw std::runtime_error("PL-DDR operation reported error " + std::to_string(code));
            }

            r.status = status;
            r.iq_accepted = read_reg(pl_ddr_regs::IQ_ACCEPTED);
            r.tensor_accepted = read_reg(pl_ddr_regs::TENSOR_ACCEPTED);
            if (r.iq_accepted != kFrameCount * kFrameLength ||
                r.tensor_accepted != kFrameCount * kFrameLength) {
                throw std::runtime_error("accepted sample counters do not match 19x1024");
            }

            std::vector<char> tensor(kTensorFileBytes);
            chunk.read(tensor.data(), kTensorOffset, tensor.size());

            // Byte-exact compare vs the frozen Golden capture.
            r.mismatch = 0;
            for (std::size_t i = 0; i < kTensorFileBytes; ++i) {
                if (tensor[i] != expected[i]) ++r.mismatch;
            }

            r.chunk_addr = chunk_addr;
            r.tensor_addr = tensor_addr;

            // Normal path: explicit free before the chunk leaves this scope.
            chunk_guard.free_now();
        }  // chunk_guard destructor runs (freed flag prevents double-free);
           // MemChunk leaves scope HERE, before Device::Close.
    } catch (const std::exception& e) {
        // Any genuine Phase A failure.  During unwinding the MemChunkGuard
        // already attempted free() exactly once.  The device is still open and
        // is closed after this catch.
        r.error = e.what();
    }

    // Close on every path (Open succeeded).  Close failure is captured by the
    // DeviceGuard into r.close_err, not swallowed.
    dev_guard.close_now();

    return r;
}

// ---- argument parsing

struct Options {
    std::string model;
    std::string raw;
    std::string iq;
    std::string expected_tensor;
    std::string reference;
    std::string device_url = kDeviceUrl;
    std::uint64_t reg_base = kRegBaseDefault;
    int first = 7;
    int last = 18;   // inclusive
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
        else if (a == "--frames") { opt.first = std::stoi(next("--frames")); opt.last = std::stoi(next("--frames")); }
        else throw std::runtime_error("unknown argument: " + a);
    }
    if (opt.model.empty() || opt.raw.empty() || opt.iq.empty() ||
        opt.expected_tensor.empty() || opt.reference.empty()) {
        throw std::runtime_error("--model/--raw/--iq/--expected-tensor/--reference are required");
    }
    if (opt.reg_base > 0xffff'ffffULL || (opt.reg_base & 3u) != 0) {
        throw std::runtime_error("register base must be an aligned 32-bit address");
    }
    if (opt.last < opt.first) throw std::runtime_error("--frames: last must be >= first");
    return opt;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options opt = parse_args(argc, argv);

        auto iq = read_exact(opt.iq, kIqFileBytes);
        const auto expected = read_exact(opt.expected_tensor, kTensorFileBytes);
        const std::map<int, int> ref = load_reference_argmax(opt.reference);

        // ---------------- Phase A: FPGA -> host memory ----------------
        std::cout << "== Phase A: FPGA Mandatory Core (PL DDR) -> host memory ==\n";
        const PhaseAResult a = run_phase_a(opt.device_url, opt.reg_base, iq, expected);

        std::cout << "JOINT_PHASE_A iq_bytes=" << kIqFileBytes
                  << " tensor_bytes=" << kTensorFileBytes
                  << " chunk=0x" << std::hex << a.chunk_addr
                  << " tensor_addr=0x" << a.tensor_addr << std::dec << '\n';
        std::cout << "JOINT_PHASE_A fpga_status=0x" << std::hex << a.status << std::dec
                  << " iq_accepted=" << a.iq_accepted
                  << " tensor_accepted=" << a.tensor_accepted << '\n';
        std::cout << "JOINT_PHASE_A tensor_mismatch=" << a.mismatch << '\n';
        if (!a.error.empty()) std::cout << "JOINT_PHASE_A error=" << a.error << '\n';
        if (!a.free_err.empty()) std::cout << "JOINT_PHASE_A free_err=" << a.free_err << '\n';
        if (!a.close_err.empty()) std::cout << "JOINT_PHASE_A close_err=" << a.close_err << '\n';

        const bool phase_a_ok = (a.mismatch == 0 && a.error.empty() &&
                                 a.free_err.empty() && a.close_err.empty());
        if (!phase_a_ok) {
            std::cout << "JOINT_STOP phase A failed (NPU phase skipped)\n";
            std::cout << "JOINT_CORRECTNESS_FAIL\n";
            std::cout << "REALTIME_NOT_YET_VALIDATED\n";
            return 2;
        }

        // ---------------- Phase B: per-frame NPU (exp4 lifecycle) ----------------
        std::cout << "== Phase B: per-frame NPU inference (frames "
                  << opt.first << ".." << opt.last << ", exp4 Device reopen) ==\n";

        // Network is created exactly once; it is a pure data structure that does
        // not depend on the Device handle and is reused across all frame-level
        // Device open/close cycles (matches npu_diag exp4).
        auto network = icraft::xir::Network::CreateFromJsonFile(opt.model);
        network.lazyLoadParamsFromFile(opt.raw);

        int matched = 0, compared = 0, timeout = 0, error = 0;
        std::vector<double> setup_ms_all, forward_ms_all;

        for (int f = opt.first; f <= opt.last; ++f) {
            const char* frame = expected.data() + static_cast<std::size_t>(f) * kFrameBytes;
            std::vector<float> iq_fp(kIqSamples), phys_fp(kPhysicalSamples);
            dequantize(frame, iq_fp, phys_fp);

            bool errored = false, timed_out = false;
            std::string err;
            std::vector<float> logits;
            double setup_ms = -1.0, forward_ms = -1.0;

            std::string close_err;
            DeviceGuard guard{ icraft::xrt::Device::Open(opt.device_url), &close_err };

            try {
                const auto t0 = std::chrono::steady_clock::now();
                {
                    auto session = icraft::xrt::Session::Create<ZG330Backend, HostBackend>(
                        network, { guard.dev, icraft::xrt::HostDevice::Default() });
                    session.apply();
                    const auto inputs = make_inputs(network, iq_fp, phys_fp, icraft::xrt::HostDevice::MemRegion());
                    setup_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
                    const auto r = forward_read(session, inputs);
                    logits = r.logits; timed_out = r.timed_out; forward_ms = r.ms;
                }   // session + inputs destroyed here, before Device::Close
            } catch (const std::exception& e) {
                errored = true;
                err = e.what();
            }

            guard.close_now();   // Device::Close on every path
            if (!close_err.empty()) {
                errored = true;
                if (err.empty()) err = close_err;
                else err += " | " + close_err;
            }

            // Determine this frame's verdict.
            std::cout << "JOINT_FRAME frame=" << f;
            const bool has_ref = ref.count(f) != 0;
            const int ref_id = has_ref ? ref.at(f) : -1;

            if (errored) {
                ++error;
                std::cout << " pred=-1 ref=" << ref_id
                          << " result=ERROR setup=" << std::fixed << std::setprecision(3) << setup_ms
                          << " forward=" << forward_ms << " err=" << err;
            } else if (timed_out) {
                ++timeout;
                const long pred = logits.empty() ? -1 : static_cast<long>(argmax(logits));
                std::cout << " pred=" << pred << " ref=" << ref_id
                          << " result=TIMEOUT setup=" << std::fixed << std::setprecision(3) << setup_ms
                          << " forward=" << forward_ms;
            } else {
                const long pred = static_cast<long>(argmax(logits));
                std::string result;
                if (!has_ref) result = "NO_REF";
                else {
                    ++compared;
                    if (pred == ref_id) { ++matched; result = "MATCH"; }
                    else result = "MISMATCH";
                }
                std::cout << " pred=" << pred << "(" << kClasses[pred] << ")"
                          << " ref=" << ref_id << "(" << (has_ref ? kClasses[ref_id] : "-") << ")"
                          << " result=" << result
                          << " setup=" << std::fixed << std::setprecision(3) << setup_ms
                          << " forward=" << forward_ms;
            }
            std::cout << '\n';

            if (setup_ms >= 0.0) setup_ms_all.push_back(setup_ms);
            if (forward_ms >= 0.0) forward_ms_all.push_back(forward_ms);
        }

        // ---------------- summary ----------------
        std::cout << "JOINT_NPU match=" << matched << "/" << compared
                  << " timeout=" << timeout << " error=" << error;
        if (!setup_ms_all.empty() || !forward_ms_all.empty()) {
            std::cout << "  setup avg=" << std::fixed << std::setprecision(3) << mean(setup_ms_all)
                      << " ms  forward avg=" << mean(forward_ms_all) << " ms";
        }
        std::cout << '\n';

        const bool pass = (a.mismatch == 0 && a.error.empty() && a.free_err.empty() &&
                           a.close_err.empty() && matched == 12 && compared == 12 &&
                           timeout == 0 && error == 0);
        std::cout << (pass ? "JOINT_CORRECTNESS_PASS" : "JOINT_CORRECTNESS_FAIL") << '\n';
        std::cout << "REALTIME_NOT_YET_VALIDATED\n";
        return pass ? 0 : 1;
    } catch (const std::exception& e) {
        std::cerr << "JOINT_SETUP_ERROR: " << e.what() << '\n';
        std::cerr << "JOINT_CORRECTNESS_FAIL\n";
        std::cerr << "REALTIME_NOT_YET_VALIDATED\n";
        return 1;
    }
}
