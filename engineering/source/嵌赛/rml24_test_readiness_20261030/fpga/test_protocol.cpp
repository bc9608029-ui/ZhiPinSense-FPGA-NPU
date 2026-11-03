#include "scan_protocol.hpp"
#include <iostream>
struct Mock {
 int fault=0;std::uint32_t frame=7,addr=0;bool ready=false,started=false;
 std::uint32_t read(std::uint32_t a) {
  if(a==scan::VERSION)return fault==1?0:1;
  if(a==scan::STATUS) return started?(fault==2?1u:(2u|8u|16u|(ready?128u:0u))):0u;
  if(a==scan::FRAME)return fault==8?0:frame;
  if(a==scan::COUNT)return fault==3?1023:1024;
  if(a==scan::ERROR)return fault==4?1:0;
  if(a==0x24)return addr;
  if(a==0x28)return fault==5?0x400000:0;
  return 0;
 }
 void write(std::uint32_t a,std::uint32_t v) {
  if(a==8 && v==1){started=true;frame=1;}
  if(a==0x20){addr=v&1023u;ready=fault!=6;if(fault==7 && addr==1023)++frame;}
 }
};
int main() {
 Mock ok;auto result=scan::run(ok,0x10000,1);
 if(result.psd.size()!=1024 || result.psd[1023]!=1023 || result.frame!=1)return 1;
 auto second=scan::run(ok,0x10000,1);if(second.frame!=1)return 3;
 for(int f=1;f<=8;++f){Mock io;io.fault=f;try {scan::run(io,0x10000,1);return 2;}catch(const std::exception&) {}}
 std::cout<<"SCAN_PROTOCOL_TEST PASS cases=10 (mock only; includes repeated job-local frame count)\n";
}
