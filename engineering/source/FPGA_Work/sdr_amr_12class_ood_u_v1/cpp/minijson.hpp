// Minimal dependency-free JSON parser for the OOD-U threshold manifest.
//
// Supports objects, arrays, strings (with standard escapes), numbers (int and
// double), booleans and null.  It is intentionally small: it only needs to read
// the frozen OOD-U manifest written by the Python tooling, not arbitrary JSON.
// The parser is fail-closed — any malformed input throws std::runtime_error.
#ifndef OOD_U_MINIJSON_HPP
#define OOD_U_MINIJSON_HPP

#include <cstddef>
#include <cstdint>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace minijson {

struct Value;

using Array = std::vector<Value>;
using Object = std::map<std::string, Value>;

struct Value {
    enum class Kind { Null, Bool, Int, Double, String, Array, Object };

    Kind kind = Kind::Null;
    bool bool_value = false;
    std::int64_t int_value = 0;
    double double_value = 0.0;
    std::string string_value;
    std::shared_ptr<Array> array_value;
    std::shared_ptr<Object> object_value;

    static Value make_null() { return Value{}; }
    static Value make_bool(bool b) { Value v; v.kind = Kind::Bool; v.bool_value = b; return v; }
    static Value make_int(std::int64_t i) { Value v; v.kind = Kind::Int; v.int_value = i; v.double_value = static_cast<double>(i); return v; }
    static Value make_double(double d) { Value v; v.kind = Kind::Double; v.double_value = d; return v; }
    static Value make_string(std::string s) { Value v; v.kind = Kind::String; v.string_value = std::move(s); return v; }
    static Value make_array() { Value v; v.kind = Kind::Array; v.array_value = std::make_shared<Array>(); return v; }
    static Value make_object() { Value v; v.kind = Kind::Object; v.object_value = std::make_shared<Object>(); return v; }

    bool is_object() const { return kind == Kind::Object; }
    bool is_array() const { return kind == Kind::Array; }
    bool is_string() const { return kind == Kind::String; }
    bool is_number() const { return kind == Kind::Int || kind == Kind::Double; }
    bool is_bool() const { return kind == Kind::Bool; }

    double as_double() const {
        if (kind == Kind::Int) return static_cast<double>(int_value);
        if (kind == Kind::Double) return double_value;
        throw std::runtime_error("JSON value is not a number");
    }
    const std::string& as_string() const {
        if (kind != Kind::String) throw std::runtime_error("JSON value is not a string");
        return string_value;
    }
    bool as_bool() const {
        if (kind != Kind::Bool) throw std::runtime_error("JSON value is not a boolean");
        return bool_value;
    }
    const Array& as_array() const {
        if (kind != Kind::Array) throw std::runtime_error("JSON value is not an array");
        return *array_value;
    }
    const Object& as_object() const {
        if (kind != Kind::Object) throw std::runtime_error("JSON value is not an object");
        return *object_value;
    }
    const Value& at(const std::string& key) const {
        const Object& obj = as_object();
        auto it = obj.find(key);
        if (it == obj.end()) throw std::runtime_error("JSON object missing key: " + key);
        return it->second;
    }
    bool has(const std::string& key) const {
        return is_object() && object_value->find(key) != object_value->end();
    }
};

class Parser {
public:
    explicit Parser(const std::string& text) : text_(text) {}

    Value parse() {
        Value v = parse_value();
        skip_ws();
        if (pos_ != text_.size()) fail("trailing content after JSON value");
        return v;
    }

private:
    const std::string& text_;
    std::size_t pos_ = 0;

    [[noreturn]] void fail(const std::string& msg) const {
        throw std::runtime_error("minijson: " + msg + " at offset " + std::to_string(pos_));
    }

    void skip_ws() {
        while (pos_ < text_.size()) {
            char c = text_[pos_];
            if (c == ' ' || c == '\t' || c == '\n' || c == '\r') { ++pos_; continue; }
            break;
        }
    }

    char peek() {
        if (pos_ >= text_.size()) fail("unexpected end of input");
        return text_[pos_];
    }

    void expect(char c) {
        if (pos_ >= text_.size() || text_[pos_] != c) fail(std::string("expected '") + c + "'");
        ++pos_;
    }

    Value parse_value() {
        skip_ws();
        if (pos_ >= text_.size()) fail("unexpected end of input");
        char c = text_[pos_];
        if (c == '{') return parse_object();
        if (c == '[') return parse_array();
        if (c == '"') return Value::make_string(parse_string());
        if (c == 't' || c == 'f') return parse_bool();
        if (c == 'n') return parse_null();
        if (c == '-' || (c >= '0' && c <= '9')) return parse_number();
        fail(std::string("unexpected character '") + c + "'");
    }

    Value parse_object() {
        expect('{');
        Value v = Value::make_object();
        skip_ws();
        if (peek() == '}') { ++pos_; return v; }
        while (true) {
            skip_ws();
            std::string key = parse_string();
            skip_ws();
            expect(':');
            (*v.object_value)[key] = parse_value();
            skip_ws();
            char c = peek();
            if (c == ',') { ++pos_; continue; }
            if (c == '}') { ++pos_; return v; }
            fail("expected ',' or '}' in object");
        }
    }

    Value parse_array() {
        expect('[');
        Value v = Value::make_array();
        skip_ws();
        if (peek() == ']') { ++pos_; return v; }
        while (true) {
            v.array_value->push_back(parse_value());
            skip_ws();
            char c = peek();
            if (c == ',') { ++pos_; continue; }
            if (c == ']') { ++pos_; return v; }
            fail("expected ',' or ']' in array");
        }
    }

    static void append_utf8(std::string& out, std::uint32_t cp) {
        if (cp <= 0x7F) {
            out.push_back(static_cast<char>(cp));
        } else if (cp <= 0x7FF) {
            out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        } else if (cp <= 0xFFFF) {
            out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        } else {
            out.push_back(static_cast<char>(0xF0 | (cp >> 18)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        }
    }

    std::string parse_string() {
        expect('"');
        std::string out;
        while (true) {
            if (pos_ >= text_.size()) fail("unterminated string");
            char c = text_[pos_++];
            if (c == '"') return out;
            if (c == '\\') {
                if (pos_ >= text_.size()) fail("unterminated escape");
                char e = text_[pos_++];
                switch (e) {
                    case '"': out.push_back('"'); break;
                    case '\\': out.push_back('\\'); break;
                    case '/': out.push_back('/'); break;
                    case 'b': out.push_back('\b'); break;
                    case 'f': out.push_back('\f'); break;
                    case 'n': out.push_back('\n'); break;
                    case 'r': out.push_back('\r'); break;
                    case 't': out.push_back('\t'); break;
                    case 'u': {
                        if (pos_ + 4 > text_.size()) fail("truncated \\u escape");
                        std::uint32_t cp = 0;
                        for (int i = 0; i < 4; ++i) {
                            char h = text_[pos_++];
                            cp <<= 4;
                            if (h >= '0' && h <= '9') cp |= static_cast<std::uint32_t>(h - '0');
                            else if (h >= 'a' && h <= 'f') cp |= static_cast<std::uint32_t>(h - 'a' + 10);
                            else if (h >= 'A' && h <= 'F') cp |= static_cast<std::uint32_t>(h - 'A' + 10);
                            else fail("invalid hex digit in \\u escape");
                        }
                        if (cp >= 0xD800 && cp <= 0xDBFF && pos_ + 6 <= text_.size()
                            && text_[pos_] == '\\' && text_[pos_ + 1] == 'u') {
                            std::uint32_t lo = 0;
                            pos_ += 2;
                            for (int i = 0; i < 4; ++i) {
                                char h = text_[pos_++];
                                lo <<= 4;
                                if (h >= '0' && h <= '9') lo |= static_cast<std::uint32_t>(h - '0');
                                else if (h >= 'a' && h <= 'f') lo |= static_cast<std::uint32_t>(h - 'a' + 10);
                                else if (h >= 'A' && h <= 'F') lo |= static_cast<std::uint32_t>(h - 'A' + 10);
                                else fail("invalid hex digit in \\u surrogate");
                            }
                            if (lo >= 0xDC00 && lo <= 0xDFFF) {
                                cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                            }
                        }
                        append_utf8(out, cp);
                        break;
                    }
                    default: fail(std::string("invalid escape '\\") + e + "'");
                }
            } else {
                out.push_back(c);
            }
        }
    }

    Value parse_number() {
        std::size_t start = pos_;
        if (peek() == '-') ++pos_;
        while (pos_ < text_.size() && text_[pos_] >= '0' && text_[pos_] <= '9') ++pos_;
        bool is_double = false;
        if (pos_ < text_.size() && text_[pos_] == '.') {
            is_double = true;
            ++pos_;
            while (pos_ < text_.size() && text_[pos_] >= '0' && text_[pos_] <= '9') ++pos_;
        }
        if (pos_ < text_.size() && (text_[pos_] == 'e' || text_[pos_] == 'E')) {
            is_double = true;
            ++pos_;
            if (pos_ < text_.size() && (text_[pos_] == '+' || text_[pos_] == '-')) ++pos_;
            while (pos_ < text_.size() && text_[pos_] >= '0' && text_[pos_] <= '9') ++pos_;
        }
        std::string token = text_.substr(start, pos_ - start);
        if (token.empty() || token == "-") fail("invalid number");
        if (!is_double) {
            try {
                std::int64_t i = std::stoll(token);
                return Value::make_int(i);
            } catch (const std::exception&) {
                is_double = true;  // overflow -> parse as double
            }
        }
        try {
            double d = std::stod(token);
            return Value::make_double(d);
        } catch (const std::exception&) {
            fail("invalid number: " + token);
        }
    }

    Value parse_bool() {
        if (text_.compare(pos_, 4, "true") == 0) { pos_ += 4; return Value::make_bool(true); }
        if (text_.compare(pos_, 5, "false") == 0) { pos_ += 5; return Value::make_bool(false); }
        fail("invalid literal");
    }

    Value parse_null() {
        if (text_.compare(pos_, 4, "null") == 0) { pos_ += 4; return Value::make_null(); }
        fail("invalid literal");
    }
};

inline Value parse(const std::string& text) { return Parser(text).parse(); }

}  // namespace minijson

#endif  // OOD_U_MINIJSON_HPP
