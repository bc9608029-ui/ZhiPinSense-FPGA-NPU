#!/usr/bin/env python3
"""PL-DDR 板级测试的输入转换 + Golden 比较工具。

两个功能：
  1) iq_input.hex  ->  iq_input.bin
        .hex 每行 8 个十六进制字符 = 一个 32-bit IQ word，布局 {Q[15:0], I[15:0]}。
        依据 iq_beat_unpacker.sv: iq_i = word[15:0], iq_q = word[31:16]。
        写入 DDR 为小端（ARM），故每个 word 按 '<I' 打包 4 字节。
        19456 word = 19 帧 x 1024 采样 = 77824 B（= EXPECTED_IQ_BYTES）。

  2) tensor_output.bin  vs  expected_tensor_plddr.hex
        .hex 每行 2 个十六进制字符 = 1 字节 SInt8（97280 行 = 97280 B）。
        tensor 布局（tensor_plane_beat_packer.sv，channel-major，每帧 5120 B）：
            plane 0 I           offset 0    (1024 B)
            plane 1 Q           offset 1024
            plane 2 power       offset 2048
            plane 3 lag1_real   offset 3072
            plane 4 lag1_imag   offset 4096
        97280 B = 19 帧 x 5 plane x 1024 = EXPECTED_TENSOR_BYTES。
        逐字节比对，并定位到 (frame, plane, sample)。

用法：
  python tensor_golden_compare.py iq_input.hex iq_input.bin
  python tensor_golden_compare.py tensor_output.bin expected_tensor_plddr.hex
（脚本按输入文件扩展名自动判断是哪种模式；也可显式 --mode iq|tensor）
"""
import sys
import struct

FRAME_LENGTH = 1024
PLANES = 5
FRAME_BYTES = PLANES * FRAME_LENGTH          # 5120
PLANE_NAMES = ("I", "Q", "power", "lag1_real", "lag1_imag")


def hex_lines_to_bytes(path):
    """读取文本 .hex（每行一个十六进制数），返回 int 列表。"""
    out = []
    with open(path, "r", encoding="ascii") as f:
        for line in f:
            t = line.strip()
            if not t or t.startswith("//") or t.startswith("#"):
                continue
            out.append(int(t, 16))
    return out


def convert_iq(hex_path, bin_path):
    words = hex_lines_to_bytes(hex_path)
    assert len(words) == 19 * FRAME_LENGTH, \
        f"iq word 数应 19456，实为 {len(words)}"
    payload = b"".join(struct.pack("<I", w & 0xFFFFFFFF) for w in words)
    assert len(payload) == 77824
    with open(bin_path, "wb") as f:
        f.write(payload)
    print(f"[iq] {hex_path} -> {bin_path}: {len(words)} words / {len(payload)} B")


def compare_tensor(bin_path, hex_path):
    golden = hex_lines_to_bytes(hex_path)
    assert len(golden) == 97280, f"golden 字节数应 97280，实为 {len(golden)}"
    with open(bin_path, "rb") as f:
        got = f.read()
    assert len(got) == 97280, f"输出字节数应 97280，实为 {len(got)}"

    mismatches = []
    for i, (g, v) in enumerate(zip(golden, got)):
        if g != v:
            frame = i // FRAME_BYTES
            rem = i % FRAME_BYTES
            plane = rem // FRAME_LENGTH
            sample = rem % FRAME_LENGTH
            mismatches.append((i, frame, PLANE_NAMES[plane], sample, g, v))

    print(f"[tensor] golden={hex_path}  output={bin_path}")
    print(f"        总字节={len(golden)}  mismatch={len(mismatches)}")
    if mismatches:
        for m in mismatches[:20]:
            i, frame, plane, sample, g, v = m
            print(f"        off={i:6d} frame={frame:2d} {plane:9s}[{sample:4d}] "
                  f"golden=0x{g:02x} got=0x{v:02x}")
        if len(mismatches) > 20:
            print(f"        ... 共 {len(mismatches)} 处")
        return 1
    print("        GOLDEN_MATCH")
    return 0


def main(argv):
    if "--mode" in argv:
        i = argv.index("--mode")
        mode = argv[i + 1]
        args = [a for j, a in enumerate(argv) if j not in (i, i + 1)]
    else:
        a, b = argv[1], argv[2]
        mode = "iq" if a.endswith(".hex") and b.endswith(".bin") else "tensor"
        args = [a, b]

    if mode == "iq":
        convert_iq(args[0], args[1])
        return 0
    if mode == "tensor":
        return compare_tensor(args[0], args[1])
    raise SystemExit("未知 mode（应为 iq|tensor）")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv))
