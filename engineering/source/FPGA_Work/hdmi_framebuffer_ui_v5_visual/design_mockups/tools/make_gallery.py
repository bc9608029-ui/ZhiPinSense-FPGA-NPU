#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# make_gallery.py — 生成 design_mockups/index.html 静态画廊，便于逐套风格审阅。

import os
import make_mockups as mm

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OUT = os.path.join(ROOT, 'output')

STYLE_NAME = {'A': '现代科研仪器风（推荐）', 'B': '比赛展示风', 'C': '浅色实验仪器风'}
STYLE_DESC = {
    'A': '中性深灰蓝底 + 少量蓝，清晰卡片层级，克制的语义色。适合长时间观察、工程/科研场合。',
    'B': '识别结果卡片更醒目，配色更饱和但仍非霓虹。适合比赛展示，重点突出 top-1。',
    'C': '浅色高对比，强环境光下可读。适合户外/展位强光、或偏好浅色的场合。',
}
STATE_NAME = {'normal': 'normal', 'lowconf': 'low-confidence', 'stale': 'stale', 'error': 'error'}
PAGE_NAME = {'main': '主识别页', 'diag': 'Diagnostics', 'touch': 'Touch'}

def hexc(rgb):
    return '#%02X%02X%02X' % tuple(rgb)

def palette_html(pal):
    rows = [('background', pal['bg']), ('surface', pal['surface']),
            ('textPrimary', pal['text']), ('textSecondary', pal['dim']),
            ('primary', pal['primary']), ('success', pal['success']),
            ('warning', pal['warning']), ('error', pal['error']),
            ('outline', pal['outline'])]
    s = ['<div class="palette">']
    for role, c in rows:
        s.append('<div class="sw"><span class="chip" style="background:%s"></span>'
                 '<code>%s</code> <span class="role">%s</span></div>' % (hexc(c), hexc(c), role))
    s.append('</div>')
    return ''.join(s)

def figure(rel, cap, w=''):
    return ('<figure class="%s"><a href="%s" target="_blank"><img src="%s" loading="lazy"></a>'
            '<figcaption>%s</figcaption></figure>' % (w, rel, rel, cap))

def build():
    pages = ['main', 'diag', 'touch']
    states = ['normal', 'lowconf', 'stale', 'error']
    H = []
    H.append('<!doctype html><html lang="zh"><head><meta charset="utf-8">')
    H.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    H.append('<title>v5_visual 静态设计稿 · 3 套风格</title>')
    H.append('<style>')
    H.append('body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:#11151b;color:#e7ecf2;margin:0;padding:24px;line-height:1.6}')
    H.append('a{color:#4a90e2}h1{font-size:26px}h2{font-size:21px;border-bottom:1px solid #2a3542;padding-bottom:6px;margin-top:40px}')
    H.append('h3{font-size:16px;color:#8b98a8;text-transform:uppercase;letter-spacing:.05em;margin-top:24px}')
    H.append('.note{background:#1a212b;border:1px solid #2a3542;border-radius:6px;padding:14px 18px;font-size:14px;color:#c3cdd8}')
    H.append('.note code{background:#0f141b;padding:1px 6px;border-radius:4px;color:#e7ecf2}')
    H.append('.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}')
    H.append('figure{margin:0;background:#1a212b;border:1px solid #2a3542;border-radius:6px;overflow:hidden}')
    H.append('figure img{width:100%;display:block;height:auto}')
    H.append('figcaption{font-size:12px;color:#8b98a8;padding:6px 10px}')
    H.append('.palette{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}')
    H.append('.sw{display:flex;align-items:center;gap:6px;background:#1a212b;border:1px solid #2a3542;border-radius:5px;padding:4px 8px;font-size:12px}')
    H.append('.chip{width:16px;height:16px;border-radius:3px;display:inline-block;border:1px solid #00000033}')
    H.append('.role{color:#8b98a8}')
    H.append('code{color:#c3cdd8}')
    H.append('.full{grid-column:1/-1}')
    H.append('</style></head><body>')
    H.append('<h1>v5_visual 静态设计稿 · 3 套风格</h1>')
    H.append('<div class="note"><b>状态：DESIGN-DRAFT-ONLY</b> — 尚未进入 C++ 实现。请逐套审阅，确认其中一套后我才会'
             '写像素级一致的 RGB565 版本，且在此之前不改 <code>hdmi_framebuffer_ui_v4_fix/sw</code> 的 Phase2/Phase3 代码。</div>')

    H.append('<h2>全局设计约束（三套通用）</h2>')
    H.append('<div class="note">')
    H.append('<b>字体</b>：DejaVu Sans（Bitstream Vera 许可，许可随包保留）电脑端预栅格化为 8-bit 灰度覆盖率，'
             '板端只做 RGB565 整数 alpha blend，<b>禁止运行时缩放 5×7</b>；固定字号 <code>20 / 28 / 40 / 52 px</code>。')
    H.append('<br><b>字号（1280×720 → 屏幕 1024×600，约 0.80/0.83 倍）</b>：正文 20→16px、次要数据 28→23px、'
             '主要数据 40→32px、识别结果 52→42px（满足正文≥16 / 主要数据≥24 / 结果 36–48）。')
    H.append('<br><b>网格</b>：水平 5px、垂直 6px 对齐（5→4、6→5 的整数缩放，避免发糊）。')
    H.append('<br><b>信息层级（主识别页自上而下）</b>：①识别结果/置信度/信号状态 → ②10/12 类概率（两列卡片）→ '
             '③SNR/延迟/帧号/数据源 → ④延迟分解+详细计数移到 Diagnostics 页。')
    H.append('<br><b>触摸</b>：底部导航原始高 90px（→75px 物理），命中区 ≥60px 物理。')
    H.append('<br><b>状态</b>：MOCK / LIVE / STALE / ERROR 一律「文字 + 形状 + 颜色」三通道表达，不靠颜色区分。')
    H.append('<br><b>对比度</b>：所有文字 ≥ 4.5:1（WCAG）。')
    H.append('</div>')

    # 每套风格
    for sn in ['A', 'B', 'C']:
        pal = mm.PALETTES[sn]
        d = 'output/style_%s' % sn
        H.append('<h2>Style %s — %s</h2>' % (sn, STYLE_NAME[sn]))
        H.append('<div class="note">%s</div>' % STYLE_DESC[sn])
        H.append('<h3>语义配色</h3>')
        H.append(palette_html(pal))
        H.append('<h3>主识别页 · 四态（1280×720 原始）</h3><div class="grid">')
        for st in states:
            H.append(figure('%s/main_%s_1280.png' % (d, st), '%s' % STATE_NAME[st]))
        H.append('</div>')
        H.append('<h3>主识别页 · normal 的 1024×600 模拟缩放预览（判定字体平滑度）</h3><div class="grid">')
        H.append(figure('%s/main_normal_1024.png' % d, 'main · normal · 1024×600'))
        H.append(figure('%s/legend_status.png' % d, '信号状态图例（4 值：文字+形状+颜色）'))
        H.append('</div>')
        H.append('<h3>Diagnostics 页 + Touch 页（1280×720，normal 态）</h3><div class="grid">')
        H.append(figure('%s/diag_normal_1280.png' % d, 'Diagnostics · normal'))
        H.append(figure('%s/touch_normal_1280.png' % d, 'Touch · normal'))
        H.append('</div>')

    # 对比
    H.append('<h2>新旧并排对比</h2>')
    H.append('<div class="note">左 = v4_fix 旧界面（5×7 点阵，scale=2/3）；右 = 本稿抗锯齿字体图集。'
             '点开 1024×600 对比可直观看出斜线/圆弧/数字的平滑差异。</div>')
    H.append('<div class="grid">')
    for sn in ['A', 'B', 'C']:
        H.append(figure('output/comparison/old_vs_%s_1024.png' % sn, 'OLD vs Style %s（1024×600）' % sn, 'full'))
    H.append('</div>')
    H.append('<h3>1280×720 原始对比</h3><div class="grid">')
    for sn in ['A', 'B', 'C']:
        H.append(figure('output/comparison/old_vs_%s_1280.png' % sn, 'OLD vs Style %s（1280×720）' % sn, 'full'))
    H.append('</div>')

    H.append('<h2>文件清单</h2><div class="note">')
    H.append('每套 24 张：<code>output/style_*/{main,diag,touch}_{normal,lowconf,stale,error}_{1280,1024}.png</code>；'
             '另加 <code>legend_status.png</code>；对比 <code>output/comparison/</code>；生成器 <code>tools/make_mockups.py</code>。')
    H.append('</div>')
    H.append('</body></html>')

    idx = os.path.join(ROOT, 'index.html')
    with open(idx, 'w', encoding='utf-8') as f:
        f.write('\n'.join(H))
    print('gallery ->', idx)

if __name__ == '__main__':
    build()
