#!/usr/bin/env python3
# verify_boot_artifacts.py -- 离线解析/核验 FMQL 启动产物（.bit / BOOT.bin）。
#
# 纯只读文件解析，不写板、不烧 Flash、不加载位流。
# 运行：python verify_boot_artifacts.py <action> [args]
#
# actions:
#   bit-info <file.bit>                解析 .bit 头（设计名/part/同步字），打印并校验
#   bootbin-info <BOOT.bin>            解析 FMSH 启动镜像头（魔数/标识/加密字/内嵌镜像定位）
#   bit-in-bootbin <BOOT.bin> <file.bit>  检查 BOOT.bin 内是否内嵌与 file.bit 相同的设计名
#   sha256 <file>                      打印 SHA256
#
# 退出码：0 = 通过/完成；1 = 失败（fail-closed）；2 = 用法错误。

import hashlib
import struct
import sys


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_bit(path):
    """解析 Vivado/Procise .bit 头。返回 dict；解析失败抛 ValueError。"""
    with open(path, 'rb') as f:
        data = f.read()
    if len(data) < 32:
        raise ValueError('file too small for a .bit header')
    # 同步字 0xAA995566（文件内 BE 字节 aa 99 55 66）
    sync_be = b'\xaa\x99\x55\x66'
    sync_le = b'\x66\x55\x99\xaa'
    sync_idx = data.find(sync_be)
    if sync_idx < 0:
        sync_idx = data.find(sync_le)
    if sync_idx < 0:
        raise ValueError('no 0xAA995566 sync word found (not a .bit?)')
    # 设计名：'a' 字段内容（本工程 .bit 的 'a' 键在同步字之前，格式 00 09 0f f0*4 00 00 01 61 00 <name>）
    # 稳健做法：在同步字之前的头部里搜可打印的设计名字符串。
    head = data[:sync_idx]
    design = ''
    part = ''
    # 找 ';UserID' 或 ';Version' 结尾的设计名
    for marker in (b';UserID', b';Version'):
        mi = head.find(marker)
        if mi >= 0:
            # 从 marker 向前回溯到最近的 0x00 或不可打印字符之后
            start = mi - 1
            while start >= 0 and 32 <= head[start] < 127 and head[start] != 0:
                start -= 1
            design = head[start + 1:mi].decode('ascii', 'replace')
            break
    if not design:
        # 退而求其次：找 ';' 之前的最长可打印串
        for i in range(len(head) - 1, 0, -1):
            if head[i:i + 1] == b';':
                j = i - 1
                while j >= 0 and 32 <= head[j] < 127:
                    j -= 1
                design = head[j + 1:i].decode('ascii', 'replace')
                break
    # part 串（'b' 字段）：常见 7z030/7a030/xc7z030 等
    for p in (b'7z030', b'7a030', b'xc7z030', b'7z020', b'7z010'):
        if p in head:
            part = p.decode('ascii')
            break
    return {
        'size': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'design_name': design,
        'part': part,
        'sync_word': '0xAA995566',
        'sync_offset': sync_idx,
    }


def parse_bootbin(path):
    """解析 FMSH 启动镜像头（0xAA995566 + 'FMSH'）。返回 dict。"""
    with open(path, 'rb') as f:
        data = f.read()
    if len(data) < 0x50:
        raise ValueError('file too small for a BOOT.bin header')
    magic = data[0x20:0x24]
    ident = data[0x24:0x28]
    enc = struct.unpack_from('<I', data, 0x28)[0]
    if magic not in (b'\x66\x55\x99\xaa', b'\xaa\x99\x55\x66'):
        raise ValueError('no 0xAA995566 magic at 0x20 (not a FMSH boot image?)')
    # ident 为 'FMSH'（BE 字节序 46 4d 53 48）
    ident_str = ident.decode('latin1')
    images = {}
    for name, tok in (('FSBL', b'FSBL'), ('bl31', b'bl31'), ('u-boot', b'u-boot'),
                      ('bitstream_XLNX', b'XLNX')):
        idx = data.find(tok)
        images[name] = idx if idx >= 0 else None
    return {
        'size': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'magic': magic.hex(),
        'ident': ident_str,
        'encryption_word': '0x%08X' % enc,
        'encrypted': bool(enc != 0),
        'image_markers': images,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    action = sys.argv[1]
    try:
        if action == 'sha256':
            print(sha256_file(sys.argv[2]))
            return 0
        if action == 'bit-info':
            r = parse_bit(sys.argv[2])
            print('size=%d' % r['size'])
            print('sha256=%s' % r['sha256'])
            print('design_name=%s' % r['design_name'])
            print('part=%s' % r['part'])
            print('sync_word=%s @%d' % (r['sync_word'], r['sync_offset']))
            if not r['design_name'] or not r['part']:
                print('BIT_INFO: FAIL (could not extract design_name/part)')
                return 1
            print('BIT_INFO: OK')
            return 0
        if action == 'bootbin-info':
            r = parse_bootbin(sys.argv[2])
            print('size=%d' % r['size'])
            print('sha256=%s' % r['sha256'])
            print('magic=%s' % r['magic'])
            print('ident=%s' % r['ident'])
            print('encryption_word=%s encrypted=%s' % (r['encryption_word'], r['encrypted']))
            for k, v in r['image_markers'].items():
                print('marker %s @ %s' % (k, v if v is not None else 'ABSENT'))
            if r['ident'] not in ('FMSH', 'HSMF'):
                print('BOOTBIN_INFO: FAIL (ident not FMSH)')
                return 1
            if r['encrypted']:
                print('BOOTBIN_INFO: NOTE encrypted image (secure boot?)')
            print('BOOTBIN_INFO: OK')
            return 0
        if action == 'bit-in-bootbin':
            bb = sys.argv[2]
            bit = sys.argv[3]
            binfo = parse_bootbin(bb)
            b = parse_bit(bit)
            with open(bb, 'rb') as f:
                blob = f.read()
            present = (b['design_name'].encode('ascii', 'replace') in blob)
            print('bootbin_sha256=%s' % binfo['sha256'])
            print('bit_design_name=%s' % b['design_name'])
            print('design_name_in_bootbin=%s' % present)
            if present:
                print('BIT_IN_BOOTBIN: OK (design name embedded)')
                return 0
            print('BIT_IN_BOOTBIN: FAIL (design name NOT found; different/absent bitstream)')
            return 1
    except (ValueError, OSError, IndexError) as e:
        print('FAIL %s' % e)
        return 1
    print('unknown action: %s' % action)
    return 2


if __name__ == '__main__':
    sys.exit(main())
