#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# make_mockups.py — v5_visual 静态设计稿生成器
#
# 从 v4_fix 的 5x7 点阵 UI 出发，用真正抗锯齿的 DejaVu 字体图集（8-bit 灰度覆盖率，
# RGB 整数 alpha blend，与后续板端 C++ RGB565 渲染同一套数学），生成 3 套风格的静态
# 设计稿。每一套都含：主识别页 / Diagnostics / Touch 三页 × normal / low-confidence /
# stale / error 四态 × 1280x720 原始 + 1024x600 模拟缩放预览，另加新旧对比与状态图例。
#
# 只生成图片与 README，不触碰任何 Phase2/Phase3 正式代码。

import os
import numpy as np
from PIL import Image, ImageFont, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, '..'))
FONT_DIR = os.path.join(ROOT, 'assets', 'fonts')
OUT = os.path.join(ROOT, 'output')

W, H = 1280, 720
PW, PH = 1024, 600

FONT_PATHS = {
    'r': 'DejaVuSans.ttf',        # regular
    'b': 'DejaVuSans-Bold.ttf',   # bold
    'm': 'DejaVuSansMono.ttf',    # mono (numbers / tabular)
}

# ---- 字体图集（8-bit 灰度覆盖率） -------------------------------------------
class FontAtlas:
    def __init__(self, path, size):
        self.f = ImageFont.truetype(path, size)
        self.ascent, self.descent = self.f.getmetrics()
        self.line_h = self.ascent + self.descent
        self.size = size
        self.glyphs = {}
        self.space = int(round(self.f.getlength(' '))) + 1

    def glyph(self, ch):
        if ch not in self.glyphs:
            adv = max(1, int(round(self.f.getlength(ch))) + 1)
            img = Image.new('L', (adv, self.line_h), 0)
            d = ImageDraw.Draw(img)
            d.text((0, self.ascent), ch, font=self.f, fill=255, anchor='ls')
            self.glyphs[ch] = (np.asarray(img, np.uint8), adv)
        return self.glyphs[ch]

_font_cache = {}
def F(weight, size):
    key = (weight, size)
    if key not in _font_cache:
        _font_cache[key] = FontAtlas(os.path.join(FONT_DIR, FONT_PATHS[weight]), size)
    return _font_cache[key]

def text_width(s, a, spacing=0):
    w = 0
    for ch in s:
        w += a.glyph(ch)[1]
        w += spacing
    if s:
        w -= spacing
    return w

# ---- 画布与形状 ------------------------------------------------------------
def canvas(color):
    c = np.empty((H, W, 3), dtype=np.uint8)
    c[:] = np.array(color, np.uint8)
    return c

def fill_rect(c, x0, y0, x1, y1, color):
    x0 = max(0, int(x0)); y0 = max(0, int(y0))
    x1 = min(W - 1, int(x1)); y1 = min(H - 1, int(y1))
    if x0 > x1 or y0 > y1:
        return
    c[y0:y1 + 1, x0:x1 + 1] = np.array(color, np.uint8)

def outline_rect(c, x0, y0, x1, y1, color, t=1):
    fill_rect(c, x0, y0, x1, y0 + t - 1, color)
    fill_rect(c, x0, y1 - t + 1, x1, y1, color)
    fill_rect(c, x0, y0, x0 + t - 1, y1, color)
    fill_rect(c, x1 - t + 1, y0, x1, y1, color)

def _mask_blit(c, cx, cy, mask, color):
    mh, mw = mask.shape
    x0 = cx - mw // 2; y0 = cy - mh // 2
    x1 = x0 + mw; y1 = y0 + mh
    bx0 = max(0, x0); by0 = max(0, y0)
    bx1 = min(W, x1); by1 = min(H, y1)
    if bx0 >= bx1 or by0 >= by1:
        return
    sub = mask[by0 - y0:by1 - y0, bx0 - x0:bx1 - x0]
    c[by0:by1, bx0:bx1][sub] = np.array(color, np.uint8)

def fill_circle(c, cx, cy, r, color):
    s = 2 * r + 1
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    _mask_blit(c, cx, cy, (xx * xx + yy * yy <= r * r), color)

def fill_diamond(c, cx, cy, r, color):
    s = 2 * r + 1
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    _mask_blit(c, cx, cy, (np.abs(xx) + np.abs(yy) <= r), color)

def fill_triangle(c, cx, cy, r, color):
    # 正三角形（尖朝上）
    s = 2 * r + 1
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    m = (yy <= r) & (np.abs(xx) <= (r - yy) * 1.0 / 2 + 0.01) & (yy >= -r)
    _mask_blit(c, cx, cy, m, color)

def fill_square(c, cx, cy, r, color, hollow=False):
    if hollow:
        outline_rect(c, cx - r, cy - r, cx + r, cy + r, color, max(1, r // 3))
    else:
        fill_rect(c, cx - r, cy - r, cx + r, cy + r, color)

# ---- 文字（从图集做整数 alpha blend） -------------------------------------
def draw_text(c, s, x, y, color, a, spacing=0):
    """在基线 (x, y) 处绘制。返回文字末端的 x。"""
    col = np.array(color, np.uint8)
    px = int(x)
    for ch in s:
        cov, adv = a.glyph(ch)
        gh, gw = cov.shape
        tx, ty = px, int(y) - a.ascent
        x0 = max(0, tx); y0 = max(0, ty)
        x1 = min(W, tx + gw); y1 = min(H, ty + gh)
        if x0 < x1 and y0 < y1:
            sub = cov[y0 - ty:y1 - ty, x0 - tx:x1 - tx]
            aa = sub[:, :, None].astype(np.uint16)
            region = c[y0:y1, x0:x1].astype(np.uint16)
            c[y0:y1, x0:x1] = ((region * (255 - aa) + col * aa + 127) // 255).astype(np.uint8)
        px += adv + spacing
    return px

def draw_text_right(c, s, x_right, y, color, a, spacing=0):
    w = text_width(s, a, spacing)
    draw_text(c, s, x_right - w, y, color, a, spacing)

def draw_text_center(c, s, xc, y, color, a, spacing=0):
    w = text_width(s, a, spacing)
    draw_text(c, s, xc - w // 2, y, color, a, spacing)

# ---- 调色板（克制的语义色，详见 README） -----------------------------------
# 每色有 (r,g,b)；status 色含文字色 + 形状色 + 底(用于 chip)。
PALETTES = {
    'A': dict(  # 现代科研仪器风（推荐）：中性深灰蓝 + 少量蓝
        bg=(15, 20, 27), surface=(26, 33, 43), surface_alt=(18, 25, 36),
        text=(231, 236, 242), dim=(139, 152, 168),
        primary=(74, 144, 226), success=(61, 220, 132),
        warning=(232, 169, 60), error=(229, 96, 95),
        outline=(42, 53, 66), accent_bar_bg=(20, 27, 37),
    ),
    'B': dict(  # 比赛展示风：结果更醒目，但不霓虹
        bg=(13, 21, 38), surface=(23, 36, 58), surface_alt=(17, 27, 46),
        text=(242, 245, 250), dim=(147, 162, 184),
        primary=(61, 139, 255), success=(56, 212, 122),
        warning=(242, 179, 61), error=(240, 101, 94),
        outline=(46, 61, 87), accent_bar_bg=(20, 32, 52),
    ),
    'C': dict(  # 浅色实验仪器风：高环境光可读
        bg=(239, 242, 246), surface=(255, 255, 255), surface_alt=(247, 249, 251),
        text=(24, 33, 43), dim=(87, 98, 115),
        primary=(37, 99, 235), success=(22, 101, 52),
        warning=(158, 70, 12), error=(185, 28, 28),
        outline=(213, 219, 227), accent_bar_bg=(233, 237, 243),
    ),
}

# ---- 类别契约（当前 10 类 V1.1；12 类目标见 README） -----------------------
CLASSES = ["AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK",
           "QPSK", "8PSK", "16QAM", "64QAM", "OFDM"]

STATUSES = ['LIVE', 'STALE', 'ERROR', 'MOCK']

# ---- 四态数据 -------------------------------------------------------------
def make_states():
    return {
        'normal': dict(status='LIVE', source='SDR', conf=0.842, top1='16QAM',
                       dist=[0.008, 0.006, 0.012, 0.015, 0.010, 0.024, 0.031, 0.842, 0.044, 0.008],
                       snr='+18 dB', lat='12.4 ms', frame='1024', age=None),
        'lowconf': dict(status='LIVE', source='SDR', conf=0.412, top1='QPSK',
                        dist=[0.015, 0.022, 0.028, 0.035, 0.042, 0.412, 0.308, 0.075, 0.038, 0.025],
                        snr='+7 dB', lat='13.1 ms', frame='1025', age=None),
        'stale': dict(status='STALE', source='SDR', conf=0.842, top1='16QAM',
                      dist=[0.008, 0.006, 0.012, 0.015, 0.010, 0.024, 0.031, 0.842, 0.044, 0.008],
                      snr='--', lat='--', frame='1007', age='3.2 s'),
        'error': dict(status='ERROR', source='SDR', conf=None, top1=None, dist=None,
                      snr='--', lat='--', frame='--', age=None),
    }

STATUS_COLOR = {
    'LIVE': 'success', 'STALE': 'warning', 'ERROR': 'error', 'MOCK': 'dim',
}

def status_color(pal, status):
    return pal[STATUS_COLOR[status]]

# ---- 状态徽标（文字 + 形状 + 颜色，三者齐备，不靠颜色区分） ----------------
def draw_status_badge(c, pal, status, x_right, yc):
    col = status_color(pal, status)
    b20 = F('b', 20)
    # 形状放在右对齐文字左侧并留 >=10px 间距，绝不覆盖 LIVE/STALE/ERROR/MOCK。
    text_left = x_right - text_width(status, b20)
    shape_r = 9 if status == 'ERROR' else 8
    cx = text_left - 10 - shape_r
    if status == 'LIVE':
        fill_circle(c, cx, yc, 8, col)
    elif status == 'STALE':
        fill_diamond(c, cx, yc, 8, col)
    elif status == 'ERROR':
        fill_triangle(c, cx, yc, 9, col)
    else:  # MOCK
        fill_square(c, cx, yc, 8, col, hollow=True)
    draw_text_right(c, status, x_right, yc + 7, col, b20)

# ---- 页头 ------------------------------------------------------------------
def draw_header(c, pal, title, st, page_labels):
    draw_text(c, title, 25, 50, pal['text'], F('b', 28))
    draw_status_badge(c, pal, st['status'], 1255, 38)
    outline_rect(c, 0, 78, W - 1, 78, pal['outline'], 1)

# ---- 主识别页 -------------------------------------------------------------
def render_main(c, pal, st):
    draw_header(c, pal, 'RF SIGNAL RECOGNITION', st, ('MAIN', 'DIAG', 'TOUCH'))

    # --- 结果卡（最高优先级） ---
    fill_rect(c, 25, 84, 1255, 252, pal['surface'])
    outline_rect(c, 25, 84, 1255, 252, pal['outline'], 1)

    if st['status'] == 'ERROR':
        draw_text(c, 'RECOGNIZED SIGNAL', 45, 126, pal['dim'], F('b', 20))
        draw_text(c, 'NO SIGNAL', 45, 196, pal['error'], F('b', 52))
        draw_text(c, 'no valid data on input', 45, 240, pal['dim'], F('r', 20))
        draw_status_chip(c, pal, 'NO SIGNAL', 'error', 1215, 122)
        # 保留信息栏 + 底部导航，允许进入 Diagnostics / Touch。
        draw_info_strip(c, pal, st)
        draw_nav(c, pal, 0)
        return

    conf = st['conf']; top1 = st['top1']
    conf_pct = conf * 100.0

    draw_text(c, 'RECOGNIZED SIGNAL', 45, 126, pal['dim'], F('b', 20))

    # 置信度 chip（状态）
    if st['status'] == 'STALE':
        draw_status_chip(c, pal, 'STALE DATA', 'warning', 1215, 122)
    elif conf >= 0.6:
        draw_status_chip(c, pal, 'CONFIDENT', 'success', 1215, 122)
    else:
        draw_status_chip(c, pal, 'LOW CONFIDENCE', 'warning', 1215, 122)

    # 类名（52px 粗体，关键结果）
    name_col = pal['dim'] if st['status'] == 'STALE' else pal['text']
    draw_text(c, top1, 45, 200, name_col, F('b', 52))

    # 置信度数值（40px 粗体，主要数据）
    conf_col = pal['warning'] if (st['status'] != 'STALE' and conf < 0.6) else \
               (pal['dim'] if st['status'] == 'STALE' else pal['success'])
    draw_text(c, 'CONFIDENCE', 45, 240, pal['dim'], F('r', 20))
    draw_text(c, '%3.1f%%' % conf_pct, 210, 240, conf_col, F('b', 40))

    # 置信度横条（右侧）
    bar_x0, bar_x1 = 700, 1215
    bar_y0, bar_y1 = 188, 224
    fill_rect(c, bar_x0, bar_y0, bar_x1, bar_y1, pal['accent_bar_bg'])
    outline_rect(c, bar_x0, bar_y0, bar_x1, bar_y1, pal['outline'], 1)
    if st['status'] != 'STALE':
        w = int((bar_x1 - bar_x0) * conf)
        fill_rect(c, bar_x0, bar_y0 + 2, bar_x0 + w - 1, bar_y1 - 2, conf_col)

    # --- 概率卡（第二优先级，两列） ---
    draw_text(c, 'CLASS PROBABILITIES', 25, 288, pal['dim'], F('b', 20))

    dist = st['dist']
    n = len(CLASSES)
    half = (n + 1) // 2
    cols = [25, 645]
    col_w = 610
    row_pitch = 50
    card_h = 44
    y0 = 300
    for i in range(n):
        col = 0 if i < half else 1
        row = i if i < half else i - half
        cx = cols[col]
        cy = y0 + row * row_pitch
        p = dist[i]
        is_top = (CLASSES[i] == top1)

        fill_rect(c, cx, cy, cx + col_w, cy + card_h, pal['surface'])
        outline_rect(c, cx, cy, cx + col_w, cy + card_h,
                     pal['primary'] if is_top else pal['outline'],
                     2 if is_top else 1)

        rank = '%2d' % (i + 1)
        draw_text(c, rank, cx + 14, cy + 31, pal['primary'] if is_top else pal['dim'], F('m', 20))
        nm_col = pal['text'] if is_top else pal['text']
        draw_text(c, CLASSES[i], cx + 54, cy + 31, nm_col, F('b', 20))

        # 迷你条
        bx0, bx1 = cx + 190, cx + col_w - 90
        by0, by1 = cy + 14, cy + 30
        fill_rect(c, bx0, by0, bx1, by1, pal['accent_bar_bg'])
        if not is_top and p < 0.5:
            fill_rect(c, bx0, by0, bx0 + int((bx1 - bx0) * p), by1, pal['dim'])
        else:
            fill_rect(c, bx0, by0, bx0 + int((bx1 - bx0) * p), by1,
                      pal['primary'] if is_top else pal['dim'])

        draw_text_right(c, '%4.1f%%' % (p * 100), cx + col_w - 12, cy + 31,
                        pal['text'] if is_top else pal['dim'], F('m', 20))

    # --- 信息条（第三优先级：SNR/延迟/帧号/数据源） ---
    draw_info_strip(c, pal, st)

    # --- 底部触摸导航（≥72px 物理；命中区≥60px 物理） ---
    draw_nav(c, pal, 0)


# ---- 诊断页 ---------------------------------------------------------------
def render_diag(c, pal, st):
    draw_header(c, pal, 'DIAGNOSTICS', st, ('MAIN', 'DIAG', 'TOUCH'))

    if st['status'] == 'ERROR':
        fill_rect(c, 25, 90, 1255, 594, pal['surface'])
        outline_rect(c, 25, 90, 1255, 594, pal['outline'], 1)
        draw_text(c, 'NO DATA', 45, 250, pal['error'], F('b', 52))
        draw_text(c, 'diagnostics unavailable - signal pipeline reports no valid frames',
                  45, 310, pal['dim'], F('r', 20))
        draw_nav(c, pal, 1)
        return

    # 延迟分解（左卡）
    fill_rect(c, 25, 90, 620, 594, pal['surface'])
    outline_rect(c, 25, 90, 620, 594, pal['outline'], 1)
    draw_text(c, 'LATENCY BREAKDOWN', 45, 132, pal['dim'], F('b', 20))

    rows = [('render', '4.2 ms'), ('copy (staging)', '0.8 ms'), ('sync + flip', '1.1 ms'),
            ('capture', '5.6 ms'), ('total', '12.4 ms')]
    ry = 200
    for k, v in rows:
        if k == 'total':
            outline_rect(c, 45, ry - 16, 600, ry + 12, pal['outline'], 1)
            draw_text(c, k, 57, ry, pal['text'], F('b', 20))
            draw_text_right(c, v, 588, ry, pal['text'], F('m', 20))
        else:
            draw_text(c, k, 57, ry, pal['dim'], F('r', 20))
            draw_text_right(c, v, 588, ry, pal['text'], F('m', 20))
        ry += 80

    # 详细计数（右卡）
    fill_rect(c, 655, 90, 1255, 594, pal['surface'])
    outline_rect(c, 655, 90, 1255, 594, pal['outline'], 1)
    draw_text(c, 'DETAILED COUNTS', 675, 132, pal['dim'], F('b', 20))

    cnt = [('frames rendered', '1024'), ('frames dropped', '0'),
           ('buffer resets', '0'), ('touch events', '57'),
           ('data source', st['source'])]
    ry = 200
    for k, v in cnt:
        draw_text(c, k, 687, ry, pal['dim'], F('r', 20))
        draw_text_right(c, v, 1223, ry, pal['text'], F('m', 20))
        ry += 64

    draw_text(c, 'signal status:', 675, 540, pal['dim'], F('r', 20))
    draw_status_badge(c, pal, st['status'], 1223, 534)

    draw_nav(c, pal, 1)


# ---- 触摸页 ---------------------------------------------------------------
def render_touch(c, pal, st):
    draw_header(c, pal, 'TOUCH TEST', st, ('MAIN', 'DIAG', 'TOUCH'))

    fill_rect(c, 25, 90, 820, 594, pal['surface'])
    outline_rect(c, 25, 90, 820, 594, pal['outline'], 1)
    draw_text(c, 'TOUCH CALIBRATION', 45, 132, pal['dim'], F('b', 20))

    rows = [('device', '/dev/input/event2'), ('vendor', 'ILITEK 7" IPS'),
            ('axis X', '0 .. 4095'), ('axis Y', '0 .. 4095'),
            ('mapping X', '(raw_x)*1280/4095'), ('mapping Y', '(raw_y)*720/4095')]
    ry = 200
    for k, v in rows:
        draw_text(c, k, 57, ry, pal['dim'], F('r', 20))
        draw_text(c, v, 250, ry, pal['text'], F('m', 20))
        ry += 64

    # 右侧命中区示意
    fill_rect(c, 850, 90, 1255, 594, pal['surface'])
    outline_rect(c, 850, 90, 1255, 594, pal['outline'], 1)
    draw_text(c, 'HIT REGIONS', 870, 132, pal['dim'], F('b', 20))
    tabs = ['MAIN', 'DIAG', 'TOUCH']
    tx = 870
    for i, t in enumerate(tabs):
        fill_rect(c, tx, 160, tx + 112, 220, pal['surface_alt'])
        outline_rect(c, tx, 160, tx + 112, 220, pal['primary'] if i == 2 else pal['outline'], 2 if i == 2 else 1)
        draw_text_center(c, t, tx + 56, 198, pal['primary'] if i == 2 else pal['text'], F('b', 20))
        tx += 124
    draw_text(c, 'hit area >= 60 px physical', 870, 268, pal['dim'], F('r', 20))
    draw_text(c, 'bottom nav height 90 px raw', 870, 300, pal['dim'], F('r', 20))

    draw_text(c, 'touch status:', 870, 540, pal['dim'], F('r', 20))
    draw_status_badge(c, pal, st['status'], 1223, 534)

    draw_nav(c, pal, 2)


# ---- 信息条 -----------------------------------------------------------------
def draw_info_strip(c, pal, st):
    y0, y1 = 558, 624
    fill_rect(c, 25, y0, 1255, y1, pal['surface_alt'])
    outline_rect(c, 25, y0, 1255, y1, pal['outline'], 1)
    items = [
        ('SNR', st['snr']),
        ('LATENCY', st['lat']),
        ('FRAME', st['frame']),
        ('SOURCE', st['source']),
    ]
    n = len(items)
    seg = 1230 // n
    x = 45
    for k, v in items:
        draw_text(c, k, x, y0 + 26, pal['dim'], F('r', 20))
        draw_text(c, v, x, y0 + 54, pal['text'], F('b', 28))
        x += seg

# ---- 状态 chip --------------------------------------------------------------
def draw_status_chip(c, pal, label, kind, x_right, yc):
    col = pal[kind]
    w = text_width(label, F('b', 20)) + 28
    x0 = x_right - w
    y0 = yc - 22
    fill_rect(c, x0, y0, x_right, yc + 14, pal['surface_alt'])
    outline_rect(c, x0, y0, x_right, yc + 14, col, 1)
    draw_text_center(c, label, (x0 + x_right) // 2, yc, col, F('b', 20))

# ---- 底部导航 ----------------------------------------------------------------
def draw_nav(c, pal, active):
    y0, y1 = 630, 719
    fill_rect(c, 0, y0, W - 1, y1, pal['surface'])
    outline_rect(c, 0, y0, W - 1, y0, pal['outline'], 1)
    tabs = ['MAIN', 'DIAGNOSTICS', 'TOUCH']
    tw = W // 3
    for i, t in enumerate(tabs):
        x0 = i * tw
        on = (i == active)
        if on:
            fill_rect(c, x0 + 10, y0 + 8, x0 + tw - 10, y1 - 8, pal['surface_alt'])
        shape_cx = x0 + 34
        shape_cy = y0 + 45
        if i == 0:
            fill_square(c, shape_cx, shape_cy, 9, pal['primary'] if on else pal['dim'], hollow=False)
        elif i == 1:
            fill_circle(c, shape_cx, shape_cy, 9, pal['primary'] if on else pal['dim'])
        else:
            fill_diamond(c, shape_cx, shape_cy, 9, pal['primary'] if on else pal['dim'])
        draw_text(c, t, x0 + 58, y0 + 60, pal['primary'] if on else pal['text'], F('b', 24))

# ---- 旧版 5x7 UI（复刻 v4_fix phase2，用于对比） ---------------------------
GLYPHS_5x7 = {
 '0': [".###.","#...#","#..##","#.#.#","##..#","#...#",".###."],
 '1': ["..#..",".##..","..#..","..#..","..#..","..#..","#####"],
 '2': [".###.","#...#","....#","...#.","..#..",".#...","#####"],
 '3': ["#####","...#.","..#..",".###.","....#","#...#",".###."],
 '4': ["...#.","..##.",".#.#.","#..#.","#####","...#.","...#."],
 '5': ["#####","#....","####.","....#","....#","#...#",".###."],
 '6': [".###.","#....","#....","####.","#...#","#...#",".###."],
 '7': ["#####","....#","...#.","..#..",".#...",".#...",".#..."],
 '8': [".###.","#...#","#...#",".###.","#...#","#...#",".###."],
 '9': [".###.","#...#","#...#",".###.","....#","....#",".###."],
 'A': ["..#..",".#.#.","#...#","#...#","#####","#...#","#...#"],
 'B': ["####.","#...#","#...#","####.","#...#","#...#","####."],
 'C': [".###.","#...#","#....","#....","#....","#...#",".###."],
 'D': ["####.","#...#","#...#","#...#","#...#","#...#","####."],
 'E': ["#####","#....","#....","####.","#....","#....","#####"],
 'F': ["#####","#....","#....","####.","#....","#....","#...."],
 'G': [".###.","#...#","#....","#.###","#...#","#...#",".###."],
 'H': ["#...#","#...#","#...#","#####","#...#","#...#","#...#"],
 'I': ["#####","..#..","..#..","..#..","..#..","..#..","#####"],
 'J': ["..###","...#.","...#.","...#.","...#.","#..#.",".##.."],
 'K': ["#...#","#..#.","#.#..","##...","#.#..","#..#.","#...#"],
 'L': ["#....","#....","#....","#....","#....","#....","#####"],
 'M': ["#...#","##.##","#.#.#","#.#.#","#...#","#...#","#...#"],
 'N': ["#...#","##..#","#.#.#","#..##","#...#","#...#","#...#"],
 'O': [".###.","#...#","#...#","#...#","#...#","#...#",".###."],
 'P': ["####.","#...#","#...#","####.","#....","#....","#...."],
 'Q': [".###.","#...#","#...#","#...#","#.#.#","#..#.",".##.#"],
 'R': ["####.","#...#","#...#","####.","#.#..","#..#.","#...#"],
 'S': [".####","#....","#....",".###.","....#","....#","####."],
 'T': ["#####","..#..","..#..","..#..","..#..","..#..","..#.."],
 'U': ["#...#","#...#","#...#","#...#","#...#","#...#",".###."],
 'V': ["#...#","#...#","#...#","#...#","#...#",".#.#.","..#.."],
 'W': ["#...#","#...#","#...#","#.#.#","#.#.#","##.##","#...#"],
 'X': ["#...#","#...#",".#.#.","..#..",".#.#.","#...#","#...#"],
 'Y': ["#...#","#...#",".#.#.","..#..","..#..","..#..","..#.."],
 'Z': ["#####","....#","...#.","..#..",".#...","#....","#####"],
 '.': [".....",".....",".....",".....",".....",".##..",".##.."],
 '%': ["##..#","##..#","...#.","..#..",".#...","#..##","#..##"],
 '-': [".....",".....",".....","#####",".....",".....","....."],
 '/': ["....#","...#.","...#.","..#..",".#...",".#...","#...."],
 ':': [".....",".##..",".##..",".....",".##..",".##..","....."],
 '>': ["#....",".#...","..#..","...#.","..#..",".#...","#...."],
 '(': ["...#.","..#..",".#...",".#...",".#...","..#..","...#."],
 ')': [".#...","..#..","...#.","...#.","...#.","..#..",".#..."],
 '_': [".....",".....",".....",".....",".....",".....","#####"],
 ' ': [".....",".....",".....",".....",".....",".....","....."],
 '+': [".....","..#..","..#..","#####","..#..","..#..","....."],
}

def draw5x7(c, ch, x, y, color, scale):
    g = GLYPHS_5x7.get(ch, GLYPHS_5x7[' '])
    for r in range(7):
        for col in range(5):
            if g[r][col] == '#':
                fill_rect(c, x + col * scale, y + r * scale,
                          x + col * scale + scale - 1, y + r * scale + scale - 1, color)

def draw5x7_text(c, s, x, y, color, scale):
    cx = x
    for ch in s:
        draw5x7(c, ch, cx, y, color, scale)
        cx += 6 * scale
    return cx

def render_old_phase2(c, conf, top1, snr, lat, frame):
    BG = (0, 8, 24); TITLEBG = (0, 16, 48); TEXT = (224, 224, 224)
    DIM = (128, 144, 160); ACCENT = (0, 192, 255); GOOD = (0, 224, 96)
    WARN = (224, 160, 0); HI = (255, 255, 255); BORDER = (64, 96, 128)
    fill_rect(c, 0, 0, W - 1, H - 1, BG)
    fill_rect(c, 0, 0, W - 1, 55, TITLEBG)
    outline_rect(c, 0, 0, W - 1, 55, ACCENT, 2)
    draw5x7_text(c, "RF SIGNAL RECOGNITION", 40, 14, ACCENT, 3)
    status = "SNR:%+ddB TOP-1:%s CONF:%3.0f%% LAT:%5.1fms FRAME:%d" % (
        snr, CLASSES[top1], conf[top1] * 100, lat, frame)
    draw5x7_text(c, status, 40, 66, DIM, 2)
    n = len(CLASSES)
    list_top, list_bot = 100, 620
    row_h = (list_bot - list_top) // n
    bar_x, bar_w = 340, W - 340 - 140
    for i in range(n):
        y0 = list_top + i * row_h
        y1 = y0 + row_h - 6
        cy = y0 + (row_h - 14) // 2
        is_top = (i == top1)
        draw5x7_text(c, "%d" % (i + 1), 24, cy, HI if is_top else DIM, 2)
        draw5x7_text(c, CLASSES[i], 72, cy, HI if is_top else TEXT, 2)
        bar_col = GOOD if conf[i] >= 0.5 else (WARN if conf[i] >= 0.15 else ACCENT)
        fill_rect(c, bar_x, y0, bar_x + bar_w - 1, y1, (8, 16, 32))
        fillw = int(bar_w * conf[i])
        if fillw > 0:
            fill_rect(c, bar_x, y0, bar_x + fillw - 1, y1, bar_col)
        outline_rect(c, bar_x, y0, bar_x + bar_w - 1, y1, HI if is_top else BORDER, 2)
        draw5x7_text(c, "%3.0f%%" % (conf[i] * 100), bar_x + bar_w + 16, cy, HI if is_top else DIM, 2)
    rbox_y = 624
    fill_rect(c, 0, rbox_y, W - 1, H - 1, TITLEBG)
    outline_rect(c, 0, rbox_y, W - 1, H - 1, ACCENT, 2)
    draw5x7_text(c, "RESULT >", 40, rbox_y + (H - rbox_y - 14) // 2, ACCENT, 2)
    draw5x7_text(c, CLASSES[top1], 200, rbox_y + (H - rbox_y - 21) // 2, HI, 3)

# ---- 输出 / 缩放 ------------------------------------------------------------
def save(c, path):
    Image.fromarray(c).save(path)

def downscale(c):
    return np.asarray(Image.fromarray(c).resize((PW, PH), Image.Resampling.BILINEAR), np.uint8)

def rgb565(c):
    # 模拟板端 RGB565（5-6-5）量化——只用于信息参考，正式稿仍存 24bit。
    r = (c[..., 0].astype(np.uint16) & 0xF8)
    g = (c[..., 1].astype(np.uint16) & 0xFC)
    b = (c[..., 2].astype(np.uint16) >> 3)
    q = np.stack([r, g, (b << 3) | (b >> 2)], axis=-1).astype(np.uint8)
    return q

def compose_compare(old_img, new_img, left_label, right_label):
    cap = 30
    gap = 8
    ih, iw = old_img.shape[:2]
    cw = iw * 2 + gap
    ch = ih + cap
    out = np.full((ch, cw, 3), (10, 10, 10), np.uint8)
    out[0:cap, 0:iw] = np.array((30, 30, 30), np.uint8)
    out[0:cap, iw + gap:iw * 2 + gap] = np.array((30, 30, 30), np.uint8)
    out[cap:cap + ih, 0:iw] = old_img
    out[cap:cap + ih, iw + gap:iw * 2 + gap] = new_img
    img = Image.fromarray(out)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf'), 18)
    d.text((10, 6), left_label, font=f, fill=(220, 220, 220))
    d.text((iw + gap + 10, 6), right_label, font=f, fill=(220, 220, 220))
    return np.asarray(img, np.uint8)

def main():
    states = make_states()
    pages = {'main': render_main, 'diag': render_diag, 'touch': render_touch}
    state_keys = ['normal', 'lowconf', 'stale', 'error']

    os.makedirs(OUT, exist_ok=True)
    for sname, pal in PALETTES.items():
        d = os.path.join(OUT, 'style_' + sname)
        os.makedirs(d, exist_ok=True)
        for pname, fn in pages.items():
            for sk in state_keys:
                st = states[sk]
                c = canvas(pal['bg'])
                fn(c, pal, st)
                save(c, os.path.join(d, '%s_%s_1280.png' % (pname, sk)))
                save(downscale(c), os.path.join(d, '%s_%s_1024.png' % (pname, sk)))

        # 状态图例（每套风格一张，展示 MOCK/LIVE/STALE/ERROR 四值）
        legend = canvas(pal['bg'])
        fill_rect(legend, 25, 40, 1255, 160, pal['surface'])
        outline_rect(legend, 25, 40, 1255, 160, pal['outline'], 1)
        draw_text(legend, 'SIGNAL STATUS (text + shape + color)', 45, 96, pal['dim'], F('b', 24))
        xs = [200, 520, 840, 1160]
        for i, s in enumerate(STATUSES):
            draw_status_badge(legend, pal, s, xs[i] + 40, 140)
        save(legend, os.path.join(d, 'legend_status.png'))

    # 新旧对比（每套风格 × 主识别页 normal，1280 + 1024）
    cmp_dir = os.path.join(OUT, 'comparison')
    os.makedirs(cmp_dir, exist_ok=True)
    old = canvas((0, 0, 0))
    st_norm = states['normal']
    render_old_phase2(old, list(st_norm['dist']), CLASSES.index(st_norm['top1']),
                      18, 12.4, 1024)
    save(old, os.path.join(cmp_dir, 'old_v4_1280.png'))
    save(downscale(old), os.path.join(cmp_dir, 'old_v4_1024.png'))
    for sname, pal in PALETTES.items():
        new = canvas(pal['bg'])
        render_main(new, pal, st_norm)
        comp = compose_compare(old, new, 'OLD  v4_fix  (5x7 dot-matrix)', 'NEW  Style %s  (anti-aliased atlas)' % sname)
        save(comp, os.path.join(cmp_dir, 'old_vs_%s_1280.png' % sname))
        comp2 = compose_compare(downscale(old), downscale(new),
                                'OLD  v4_fix  (1024x600)', 'NEW  Style %s  (1024x600)' % sname)
        save(comp2, os.path.join(cmp_dir, 'old_vs_%s_1024.png' % sname))

    write_readme(states)
    print('DONE ->', OUT)

# ---- README ----------------------------------------------------------------
def hexc(rgb):
    return '#%02X%02X%02X' % tuple(rgb)

def write_readme(states):
    lines = []
    lines.append('# v5_visual 静态设计稿（design mockups）\n')
    lines.append('本目录是 **Phase2/Phase3 视觉重构** 的静态设计稿，**尚未进入 C++ 实现**。')
    lines.append('在确认某一套风格之前，`hdmi_framebuffer_ui_v4_fix/sw` 的正式 Phase2/Phase3 代码')
    lines.append('**一律不改**。\n')
    lines.append('## 字体（真正的抗锯齿字体图集）\n')
    lines.append('- 字体：**DejaVu Sans**（Regular / Bold / Mono），Bitstream Vera 许可，允许随程序再分发')
    lines.append('  （需保留版权与许可声明，见 `assets/fonts/LICENSE-DejaVu.txt`）。')
    lines.append('- 板端不依赖 FreeType：设计稿用电脑端把字形预栅格化为 **8-bit 灰度覆盖率**，板端只做')
    lines.append('  **RGB565 整数 alpha blend**（`dst = (dst*(255-a) + fg*a + 127) >> 8`，逐通道）。')
    lines.append('- 固定字号 4 档：**20 / 28 / 40 / 52 px**（粗体 + 常规 + 等宽数字）。**禁止运行时缩放 5x7。**')
    lines.append('- 1280x720 输出 → 屏幕 1024x600（约 0.80 水平 / 0.83 垂直）。缩放后：正文 20→16px、')
    lines.append('  次要数据 28→23px、主要数据 40→32px、识别结果 52→42px。\n')
    lines.append('## 三套风格\n')
    for sname, pal in PALETTES.items():
        lines.append('### Style %s — %s' % (sname, {'A': '现代科研仪器风（推荐）',
                                                   'B': '比赛展示风',
                                                   'C': '浅色实验仪器风'}[sname]))
        lines.append('- background `%s` · surface `%s` · textPrimary `%s` · textSecondary `%s`' % (
            hexc(pal['bg']), hexc(pal['surface']), hexc(pal['text']), hexc(pal['dim'])))
        lines.append('- primary `%s`（仅当前选中 + 关键结果）· success `%s` · warning `%s` · error `%s` · outline `%s`' % (
            hexc(pal['primary']), hexc(pal['success']), hexc(pal['warning']), hexc(pal['error']), hexc(pal['outline'])))
        lines.append('')
    lines.append('## 信息层级（主识别页，自上而下）\n')
    lines.append('1. **识别结果 / 置信度 / 信号状态** — 顶部结果卡（52px 类名 + 40px 置信度 + 状态 chip）。')
    lines.append('2. **10/12 类概率** — 两列卡片，简洁排行，非全宽描边。')
    lines.append('3. **SNR / 延迟 / 帧号 / 数据源** — 底部信息条（28px）。')
    lines.append('4. **延迟分解 + 详细计数** → 移到 Diagnostics 页。')
    lines.append('5. 底部触摸导航高度 **90px 原始（→75px 物理）**，命中区 ≥60px 物理。')
    lines.append('6. **MOCK / LIVE / STALE / ERROR** 一律「文字 + 形状 + 颜色」三通道表达（见 legend_status.png）。\n')
    lines.append('## 布局网格\n')
    lines.append('- 水平按 **5px**、垂直按 **6px** 对齐：1280→1024 是 0.8 倍（5→4 整数），720→600 是 5/6（6→5 整数），')
    lines.append('  避免非整数缩放导致的发糊。')
    lines.append('- 不使用阴影、模糊、渐变、透明图层。\n')
    lines.append('## 文件清单\n')
    lines.append('- `output/style_*/{main,diag,touch}_{normal,lowconf,stale,error}_{1280,1024}.png` — 每套 24 张。')
    lines.append('- `output/style_*/legend_status.png` — 状态图例（4 值）。')
    lines.append('- `output/comparison/old_vs_*_1280.png / _1024.png` — 新旧并排对比。')
    lines.append('- `tools/make_mockups.py` — 生成器（numpy + Pillow，无其它依赖）。\n')
    lines.append('> 状态：**DESIGN-DRAFT-ONLY**。确认风格后才会写像素级一致的 C++ RGB565 版本。\n')
    with open(os.path.join(ROOT, 'README.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))

if __name__ == '__main__':
    main()
