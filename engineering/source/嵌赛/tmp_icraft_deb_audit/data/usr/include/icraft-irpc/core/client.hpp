/**
 * @file client.hpp
 * @author Weifan Gao (gaoweifan@fmsh.com.cn)
 * @brief IRPC客户端，用于客户端调用服务端的函数，构造请求，解析响应
 * @date 2023-08-29
 * 
 * @copyright Copyright (c) 2023 Shanghai Fudan Microelectronics Group Co., Ltd. All rights reserved.
 * 
 */
#ifndef _RPC_CLIENT_H
#define _RPC_CLIENT_H

#include <memory>
#include <string>
#include <iostream>
#include <cstdlib>
#include <array>
#include <tuple>

// #include <boost/asio.hpp>

#include "icraft-irpc/core/codec.hpp"
#include "icraft-irpc/port/base/port.hpp"
#include "icraft-irpc/utils/threadpool.hpp"
#include "icraft-irpc/utils/safemap.hpp"

namespace irpc{
    /**
     * @brief IRPC客户端
     * 
     * @details 用于客户端调用服务端的函数，构造请求，解析响应
     * 
     */
    class client : public std::enable_shared_from_this<client>{
    public:
        /**
         * @brief Destroy the client object
         * 
         */
        ~client(){
            this->deinit();
        }

        /**
         * @brief Construct a new client object
         * 
         */
        client() = default;

        /**
         * @brief Construct a new client object and init
         * 
         * @param cp 通信端口对象智能指针
         * @param verbose 是否开启调试输出
         */
        client(std::shared_ptr<irpc::port::client::client_port> cp, bool verbose=false){
            this->init(cp,4,verbose);
        }
        
        /**
         * @brief 初始化客户端编解码器及相关参数
         * 
         * @details 将传入的通信端口对象指针赋值给成员变量cp_ptr，
         * 并实例化编解码器与线程池，将其指针赋值给codec_ptr、tp_ptr，供其他成员函数调用
         * 
         * @param cp 通信端口对象智能指针
         * @param threadpool_num 线程池线程数，若为0则关闭多线程处理，仅可使用同步调用
         * @param verbose 是否开启调试输出
         */
        void init(std::shared_ptr<irpc::port::client::client_port> cp, int threadpool_num=8, bool verbose=false);

        /**
         * @brief 逆初始化客户端
         * 
         */
        void deinit();

        /**
         * @brief 从客户端调用服务端函数
         * 
         * @details 与call_sync一致
         * 
         * @tparam T 服务端函数返回值类型
         * @tparam Args 服务端函数参数类型
         * @param funcName 要调用的服务端函数名
         * @param args 要传递给服务端函数的参数
         * @return T 以指定类型T返回服务端函数运行完毕的返回值
         */
        template<typename T, typename... Args>
        T call(const std::string& funcName, Args&&... args);

        /**
         * @brief 从客户端同步调用服务端函数
         * 
         * @details 当线程池线程数为0时同步调用采用传统方式，阻塞式发送请求，并阻塞式等待接收返回的数据包。
         * 若线程数不为零则同步调用采用异步调用方式实现，即异步发送调用请求，阻塞式等待异步调用返回，模拟同步调用行为。
         * 
         * @tparam T 服务端函数返回值类型
         * @tparam Args 服务端函数参数类型
         * @param funcName 要调用的服务端函数名
         * @param args 要传递给服务端函数的参数
         * @return T 以指定类型T返回服务端函数运行完毕的返回值
         */
        template<typename T, typename... Args>
        T call_sync(const std::string& funcName, Args&&... args);

        /**
         * @brief 从客户端异步调用服务端函数
         * 
         * @details 创建调用任务，提交线程池后返回任务future，其中返回值可以调用future.get()得到。
         * 
         * @tparam Ret 服务端函数返回值类型
         * @tparam Args 服务端函数参数类型
         * @param funcName 要调用的服务端函数名
         * @param args 要传递给服务端函数的参数
         * @return std::future<Ret> 以指定类型Ret返回服务端函数运行完毕的返回值future句柄
         */
        template<typename Ret, typename... Args>
        std::future<Ret> call_async(const std::string& funcName, Args&&... args);

        /**
         * @brief 处理服务端发回的数据包并解析返回值
         * 
         * @tparam T 服务端函数返回值类型
         * @param pkt 服务端发回的数据包
         * @return T 以指定类型T返回服务端函数运行完毕的返回值
         */
        template<typename T>
        T process_packet(pkt_t pkt);

        /**
         * @brief 数据链路测试，发什么回什么
         * 
         * @details 输入长度为size的data会作为payload以msg_type::test_echo的标签发送至服务端，
         *          服务端收到后会将此数据原封不动发回来，函数返回值即为从服务端接收的数据
         * 
         * @param[in] data 将要发送的数据内容的智能指针
         * @param size 将要发送的数据字节数
         * @return std::shared_ptr<uint8_t []> 从服务端接收的数据的智能指针
         */
        std::shared_ptr<uint8_t []> test_echo(std::shared_ptr<uint8_t []> data, uint32_t size);

        /**
         * @brief 停止运行客户端接收机
         * 
         * @details runReceiver置零
         * 
         */
        void receiverStop();
        
        /**
         * @brief 客户端接收机是否正在运行
         * 
         * @details 返回runReceiver取值
         * 
         * @return true 正在运行
         * @return false 停止运行
         */
        bool isReceiverRunning();

        /**
         * @brief 非阻塞式运行客户端接收机
         * 
         * @details runReceiver为真时循环接收数据包，并将收到的数据包放入映射表m_packets，
         *          可通过pktID找到相应数据包。
         */
        void runReceiverNonBlock();

        /**
         * @brief 异步运行客户端接收机
         * 
         * @details 在另一个线程中异步运行runReceiverNonBlock，并将其future存入run_async_fut，可通过run_async_fut
         * 判断是否停止运行。需要注意的是，接收机在单独的线程中运行时大概率会长时间将read的mutex锁上，
         * 导致其他线程想调用read时因资源被占用而被阻塞。故若想单独执行read操作而非在映射表m_packets中找到接收的数据包，
         * 如单独运行get_packet，需先使receiver停止运行再read。
         * 
         * @return std::future<void>* 
         */
        std::future<void>* runReceiver_async();

        /**
         * @brief 等待异步客户端接收机运行完毕
         * 
         * @details 通过runReceiver_async创建的run_async_fut阻塞等待runReceiverNonBlock运行结束退出。
         * 可通过receiverStop将runReceiver置零，runReceiverNonBlock便不会继续循环接收并退出。
         * 
         */
        void runReceiver_wait();
                
        /**
         * @brief 判断客户端是否已关闭
         * 
         * @details 通过cp_ptr指针是否为空判断客户端是否已关闭，即已deinit
         * 
         * @return true 客户端已关闭
         * @return false 客户端未关闭
         */
        bool isClose();

        auto getCodec(){return codec_ptr;}
    private:
        /**
         * @brief 客户端适配指针
         * 
         */
        std::shared_ptr<irpc::port::client::client_port> cp_ptr;
        /**
         * @brief 线程池指针
         * 
         */
        std::shared_ptr<irpc::utils::ThreadPool> tp_ptr;
        /**
         * @brief 编解码器指针
         * 
         */
        std::shared_ptr<codec> codec_ptr;
        /**
         * @brief 是否启用调试输出
         * 
         */
        bool verbose = false;
        /**
         * @brief 数据包ID记录
         * 
         */
        uint24_t packetID = 0;
        /**
         * @brief 数据包ID记录mutex
         * 
         */
        std::mutex packetID_mutex;
        /**
         * @brief 数据包ID与接收数据包映射表，用于存储到达数据包
         * 
         */
        utils::SafeMap<uint32_t, pkt_t> m_retPkts;
        /**
         * @brief 数据包ID与接收数据包映射表mutex
         * 
         */
        std::mutex m_retPkts_mutex;
        /**
         * @brief 通知数据包到达的条件变量
         * 
         */
        std::condition_variable recv_pkt_cv;
        /**
         * @brief 控制客户端接收机是否继续循环运行
         * 
         */
        volatile std::atomic_bool runReceiver = false;
        /**
         * @brief 异步接收线程未来句柄
         * 
         */
        std::future<void> run_async_fut;
        /**
         * @brief 同步调用mutex
         * 
         */
        std::mutex call_sync_mutex;

    private:
        /**
         * @brief 获取新的数据包ID
         * 
         * @return uint24_t 
         */
        uint24_t getNewPktID();
        /**
         * @brief 设置客户端接收机运行状态
         * 
         * @param runReceiver 客户端接收机是否正在运行
         */
        void setRunFlag(bool runReceiver);
    };
}

#include "client.tpp"

#endif
