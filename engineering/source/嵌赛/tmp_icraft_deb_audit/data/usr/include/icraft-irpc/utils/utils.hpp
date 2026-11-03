/**
 * @file utils.hpp
 * @author Weifan Gao (gaoweifan@fmsh.com.cn)
 * @brief IRPC实用程序，如十六进制打印，函数参数萃取等
 * @date 2023-08-29
 * 
 * @copyright Copyright (c) 2023 Shanghai Fudan Microelectronics Group Co., Ltd. All rights reserved.
 * 
 */
#ifndef _UTILS_H
#define _UTILS_H

#include <cctype>       // isprint
#include <iomanip>      // setw
#include <typeinfo>     // typeid
#include <sstream>      // std::ostringstream, std::string
#include <type_traits>  // std::is_array
#include <utility>      // std::move
#include <functional>   // std::function
#if defined(__GNUC__)
    #include <memory>   // std::unique_ptr
    #include <cxxabi.h> // abi::__cxa_demangle
#endif

#include <msgpack.hpp>

#ifdef __GNUC__
#define PACK(...) __VA_ARGS__ __attribute__((__packed__))
#endif

#ifdef _MSC_VER
#define PACK(...) __pragma(pack(push, 1)) __VA_ARGS__ __pragma(pack(pop))
#endif

namespace irpc{
    /**
     * @brief 缓冲区类型
     * 
     * @details 详情请参考msgpack::sbuffer
     */
    using buffer_type = msgpack::sbuffer;
    /**
     * @brief 数据释放函数指针类型
     * 
     */
    using ptr_del_func = std::function<void(void*)>;
    /**
     * @brief 原始字节数据类型
     * 
     */
    class bchar{
    public:
        bchar():deleter(nullptr){}
        /**
         * @brief Construct a new bchar object
         * 
         * @param ptr 数据指针
         * @param size 数据字节数
         * @param del 数据释放函数指针
         */
        bchar(const char* ptr, uint32_t size, ptr_del_func del = nullptr){
            this->raw_data.ptr = ptr;
            this->raw_data.size = size;
            this->deleter = del;
        }
        /**
         * @brief Destroy the bchar object
         * 
         */
        ~bchar(){
            if(this->raw_data.ptr && this->deleter)
                this->deleter((void *)this->raw_data.ptr);
            this->raw_data.ptr = nullptr;
            this->raw_data.size = 0;
        }
        // bchar &operator=(const bchar &) = delete; ///< 阻止赋值
    public:
        uint32_t size() const {return raw_data.size;};
        const char* ptr() const {return raw_data.ptr;};
        bool operator== (const bchar& x) const{
            return raw_data == x.raw_data;
        }
        bool operator!= (const bchar& x) const{
            return raw_data != x.raw_data;
        }
        bool operator< (const bchar& x) const{
            return raw_data < x.raw_data;
        }
        bool operator> (const bchar& x) const{
            return raw_data > x.raw_data;
        }
        ptr_del_func deleter;
    public:
        msgpack::type::raw_ref raw_data;
        MSGPACK_DEFINE(raw_data);
    };
    /**
     * @brief 24位无符号整型的实现，与基本数值类型用法一致
     * 
     */
    PACK(class uint24_t {
        uint8_t data[3]={0,0,0};
    public:
        uint32_t asUInt() const {
            return (data[2] << 16) | (data[1] << 8) | (data[0]);
        }
        void setVal(int val){
            data[2] = (val & 0xff0000) >> 16;
            data[1] = (val & 0xff00) >> 8;
            data[0] = (val & 0xff);
        }
        uint24_t(int val) {
            setVal(val);
        }

        uint24_t() = default;
        uint24_t(const uint24_t &that) = default;
        uint24_t &operator=(const uint24_t &that) = default;
        uint24_t &operator=(int val) { return *this = uint24_t(val); }

        // obey usual arithmetic conversion rule
        operator int() const { return asUInt(); }

        // some other operators: a++, ++a, a--, --a
        // 前置++
        uint24_t & operator++(){
            setVal(asUInt()+1);
            return *this;
        }
        // 前置--
        uint24_t & operator--(){
            setVal(asUInt()-1);
            return *this;
        }
        // 后置++
        uint24_t operator++(int){
            uint24_t tmp(*this); // 记录修改前的对象
            setVal(asUInt()+1);
            return tmp;       // 返回修改前的对象
        }
        // 后置--
        uint24_t operator--(int){ 
            uint24_t tmp(*this); // 记录修改前的对象
            setVal(asUInt()-1);
            return tmp;       // 返回修改前的对象
        }
    });
    
    /**
     * @brief IRPC实用程序
     * 
     * @details 十六进制打印，函数参数萃取等实用程序
     * 
     */
    namespace utils{
        /**
         * @brief hex dump
         * 
         * @cond INTERNAL
         */
        namespace private_hex_dump {
            template <unsigned RowSize, bool ShowAscii>
            struct CustomHexdump
            {
                CustomHexdump(const void* data, unsigned length) :
                    mData(static_cast<const unsigned char*>(data)), mLength(length) { }
                const unsigned char* mData;
                const unsigned mLength;
            };

            template <unsigned RowSize, bool ShowAscii>
            std::ostream& operator<<(std::ostream& out, const CustomHexdump<RowSize, ShowAscii>& dump)
            {
                std::ios_base::fmtflags f(out.flags()); // save old format
                out.fill('0');
                for (int i = 0; i < dump.mLength; i += RowSize)
                {
                    if(i != 0) out << std::endl;
                    out << "0x" << std::setw(6) << std::hex << i << ": ";
                    for (int j = 0; j < RowSize; ++j)
                    {
                        if (i + j < dump.mLength)
                        {
                            out << std::hex << std::setw(2) << static_cast<int>(dump.mData[i + j]) << " ";
                        }
                        else
                        {
                            out << "   ";
                        }
                    }

                    out << " ";
                    if (ShowAscii)
                    {
                        for (int j = 0; j < RowSize; ++j)
                        {
                            if (i + j < dump.mLength)
                            {
                                if (std::isprint(dump.mData[i + j]))
                                {
                                    out << static_cast<char>(dump.mData[i + j]);
                                }
                                else
                                {
                                    out << ".";
                                }
                            }
                        }
                    }
                }
                out.flags(f); // format restored
                return out;
            }
        } ///< @endcond

        /**
         * @brief 将字节数据以十六进制形式打印输出
         * 
         * @details 默认以每行16字节，且显示每字节对应ASCII的方式输出
         * 
         * @param data 待打印的数据
         * @param length 数据字节长度
         * 
         */
        typedef private_hex_dump::CustomHexdump<16, true> Hexdump;



        /**
         * @brief function trait
         * 
         * @cond INTERNAL
         */
        namespace private_function_trait {
            /**
             * @brief function_traits base template
             * 
             * @tparam T type
             */
            template<typename T>
            struct function_traits_impl;

            /**
             * @brief function_traits template for vanilla function
             * 
             * @tparam Ret return type
             * @tparam Args arguments type
             */
            template<typename Ret, typename ... Args>
            struct function_traits_impl<Ret(Args...)> {
                using return_type = Ret;

                template<std::size_t I>
                struct args {
                    using type = typename std::tuple_element<I, std::tuple<Args...>>::type;
                };
                using tuple_type = std::tuple<std::remove_cv_t<std::remove_reference_t<Args>>...>;
            };

            /**
             * @brief function_traits template for vanilla function pointer
             * 
             * @tparam Ret return type
             * @tparam Args arguments type
             */
            template<typename Ret, typename ... Args>
            struct function_traits_impl<Ret(*)(Args...)>: 
                function_traits_impl<Ret(Args...)> {};

            /**
             * @brief function_traits template for vanilla function reference
             * 
             * @tparam Ret return type
             * @tparam Args arguments type
             */
            template<typename Ret, typename ... Args>
            struct function_traits_impl<Ret(&)(Args...)>: 
                function_traits_impl<Ret(Args...)> {};

            /**
             * @brief function_traits template for class method (non-const, no ref-qualifier)
             * 
             * @tparam Ret return type
             * @tparam Cls class type
             * @tparam Args arguments type
             */
            template<typename Ret, typename Cls, typename ... Args>
            struct function_traits_impl<Ret(Cls::*)(Args...)>: 
                function_traits_impl<Ret(Args...)> {
                    using class_type = Cls;
                };

            /**
             * @brief function_traits template for class method (const, no ref-qualifier)
             * 
             * @tparam Ret return type
             * @tparam Cls class type
             * @tparam Args arguments type
             */
            template<typename Ret, typename Cls, typename ... Args>
            struct function_traits_impl<Ret(Cls::*)(Args...) const>: 
                function_traits_impl<Ret(Args...)> {
                    using class_type = Cls;
                };

            /**
             * @brief function_traits template for class method (non-const, lvalue ref-qualifier)
             * 
             * @tparam Ret return type
             * @tparam Cls class type
             * @tparam Args arguments type
             */
            template<typename Ret, typename Cls, typename ... Args>
            struct function_traits_impl<Ret(Cls::*)(Args...) &>: 
                function_traits_impl<Ret(Args...)> {
                    using class_type = Cls;
                };

            /**
             * @brief function_traits template for class method (const, lvalue ref-qualifier)
             * 
             * @tparam Ret return type
             * @tparam Cls class type
             * @tparam Args arguments type
             */
            template<typename Ret, typename Cls, typename ... Args>
            struct function_traits_impl<Ret(Cls::*)(Args...) const &>: 
                function_traits_impl<Ret(Args...)> {
                    using class_type = Cls;
                };
        } ///< @endcond
        
        /**
         * @brief 提取函数数据类型
         * 
         * @tparam T 待提取的函数类型T
         */
        template<typename T>
        struct function_traits :
            private_function_trait::function_traits_impl<std::remove_cv_t<std::remove_reference_t<T>>> 
        {};

        /**
         * @brief 提取lambda函数数据类型
         * 
         * @tparam T 待提取的lambda函数类型T
         */
        template<typename T>
        struct function_traits_lambda :
            function_traits<decltype(&T::operator())>
        {};



        /**
         * @brief 数据类型名称提取
         * 
         * @cond INTERNAL
         */
        namespace private_check_type {

            template <typename T, bool IsBase = false>
            struct check;

            /*
                Output state management
            */

            class output
            {
                bool is_compact_ = true;

                template <typename T>
                bool check_empty(const T&) { return false; }
                bool check_empty(const char* val)
                {
                    return (!val) || (val[0] == 0);
                }

                template <typename T>
                void out(const T& val)
                {
                    if (check_empty(val)) return;
                    if (!is_compact_) sr_ += " ";
                    using ss_t = std::ostringstream;
                    // #ifdef __linux__
                    //     sr_ += static_cast<ss_t&>(ss_t() << val).str();
                    // #elif _WIN32
                        ss_t st;
                        st << val;
                        sr_ += st.str();
                    // #endif
                    is_compact_ = false;
                }

                std::string& sr_;

            public:
                output(std::string& sr) : sr_(sr) {}

                output& operator()(void) { return (*this); }

                template <typename T1, typename... T>
                output& operator()(const T1& val, const T&... args)
                {
                    out(val);
                    return operator()(args...);
                }

                output& compact(void)
                {
                    is_compact_ = true;
                    return (*this);
                }
            };

            // ()

            template <bool>
            struct bracket
            {
                output& out_;

                bracket(output& out, const char* = nullptr) : out_(out)
                { out_("(").compact(); }

                ~bracket(void)
                { out_.compact()(")"); }
            };

            template <>
            struct bracket<false>
            {
                bracket(output& out, const char* str = nullptr)
                { out(str); }
            };

            // [N]

            template <size_t N = 0>
            struct bound
            {
                output& out_;

                bound(output& out) : out_(out) {}
                ~bound(void)
                {
                    if (N == 0) out_("[]");
                    else        out_("[").compact()
                                    ( N ).compact()
                                    ("]");
                }
            };

            // (P1, P2, ...)

            template <bool, typename... P>
            struct parameter;

            template <bool IsStart>
            struct parameter<IsStart>
            {
                output& out_;

                parameter(output& out) : out_(out) {}
                ~parameter(void)
                { bracket<IsStart> { out_ }; }
            };

            template <bool IsStart, typename P1, typename... P>
            struct parameter<IsStart, P1, P...>
            {
                output& out_;

                parameter(output& out) : out_(out) {}
                ~parameter(void)
                {
                    [this](bracket<IsStart>&&)
                    {
                        check<P1> { out_ };
                        parameter<false, P...> { out_.compact() };
                    } (bracket<IsStart> { out_, "," });
                }
            };

            // Do output at destruct

            struct at_destruct
            {
                output&     out_;
                const char* str_;

                at_destruct(output& out, const char* str = nullptr)
                    : out_(out)
                    , str_(str)
                {}
                ~at_destruct(void)
                { out_(str_); }

                void set_str(const char* str = nullptr)
                { str_ = str; }
            };

            /*
                CV-qualifiers, references, pointers
            */

            template <typename T, bool IsBase>
            struct check
            {
                output out_;
                check(const output& out) : out_(out)
                {
            #   if defined(__GNUC__)
                    const char* typeid_name = typeid(T).name();
                    auto deleter = [](char* p)
                    {
                        if (p) free(p);
                    };
                    std::unique_ptr<char, decltype(deleter)> real_name
                    {
                        abi::__cxa_demangle(typeid_name, nullptr, nullptr, nullptr), deleter
                    };
                    out_(real_name ? real_name.get() : typeid_name);
            #   else
                    out_(typeid(T).name());
            #   endif
                }
            };

            #define CHECK_TYPE__(OPT) \
                template <typename T, bool IsBase> \
                struct check<T OPT, IsBase> : check<T, true> \
                { \
                    using base_t = check<T, true>; \
                    using base_t::out_; \
                    check(const output& out) : base_t(out) { out_(#OPT); } \
                };

            CHECK_TYPE__(const)
            CHECK_TYPE__(volatile)
            CHECK_TYPE__(const volatile)
            CHECK_TYPE__(&)
            CHECK_TYPE__(&&)
            CHECK_TYPE__(*)

            #undef CHECK_TYPE__

            /*
                Arrays
            */

            #define CHECK_TYPE_ARRAY__(CV_OPT, BOUND_OPT, ...) \
                template <typename T, bool IsBase __VA_ARGS__> \
                struct check<T CV_OPT [BOUND_OPT], IsBase> : check<T CV_OPT, !std::is_array<T>::value> \
                { \
                    using base_t = check<T CV_OPT, !std::is_array<T>::value>; \
                    using base_t::out_; \
                \
                    bound<BOUND_OPT> bound_   = out_; \
                    bracket<IsBase>  bracket_ = out_; \
                \
                    check(const output& out) : base_t(out) {} \
                };

            #define CHECK_TYPE_ARRAY_CV__(BOUND_OPT, ...) \
                CHECK_TYPE_ARRAY__(, BOUND_OPT, ,##__VA_ARGS__) \
                CHECK_TYPE_ARRAY__(const, BOUND_OPT, ,##__VA_ARGS__) \
                CHECK_TYPE_ARRAY__(volatile, BOUND_OPT, ,##__VA_ARGS__) \
                CHECK_TYPE_ARRAY__(const volatile, BOUND_OPT, ,##__VA_ARGS__)

            #define CHECK_TYPE_PLACEHOLDER__
            CHECK_TYPE_ARRAY_CV__(CHECK_TYPE_PLACEHOLDER__)
            #if defined(__GNUC__)
            CHECK_TYPE_ARRAY_CV__(0)
            #endif
            CHECK_TYPE_ARRAY_CV__(N, size_t N)

            #undef CHECK_TYPE_PLACEHOLDER__
            #undef CHECK_TYPE_ARRAY_CV__
            #undef CHECK_TYPE_ARRAY__

            /*
                Functions
            */

            template <typename T, bool IsBase, typename... P>
            struct check<T(P...), IsBase> : check<T, true>
            {
                using base_t = check<T, true>;
                using base_t::out_;

                parameter<true, P...> parameter_ = out_;
                bracket<IsBase>       bracket_   = out_;

                check(const output& out) : base_t(out) {}
            };

            /*
                Pointers to members
            */

            template <typename T, bool IsBase, typename C>
            struct check<T C::*, IsBase> : check<T, true>
            {
                using base_t = check<T, true>;
                using base_t::out_;

                check(const output& out) : base_t(out)
                {
                    check<C> { out_ };
                    out_.compact()("::*");
                }
            };

            /*
                Pointers to member functions
            */

            #define CHECK_TYPE_MEM_FUNC__(...) \
                template <typename T, bool IsBase, typename C, typename... P> \
                struct check<T(C::*)(P...) __VA_ARGS__, IsBase> \
                { \
                    at_destruct cv_ = base_.out_; \
                    check<T(P...), true> base_; \
                    output& out_ = base_.out_; \
                \
                    check(const output& out) : base_(out) \
                    { \
                        cv_.set_str(#__VA_ARGS__); \
                        check<C> { out_ }; \
                        out_.compact()("::*"); \
                    } \
                };

            CHECK_TYPE_MEM_FUNC__()
            CHECK_TYPE_MEM_FUNC__(const)
            CHECK_TYPE_MEM_FUNC__(volatile)
            CHECK_TYPE_MEM_FUNC__(const volatile)

            #undef CHECK_TYPE_MEM_FUNC__

        } ///< @endcond
        
        /**
         * @brief Get the name of the given type T
         * 
         * @tparam T type to be checked
         * @return std::string type name
         */
        template <typename T>
        inline std::string check_type(void)
        {
            std::string str;
            private_check_type::check<T> { str };
            return std::move(str);
        }



        /**
         * @brief 创建指定类型T的数组的智能指针
         * 
         * @tparam T 数组数据类型
         * @param size 数组成员个数
         * @return std::shared_ptr<T[]> 返回指向类型T的数组的智能指针
         */
        template<typename T>
        std::shared_ptr<T[]> make_shared_array_tpl(size_t size) {
            return std::shared_ptr<T[]>(new T[size](), std::default_delete<T[]>());
        }

    } // namespace utils
} // namespace irpc
#endif