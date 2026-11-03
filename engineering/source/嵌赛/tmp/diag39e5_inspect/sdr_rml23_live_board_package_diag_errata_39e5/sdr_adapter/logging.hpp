#pragma once

// Minimal leveled logger for the non-model system layer.
//
// Writes timestamped "[LEVEL] message" lines to stderr and, when a file path is
// set, appends the same line to that file.  Levels are Trace < Info < Warn <
// Error < Off.  The pipeline is single-threaded today, so no mutex is used.
//
// iCraft-free and header-only; unit-tested via the log_level filter and file
// append path.

#include <cstdarg>
#include <cstdio>
#include <string>

namespace logx {

enum class Level { Trace = 0, Info = 1, Warn = 2, Error = 3, Off = 4 };

class Logger {
public:
    static Logger& instance() {
        static Logger l;
        return l;
    }

    void set_level(Level l) { level_ = l; }
    void set_file(const std::string& path) { path_ = path; }
    Level level() const { return level_; }

    void log(Level lv, const char* fmt, ...) {
        if (static_cast<int>(lv) < static_cast<int>(level_)) return;
        char buf[2048];
        va_list ap;
        va_start(ap, fmt);
        std::vsnprintf(buf, sizeof(buf), fmt, ap);
        va_end(ap);

        const char* tag = tag_of(lv);
        std::fprintf(stderr, "[%s] %s\n", tag, buf);
        if (!path_.empty()) {
            FILE* f = std::fopen(path_.c_str(), "a");
            if (f) {
                std::fprintf(f, "[%s] %s\n", tag, buf);
                std::fclose(f);
            }
        }
    }

private:
    Logger() = default;

    static const char* tag_of(Level lv) {
        switch (lv) {
            case Level::Trace: return "TRACE";
            case Level::Info:  return "INFO";
            case Level::Warn:  return "WARN";
            case Level::Error: return "ERROR";
            default:           return "OFF";
        }
    }

    Level level_ = Level::Info;
    std::string path_;
};

}  // namespace logx

#define LOG_TRACE(...) logx::Logger::instance().log(logx::Level::Trace, __VA_ARGS__)
#define LOG_INFO(...)  logx::Logger::instance().log(logx::Level::Info,  __VA_ARGS__)
#define LOG_WARN(...)  logx::Logger::instance().log(logx::Level::Warn,  __VA_ARGS__)
#define LOG_ERROR(...) logx::Logger::instance().log(logx::Level::Error, __VA_ARGS__)
