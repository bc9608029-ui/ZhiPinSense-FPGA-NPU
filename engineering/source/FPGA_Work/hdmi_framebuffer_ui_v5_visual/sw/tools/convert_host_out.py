#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# convert_host_out.py — 把 host_screenshot 生成的 1280x720 BMP 转成 PNG，生成
# 1024x600 模拟缩放预览（Pillow BILINEAR，与设计稿 downscale 同法）与 HTML 画廊；
# 并对主识别页与已确认的 Style A 设计稿做程序化像素比对（含 RGB565 量化对齐），
# 佐证「像素级一致」。
import os
import numpy as np
from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
HOST = os.path.join(ROOT, 'host_out')
PNG = os.path.join(HOST, 'png')
MOCK = os.path.normpath(os.path.join(ROOT, '..', 'design_mockups', 'output', 'style_A'))

PW, PH = 1024, 600
os.makedirs(PNG, exist_ok=True)

def load_rgb(path):
    return np.asarray(Image.open(path).convert('RGB'), np.uint8)

def save_png(arr, path):
    Image.fromarray(arr).save(path)

def downscale(arr):
    return np.asarray(Image.fromarray(arr).resize((PW, PH), Image.Resampling.BILINEAR), np.uint8)

# 与板端一致的 565 -> 888 展开（5/6 位按位复制），用于把 888 设计稿对齐到 565 空间。
def to565_888(arr):
    r5 = (arr[..., 0].astype(np.uint16) >> 3)
    g6 = (arr[..., 1].astype(np.uint16) >> 2)
    b5 = (arr[..., 2].astype(np.uint16) >> 3)
    r = ((r5 << 3) | (r5 >> 2)).astype(np.uint8)
    g = ((g6 << 2) | (g6 >> 4)).astype(np.uint8)
    b = ((b5 << 3) | (b5 >> 2)).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)

def diff_report(name, a, b):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return '  %-22s mean=%.2f  max=%d' % (name, d.mean(), d.max())

def main():
    # BMP 中 565 已经由 C++ 展开为 888（bit 复制），直接读取即 565 空间的 888。
    files = sorted(os.listdir(HOST))
    bmps = [f for f in files if f.endswith('_1280.bmp')]

    page_cap = {'main': '主识别页', 'diag': 'Diagnostics', 'touch': 'Touch'}
    state_cap = {'normal': 'normal', 'lowconf': 'low-confidence', 'stale': 'stale', 'error': 'error'}

    for b in bmps:
        base = b[:-len('_1280.bmp')]
        img = load_rgb(os.path.join(HOST, b))
        save_png(img, os.path.join(PNG, base + '_1280.png'))
        save_png(downscale(img), os.path.join(PNG, base + '_1024.png'))

    # ---- 程序化比对：主识别页 normal / stale / error 与设计稿 Style A ----
    print('pixel-diff vs Style A design draft (565-space aligned):')
    for state in ['normal', 'lowconf', 'stale', 'error']:
        a = load_rgb(os.path.join(PNG, 'main_%s_1280.png' % state))
        b = to565_888(load_rgb(os.path.join(MOCK, 'main_%s_1280.png' % state)))
        print(diff_report('main_%s' % state, a, b))

    # ---- HTML 画廊 ----
    H = ['<!doctype html><html lang="zh"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width, initial-scale=1">',
         '<title>v5_visual C++ RGB565 主机截图 · Style A</title>',
         '<style>',
         'body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:#11151b;color:#e7ecf2;margin:0;padding:24px;line-height:1.6}',
         'a{color:#4a90e2}h1{font-size:26px}h2{font-size:21px;border-bottom:1px solid #2a3542;padding-bottom:6px;margin-top:36px}',
         '.note{background:#1a212b;border:1px solid #2a3542;border-radius:6px;padding:14px 18px;font-size:14px;color:#c3cdd8}',
         '.note code{background:#0f141b;padding:1px 6px;border-radius:4px;color:#e7ecf2}',
         '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}',
         'figure{margin:0;background:#1a212b;border:1px solid #2a3542;border-radius:6px;overflow:hidden}',
         'figure img{width:100%;display:block;height:auto}',
         'figcaption{font-size:12px;color:#8b98a8;padding:6px 10px}',
         '</style></head><body>',
         '<h1>v5_visual · C++ RGB565 主机截图 · Style A（现代科研仪器风）</h1>',
         '<div class="note">由 <code>host_screenshot</code>（<code>-O2 -Wall -Wextra</code> 零告警）用<b>与板端完全一致</b>的'
         ' DejaVu 抗锯齿图集 + RGB565 整数 alpha blend 渲染；本页 PNG 由 BMP 直接转出，'
         ' 1024×600 为 Pillow BILINEAR 模拟屏幕缩放（与设计稿同法）。板端由 <code>submit_frame</code> 标量写、'
         ' 双缓冲翻转，未改。状态：<b>READY-FOR-HARDWARE-VISUAL-RETEST</b>。</div>']

    for p in ['main', 'diag', 'touch']:
        H.append('<h2>%s 页 · 四态（1280×720）</h2><div class="grid">' % page_cap[p])
        for s in ['normal', 'lowconf', 'stale', 'error']:
            rel = 'png/%s_%s_1280.png' % (p, s)
            H.append('<figure><a href="%s" target="_blank"><img src="%s" loading="lazy"></a>'
                     '<figcaption>%s · %s · 1280×720</figcaption></figure>' % (rel, rel, page_cap[p], state_cap[s]))
        H.append('</div>')

    H.append('<h2>normal 的 1024×600 模拟缩放预览（判定字体平滑度）</h2><div class="grid">')
    for p in ['main', 'diag', 'touch']:
        rel = 'png/%s_normal_1024.png' % p
        H.append('<figure><a href="%s" target="_blank"><img src="%s" loading="lazy"></a>'
                 '<figcaption>%s · normal · 1024×600</figcaption></figure>' % (rel, rel, page_cap[p]))
    H.append('</div>')

    H.append('<h2>12 类目标契约 + 状态图例</h2><div class="grid">')
    rel = 'png/main_normal_12class_1280.png'
    H.append('<figure><a href="%s" target="_blank"><img src="%s" loading="lazy"></a>'
             '<figcaption>主识别页 · 12 类目标（两列卡片同版式）· 1280×720</figcaption></figure>' % (rel, rel))
    rel = 'png/legend_status_1280.png'
    H.append('<figure><a href="%s" target="_blank"><img src="%s" loading="lazy"></a>'
             '<figcaption>信号状态图例（文字+形状+颜色）</figcaption></figure>' % (rel, rel))
    H.append('</div>')

    H.append('</body></html>')
    idx = os.path.join(HOST, 'index.html')
    with open(idx, 'w', encoding='utf-8') as f:
        f.write('\n'.join(H))
    print('gallery ->', idx)
    print('pngs   ->', PNG)

if __name__ == '__main__':
    main()
