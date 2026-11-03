/**
 * @file codec.hpp
 * @author Weifan Gao (gaoweifan@fmsh.com.cn)
 * @brief IRPC编解码器，负责数据包的编解码（序列化/反序列化）
 * @date 2023-08-29
 * 
 * @note IRPC使用msgpack进行编解码，有关数据类型的支持等请参考msgpack官方文档。
 * msgpack支持的数据类型:
 * https://github.com/msgpack/msgpack-c/wiki/v2_0_cpp_adaptor
 * msgpack README.md:
 * https://github.com/msgpack/msgpack-c/blob/cpp_master/README.md
 * msgpack 快速开始:
 * https://github.com/msgpack/msgpack-c/blob/cpp_master/QUICKSTART-CPP.md
 * msgpack wiki:
 * https://github.com/msgpack/msgpack-c/wiki/v2_0_cpp_overview
 * 
 * @copyright Copyright (c) 2023 Shanghai Fudan Microelectronics Group Co., Ltd. All rights reserved.
 * 
 */
#ifndef _RPC_CODEC_H
#define _RPC_CODEC_H

#include <tuple>
#include <string>
#include <iostream>
#include <functional>
#include <chrono>

#include <msgpack.hpp>

#include "icraft-irpc/port/base/port.hpp"
#include "icraft-irpc/utils/utils.hpp"
#include "icraft-irpc/utils/threadpool.hpp"

namespace irpc{
    #define FMSH_PREAMBLE {'F','M','S','H'}
    /**
     * @brief 数据包头部结构定义
     * 
     */
    PACK(typedef struct packetHead{
        const char preamble[4]=FMSH_PREAMBLE; ///< 数据包前导(preamble)，由4字节ASCII编码字符'FMSH'组成，用于确定该数据包在数据流中的起始位置
        uint8_t type;    ///< 数据包类型(type)，由1字节无符号整型组成，其取值为msg_type，用于判断数据包类型
        uint24_t pktID;  ///< 数据包ID(pktID)，由3字节无符号整型组成，用于判断请求发起方是谁并将返回值传递给对方
        uint32_t length; ///< 数据包有效载荷长度(length)，由4字节无符号整型组成，用于确定将要读入的payload大小
    }) packetHead_t;

    /**
     * @brief 数据包类型标签（最大256种）
     * 
     */
    enum msg_type{
        func_execute, ///< 执行函数，payload为msgpack封装的函数名及参数["funcName",[args…]]
        func_return,  ///< 函数执行成功，发送返回值，payload为msgpack封装的返回值
        func_failed,  ///< 函数执行失败，发送错误信息，payload为msgpack封装的错误信息字符串（如参数不匹配
        test_echo     ///< 数据链路测试，发什么回什么，payload为二进制原始数据
    };

    /**
     * @brief 接收状态机状态
     * 
     */
    enum recv_state{
        recv_packet_preamble,///< 接收packet preamble
        recv_packet_header,  ///< 接收packet header
        recv_packet_payload, ///< 接收packet payload
        recv_packet_crc,     ///< 接收CRC(TBD)
    };

    /**
     * @brief 数据包类型
     * 
     * @details tuple组成如下
     * msg_type type      = std::get<0>(pkt);
     * uint24_t pktID     = std::get<1>(pkt);
     * uint32_t length    = std::get<2>(pkt);
     * auto payload_bytes = std::get<3>(pkt);
     * 
     */
    using pkt_t = std::tuple<msg_type, uint24_t, uint32_t, std::shared_ptr<uint8_t []>>;

    /**
     * @brief 编解码器
     * 
     */
    class codec final{
    public:
        /**
         * @brief Construct a new codec object
         * 
         */
        codec() = default;
        /**
         * @brief Destroy the codec object
         * 
         */
        ~codec() = default;
        
        /**
         * @brief 打包指定类型T的数据t（序列化）
         * 
         * @tparam T 要打包的数据类型
         * @param[in] t 要打包的数据
         * @return buffer_type 返回打包后的二进制buffer
         */
        template <typename T> 
        buffer_type pack(T &&t);

        /**
         * @brief 解包为指定类型T的数据（反序列化）
         * 
         * @tparam T 要解包的数据类型
         * @param[in] data 二进制数据指针
         * @param[in] length 二进制数据长度
         * @return T 返回解包后的指定类型T的数据
         */
        template<typename T>
        T unpack(const char* data, const size_t length);
        /**
         * @brief 解包为指定类型T的数据（反序列化）
         * 
         * @tparam T 要解包的数据类型
         * @param[in] data 二进制数据buffer
         * @return T 返回解包后的指定类型T的数据
         */
        template<typename T>
        T unpack(const buffer_type& data){
            return this->unpack<T>(data.data(),data.size());
        }
        /**
         * @brief 解包为指定类型T的数据（反序列化）
         * 
         * @tparam T 要解包的数据类型
         * @param[in] data 二进制数据智能指针
         * @param[in] len 二进制数据长度
         * @return T 返回解包后的指定类型T的数据
         */
        template<typename T>
        T unpack(std::shared_ptr<uint8_t []> data, size_t len){
            return this->unpack<T>((char *)(data.get()),len);
        }
        
        /**
         * @brief 打包函数名及其参数
         * 
         * @tparam Args 函数的参数类型
         * @param funcName 函数名
         * @param args 函数的参数
         * @return buffer_type 返回打包后的二进制buffer
         */
        template<typename... Args>
        buffer_type pack_func(const std::string funcName, Args&&... args);

        /**
         * @brief 解包并返回msgpack::object_handle对象句柄
         * 
         * @param[in] data 二进制数据指针
         * @param[in] len 二进制数据字节数
         * @return msgpack::object_handle 返回msgpack对象句柄
         */
        msgpack::object_handle unpack_obj(const char *data, size_t len);
        /**
         * @brief 解包并返回msgpack::object_handle对象句柄
         * 
         * @param[in] data 二进制数据buffer
         * @return msgpack::object_handle 返回msgpack对象句柄
         */
        msgpack::object_handle unpack_obj(const buffer_type& data){
            return this->unpack_obj(data.data(),data.size());
        }
        /**
         * @brief 解包并返回msgpack::object_handle对象句柄
         * 
         * @param[in] data 二进制数据智能指针
         * @param[in] len 二进制数据字节数
         * @return msgpack::object_handle 返回msgpack对象句柄
         */
        msgpack::object_handle unpack_obj(std::shared_ptr<uint8_t []> data, size_t len){
            return this->unpack_obj((char *)(data.get()),len);
        }

        /**
         * @brief 从msgpack::object对象解包函数名
         * 
         * @note msgpack::object可通过msgpack::object_handle.get()得到
         * 
         * @param[in] obj 待解包的msgpack::object对象
         * @return std::string 返回函数名
         */
        std::string unpack_func_name(msgpack::object &obj);

        /**
         * @brief 从msgpack::object对象解包函数参数
         * 
         * @note msgpack::object可通过msgpack::object_handle.get()得到
         * 
         * @tparam AT 指定参数数据类型
         * @param[in] obj 待解包的msgpack::object对象
         * @return AT 以指定类型返回解包后的参数
         */
        template<typename AT>
        AT unpack_func_args(msgpack::object &obj);

        /**
         * @brief Get data packet from pb
         * 
         * @details receive and parse packet from any port derived from irpc::port::port_base
         *          and return a tuple consisting of "packet type", "payload length" and "payload data"
         * 
         * @param pb 通信端口
         * @param verbose 是否启用调试输出
         * @param block 是否阻塞等待（否则抛异常告知资源忙）
         * @return pkt_t return a tuple consisting of "packet type", "packet ID", "payload length" and "payload data"
         */
        pkt_t get_packet(std::shared_ptr<port::port_base> pb, bool verbose = false, bool block = true);

        /**
         * @brief Get data packet by byte using state machine
         * 
         * @details parse packet data by byte, and once the whole packet has been received,
         *          callback function "process_packet" will be called
         * 
         * @param data_queue 字节数据队列
         * @param isRun 是否继续运行标志位指针
         * @param process_packet 数据包处理回调函数
         * @param verbose 是否启用调试输出
         */
        void parse_packet_by_byte(std::shared_ptr<utils::SafeQueue<std::pair<std::shared_ptr<uint8_t []>, uint32_t>>> data_queue, 
                                  volatile std::atomic_bool &isRun,
                                  std::function<void (pkt_t, bool)> const &process_packet, 
                                  bool verbose);

        /**
         * @brief Send data packet to pb
         * 
         * @details parse and send packet to any port derived from irpc::port::port_base
         * 
         * @param pb 通信端口
         * @param type 数据包类型
         * @param pktID 数据包ID
         * @param length payload长度
         * @param[in] payload 数据包有效载荷指针
         * @param verbose 是否启用调试输出
         */
        void send_packet (std::shared_ptr<port::port_base> pb,
                          msg_type type, 
                          uint24_t pktID,
                          uint32_t length, 
                          const void *payload, 
                          bool verbose = false);
        /**
         * @brief Send data packet to pb
         * 
         * @details parse and send packet to any port derived from irpc::port::port_base
         * 
         * @param pb 通信端口
         * @param type 数据包类型
         * @param pktID 数据包ID
         * @param[in] buffer 数据包有效载荷buffer
         * @param verbose 是否启用调试输出
         */
        void send_packet (std::shared_ptr<port::port_base> pb,
                          msg_type type, 
                          uint24_t pktID,
                          const buffer_type& buffer, 
                          bool verbose = false)
        {
            this->send_packet(pb,type,pktID,buffer.size(),buffer.data(),verbose);
        };
        /**
         * @brief set CRC enable state
         * 
         * @param enableCRC whether to enable CRC
         */
        void setCRC(bool enableCRC){
            this->enableCRC = enableCRC;
        }
    public:
        static const uint8_t preamble_len;   ///< 前导字节数=4
        static const uint8_t type_len;       ///< 数据包类型字节数=1
        static const uint8_t pktID_len;      ///< 数据包ID字节数=3
        static const uint8_t length_len;     ///< 数据长度字节数=4
        static const uint8_t CRC_len;        ///< CRC校验码字节数=2
        static const uint8_t packetHead_len; ///< 数据包头部字节数，等于preamble_len+type_len+pktID_len+length_len=12
    private:
        msgpack::unpacked msg_; ///< msgpack对象句柄
        std::mutex sendPkt_mutex; ///< 数据包发送mutex，防止多线程下不同包的header与payload交错发送
        std::mutex recvPkt_mutex; ///< 数据包接收mutex，防止多线程下不同包的header与payload交错发送
        bool enableCRC=false;
    };
}

#include "codec.tpp"

#endif
