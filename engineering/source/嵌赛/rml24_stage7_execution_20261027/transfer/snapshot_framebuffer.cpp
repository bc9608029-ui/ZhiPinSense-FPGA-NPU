#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
int main(){int f=open("/dev/mem",O_RDONLY|O_SYNC);if(f<0)return 1;auto r=(volatile uint32_t*)mmap(nullptr,4096,PROT_READ,MAP_SHARED,f,0x40080000);if(r==MAP_FAILED)return 2;if(r[3]!=0x20230218)return 3;uint64_t base=uint64_t(r[0x54/4])<<3;unsigned frame=r[0x50/4]&1;int u=open("/dev/udmabuf0",O_RDONLY|O_SYNC);auto m=(volatile uint16_t*)mmap(nullptr,3686400,PROT_READ,MAP_SHARED,u,0);if(m==MAP_FAILED)return 4;FILE* o=fopen("/root/rml24_stage7_execution_20261027/framebuffer_snapshot.ppm","wb");if(!o)return 5;fprintf(o,"P6\n1280 720\n255\n");for(unsigned i=0;i<1280*720;i++){uint16_t v=m[frame*1280*720+i];unsigned char p[3]={(unsigned char)(((v>>11)&31)*255/31),(unsigned char)(((v>>5)&63)*255/63),(unsigned char)((v&31)*255/31)};fwrite(p,1,3,o);}fclose(o);printf("FRAMEBUFFER_SNAPSHOT base=0x%llx frame=%u\n",(unsigned long long)base,frame);munmap((void*)m,3686400);munmap((void*)r,4096);close(u);close(f);}