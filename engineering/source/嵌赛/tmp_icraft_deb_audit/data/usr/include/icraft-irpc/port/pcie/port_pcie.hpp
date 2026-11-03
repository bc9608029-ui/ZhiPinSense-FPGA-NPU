/**
 * @file port_pcie.hpp
 * @author Weifan Gao (gaoweifan@fmsh.com.cn)
 * @brief 基于PCIE适配IRPC统一通信端口
 * @date 2023-10-08
 * 
 * @copyright Copyright (c) 2023 Shanghai Fudan Microelectronics Group Co., Ltd. All rights reserved.
 * 
 */
#ifndef _IRPC_PORT_PCIE_H
#define _IRPC_PORT_PCIE_H

#include "icraft-irpc/port/base/port.hpp"
#include <icraft-xrt/dev/buyi_device.h>

namespace irpc::port{
    static inline const uint64_t SHARED_MEM_SIZE=16*1024*1024; ///< ARM端与HOST端共享PL内存大小
    static inline const uint64_t REG_BASE_HOST=0x00140C00;     ///< HOST端共享寄存器组基地址
    static inline const uint64_t REG_BASE_ARM =0x80040C00;     ///< ARM端共享寄存器组基地址
    #define SHARED_REG_START_OFFSET 0x5c                       ///< 共享寄存器组起始偏移地址
    #define SHARED_REG_NUM 16                                  ///< 16个连续可读写共享寄存器组
    using shared_reg_t=uint32_t;                               ///< 32位寄存器
    static inline const uint32_t IRPC_START_FLAG = 0xAAAAAAAA; ///< IRPC启动标志
    /**
     * @brief 共享寄存器组地址
     * 
     */
    struct reg_addr{
        /**
         * @brief Construct a new reg addr object
         * 
         * @param base_addr 寄存器组基地址
         */
        reg_addr(uint64_t base_addr){
            for(int i=0;i<SHARED_REG_NUM;i++)
                addr_of[i] = base_addr + SHARED_REG_START_OFFSET + sizeof(shared_reg_t)*i;
        }
        reg_addr()=default;
        /**
         * @brief address of shared registers
         * 
         */
        uint64_t addr_of[SHARED_REG_NUM]={0};
    };
    /**
     * @brief 共享寄存器组各寄存器功能定义
     * 
     */
    enum shared_reg_def:uint8_t{
        IRPC_STATUS_REG=0,      ///< IRPC启动状态，为0xAAAAAAAA表示已启动
        C2H_MEM_ADDR_H_POS_REG, ///< 低16位用于记录地址高16位，最高位用于指示PL(0)/PS(1)，其余位保留
        C2H_MEM_ADDR_L_REG,     ///< 记录地址低32位
        C2H_MEM_SIZE_REG,       ///< 记录地址对应空间大小
        C2H_PKT_SIZE_REG,       ///< 记录数据包字节大小
        C2H_PKT_STATUS_REG,     ///< 数据包传输状态(pkt_status_def)
        C2H_PKT_SEQ_REG,        ///< 数据包序号，传输中置零表示已读完缓冲区
        H2C_MEM_ADDR_H_POS_REG, ///< 低16位用于记录地址高16位，最高位用于指示PL(0)/PS(1)，其余位保留
        H2C_MEM_ADDR_L_REG,     ///< 记录地址低32位
        H2C_MEM_SIZE_REG,       ///< 记录地址对应空间大小
        H2C_PKT_SIZE_REG,       ///< 记录数据包字节大小
        H2C_PKT_STATUS_REG,     ///< 数据包传输状态(pkt_status_def)
        H2C_PKT_SEQ_REG,        ///< 数据包序号，传输中置零表示已读完缓冲区
        COUNT_END               ///< 标志enum结束，用于统计enum中REG个数
    };
    /**
     * @brief 数据包传输状态
     */
    enum pkt_status_def:int32_t{
        NO_PKT_IDLE=0, ///< 无数据包待传输
        REQUEST_SEND,  ///< 请求发送数据包，PKT_SIZE_REG存储数据包大小，对端需根据大小分配相应内存并计算数据包个数
        SEND_PACKET,   ///< 已分配相应内存，开始向MEM_ADDR_H_POS_REG，MEM_ADDR_L_REG所述地址写入数据，写完一个包变换PKT_SEQ_REG序号
        SEND_DONE      ///< 写入完成，等待状态变为NO_PACKET_IDLE，传输流程结束
    };

    namespace server{
        /**
         * @brief 服务端PCIe端口，运行在ARM上
         * 
         */
        class pcie final: public server_port{
        public:
            pcie()=default;
            ~pcie(){deinit();}
            uint32_t read(void *buffer, uint32_t size, bool block=true);
            uint32_t write(const void *data, uint32_t size, bool block=true);
            void init(icraft::xrt::Device &device, uint32_t buffer_size=SHARED_MEM_SIZE, bool verbose=false, bool onPS=false);
            void deinit();
        private:
            void _clear_shared_regs(); ///< 清空共享寄存器组
            void _set_mem_reg(uint64_t mem_addr, uint32_t mem_size, bool isC2H, bool isPS=false); ///< 设置内存地址大小信息寄存器
            void _set_stat_reg(); ///< 设置运行状态寄存器
        private:
            reg_addr shared_regs = reg_addr(REG_BASE_ARM); ///< ARM端寄存器组地址
            icraft::xrt::Device axi_dev; ///< ARM端AXI device
            icraft::xrt::RegRegion rregion; ///< ARM端AXI设备默认RegRegion
            icraft::xrt::MemRegion psddr_region; ///< ARM端AXI设备PS DDR UDMA MemRegion
            icraft::xrt::MemRegion plddr_region; ///< ARM端AXI设备PL DDR MemRegion
            icraft::xrt::MemChunk buffer_chunk_c2h; ///< ARM->HOST数据缓冲Chunk
            icraft::xrt::MemChunk buffer_chunk_h2c; ///< HOST->ARM数据缓冲Chunk
            uint64_t rwTimeout; ///< 阻塞状态下读写超时时间(s)
            bool verbose; ///< 是否开启调试输出
        };
    }

    namespace client{
        /**
         * @brief 客户端PCIe端口，运行在主机上
         * 
         */
        class pcie final: public client_port{
        public:
            pcie()=default;
            ~pcie(){deinit();}
            uint32_t read(void *buffer, uint32_t size, bool block=true);
            uint32_t write(const void *data, uint32_t size, bool block=true);
            void init(icraft::xrt::Device &device, bool verbose=false);
            void deinit();
        private:
            std::tuple<uint64_t, uint32_t, bool> _get_mem_reg(bool isC2H);
        private:
            reg_addr shared_regs = reg_addr(REG_BASE_HOST); ///< HOST端寄存器组地址
            icraft::xrt::Device pcie_dev; ///< HOST端PCIe device
            icraft::xrt::RegRegion rregion; ///< HOST端PCIe设备默认RegRegion
            icraft::xrt::MemRegion psddr_region; ///< HOST端PCIe设备PS DDR UDMA MemRegion
            icraft::xrt::MemRegion plddr_region; ///< HOST端PCIe设备PL DDR MemRegion
            icraft::xrt::MemChunk buffer_chunk_c2h; ///< ARM->HOST数据缓冲Chunk
            icraft::xrt::MemChunk buffer_chunk_h2c; ///< HOST->ARM数据缓冲Chunk
            uint64_t rwTimeout; ///< 阻塞状态下读写超时时间(s)
            bool verbose; ///< 是否开启调试输出
        };
    }
}
#endif