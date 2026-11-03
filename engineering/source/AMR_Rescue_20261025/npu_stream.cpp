#include "npu_classifier24.hpp"
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
