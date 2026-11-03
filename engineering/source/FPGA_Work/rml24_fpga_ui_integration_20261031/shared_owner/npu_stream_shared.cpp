#include "npu_classifier24.hpp"
#include "scan_protocol.hpp"
#include <icraft-xrt/dev/zg330_device.h>
#include <array>
#include <limits>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <cerrno>
#include <cmath>
#include <iostream>

bool io(int fd,void* data,size_t bytes,bool sending) {
    char* p=static_cast<char*>(data);
    while(bytes) {
        ssize_t n=sending ? ::send(fd,p,bytes,MSG_NOSIGNAL) : ::read(fd,p,bytes);
        if(n<0&&errno==EINTR)continue;
        if(n<=0)return false;
        p+=n;bytes-=static_cast<size_t>(n);
    }
    return true;
}

// One XRT Device owner and one allocator, shared with the already-applied NPU.
// No second Device::Open / Close anywhere on the auxiliary request path.
struct SharedIo {
 icraft::xrt::RegRegion regs;
 std::uint32_t read(std::uint32_t off){return static_cast<std::uint32_t>(regs.read(0x400d0000ULL+off,false));}
 void write(std::uint32_t off,std::uint32_t v){regs.write(0x400d0000ULL+off,v,false);}
};
std::vector<std::uint64_t> spectrum(chain::NpuClassifier24& npu,const char* iq){
 auto device=npu.auxiliary_device().cast<icraft::xrt::ZG330Device>();SharedIo io{device.defaultRegRegion()};
 if(io.read(scan::STATUS)&1u)throw std::runtime_error("preexisting scan busy");
 auto memory=device.defaultMemRegion().malloc(4096,false,64);bool started=false;
 try{
  auto address=memory->begin.addr();if(address>std::numeric_limits<std::uint32_t>::max()-4095 || (address&63u))throw std::runtime_error("DDR alignment/range");
  memory.write(0,const_cast<char*>(iq),4096);std::array<char,4096> verify{};memory.read(verify.data(),0,4096);
  if(std::memcmp(verify.data(),iq,4096))throw std::runtime_error("DDR readback");
  started=true;auto result=scan::run(io,static_cast<std::uint32_t>(address));memory.free();return result.psd;
 }catch(...){
  bool busy=false;if(started){try{busy=(io.read(scan::STATUS)&1u)!=0;}catch(...){busy=true;}}
  if(busy){std::cerr<<"UNSAFE_BUSY_REQUIRES_BOARD_RESET"<<std::endl;std::_Exit(3);}
  memory.free();throw;
 }
}

int main(int argc,char** argv) {
    if(argc!=4)return 2;
    int listener=-1,client=-1;
    try {
        chain::NpuClassifier24 npu(argv[1],argv[2]);
        listener=socket(AF_UNIX,SOCK_STREAM,0);if(listener<0)throw std::runtime_error("socket");
        sockaddr_un address{};address.sun_family=AF_UNIX;
        if(std::strlen(argv[3])>=sizeof(address.sun_path))throw std::runtime_error("path");
        std::strcpy(address.sun_path,argv[3]);
        if(bind(listener,reinterpret_cast<sockaddr*>(&address),sizeof(address))<0)throw std::runtime_error("bind (path must be fresh)");
        if(listen(listener,1)<0)throw std::runtime_error("listen");
        std::cerr<<"NPU_STREAM_READY"<<std::endl;
        client=accept(listener,nullptr,nullptr);if(client<0)throw std::runtime_error("accept");
        std::vector<float> input(chain::kTensorFloats),logits;
        while(io(client,input.data(),input.size()*sizeof(float),false)) {
            std::uint32_t tag0=0,tag1=0;std::memcpy(&tag0,input.data(),4);std::memcpy(&tag1,reinterpret_cast<char*>(input.data())+4,4);
            // Distinct NaN tag cannot collide with a legal finite model tensor.
            if(tag0==0x7fc05350u && tag1==0x31505344u){
                auto psd=spectrum(npu,reinterpret_cast<char*>(input.data())+16);
                if(!io(client,psd.data(),psd.size()*8,true))break;
                std::cerr<<"SHARED_PSD_PASS"<<std::endl;continue;
            }
            for(float value:input)if(!std::isfinite(value))throw std::runtime_error("nonfinite input");
            npu.infer(input.data(),logits);
            if(logits.size()!=24)throw std::runtime_error("output shape");
            if(!io(client,logits.data(),logits.size()*sizeof(float),true))break;
        }
        std::cerr<<"NPU_STREAM_STOP frames="<<npu.frame_count()<<" apply="<<npu.apply_count()
                 <<" reset="<<npu.reset_count()<<" discipline="<<npu.discipline_ok()<<std::endl;
        close(client);close(listener);unlink(argv[3]);return npu.discipline_ok()?0:1;
    }catch(const std::exception& e) {
        std::cerr<<"NPU_STREAM_ERROR "<<e.what()<<std::endl;
        if(client>=0)close(client);if(listener>=0)close(listener);
        return 1;
    }
}
