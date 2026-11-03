/**
 * @file server.hpp
 * @author Weifan Gao (gaoweifan@fmsh.com.cn)
 * @brief IRPC服务端，负责服务端函数注册，解析请求并执行，构造响应
 * @date 2023-08-29
 * 
 * @copyright Copyright (c) 2023 Shanghai Fudan Microelectronics Group Co., Ltd. All rights reserved.
 * 
 */
#ifndef _SERVER_H
#define _SERVER_H

#include <iostream>
#include <functional>
#include <unordered_map>
#include <memory>
#include <tuple>
#include <cstdlib>
#include <array>
#include <thread>
#include <atomic>
#include <future>

#include <msgpack.hpp>

#include "icraft-irpc/core/codec.hpp"
#include "icraft-irpc/port/base/port.hpp"
#include "icraft-irpc/utils/utils.hpp"
#include "icraft-irpc/utils/threadpool.hpp"

namespace irpc{
    /**
     * @brief IRPC服务端
     * 
     * @details 负责服务端函数注册，解析请求并执行，构造响应。采用Lazy Singleton方式保证单一实例
     * 
     */
    class server{
    public:
        server() = default;
        server(const server& other){
            this->m_handlers=other.m_handlers;
        }
        server(server&&) = delete;
        server operator=(const server&) = delete;

        /**
         * @brief 获取server实例对象
         * 
         * @return server& 返回server实例对象的引用
         */
        static server& getInstance(){
            static server instance;
            return instance;
        }

        /**
         * @brief Destroy the server object
         * 
         */
        ~server(){
            deinit();
        }

        /**
         * @brief Construct a new server object
         * 
         * @param sp 
         */
        server(std::shared_ptr<irpc::port::server::server_port> sp){
            this->init(sp);
        }

        /**
         * @brief 初始化服务端编解码器及相关参数
         * 
         * @details 将传入的通信端口对象指针赋值给成员变量sp_ptr，
         * 并实例化编解码器与线程池，将其指针赋值给codec_ptr、tp_ptr，供其他成员函数调用
         * 
         * @param sp 通信端口对象智能指针
         * @param threadpool_num 线程池线程数
         * @param verbose 是否开启调试输出
         */
        void init(std::shared_ptr<irpc::port::server::server_port> sp, int threadpool_num=8, bool verbose=false);

        /**
         * @brief 逆初始化服务端
         * 
         * @param del_methods 是否同时删除所有已注册函数
         */
        void deinit(bool del_methods=true);
        
        /**
         * @brief 调用指定的函数
         * 
         * @details 服务端收到客户端的函数调用请求后，将解析出的函数名及参数信息通过msgpack对象传递进来，
         * 本函数会根据该对象信息找到函数映射表中相应的函数，并跳转到callproxy执行，
         * callproxy会负责该函数的执行与返回值的发送。
         * 
         * @param obj 函数名及参数数据
         * @param pktID 数据包ID
         */
        void call(msgpack::object obj, uint24_t pktID);

        /**
         * @brief 函数调用代理
         * 
         * @details 负责函数的绑定与调用，即注册函数时将目标函数与callproxy绑定，调用时通过callproxy调用对应函数。
         * 具体而言，通过register_func注册函数时会将函数指针与callproxy绑定，并放入函数映射表m_handlers中。
         * 通过call调用目标函数时会根据函数名在m_handlers中寻找对应callproxy，并通过该callproxy进行目标函数的调用与返回值的发送。
         * 
         * @tparam F 函数指针类型
         * @param func 函数指针
         * @param obj 函数参数数据
         * @param pktID 数据包ID
         */
        template<typename F>
        void callproxy(F func, msgpack::object &obj, uint24_t pktID);

        /**
         * @brief 类成员函数调用代理
         * 
         * @tparam R 返回值类型
         * @tparam C 函数所在类名
         * @tparam obj 函数所在类对象类型
         * @tparam Args 函数参数类型
         * @param func 函数指针
         * @param s 函数所在类对象指针
         * @param o 函数参数数据
         * @param pktID 数据包ID
         */
        template<typename R, typename C, typename obj, typename... Args>
        void callproxy(R(C::* func)(Args...), obj* s, msgpack::object &o, uint24_t pktID);

        /**
         * @brief 类成员函数调用代理
         * 
         * @tparam F 函数指针类型
         * @tparam obj 函数所在类对象类型
         * @param func 函数指针
         * @param self 函数所在类对象指针
         * @param o 函数参数数据
         */
        template<typename F, typename obj>
        void callproxy_(F func, obj* self, msgpack::object &o, uint24_t pktID);

        /**
         * @brief 删除映射表中的函数
         * 
         * @param funcName 待删除的函数名
         */
        void delete_method(const std::string& funcName);

        /**
         * @brief 清空映射表中的所有函数
         * 
         */
        void delete_all_methods();

        /**
         * @brief 注册函数
         * 
         * @details 将函数指针与callproxy绑定，并放入函数映射表m_handlers中
         * 
         * @tparam F 函数指针类型
         * @param funcName 函数名
         * @param handler 函数指针（句柄）
         */
        template<typename F>
        void register_func(const std::string funcName, F handler);

        /**
         * @brief 注册类成员函数
         * 
         * @tparam F 函数指针类型
         * @tparam obj 类对象类型
         * @param funcName 函数名
         * @param handler 函数指针（句柄）
         * @param self 函数所在类对象指针
         */
        template<typename F, typename obj>
        void register_func(const std::string funcName, F handler, obj* self);
        
        /**
         * @brief 同步运行服务端
         * 
         * @details 当runServer为真时循环进行数据包接收与处理，并根据数据包类型进行对应操作。
         * 
         */
        void run();

        /**
         * @brief 异步运行服务端
         * 
         * @details 当runServer为真时循环进行数据包接收与处理，并根据数据包类型进行对应操作。
         * 
         * @return std::future<void>* 返回future的指针，可用get等待运行完毕，用wait无法捕获异常抛出
         */
        std::future<void>* run_async();

        /**
         * @brief non-block run func for async mode
         * 
         * @param process_packet_cb callback func to process packet
         */
        void run_nonblock(std::function<void(pkt_t)> process_packet_cb);

        /**
         * @brief 等待异步运行服务端运行完成
         * 
         */
        void async_wait();

        /**
         * @brief 停止运行服务端
         * 
         * @details runServer置零
         * 
         */
        void stop();
        
        /**
         * @brief 服务端是否正在运行
         * 
         * @details 返回runServer取值
         * 
         * @return true 正在运行
         * @return false 停止运行
         */
        bool isRunning();

        auto getCodec(){return codec_ptr;}

    private:
        /**
         * @brief 设置服务端运行状态
         * 
         * @param runServer 服务端是否正在运行
         */
        void setRunFlag(bool runServer);

        /**
         * @brief 发送错误信息
         * 
         * @param msg 将要发送的错误信息字符串
         * @param pktID 数据包ID
         */
        void send_err(std::string msg, uint24_t pktID);
        
        /**
         * @brief 发送函数参数类型错误信息
         * 
         * @tparam args_type 可接受的函数参数类型
         * @param pktID 数据包ID
         */
        template<typename args_type>
        void send_err_args(uint24_t pktID);

        /**
         * @brief 发送函数返回值
         * 
         * @tparam T 函数返回值类型
         * @param res 函数返回值
         * @param pktID 数据包ID
         */
        template<typename T>
        void send_res(T& res, uint24_t pktID);

        /**
         * @brief 处理到达数据包
         * 
         * @param pkt 待处理的到达数据包元组，包含"packet type", "packet ID", "payload length" 和 "payload data"
         * @param verbose 是否启用调试输出
         */
        void process_packet(pkt_t pkt, bool verbose=false);

    private:
        /**
         * @brief 服务端适配指针
         * 
         */
        std::shared_ptr<irpc::port::server::server_port> sp_ptr;

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
         * @brief 函数映射表
         * 
         */
        std::unordered_map<std::string, std::function<void(msgpack::object &obj,uint24_t pktID)>> m_handlers;

        /**
         * @brief 是否启用调试输出
         * 
         */
        bool verbose = false;

        /**
         * @brief 控制服务端是否继续循环运行
         * 
         */
        volatile std::atomic_bool runServer = false;

        /**
         * @brief 异步运行未来句柄
         * 
         */
        std::future<void> run_async_fut;
    };
}

#include "server.tpp"

#endif
