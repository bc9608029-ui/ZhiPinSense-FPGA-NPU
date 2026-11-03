/**
 * @file port.hpp
 * @author Weifan Gao (gaoweifan@fmsh.com.cn)
 * @brief IRPC统一通信端口适配，继承该端口基类并实现两个纯虚函数（read和write）即可适配任意通信端口
 * @date 2023-08-29
 * 
 * @copyright Copyright (c) 2023 Shanghai Fudan Microelectronics Group Co., Ltd. All rights reserved.
 * 
 */
#ifndef _IRPC_PORT_H
#define _IRPC_PORT_H

#include <cstddef>
#include <stdint.h>
#include <mutex>
#include <stdexcept>

namespace irpc::port{
    /**
     * @brief 统一通信端口基类
     * 
     */
    class port_base{
    public:
        /**
         * @brief Destroy the port base object
         * 
         */
        virtual ~port_base() = default;

        /**
         * @brief 从对端读取数据
         * 
         * @param[out] buffer 接收对端数据的缓存指针
         * @param size 需要从对端读取的字节数
         * @param block 是否为阻塞模式
         * @return uint32_t 返回已读字节数
         */
        virtual uint32_t read(void *buffer, uint32_t size, bool block=true)=0;

        /**
         * @brief 向对端写入数据
         * 
         * @param[in] data 需要写入的数据所在内存指针
         * @param size 需要写入的数据字节数
         * @param block 是否为阻塞模式
         * @return uint32_t 返回已写入的数据字节数
         */
        virtual uint32_t write(const void *data, uint32_t size, bool block=true)=0;
    public:
        uint32_t maxBufSize;   ///< 最大缓冲区长度，一次能发送或接收的最大数据量
    protected:
        std::timed_mutex read_mutex; ///< read操作互斥量，需在read操作开始时上锁，结束时解锁
        std::timed_mutex write_mutex;///< write操作互斥量，需在write操作开始时上锁，结束时解锁
    };

    namespace server{
        /**
         * @brief 服务端通信端口基类
         * 
         */
        class server_port: public port_base{};
    }
    
    namespace client{
        /**
         * @brief 客户端通信端口基类
         * 
         */
        class client_port: public port_base{};
    }

    /**
     * @brief 连接已关闭异常
     * 
     */
    class connClosedErr:public std::runtime_error {
    public:
        /**
         * @brief Construct a new connection closed err object
         * 
         */
        connClosedErr():runtime_error("[irpc::port] connection closed") {}
        /**
         * @brief Construct a new connection closed err object with port name
         * 
         * @param port_name 指定端口名称
         */
        connClosedErr(std::string port_name):runtime_error("[irpc::port::"+port_name+"] connection closed") {}
    };
    /**
     * @brief 非阻塞资源忙异常
     * 
     */
    class nonBlockBusyErr:public std::runtime_error {
    public:
        /**
         * @brief Construct a new non Block Busy Err object
         * 
         */
        nonBlockBusyErr():runtime_error("[irpc::port] non-block busy error") {}
        /**
         * @brief Construct a new non Block Busy Err object with port name
         * 
         * @param port_name 指定端口名称
         */
        nonBlockBusyErr(std::string port_name):runtime_error("[irpc::port::"+port_name+"]  non-block busy error") {}
    };
}

#endif