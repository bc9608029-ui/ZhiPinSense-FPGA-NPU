#pragma once

// m24_event.hpp -- M24-A event recorder (offline).
//
// Records patrol findings / spectrum events with bounded memory and bounded
// disk use: duplicate events merge (counted), the in-memory buffer is capped,
// and the file sink rotates by byte size with a fixed number of files.  A disk
// write failure is fail-closed: record() returns false and stops claiming
// success.  No unbounded in-memory or on-disk growth.

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <functional>
#include <string>
#include <vector>

namespace m24 {

struct EventRecord {
    double time_s = 0.0;
    double center_freq_hz = 0.0;
    double power_dbfs = 0.0;
    double snr_db = 0.0;        // may be non-finite -> "approximate"/missing
    double bandwidth_hz = 0.0;
    std::string classify_status;  // NO_SIGNAL / SIGNAL_PRESENT / UNKNOWN_EXPERIMENTAL / ERROR
    std::string class_name;
    bool unknown_experimental = false;
    std::string model_id;         // e.g. "24CLASS_STUB_SIMULATED" or a frozen SHA
    std::string iq_ref;           // IQ snippet reference (file:offset:frames)
    std::uint32_t count = 1;      // number of merged duplicate occurrences
};

struct EventMergeConfig {
    double freq_tol_hz = 1000.0;
    double time_window_s = 5.0;
    bool merge_same_class = true;
};

// Pure dedup rule: merge b into a when same class (or merge_same_class off),
// frequency within tolerance and time within the window.
inline bool should_merge(const EventRecord& a, const EventRecord& b,
                         const EventMergeConfig& c) {
    if (c.merge_same_class && a.class_name != b.class_name) return false;
    if (a.unknown_experimental != b.unknown_experimental) return false;
    const double df = a.center_freq_hz - b.center_freq_hz;
    const double dt = a.time_s - b.time_s;
    return (df >= -c.freq_tol_hz && df <= c.freq_tol_hz) &&
           (dt >= -c.time_window_s && dt <= c.time_window_s);
}

// Minimal JSON string escaping (no external dependency).
inline std::string json_escape(const std::string& s) {
    std::string o;
    o.reserve(s.size() + 8);
    for (char ch : s) {
        switch (ch) {
            case '"': o += "\\\""; break;
            case '\\': o += "\\\\"; break;
            case '\n': o += "\\n"; break;
            case '\r': o += "\\r"; break;
            case '\t': o += "\\t"; break;
            default: o += ch;
        }
    }
    return o;
}

// Serialize one record to a single JSON line (no trailing newline).
inline std::string serialize_event(const EventRecord& e) {
    std::string s;
    s += "{\"time_s\":";
    s += std::to_string(e.time_s);
    s += ",\"center_freq_hz\":";
    s += std::to_string(e.center_freq_hz);
    s += ",\"power_dbfs\":";
    s += std::to_string(e.power_dbfs);
    s += ",\"snr_db\":";
    s += std::to_string(e.snr_db);
    s += ",\"bandwidth_hz\":";
    s += std::to_string(e.bandwidth_hz);
    s += ",\"classify_status\":\"";
    s += json_escape(e.classify_status);
    s += "\",\"class_name\":\"";
    s += json_escape(e.class_name);
    s += "\",\"unknown_experimental\":";
    s += e.unknown_experimental ? "true" : "false";
    s += ",\"model_id\":\"";
    s += json_escape(e.model_id);
    s += "\",\"iq_ref\":\"";
    s += json_escape(e.iq_ref);
    s += "\",\"count\":";
    s += std::to_string(e.count);
    s += "}";
    return s;
}

class EventRecorder {
public:
    void configure(std::size_t capacity, const EventMergeConfig& c) {
        capacity_ = capacity;
        merge_cfg_ = c;
        if (events_.size() > capacity_) events_.resize(capacity_);
    }

    // Sink: write one serialized line; return false on failure (fail-closed).
    void set_sink(std::function<bool(const std::string&)> sink) {
        sink_ = std::move(sink);
    }

    bool record(const EventRecord& e) {
        // Duplicate merge against the most recent event (time-ordered).
        if (!events_.empty()) {
            EventRecord& last = events_.back();
            if (should_merge(last, e, merge_cfg_)) {
                last.count += e.count ? e.count : 1;
                // refresh scalar estimates to the latest observation
                last.power_dbfs = e.power_dbfs;
                last.snr_db = e.snr_db;
                last.bandwidth_hz = e.bandwidth_hz;
                last.time_s = e.time_s;
                ++total_merged_;
                return !write_failed_;
            }
        }
        // New distinct event.
        if (capacity_ == 0) {
            ++dropped_;
            ++total_merged_;  // dropped as overflow (counted, not stored)
            return !write_failed_;
        }
        events_.push_back(e);
        if (events_.size() > capacity_) {
            events_.erase(events_.begin());  // bounded: drop oldest
            ++dropped_;
        }
        // Persist if a sink is attached.
        if (sink_) {
            const bool ok = sink_(serialize_event(e));
            if (!ok) {
                write_failed_ = true;
                return false;
            }
        }
        return true;
    }

    std::vector<EventRecord> events() const { return events_; }  // oldest-first
    std::size_t distinct() const { return events_.size(); }
    std::size_t total_merged() const { return total_merged_; }
    std::size_t dropped() const { return dropped_; }
    std::size_t capacity() const { return capacity_; }
    bool write_failed() const { return write_failed_; }

    void clear() {
        events_.clear();
        total_merged_ = 0;
        dropped_ = 0;
        write_failed_ = false;
    }

private:
    std::size_t capacity_ = 256;
    EventMergeConfig merge_cfg_;
    std::vector<EventRecord> events_;
    std::function<bool(const std::string&)> sink_;
    std::size_t total_merged_ = 0;
    std::size_t dropped_ = 0;
    bool write_failed_ = false;
};

// Rotating file sink: bounded total disk usage (max_files * max_bytes_per_file).
// Files are base_path + "." + index, index wrapping in [0, max_files).
class RotatingFileSink {
public:
    void configure(const std::string& base_path, std::size_t max_bytes_per_file,
                   std::size_t max_files) {
        close();
        base_path_ = base_path;
        max_bytes_ = max_bytes_per_file;
        max_files_ = max_files;
        file_index_ = 0;
        files_written_ = 0;
        bytes_in_current_ = 0;
    }

    bool write(const std::string& line) {
        if (base_path_.empty() || max_files_ == 0 || max_bytes_ == 0) return false;
        if (!file_.is_open() || bytes_in_current_ + line.size() + 1 > max_bytes_) {
            if (!rotate()) return false;
        }
        file_ << line << '\n';
        if (!file_.good()) return false;
        bytes_in_current_ += line.size() + 1;
        return true;
    }

    std::string current_path() const {
        return base_path_ + "." + std::to_string(file_index_);
    }

    std::size_t files_written() const { return files_written_; }
    std::size_t bytes_in_current() const { return bytes_in_current_; }

    void close() {
        if (file_.is_open()) file_.close();
    }

private:
    bool rotate() {
        if (file_.is_open()) file_.close();
        ++files_written_;
        file_index_ = files_written_ % max_files_;  // wrap -> overwrite oldest
        file_.open(current_path(), std::ios::out | std::ios::trunc);
        if (!file_.is_open()) return false;
        bytes_in_current_ = 0;
        return true;
    }

    std::string base_path_;
    std::size_t max_bytes_ = 0;
    std::size_t max_files_ = 0;
    std::size_t file_index_ = 0;
    std::size_t files_written_ = 0;
    std::size_t bytes_in_current_ = 0;
    std::ofstream file_;
};

}  // namespace m24
