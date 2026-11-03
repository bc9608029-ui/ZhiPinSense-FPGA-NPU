// read_display_registers_ro.cpp -- 只读 MMIO 寄存器采集工具（FMQL30TAI HDMI/NPU 诊断）。
//
// 约束（严格）：
//   - 仅以 O_RDONLY|O_SYNC 打开 /dev/mem；
//   - 仅 mmap(PROT_READ, MAP_SHARED)，禁止任何写权限（绝不 PROT_WRITE）；
//   - 只读「已确认」的寄存器地址（见 DISPLAY_AB_EVIDENCE.md 清单）；
//   - 读取失败 fail-closed：任一寄存器不可读即整体退出非零并打印 READ_FAIL；
//   - 输出：地址、值、采集时间（CLOCK_REALTIME 秒+纳秒）。
//
// 编译（板端或交叉环境，未来用户步骤）：
//   aarch64-linux-gnu-g++ -O2 -o read_display_registers_ro read_display_registers_ro.cpp
// 运行（需 root，只读 /dev/mem）：
//   ./read_display_registers_ro
//
// 本文件无法在 Windows 主机对 /dev/mem 实跑；离线阶段仅做 g++ 语法编译检查。

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cerrno>
#include <ctime>

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

namespace {

// 已知寄存器清单（只读，来源见 docs/DISPLAY_AB_EVIDENCE.md）。
struct RegDesc {
    const char* name;
    std::uint64_t addr;  // 物理地址
};

// frame_ctrl 版本 0x40080000+0x0C；pl_ddr core VERSION/STATUS 0x400C0000+0x00/+0x08。
const RegDesc kRegs[] = {
    {"frame_ctrl_VERSION(0x4008000C)", 0x4008000Cull},
    {"frame_ctrl_REG_0x50(帧基址相关)", 0x40080050ull},
    {"frame_ctrl_REG_0x54(帧基址相关)", 0x40080054ull},
    {"pl_ddr_core_VERSION(0x400C0000)", 0x400C0000ull},
    {"pl_ddr_core_STATUS(0x400C0008)", 0x400C0008ull},
};
const int kRegCount = static_cast<int>(sizeof(kRegs) / sizeof(kRegs[0]));

const std::uint64_t kPageSize = 4096;  // 系统页（aarch64 上通常 4K）

bool read_u32_phys(int fd, std::uint64_t phys, std::uint32_t* out) {
    std::uint64_t page_base = phys & ~(kPageSize - 1);
    std::uint64_t page_off = phys & (kPageSize - 1);
    // 只读映射（PROT_READ），绝不加 PROT_WRITE。
    void* map = mmap(nullptr, static_cast<std::size_t>(kPageSize), PROT_READ, MAP_SHARED,
                     fd, static_cast<off_t>(page_base));
    if (map == MAP_FAILED) {
        return false;
    }
    const volatile std::uint32_t* p =
        reinterpret_cast<const volatile std::uint32_t*>(
            static_cast<const unsigned char*>(map) + page_off);
    *out = *p;  // 只读访问；读取失败会触发 SIGBUS，见 main 中的 sigbus 处理说明。
    munmap(map, static_cast<std::size_t>(kPageSize));
    return true;
}

}  // namespace

int main() {
    // 只读打开 /dev/mem。
    const int fd = ::open("/dev/mem", O_RDONLY | O_SYNC);
    if (fd < 0) {
        std::fprintf(stderr, "READ_FAIL open /dev/mem: %s (errno=%d)\n",
                     std::strerror(errno), errno);
        return 2;
    }

    std::timespec now;
    ::clock_gettime(CLOCK_REALTIME, &now);
    std::printf("# read_display_registers_ro ts=%lld.%09ld\n",
                static_cast<long long>(now.tv_sec), static_cast<long>(now.tv_nsec));

    bool any_fail = false;
    for (int i = 0; i < kRegCount; ++i) {
        std::uint32_t v = 0;
        ::clock_gettime(CLOCK_REALTIME, &now);
        if (!read_u32_phys(fd, kRegs[i].addr, &v)) {
            std::printf("READ_FAIL addr=0x%08llx name=%s ts=%lld.%09ld\n",
                        static_cast<unsigned long long>(kRegs[i].addr), kRegs[i].name,
                        static_cast<long long>(now.tv_sec), static_cast<long>(now.tv_nsec));
            any_fail = true;
        } else {
            std::printf("reg addr=0x%08llx value=0x%08x name=%s ts=%lld.%09ld\n",
                        static_cast<unsigned long long>(kRegs[i].addr), v, kRegs[i].name,
                        static_cast<long long>(now.tv_sec), static_cast<long>(now.tv_nsec));
        }
    }

    // 可选：只读 sysfs 帧缓冲物理地址/容量（若可读）。
    std::printf("# sysfs udmabuf0 phys_addr/size (read-only)\n");
    for (const char* p : {"/sys/class/u-dma-buf/udmabuf0/phys_addr",
                          "/sys/class/u-dma-buf/udmabuf0/size"}) {
        FILE* f = std::fopen(p, "r");
        if (f) {
            char buf[64] = {0};
            if (std::fgets(buf, sizeof(buf), f)) {
                std::printf("sysfs %s = %s", p, buf);
                if (buf[0] && buf[std::strlen(buf) - 1] != '\n') std::printf("\n");
            }
            std::fclose(f);
        } else {
            std::printf("READ_FAIL sysfs %s\n", p);
            any_fail = true;
        }
    }

    ::close(fd);

    // fail-closed：任何读取失败 → 非零退出。
    if (any_fail) {
        std::fprintf(stderr, "collector: FAIL (one or more reads failed; fail-closed)\n");
        return 1;
    }
    std::printf("collector: OK (all reads succeeded)\n");
    return 0;
}
