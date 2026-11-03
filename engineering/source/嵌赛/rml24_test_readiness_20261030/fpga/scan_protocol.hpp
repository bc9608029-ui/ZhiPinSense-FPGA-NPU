#pragma once
#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace scan {
constexpr std::uint32_t VERSION=0x0c,STATUS=0x10,FRAME=0x14,COUNT=0x18,ERROR=0x1c;
struct Result {std::vector<std::uint64_t> psd;std::uint32_t frame=0;};
template<class Io> Result run(Io& io,std::uint32_t address,int timeout_ms=1500) {
 if ((address&63u)!=0 || timeout_ms<=0) throw std::runtime_error("bad_config");
 if (io.read(VERSION)!=1) throw std::runtime_error("version_mismatch");
 if (io.read(STATUS)&1u) throw std::runtime_error("preexisting_busy");
 io.write(8,2);io.write(0,address);io.write(4,4096);io.write(8,1);
 auto wait=[&](std::uint32_t mask,const char* message) {
  auto until=std::chrono::steady_clock::now()+std::chrono::milliseconds(timeout_ms);
  do {
   auto s=io.read(STATUS);
   if ((s&mask)!=0) return s;
   std::this_thread::sleep_for(std::chrono::microseconds(20));
  } while(std::chrono::steady_clock::now()<until);
  throw std::runtime_error(message);
 };
 auto status=wait(2,"completion_timeout");
 const auto error=io.read(ERROR);
 if ((status&1u) || (status&0x64u) || error!=0)
  throw std::runtime_error("hardware_error status="+std::to_string(status)+" code="+std::to_string(error)
                          +" accepted="+std::to_string(io.read(COUNT))+" frame="+std::to_string(io.read(FRAME)));
 if (io.read(COUNT)!=1024) throw std::runtime_error("sample_count_mismatch");
 auto frame=io.read(FRAME);
 // RTL resets smart_scan_top with core_job_rst_n on every job. FRAME is a
 // job-local committed-frame count, not a global generation across STARTs.
 if (frame!=1u) throw std::runtime_error("job_frame_count");
 if (!(status&8u)) throw std::runtime_error("not_committed");
 auto bank=(status>>4)&1u;
 Result out;out.frame=frame;out.psd.reserve(1024);
 for(std::uint32_t i=0;i<1024;++i) {
  io.write(0x20,(bank<<10)|i);wait(0x80,"readback_timeout");
  std::uint64_t value=io.read(0x24);value|=static_cast<std::uint64_t>(io.read(0x28))<<32;
  if (value>>54) throw std::runtime_error("u54_upper_bits");
  out.psd.push_back(value);
 }
 auto after=io.read(STATUS);
 if (io.read(FRAME)!=frame || ((after>>4)&1u)!=bank || !(after&8u) || (after&0x65u))
  throw std::runtime_error("readback_generation_changed");
 return out;
}
}
