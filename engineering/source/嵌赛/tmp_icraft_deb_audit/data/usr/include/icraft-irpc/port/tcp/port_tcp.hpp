/**
 * @file port_tcp.hpp
 * @author Weifan Gao (gaoweifan@fmsh.com.cn)
 * @brief 基于TCP适配IRPC统一通信端口的示例
 * @date 2023-08-29
 * 
 * @copyright Copyright (c) 2023 Shanghai Fudan Microelectronics Group Co., Ltd. All rights reserved.
 * 
 */
#ifndef _IRPC_PORT_TCP_H
#define _IRPC_PORT_TCP_H

#include "icraft-irpc/port/base/port.hpp"

#ifdef _WIN32
#include <winsock2.h>
#endif
namespace irpc::port{
    #ifdef __linux__
        using SOCKET=int; ///< socket文件描述符
    #elif _WIN32
        void _WSAStartup(); ///< 启动 Winsock DLL
    #endif
    const int MaxBuf = 256*1024; ///< 最大缓冲区长度

    /**
     * @brief 通过TCP从对端读取数据
     * 
     * @param sockfd socket文件描述符
     * @param[out] buffer 接收对端数据的缓存指针
     * @param size 需要从对端读取的字节数
     * @param block 是否为阻塞模式
     * @return uint32_t 返回已读字节数
     */
    uint32_t _read_tcp(SOCKET sockfd, void *buffer, uint32_t size, bool block=true);

    /**
     * @brief 通过TCP向对端写入数据
     * 
     * @param sockfd socket文件描述符
     * @param data 需要写入的数据所在内存指针
     * @param size 需要写入的数据字节数
     * @param block 是否为阻塞模式
     * @return uint32_t 返回已写入的数据字节数
     */
    uint32_t _write_tcp(SOCKET sockfd, const void *data,uint32_t size, bool block=true);

    /**
     * @brief 等待客户端连接
     * 
     * @param serverSocketFD 服务端socket句柄
     * @param verbose 是否开启日志输出
     * @return SOCKET 连接成功返回客户端socket句柄client_sockfd
     */
    std::tuple<SOCKET,std::string> _waitNewConn(SOCKET serverSocketFD, bool verbose);

    /**
     * @brief 判断socket缓冲区状态
     * 
     * @param socketFD socket句柄
     * @return true socket缓冲区有数据
     * @return false socket缓冲区无数据
     * @throw connClosedErr socket已关闭
     */
    bool _socBufStat(SOCKET socketFD);

    /**
     * @brief 设置socket是否为阻塞模式
     * 
     * @param sockfd socket句柄
     * @param isBlock 是否为阻塞模式
     */
    void _setBlock(SOCKET sockfd, bool isBlock);

    /**
     * @brief 设置socket是否开启NoDelay,即禁用Nagle算法
     * 
     * @param sockfd socket句柄
     * @param isNoDelay 是否开启NoDelay
     */
    void _setNoDelay(SOCKET sockfd, bool isNoDelay);

    /**
     * @brief 设置socket是否开启QuickACK,即禁用TCP延迟确认机制(Linux only)
     * 
     * @param sockfd socket句柄
     * @param isQuickACK 是否开启QuickACK
     */
    void _setQuickACK(SOCKET sockfd, bool isQuickACK);

    namespace server{
        /**
         * @brief 服务端TCP端口
         * 
         */
        class tcp final: public server_port{
        public:
            /**
             * @brief Construct a new tcp object and init
             * 
             * @param addr 服务端IPV4监听地址，默认0.0.0.0表示监听所有地址
             * @param port 服务端IPV4端口号
             * @param verbose 是否开启日志输出
             */
            tcp(const char* addr, uint16_t port, bool verbose=true){
                init(addr, port, verbose);
            }
            /**
             * @brief Construct a new tcp object
             */
            tcp()=default;
            /**
             * @brief Destroy the tcp object and deinit
             */
            ~tcp(){
                deinit();
            }
            
            uint32_t read(void *buffer, uint32_t size, bool block=true);
            uint32_t write(const void *data,uint32_t size, bool block=true);
            
            /**
             * @brief 等待客户端建立新连接
             * 
             * @return std::string 客户端IP地址
             */
            std::string waitNewConn();
            /**
             * @brief 判断客户端socket是否关闭
             * 
             * @return true 客户端socket已关闭
             * @return false 客户端socket未关闭
             */
            bool isSocketClosed();
            /**
             * @brief 初始化socket，绑定并监听指定IPaddr:port
             * 
             * @param addr 服务端IPV4监听地址，0.0.0.0表示监听所有地址
             * @param port 服务端IPV4端口号
             * @param verbose 是否开启日志输出
             */
            void init(const char* addr, uint16_t port, bool verbose=true);
            /**
             * @brief 逆初始化，关闭socket
             * 
             */
            void deinit();
        private:
            SOCKET server_sockfd=-1;  ///<服务端socket文件描述符（句柄）
            SOCKET client_sockfd=-1;  ///<客户端socket文件描述符（句柄）
            const char* listen_addr;  ///<服务端IPV4监听地址
            uint16_t listen_port;     ///<服务端IPV4端口号
            bool verbose;             ///<是否开启日志输出
        };
    }

    namespace client{
        /**
         * @brief 客户端TCP端口
         * 
         */
        class tcp final: public client_port{
        public:
            /**
             * @brief Construct a new tcp object and init
             * 
             * @param addr 服务端IPV4地址，默认127.0.0.1为本地回环地址，若服务端与客户端运行在同一台终端上即可使用该地址
             * @param port 服务端IPV4端口号
             * @param verbose 是否开启日志输出
             */
            tcp(const char* addr, uint16_t port, bool verbose=true){
                init(addr,port,verbose);
            }
            /**
             * @brief Construct a new tcp object
             */
            tcp()=default;
            /**
             * @brief Destroy the tcp object and deinit
             */
            ~tcp(){
                deinit();
            }

            uint32_t read(void *buffer, uint32_t size, bool block=true);
            uint32_t write(const void *data,uint32_t size, bool block=true);

            /**
             * @brief 初始化socket，连接到指定IPaddr:port
             * 
             * @param addr 服务端IPV4地址，127.0.0.1为本地回环地址，若服务端与客户端运行在同一台终端上即可使用该地址
             * @param port 服务端IPV4端口号
             * @param verbose 是否开启日志输出
             */
            void init(const char* addr, uint16_t port, bool verbose=true);
            /**
             * @brief 逆初始化，关闭socket
             */
            void deinit();
        private:
            SOCKET sockfd=-1;         ///<socket文件描述符（句柄）
            const char* server_addr;  ///<服务端IPV4地址
            uint16_t server_port;     ///<服务端IPV4端口号
            bool verbose;             ///<是否开启日志输出
        };
    }
}

#endif