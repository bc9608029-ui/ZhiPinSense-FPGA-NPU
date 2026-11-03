// Offline-prepared board diagnostic. Never programs FPGA or opens SDR.
#include "scan_protocol.hpp"
#include <icraft-xrt/core/session.h>
#include <icraft-xrt/dev/zg330_device.h>
#include <array>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>

using icraft::xrt::Device;
using icraft::xrt::ZG330Device;
struct Io {
 icraft::xrt::RegRegion regs;
 std::uint32_t read(std::uint32_t off) {return static_cast<std::uint32_t>(regs.read(0x400d0000ULL+off,false));}
 void write(std::uint32_t off,std::uint32_t v) {regs.write(0x400d0000ULL+off,v,false);}
};
int main(int argc,char** argv) {
 if (argc!=2 && argc!=5) {std::cerr<<"usage: scan_xrt --probe | --execute IQ.i16 PSD.u64 META.json\n";return 2;}
 const std::string mode=argv[1];
 if ((argc==2 && mode!="--probe") || (argc==5 && mode!="--execute")) return 2;
 std::array<char,4096> input{};
 if(argc==5) {
  std::ifstream f(argv[2],std::ios::binary);f.read(input.data(),input.size());
  if(f.gcount()!=4096 || f.peek()!=std::char_traits<char>::eof()) {std::cerr<<"IQ must be exactly 4096 bytes\n";return 2;}
  if(std::ifstream(argv[3]).good() || std::ifstream(argv[4]).good()) {std::cerr<<"fresh outputs required\n";return 2;}
 }
 try {
  auto dev=Device::Open("axi://zg330aiu?npu=0x40000000&dma=0x80000000");
  auto fpai=dev.cast<ZG330Device>();Io io{fpai.defaultRegRegion()};
  try {
   if(io.read(scan::VERSION)!=1) throw std::runtime_error("version_mismatch");
   if(io.read(scan::STATUS)&1u) throw std::runtime_error("preexisting_busy_reset_before_test");
   if(argc==2) {std::cout<<"SMARTSCAN_PROBE version=1 idle=1 status="<<io.read(scan::STATUS)
     <<" error="<<io.read(scan::ERROR)<<" count="<<io.read(scan::COUNT)<<" frame="<<io.read(scan::FRAME)<<'\n';Device::Close(dev);return 0;}
   // Dynamic XRT-managed PL DDR allocation; never use a guessed physical address.
   auto memory=fpai.defaultMemRegion().malloc(4096,false,64);
   const auto addr=memory->begin.addr();bool started=false;
   try {
    if(addr>std::numeric_limits<std::uint32_t>::max()-4095 || (addr&63u)) throw std::runtime_error("DDR address range/alignment");
    memory.write(0,input.data(),input.size());
    std::array<char,4096> verify{};memory.read(verify.data(),0,verify.size());
    if(verify!=input) throw std::runtime_error("DDR transfer readback mismatch");
    // XRT transfer APIs perform the host/device transfer. No CPU cache pointer alias is used.
    started=true;auto t=std::chrono::steady_clock::now();
    auto result=scan::run(io,static_cast<std::uint32_t>(addr));
    const auto us=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-t).count();
    std::ofstream out(argv[3],std::ios::binary);out.write(reinterpret_cast<const char*>(result.psd.data()),8192);out.close();
    if(!out) throw std::runtime_error("PSD output write failed");
    std::ofstream meta(argv[4]);
    meta<<"{\"frame_id\":"<<result.frame<<",\"iq_address\":"<<addr<<",\"accepted\":1024,\"elapsed_us\":"<<us<<",\"backend\":\"fpga\"}\n";
    meta.close();if(!meta) throw std::runtime_error("metadata output write failed");
    memory.free();std::cout<<"SMARTSCAN_FRAME_PASS frame="<<result.frame<<" us="<<us<<'\n';
   } catch(const std::exception& e) {
    // Never release a DMA input allocation while a timed-out PL reader may still own it.
    bool unsafe=false;
    if(started) {try {unsafe=(io.read(scan::STATUS)&1u)!=0;} catch(...) {unsafe=true;}}
    if(unsafe) {
     std::cerr<<"UNSAFE_BUSY_REQUIRES_BOARD_RESET: "<<e.what()<<"; allocation deliberately not freed. Stop this test, reboot before any NPU/DDR reuse.\n"<<std::flush;
     std::_Exit(3);
    }
    memory.free();throw;
   }
  } catch(...) {Device::Close(dev);throw;}
  Device::Close(dev);return 0;
 } catch(const std::exception& e) {std::cerr<<"SMARTSCAN_DIAG_FAIL "<<e.what()<<'\n';return 1;}
}
