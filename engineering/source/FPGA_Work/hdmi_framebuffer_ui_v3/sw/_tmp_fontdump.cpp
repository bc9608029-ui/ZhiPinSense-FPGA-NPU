#include "font.hpp"
#include <cstdio>
int main() {
    const char* chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_:.%/+><()";
    for (const char* p = chars; *p; ++p) {
        font::Glyph g = font::glyph(*p);
        std::printf("[%c]\n", *p);
        for (int r = 0; r < 8; ++r) {
            unsigned char b = g.rows[r];
            for (int c = 0; c < 8; ++c) { std::putchar(b & 0x80 ? (unsigned char)"#"[(0)] : (unsigned char)"."[(0)]); b <<= 1; }
            std::putchar((unsigned char)"\n"[(0)]);
        }
    }
    return 0;
}
