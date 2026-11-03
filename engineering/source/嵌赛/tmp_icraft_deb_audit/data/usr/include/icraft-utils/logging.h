#pragma once
#include <chrono>
#include <cstddef>
#include <string>
#include <cstdlib>
#include <sstream>
#include <initializer_list>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <array>
#include <vector>

/// @cond
#ifndef FMT_HEADER_ONLY
#define FMT_HEADER_ONLY
#endif
/// @endcond
#include <fmt/core.h>
#include "icraft-utils/midware/clock.hpp"
#include "icraft-utils/midware/path.hpp"

#include "icraft-utils/dllexport.h"

/// @cond
#if defined(_MSC_VER)
#define ICRAFT_NO_INLINE __declspec(noinline)
#else
#define ICRAFT_NO_INLINE __attribute__((noinline))
#endif

#ifdef _MSC_VER
#define ICRAFT_ALWAYS_INLINE __forceinline
#else
#define ICRAFT_ALWAYS_INLINE inline __attribute__((always_inline))
#endif

#define ICRAFT_THROW_EXCEPTION noexcept(false)
/// @endcond

/// @cond
namespace icraft::detail {
	class Console {
	public:
		UTILS_DLL static void SetAnsiMode();

		UTILS_DLL static void SetUTF8Output();
	};

	struct UFT8ConsoleHelper {
		UTILS_DLL UFT8ConsoleHelper();
	};
}
/// @endcond

namespace icraft {

	/** 表示日志等级的枚举 */
	enum class LogLevel {
		TRACE,	///< 追踪
		DEBUG,	///< 调试
		INFO,	///< 信息
		WARN,	///< 警告
		ERR,	///< 错误
		FATAL,	///< 致命
		OFF		///< 关闭
	};

	/** 表示颜色的枚举 */
	enum class ColorName {
		BLACK,		///< 黑色
		RED,		///< 红色
		GREEN,		///< 绿色
		YELLOW,		///< 黄色
		BLUE,		///< 蓝色
		MAGENTA,	///< 品红
		CYAN,		///< 青色
		WHITE		///< 白色
	};

	/**
	 * @brief	表示日志颜色的类	 * @details 对ANSI Color做了封装，可以获取常见颜色对应的控制字符串	 */
	class LogColor {
	public:
		/**
		 * @brief 从颜色名获取对应的前景色		 * @param	name	颜色名
		 * @return	表示前景色的LogColor对象
		 */
		UTILS_DLL static LogColor Foregroud(ColorName name);

		/**
		 * @brief 从颜色名获取对应的背景色		 * @param	name	颜色名
		 * @return	表示背景色的LogColor对象
		 */
		UTILS_DLL static LogColor Background(ColorName name);

		/**
		 * @brief 构造函数，从前景和背景的颜色名构造对象		 * @param	fg_color	前景颜色名
		 * @param	bg_color	背景颜色名
		 */
		UTILS_DLL LogColor(ColorName fg_color, ColorName bg_color);

	private:
		UTILS_DLL auto get();
		friend class StdoutSink;
		friend class StderrSink;

		UTILS_DLL LogColor(std::string_view color);

		inline static constexpr std::string_view black = "\033[90m";
		inline static constexpr std::string_view red = "\033[91m";
		inline static constexpr std::string_view green = "\033[92m";
		inline static constexpr std::string_view yellow = "\033[93m";
		inline static constexpr std::string_view blue = "\033[94m";
		inline static constexpr std::string_view magenta = "\033[95m";
		inline static constexpr std::string_view cyan = "\033[96m";
		inline static constexpr std::string_view white = "\033[97m";

		inline static constexpr std::array<std::string_view, 8> fg_colors {
			black, red, green, yellow, blue, magenta, cyan, white
		};

		inline static constexpr std::string_view on_black = "\033[100m";
		inline static constexpr std::string_view on_red = "\033[101m";
		inline static constexpr std::string_view on_green = "\033[102m";
		inline static constexpr std::string_view on_yellow = "\033[103m";
		inline static constexpr std::string_view on_blue = "\033[104m";
		inline static constexpr std::string_view on_magenta = "\033[105m";
		inline static constexpr std::string_view on_cyan = "\033[106m";
		inline static constexpr std::string_view on_white = "\033[107m";
		inline static constexpr std::array<std::string_view, 8> bg_colors{
			on_black, on_red, on_green, on_yellow, on_blue, on_magenta, on_cyan, on_white
		};

		std::string color_;
	};
#if !defined(_BAREME) && !defined(_FREERTOS)
	/**
	 * @brief 表示Logger的Sink的基类	 * @details Sink表示Logger的输出通道，比如文件、标准输出和错误输出等	 */
	class BasicSink {
	public:
		/**
		 * @brief 设置输出格式模板		 * @param pattern	表示模板的字符串		 * 
		 * 模板格式请参考
		 * <a href="自定义格式">https://github.com/gabime/spdlog/wiki/3.-Custom-formatting/</a>
		 */
		UTILS_DLL void setPattern(const char* pattern);

		/**
		 * @brief 设置日志等级		 * @param level	日志等级
		 */
		UTILS_DLL void setLevel(LogLevel level);

		/**
		 * @brief 获取日志等级		 * @return 日志等级
		 */
		UTILS_DLL LogLevel level() const;

		/**
		 * @brief 设置某日志等级对应的颜色		 * @param level	日志等级
		 * @param color	日志颜色
		 */
		UTILS_DLL virtual void setColor(LogLevel level, LogColor color);

		/// @cond
		UTILS_DLL virtual ~BasicSink();
		/// @endcond

	protected:
		struct Impl;
		std::shared_ptr<Impl> impl_ = nullptr;

		/// @cond
		UTILS_DLL explicit BasicSink(std::shared_ptr<Impl> impl);
		/// @endcond
	private:
		friend class Logger;
	};

	/**
	 * @brief 表示文件Sink的类	 * @details 使用FileSink可以将日志输出到指定文件中
	 */
	class FileSink : public BasicSink {
	public:
		/**
		 * @brief 构造函数，从midware::path构造
		 * @param file_path 表示文件路径的midware::path类型		 */
		UTILS_DLL explicit FileSink(const icraft::midware::path& file_path, const bool new_file = true);
	};

	/**
	 * @brief 表示标准输出Sink的类	 * @details 使用StdoutSink可以将日志输出到标准输出
	 */
	class StdoutSink : public BasicSink {
	public:
		/** 构造函数 */
		UTILS_DLL StdoutSink();

		/**
		 * @see BasicSink::setColor		 */
		UTILS_DLL virtual void setColor(LogLevel level, LogColor color) override;
	};

	/**
	 * @brief 表示错误输出Sink的类	 * @details 使用StderrSink可以将日志输出到错误输出
	 */
	class StderrSink : public BasicSink {
	public:
		/** 构造函数 */
		UTILS_DLL StderrSink();

		/**
		 * @see BasicSink::setColor		 */
		UTILS_DLL virtual void setColor(LogLevel level, LogColor color) override;
	};
#endif	// !defined(_BAREME) && !defined(_FREERTOS)

	/**
	 * @brief 表示日志的类	 * @details 使用Logger类可以记录各个级别的日志
	 */
	class Logger {
	public:
#if !defined(_BAREME) && !defined(_FREERTOS)
		/**
		 * @brief 构造函数，从Sink容器的迭代器构造		 * @details 该构造方法用于将Logger绑定到多个Sink
		 * @tparam It	Sink容器的迭代器类型
		 * @param name	Logger的名称
		 * @param begin	Sink容器迭代器的起始位置
		 * @param end	Sink容器迭代器的结束位置
		 */
		template<typename It>
		Logger(const std::string& name, It begin, It end)
			: name_(name) {
			std::vector<BasicSink> sinks(begin, end);
			initFromSinks(name_, sinks.data(), sinks.size());
		}

		/**
		 * @brief 构造函数，从单个Sink构造		 * @param name	Logger的名称
		 * @param sink	该Logger要绑定的BasicSink
		 */
		UTILS_DLL Logger(const std::string& name, const BasicSink& sink);

		/**
		 * @brief 构造函数，从Sink的initializer_list构造		 * @details 该构造方法用于将Logger绑定到多个Sink
		 * @param name	Logger的名称
		 * @param sink	该Logger要绑定的BasicSink的initializer_list
		 */
		UTILS_DLL Logger(const std::string& name, std::initializer_list<BasicSink> sinks);
#endif	// !defined(_BAREME) && !defined(_FREERTOS)


		UTILS_DLL Logger(const std::string& name, LogLevel level);

		/**
		 * @brief 获取Logger的名称		 * @return Logger的名称
		 */
		UTILS_DLL const std::string& name() const;

		/**
		 * @brief 设置输出格式模板		 * @param pattern	表示模板的字符串		 *
		 * 模板格式请参考
		 * <a href="自定义格式">https://github.com/gabime/spdlog/wiki/3.-Custom-formatting/</a>
		 */
		UTILS_DLL void setPattern(const char* pattern);

		/**
		 * @brief 设置日志等级		 * @param level	日志等级
		 */
		UTILS_DLL void setLevel(LogLevel level);

		/**
		 * @brief 获取日志等级		 * @return 日志等级
		 */
		UTILS_DLL LogLevel level() const;

		/**
		 * @brief 获取全局默认Logger单例		 * @note 不建议直接使用，请使用ICRAFT_LOG(level)宏
		 */
		UTILS_DLL static Logger& Global();

		/**
		 * @brief 记录日志信息		 * @param level 日志等级
		 * @msg	  msg	日志信息
		 */
		UTILS_DLL void log(LogLevel level, std::string_view msg);

		/** 记录日志debug信息 */
		template<typename... Args>
		void debug(std::string fmt, Args&&... args) {
			logFormatted(LogLevel::DEBUG, fmt::format(fmt::runtime(fmt), std::forward<Args>(args)...));
		}

		/** 记录日志info信息 */
		template<typename... Args>
		void info(std::string fmt, Args&&... args) {
			logFormatted(LogLevel::INFO, fmt::format(fmt::runtime(fmt), std::forward<Args>(args)...));
		}

		/** 记录日志warn信息 */
		template<typename... Args>
		void warn(std::string fmt, Args&&... args) {
			logFormatted(LogLevel::WARN, fmt::format(fmt::runtime(fmt), std::forward<Args>(args)...));
		}

		/** 记录日志error信息 */
		template<typename... Args>
		void error(std::string fmt, Args&&... args) {
			logFormatted(LogLevel::ERR, fmt::format(fmt::runtime(fmt), std::forward<Args>(args)...));
		}

		/** 记录日志fatal信息 */
		template<typename... Args>
		void fatal(std::string fmt, Args&&... args) {
			logFormatted(LogLevel::FATAL, fmt::format(fmt::runtime(fmt), std::forward<Args>(args)...));
		}

		/** 记录日志debug信息 */
		UTILS_DLL void debug(const std::string_view& msg);

		/** 记录日志info信息 */
		UTILS_DLL void info(const std::string_view& msg);

		/** 记录日志warn信息 */
		UTILS_DLL void warn(const std::string_view& msg);

		/** 记录日志error信息 */
		UTILS_DLL void error(const std::string_view& msg);

		/** 记录日志fatal信息 */
		UTILS_DLL void fatal(const std::string_view& msg);

	private:
		struct Impl;

		UTILS_DLL void logFormatted(LogLevel level, std::string msg);

#if !defined(_BAREME) && !defined(_FREERTOS)
		UTILS_DLL void initFromSinks(const std::string& name, const BasicSink* sinks, std::size_t sink_count);
		std::shared_ptr<Impl> impl_ = nullptr;
#endif

		std::string name_;
		LogLevel level_;
#if defined(_BAREME) || defined(_FREERTOS)
		LogColor color_{ ColorName::BLACK, ColorName::WHITE };
#endif	// defined(_BAREME) || defined(_FREERTOS)
	};

	/** 表示调用栈追踪信息 */
	class BackTrace {
	public:
		/**
		 * @brief  生成backtrace		 * @param bt_limit 默认的backtrace长度
		 * @return 多行字符串表示的backtrace		 */
		UTILS_DLL static std::string Get(int bt_limit = 500);
	};

	/** ICRAFT中表示错误的基类 */
	class Error : public std::runtime_error {
	public:
		/**
		 * @brief   Error类的构造函数		 * @param s 表示错误的信息
		 */
		UTILS_DLL explicit Error(const std::string& s);
	};

	using system_clock = icraft::midware::system_clock;

	/** 内部错误，由ICRAFT_LOG(EXCEPT)产生，携带backtrace信息 */
	class InternalError : public Error {
	public:
		/**
		 * @brief InternalError构造函数，不建议直接使用，请使用`ICRAFT_LOG(EXCEPT)`		 * @param file		错误发生的源文件
		 * @param lineno	错误发生的行号
		 * @param msg		错误信息
		 * @param time		错误发生的时间
		 * @param backtrace 错误发生时的backtrace
		 */
	#if defined(_BAREME) || defined(_FREERTOS)
		UTILS_DLL InternalError(std::string file, int lineno, std::string msg, int err_code);
	#else
		UTILS_DLL InternalError(std::string file, int lineno, std::string msg, int err_code);
		UTILS_DLL InternalError(std::string file, int lineno, std::string msg, int err_code,
			system_clock::time_point time, std::string backtrace);
	#endif // defined(_BAREME) || defined(_FREERTOS)

		/**
		 * @return 错误发生的源文件路径		 */
		UTILS_DLL const std::string& file() const;

		/**
		 * @return 错误信息		 */
		UTILS_DLL const std::string& msg() const;

		/**
		 * @return 包含文件、行号、backtrace和错误信息的格式化字符串		 */
		UTILS_DLL const std::string& fullMsg() const;

		/**
		 * @return 错误发生时的backtrace		 */
		UTILS_DLL const std::string& backtrace() const;
		
		#if !defined(_BAREME) && !defined(_FREERTOS)
		/**
		 * @return 错误发生的时间		 */
		UTILS_DLL const system_clock::time_point& time() const;
		#endif // !defined(_BAREME) && !defined(_FREERTOS)

		/**
		 * @return 错误发生的行号		 */
		UTILS_DLL int lineno() const;

		UTILS_DLL virtual const char* what() const noexcept;

		/**
		 * @return 错误码		 */
		UTILS_DLL const int errorCode() const;

		UTILS_DLL void rethrow(std::string info, std::string file, int line, int err_code);

	private:
		std::string file_;
		int lineno_;
		std::string msg_;
		#if !defined(_BAREME) && !defined(_FREERTOS)
			system_clock::time_point time_;
		#endif // !defined(_BAREME) && !defined(_FREERTOS)
		std::string backtrace_;
		std::string full_msg_;
		int err_code_;
	};

	/// @cond
	namespace detail{

		class StreamBuf {
		public:
			template<typename... Args>
			StreamBuf& append(std::string fmt, Args&&... args) {
				stream_ << fmt::format(fmt::runtime(fmt), std::forward<Args>(args)...);
				return *this;
			}

			template<typename T>
			StreamBuf& append(const T& msg) {
				stream_ << msg;
				return *this;
			}

			template<typename T>
			StreamBuf& operator<<(const T& args) {
				stream_ << args;
				return *this;
			}

			UTILS_DLL std::string str() const;

			UTILS_DLL void str(const std::string& s);

		private:
			std::ostringstream stream_;
		};

		/**
		 * @brief 为日志消息添加组件名前缀
		 * @details 当编译期定义了宏 ICRAFT_LOG_COMPONENT_NAME 时，返回 "[组件名] " + msg；
		 *          未定义时原样返回 msg，保持向后兼容。供 LogMsg 析构调用，使
		 *          ICRAFT_LOG(INFO) << "..." 自动输出形如 "[OnnxParser] ..." 的消息体。
		 */
		inline std::string with_component_prefix(std::string_view msg) {
		#ifdef ICRAFT_LOG_COMPONENT_NAME
			return std::string("[") + ICRAFT_LOG_COMPONENT_NAME + "] " + std::string(msg);
		#else
			return std::string(msg);
		#endif
		}

		/**
		 * @brief 表示致命错误，抛出携带错误信息的InternalError		 */
		class LogExcept {
		public:
			ICRAFT_NO_INLINE LogExcept(const char* file, int lineno, int err_code = 1) { GetEntry().init(file, lineno, err_code); }

			ICRAFT_NO_INLINE LogExcept(InternalError* err, const char* file, int lineno) {
				GetEntry().init(err, file, lineno, err->errorCode());
			}

			ICRAFT_NO_INLINE LogExcept(InternalError* err, const char* file, int lineno, int err_code) {
				GetEntry().init(err, file, lineno, err_code);
			}
#ifdef _MSC_VER
#pragma warning(disable : 4722)
#endif
			~LogExcept() ICRAFT_THROW_EXCEPTION { GetEntry().finalize(); }

			StreamBuf& stream() { return GetEntry().streambuf_; }

		private:
			class Entry {
			public:
				UTILS_DLL void init(const char* file, int lineno, int err_code);
	
				UTILS_DLL void init(InternalError* err, const char* file, int lineno, int err_code);

				UTILS_DLL Error finalize();

				StreamBuf streambuf_;
				std::string file_;
				int lineno_;
				int err_code_;
				InternalError* err_ = nullptr;
			};

			UTILS_DLL ICRAFT_NO_INLINE static Entry& GetEntry();
		};

		template<LogLevel L>
		class LogMsg {
		public:
			LogMsg() {
				#if !defined(_BAREME) && !defined(_FREERTOS)
				fmt::print("\033[2K\r");
				#endif
			};

			LogMsg(const std::string& file, int lineno) : LogMsg() {
				streambuf_.append("{}:{}: ", file, lineno);
			}

			StreamBuf& stream() { return streambuf_; }

			ICRAFT_NO_INLINE ~LogMsg() {
				Logger::Global().log(L, with_component_prefix(streambuf_.str()));
			}

		private:
			StreamBuf streambuf_;
		};
	}
	/// @endcond
}

/// @cond
#define ICRAFT_CONCAT_IMPL( x, y ) x##y
#define ICRAFT_MACRO_CONCAT( x, y ) ICRAFT_CONCAT_IMPL( x, y )
/// @endcond

/**
 * @brief 以指定日志等级 @a level 来记录日志 * @param level 日志等级，可选的有DEBUG, INFO, WARNING, ERROR, FATAL和EXCEPT */
#define ICRAFT_LOG(level, ...) ICRAFT_LOG_##level(__VA_ARGS__)
/// @cond
#define ICRAFT_LOG_DEBUG() ::icraft::detail::LogMsg<::icraft::LogLevel::DEBUG>().stream()
#define ICRAFT_LOG_INFO() ::icraft::detail::LogMsg<::icraft::LogLevel::INFO>().stream()
#define ICRAFT_LOG_WARNING() ::icraft::detail::LogMsg<::icraft::LogLevel::WARN>().stream()
#define ICRAFT_LOG_ERROR() ::icraft::detail::LogMsg<::icraft::LogLevel::ERR>().stream()
#define ICRAFT_LOG_FATAL() ::icraft::detail::LogMsg<::icraft::LogLevel::FATAL>().stream()
#define ICRAFT_LOG_EXCEPT(...) ::icraft::detail::LogExcept(__FILE__, __LINE__, ##__VA_ARGS__).stream()
#define ICRAFT_RETHROW(err, ...) ::icraft::detail::LogExcept(&err, __FILE__, __LINE__, ##__VA_ARGS__).stream()
/// @endcond

/**
 * @brief 以指定日志等级 @a level 来输出日志 * @param level 日志等级，可选的有OFF，DEBUG, INFO, WARNING, ERROR, FATAL和EXCEPT */
#define ICRAFT_SET_LOG_LEVEL(level) ICRAFT_SET_LOG_LEVEL_##level
/// @cond
#define ICRAFT_SET_LOG_LEVEL_OFF ::icraft::Logger::Global().setLevel(::icraft::LogLevel::OFF);
#define ICRAFT_SET_LOG_LEVEL_DEBUG ::icraft::Logger::Global().setLevel(::icraft::LogLevel::DEBUG);
#define ICRAFT_SET_LOG_LEVEL_INFO ::icraft::Logger::Global().setLevel(::icraft::LogLevel::INFO);
#define ICRAFT_SET_LOG_LEVEL_WARNING ::icraft::Logger::Global().setLevel(::icraft::LogLevel::WARN);
#define ICRAFT_SET_LOG_LEVEL_ERROR ::icraft::Logger::Global().setLevel(::icraft::LogLevel::ERR);
#define ICRAFT_SET_LOG_LEVEL_FATAL ::icraft::Logger::Global().setLevel(::icraft::LogLevel::FATAL);
#define ICRAFT_SET_LOG_LEVEL_EXCEPT ::icraft::Logger::Global().setLevel(::icraft::LogLevel::EXCEPT);
/// @endcond

#ifndef ICRAFT_NO_EXCEPTIONS

#define ICRAFT_TRY(...)									\
try {													\
	__VA_ARGS__											\
}catch (const std::exception& e) {						\
	ICRAFT_LOG(FATAL) << e.what();						\
	exit(-1);											\
}	
#endif

/**
 * @brief 让Console使用utf-8编码输出
 */
#define ICRAFT_CONSOLE_USE_UTF8 icraft::detail::UFT8ConsoleHelper ICRAFT_MACRO_CONCAT(_utf8_console_helper_, __COUNTER__);

#define ICRAFT_CHECK_BINARY_OP(name, op, x, y, ...) if (!(x op y)) (ICRAFT_LOG(EXCEPT, ##__VA_ARGS__) << "Check failed: " #x " " #op " " #y << "\n")

#define ICRAFT_CHECK_LT(x, y, ...) ICRAFT_CHECK_BINARY_OP(_LT, <, x, y, ##__VA_ARGS__)
#define ICRAFT_CHECK_GT(x, y, ...) ICRAFT_CHECK_BINARY_OP(_GT, >, x, y, ##__VA_ARGS__)
#define ICRAFT_CHECK_LE(x, y, ...) ICRAFT_CHECK_BINARY_OP(_LE, <=, x, y, ##__VA_ARGS__)
#define ICRAFT_CHECK_GE(x, y, ...) ICRAFT_CHECK_BINARY_OP(_GE, >=, x, y, ##__VA_ARGS__)
#define ICRAFT_CHECK_EQ(x, y, ...) ICRAFT_CHECK_BINARY_OP(_EQ, ==, x, y, ##__VA_ARGS__)
#define ICRAFT_CHECK_NE(x, y, ...) ICRAFT_CHECK_BINARY_OP(_NE, !=, x, y, ##__VA_ARGS__)

#define ICRAFT_CHECK(x, ...) if (!(x)) (ICRAFT_LOG(EXCEPT, ##__VA_ARGS__) << "Check failed: (" #x ") is false\n")
