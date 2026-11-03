#pragma once

// resource_snapshot.hpp — M22 runtime-baseline process-resource sampling
// (task 39e5 M22 §三): RSS / VM / file-descriptor count / thread count / CPU
// time, plus the JSON the baseline report needs.  The FD count and RSS are the
// leak detectors (§六: FD stable, RSS no growth, no device reopen).
//
// Linux-only (/proc + getrusage); on a non-Linux host every field is 0 and
// is_supported() is false, so the host unit test can still exercise the JSON
// and leak-detection logic with synthetic samples.  Header-only, iCraft-free.

#include <cstdint>
#include <cstdio>
#include <string>

#if defined(__linux__)
#include <dirent.h>
#include <sys/resource.h>
#include <cstring>
#endif

namespace m22 {

struct ResourceSample {
    long rss_kb = 0;         // current resident set (VmRSS)
    long vm_kb = 0;          // virtual size (VmSize)
    long fd_count = 0;       // open file descriptors (count of /proc/self/fd)
    long thread_count = 0;   // native threads (Threads:)
    double cpu_seconds = 0.0;// utime + stime via getrusage

    // Deterministic one-line JSON object.  Allocate-safe (outside hot path).
    std::string json() const {
        char b[256];
        std::snprintf(b, sizeof(b),
                      "{\"rss_kb\":%ld,\"vm_kb\":%ld,\"fd_count\":%ld,"
                      "\"thread_count\":%ld,\"cpu_seconds\":%.3f}",
                      rss_kb, vm_kb, fd_count, thread_count, cpu_seconds);
        return std::string(b);
    }
};

inline bool resource_sampling_supported() {
#if defined(__linux__)
    return true;
#else
    return false;
#endif
}

// Read one resource sample for THIS process.  Never throws: any field it cannot
// read is left at 0 (the caller reports the sample with a 实测/UNKNOWN tag).
inline ResourceSample read_resources() {
    ResourceSample s;
#if defined(__linux__)
    // RSS + VM + thread count from /proc/self/status (stable across kernels).
    FILE* f = std::fopen("/proc/self/status", "r");
    if (f) {
        char line[256];
        while (std::fgets(line, sizeof(line), f)) {
            if (std::strncmp(line, "VmRSS:", 6) == 0)
                s.rss_kb = std::atol(line + 6);
            else if (std::strncmp(line, "VmSize:", 7) == 0)
                s.vm_kb = std::atol(line + 7);
            else if (std::strncmp(line, "Threads:", 8) == 0)
                s.thread_count = std::atol(line + 8);
        }
        std::fclose(f);
    }

    // FD count = number of directory entries in /proc/self/fd (minus . and ..).
    DIR* d = ::opendir("/proc/self/fd");
    if (d) {
        long n = 0;
        while (::readdir(d)) ++n;
        ::closedir(d);
        s.fd_count = (n > 2) ? (n - 2) : 0;
    }

    // CPU time via getrusage (avoids parsing /proc/self/stat's comm field).
    struct rusage ru;
    if (::getrusage(RUSAGE_SELF, &ru) == 0) {
        s.cpu_seconds =
            static_cast<double>(ru.ru_utime.tv_sec) + ru.ru_utime.tv_usec / 1e6 +
            static_cast<double>(ru.ru_stime.tv_sec) + ru.ru_stime.tv_usec / 1e6;
    }
#endif
    return s;
}

}  // namespace m22
