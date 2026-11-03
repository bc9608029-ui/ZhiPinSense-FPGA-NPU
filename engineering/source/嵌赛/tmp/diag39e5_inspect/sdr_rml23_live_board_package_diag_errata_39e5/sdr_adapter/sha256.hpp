#pragma once

// sha256.hpp -- header-only SHA-256 (FIPS 180-4) for the Gate 10 dump-error
// manifest (M17 Task C).  The M17 dump writes a SHA256SUMS sidecar that
// fingerprints the manifest.tsv and every error_*.bin tensor, so the board run
// can be audited off-line for exactly which misclassified frames were captured.
//
// iCraft-free, libiio-free, header-only, deterministic, C++17.
// Verified against the FIPS 180-4 test vectors (see sha256_self_test()).

#include <cstdint>
#include <cstdio>
#include <string>

namespace sdr {

class Sha256 {
public:
    Sha256() { reset(); }

    void reset() {
        h_[0] = 0x6a09e667u; h_[1] = 0xbb67ae85u; h_[2] = 0x3c6ef372u;
        h_[3] = 0xa54ff53au; h_[4] = 0x510e527fu; h_[5] = 0x9b05688cu;
        h_[6] = 0x1f83d9abu; h_[7] = 0x5be0cd19u;
        total_len_ = 0;
        buf_len_ = 0;
    }

    void update(const std::uint8_t* data, std::size_t len) {
        total_len_ += static_cast<std::uint64_t>(len);
        while (len > 0) {
            const std::size_t room = 64 - buf_len_;
            const std::size_t take = (len < room) ? len : room;
            for (std::size_t i = 0; i < take; ++i) buf_[buf_len_ + i] = data[i];
            buf_len_ += take;
            data += take;
            len -= take;
            if (buf_len_ == 64) {
                process_block(buf_);
                buf_len_ = 0;
            }
        }
    }

    void update(const std::string& s) {
        update(reinterpret_cast<const std::uint8_t*>(s.data()), s.size());
    }

    // Finalize into `out[32]`.  Reusable (a later update() restarts cleanly).
    void finalize(std::uint8_t out[32]) {
        const std::uint64_t bit_len = total_len_ * 8u;
        const std::uint8_t pad = 0x80u;
        const std::uint8_t zero = 0x00u;
        update(&pad, 1);
        while (buf_len_ != 56) update(&zero, 1);
        std::uint8_t len_be[8];
        for (int i = 0; i < 8; ++i)
            len_be[i] = static_cast<std::uint8_t>(bit_len >> (56 - 8 * i));
        update(len_be, 8);
        for (int i = 0; i < 8; ++i)
            out[i * 4 + 0] = static_cast<std::uint8_t>(h_[i] >> 24);
        for (int i = 0; i < 8; ++i) {
            out[i * 4 + 1] = static_cast<std::uint8_t>(h_[i] >> 16);
            out[i * 4 + 2] = static_cast<std::uint8_t>(h_[i] >> 8);
            out[i * 4 + 3] = static_cast<std::uint8_t>(h_[i]);
        }
        reset();
    }

    // One-shot hex digest of a byte range.
    static std::string hex(const void* data, std::size_t len) {
        Sha256 h;
        h.update(reinterpret_cast<const std::uint8_t*>(data), len);
        std::uint8_t d[32];
        h.finalize(d);
        return to_hex(d, 32);
    }

    static std::string hex(const std::string& s) {
        return hex(s.data(), s.size());
    }

    static std::string to_hex(const std::uint8_t* d, std::size_t n) {
        static const char* hexdig = "0123456789abcdef";
        std::string s;
        s.reserve(n * 2);
        for (std::size_t i = 0; i < n; ++i) {
            s += hexdig[d[i] >> 4];
            s += hexdig[d[i] & 0x0f];
        }
        return s;
    }

private:
    static std::uint32_t rotr(std::uint32_t x, std::uint32_t n) {
        return (x >> n) | (x << (32 - n));
    }

    void process_block(const std::uint8_t* p) {
        static const std::uint32_t K[64] = {
            0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
            0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
            0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
            0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
            0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
            0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
            0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
            0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
            0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
            0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
            0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
            0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
            0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
            0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
            0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
            0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u};

        std::uint32_t w[64];
        for (int i = 0; i < 16; ++i)
            w[i] = (static_cast<std::uint32_t>(p[i * 4 + 0]) << 24) |
                   (static_cast<std::uint32_t>(p[i * 4 + 1]) << 16) |
                   (static_cast<std::uint32_t>(p[i * 4 + 2]) << 8) |
                   (static_cast<std::uint32_t>(p[i * 4 + 3]));
        for (int i = 16; i < 64; ++i) {
            const std::uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^
                                     (w[i - 15] >> 3);
            const std::uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^
                                     (w[i - 2] >> 10);
            w[i] = w[i - 16] + s0 + w[i - 7] + s1;
        }

        std::uint32_t a = h_[0], b = h_[1], c = h_[2], d = h_[3];
        std::uint32_t e = h_[4], f = h_[5], g = h_[6], h = h_[7];

        for (int i = 0; i < 64; ++i) {
            const std::uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
            const std::uint32_t ch = (e & f) ^ ((~e) & g);
            const std::uint32_t t1 = h + S1 + ch + K[i] + w[i];
            const std::uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
            const std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
            const std::uint32_t t2 = S0 + maj;
            h = g; g = f; f = e; e = d + t1;
            d = c; c = b; b = a; a = t1 + t2;
        }

        h_[0] += a; h_[1] += b; h_[2] += c; h_[3] += d;
        h_[4] += e; h_[5] += f; h_[6] += g; h_[7] += h;
    }

    std::uint32_t h_[8];
    std::uint64_t total_len_;
    std::uint8_t buf_[64];
    std::size_t buf_len_;
};

// SHA-256 hex digest of a whole file.  Returns "" and sets *ok = false on any
// read error (the caller fails closed).  `ok` may be null.
inline std::string sha256_hex_file(const std::string& path, bool* ok = nullptr) {
    if (ok) *ok = true;
    std::FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) {
        if (ok) *ok = false;
        return "";
    }
    Sha256 h;
    std::uint8_t buf[8192];
    std::size_t n;
    while ((n = std::fread(buf, 1, sizeof buf, f)) > 0) h.update(buf, n);
    const bool read_ok = !std::ferror(f);
    std::fclose(f);
    if (!read_ok) {
        if (ok) *ok = false;
        return "";
    }
    std::uint8_t d[32];
    h.finalize(d);
    return Sha256::to_hex(d, 32);
}

// Self-test against the FIPS 180-4 known-answer vectors.  Returns true when the
// implementation is byte-exact.
inline bool sha256_self_test() {
    struct Vec {
        const char* in;
        const char* want;
    };
    static const Vec k[] = {
        {"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
        {"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"},
        {"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
         "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"}};
    for (const Vec& v : k) {
        if (Sha256::hex(v.in) != v.want) return false;
    }
    return true;
}

}  // namespace sdr
