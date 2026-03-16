#!/usr/bin/env python3
"""Print all thesis data tables as Markdown from raw benchmark results."""

import json
import os
import re
import numpy as np
from scipy.stats import mannwhitneyu

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Data loading ────────────────────────────────────────────────────────────

def load_json(relpath):
    with open(os.path.join(SCRIPT_DIR, relpath)) as f:
        return json.load(f)


def parse_warm_txt(relpath):
    path = os.path.join(SCRIPT_DIR, relpath)
    vals = []
    with open(path) as f:
        for line in f:
            m = re.search(r':\s*([\d.]+)\s*ms', line)
            if m:
                vals.append(float(m.group(1)))
    return vals


def load_rss(relpath):
    with open(os.path.join(SCRIPT_DIR, relpath)) as f:
        return int(f.read().strip())


def browser_filter(data, test, toolchain=None, **params):
    out = []
    for entry in data:
        if entry['test'] != test:
            continue
        if toolchain and entry['toolchain'] != toolchain:
            continue
        match = all(entry['params'].get(k) == v for k, v in params.items())
        if match:
            out.append(entry)
    return out


def fmt_int(v):
    return f'{v:,}'


SUPERSCRIPT = str.maketrans('0123456789-', '⁰¹²³⁴⁵⁶⁷⁸⁹⁻')


def _sci_unicode(p):
    """Format a small float as e.g. 3.02×10⁻¹¹."""
    s = f'{p:.2e}'
    coeff, exp = s.split('e')
    exp_int = int(exp)
    exp_str = str(exp_int).translate(SUPERSCRIPT)
    return f'{coeff}×10{exp_str}'


def p_str(p):
    if p < 0.001:
        return '< 0.001 ***'
    elif p < 0.01:
        return f'{p:.3f} **'
    elif p < 0.05:
        return f'{p:.3f} *'
    else:
        return f'{p:.3f} n.s.'


def mwu(a, b):
    _, p = mannwhitneyu(a, b, alternative='two-sided')
    return p


# ── Table printers ──────────────────────────────────────────────────────────

def table_c1(metrics):
    print('\n## 6.2.1 二进制体积（C1）\n')
    sizes = metrics['binary_sizes']
    targets = [
        ('conv-browser', 'conv-browser'),
        ('json-browser', 'json-browser'),
        ('conv-wasi', 'conv-wasi'),
        ('json-wasi', 'json-wasi'),
        ('sha-wasi', 'sha-wasi'),
    ]
    print('| 产物文件 | Go (bytes) | TinyGo (bytes) | Rust (bytes) |')
    print('|----------|-----------|----------------|-------------|')
    for label, prefix in targets:
        go = sizes[f'{prefix}-go.wasm']
        tg = sizes[f'{prefix}-tinygo.wasm']
        rs = sizes[f'{prefix}-rust.wasm']
        print(f'| {label} | {fmt_int(go)} | {fmt_int(tg)} | {fmt_int(rs)} |')


def table_c2(metrics):
    print('\n## 6.2.2 构建时间（C2）\n')
    bt = metrics['build_times']

    go_targets = [
        ('conv-browser', 'go-conv-browser'),
        ('json-browser', 'go-json-browser'),
        ('conv-wasi', 'go-conv-wasi'),
        ('json-wasi', 'go-json-wasi'),
        ('sha-wasi', 'go-sha-wasi'),
    ]
    tg_targets = [
        ('conv-browser', 'tinygo-conv-browser'),
        ('json-browser', 'tinygo-json-browser'),
        ('conv-wasi', 'tinygo-conv-wasi'),
        ('json-wasi', 'tinygo-json-wasi'),
        ('sha-wasi', 'tinygo-sha-wasi'),
    ]

    print('| 构建目标 | Go 中位数 (s) | TinyGo 中位数 (s) | Rust 中位数 (s) |')
    print('|----------|-------------|-------------------|----------------|')
    for i in range(5):
        label = go_targets[i][0]
        go_med = bt[go_targets[i][1]]['median']
        tg_med = bt[tg_targets[i][1]]['median']
        print(f'| {label} | {go_med:.4f} | {tg_med:.4f} | （合并统计） |')

    go_browser = sum(bt[k]['median'] for _, k in go_targets[:2])
    tg_browser = sum(bt[k]['median'] for _, k in tg_targets[:2])
    rs_browser = bt['rust-browser']['median']
    go_wasi = sum(bt[k]['median'] for _, k in go_targets[2:])
    tg_wasi = sum(bt[k]['median'] for _, k in tg_targets[2:])
    rs_wasi = bt['rust-wasi']['median']

    print(f'| 浏览器目标合计 | {go_browser:.4f} | {tg_browser:.4f} | {rs_browser:.4f} |')
    print(f'| WASI 目标合计 | {go_wasi:.4f} | {tg_wasi:.4f} | {rs_wasi:.4f} |')


def table_b1_r1(browser):
    print('\n## 6.3.1 B1 模块实例化时间（R1）\n')
    image_sizes = [(256, 256), (512, 512), (1024, 1024), (1920, 1080)]
    kernels = [3, 5]

    print('| 图像尺寸 | 卷积核 | Go R1 (ms) | TinyGo R1 (ms) | Rust R1 (ms) |')
    print('|----------|--------|-----------|----------------|-------------|')
    for k in kernels:
        for w, h in image_sizes:
            go = browser_filter(browser, 'conv', 'go', w=w, h=h, k=k)[0]
            tg = browser_filter(browser, 'conv', 'tinygo', w=w, h=h, k=k)[0]
            rs = browser_filter(browser, 'conv', 'rust', w=w, h=h, k=k)[0]
            print(f'| {w}×{h} | K{k} | {go["initTimeMs"]:.2f} | '
                  f'{tg["initTimeMs"]:.2f} | {rs["initTimeMs"]:.2f} |')


def table_b1_r2(browser):
    print('\n## 6.3.1 B1 执行时间（R2）\n')
    image_sizes = [(256, 256), (512, 512), (1024, 1024), (1920, 1080)]
    kernels = [3, 5]

    print('| 图像尺寸 | 卷积核 | Go 均值 (ms) | TinyGo 均值 (ms) | Rust 均值 (ms) | p 值 (Go vs Rust) |')
    print('|----------|--------|-------------|-----------------|---------------|------------------|')
    for k in kernels:
        for w, h in image_sizes:
            go = browser_filter(browser, 'conv', 'go', w=w, h=h, k=k)[0]
            tg = browser_filter(browser, 'conv', 'tinygo', w=w, h=h, k=k)[0]
            rs = browser_filter(browser, 'conv', 'rust', w=w, h=h, k=k)[0]
            p = mwu(go['execution']['values'], rs['execution']['values'])
            print(f'| {w}×{h} | K{k} | {go["execution"]["mean"]:.3f} | '
                  f'{tg["execution"]["mean"]:.3f} | {rs["execution"]["mean"]:.3f} | '
                  f'{p_str(p)} |')


def table_b1_r3(browser):
    print('\n## 6.3.1 B1 内存增量（R3）\n')
    image_sizes = [(256, 256), (512, 512), (1024, 1024), (1920, 1080)]
    kernels = [3, 5]

    print('| 图像尺寸 | 卷积核 | Go (bytes) | TinyGo (bytes) | Rust (bytes) |')
    print('|----------|--------|-----------|----------------|-------------|')
    for k in kernels:
        for w, h in image_sizes:
            go = browser_filter(browser, 'conv', 'go', w=w, h=h, k=k)[0]
            tg = browser_filter(browser, 'conv', 'tinygo', w=w, h=h, k=k)[0]
            rs = browser_filter(browser, 'conv', 'rust', w=w, h=h, k=k)[0]
            print(f'| {w}×{h} | K{k} | {fmt_int(go["memoryDelta"])} | '
                  f'{fmt_int(tg["memoryDelta"])} | {fmt_int(rs["memoryDelta"])} |')


def table_b2_r1(browser):
    print('\n## 6.3.2 B2 模块实例化时间（R1）\n')
    go = browser_filter(browser, 'json', 'go', n=100)[0]
    tg = browser_filter(browser, 'json', 'tinygo', n=100)[0]
    rs = browser_filter(browser, 'json', 'rust', n=100)[0]

    print('| 记录数 N | Go R1 (ms) | TinyGo R1 (ms) | Rust R1 (ms) |')
    print('|----------|-----------|----------------|-------------|')
    print(f'| 100 | {go["initTimeMs"]:.2f} | {tg["initTimeMs"]:.2f} | {rs["initTimeMs"]:.2f} |')


def table_b2_r2(browser):
    print('\n## 6.3.2 B2 执行时间（R2）\n')
    ns = [100, 1000, 10000]

    print('| 记录数 N | Go 均值 (ms) | Go 标准差 | TinyGo 均值 (ms) | TinyGo 标准差 | '
          'Rust 均值 (ms) | Rust 标准差 | p 值 (Go vs Rust) |')
    print('|----------|-------------|----------|-----------------|--------------|'
          '---------------|------------|------------------|')
    for n in ns:
        go = browser_filter(browser, 'json', 'go', n=n)[0]
        tg = browser_filter(browser, 'json', 'tinygo', n=n)[0]
        rs = browser_filter(browser, 'json', 'rust', n=n)[0]
        p = mwu(go['execution']['values'], rs['execution']['values'])
        n_label = fmt_int(n)
        print(f'| {n_label} | {go["execution"]["mean"]:.3f} | {go["execution"]["stdev"]:.3f} | '
              f'{tg["execution"]["mean"]:.3f} | {tg["execution"]["stdev"]:.3f} | '
              f'{rs["execution"]["mean"]:.3f} | {rs["execution"]["stdev"]:.3f} | '
              f'{p_str(p)} |')


def table_b2_r3(browser):
    print('\n## 6.3.2 B2 内存增量（R3）\n')
    ns = [100, 1000, 10000]

    print('| 记录数 N | Go (bytes) | TinyGo (bytes) | Rust (bytes) |')
    print('|----------|-----------|----------------|-------------|')
    for n in ns:
        go = browser_filter(browser, 'json', 'go', n=n)[0]
        tg = browser_filter(browser, 'json', 'tinygo', n=n)[0]
        rs = browser_filter(browser, 'json', 'rust', n=n)[0]
        n_label = fmt_int(n)
        print(f'| {n_label} | {fmt_int(go["memoryDelta"])} | '
              f'{fmt_int(tg["memoryDelta"])} | {fmt_int(rs["memoryDelta"])} |')


def _load_wasi_cold(prefix, param_label):
    data = load_json(f'wasi/{prefix}_{param_label}_cold.json')
    result = {}
    for r in data['results']:
        tc = {'go': 'Go', 'tinygo': 'TinyGo', 'rust': 'Rust'}[r['command']]
        result[tc] = {
            'mean': r['mean'] * 1000,
            'stddev': r['stddev'] * 1000,
            'times': [t * 1000 for t in r['times']],
        }
    return result


def _load_wasi_warm(prefix, param_label):
    result = {}
    for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        result[tc_label] = parse_warm_txt(f'wasi/{prefix}_{param_label}_warm_{tc_key}.txt')
    return result


def _load_wasi_rss(prefix, param_label):
    result = {}
    for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        result[tc_label] = load_rss(f'wasi/{prefix}_{param_label}_rss_{tc_key}.txt')
    return result


def table_b3_r4():
    print('\n## 6.4.1 B3 冷启动时间（R4）\n')
    sizes = [('1 KB', '1KB'), ('64 KB', '64KB'), ('1 MB', '1MB'), ('16 MB', '16MB')]

    print('| 输入大小 | Go 均值 (ms) | TinyGo 均值 (ms) | Rust 均值 (ms) |')
    print('|----------|-------------|-----------------|---------------|')
    for label, key in sizes:
        cold = _load_wasi_cold('sha256', key)
        go_s = f'{cold["Go"]["mean"]:.1f} ± {cold["Go"]["stddev"]:.1f}'
        tg_s = f'{cold["TinyGo"]["mean"]:.1f} ± {cold["TinyGo"]["stddev"]:.1f}'
        rs_s = f'{cold["Rust"]["mean"]:.1f} ± {cold["Rust"]["stddev"]:.1f}'
        print(f'| {label} | {go_s} | {tg_s} | {rs_s} |')


def table_b3_r5():
    print('\n## 6.4.1 B3 暖执行时间（R5）\n')
    sizes = [('1 KB', '1KB'), ('64 KB', '64KB'), ('1 MB', '1MB'), ('16 MB', '16MB')]

    print('| 输入大小 | Go 均值 (ms) | Go 标准差 | TinyGo 均值 (ms) | TinyGo 标准差 | '
          'Rust 均值 (ms) | Rust 标准差 | p 值 (Go vs Rust) |')
    print('|----------|-------------|----------|-----------------|--------------|'
          '---------------|------------|------------------|')
    for label, key in sizes:
        warm = _load_wasi_warm('sha256', key)
        go_v, tg_v, rs_v = warm['Go'], warm['TinyGo'], warm['Rust']
        p = mwu(go_v, rs_v)
        print(f'| {label} | {np.mean(go_v):.4f} | {np.std(go_v, ddof=1):.4f} | '
              f'{np.mean(tg_v):.4f} | {np.std(tg_v, ddof=1):.4f} | '
              f'{np.mean(rs_v):.4f} | {np.std(rs_v, ddof=1):.4f} | '
              f'{p_str(p)} |')


def table_b3_r6():
    print('\n## 6.4.1 B3 峰值内存（R6）\n')
    sizes = [('1 KB', '1KB'), ('64 KB', '64KB'), ('1 MB', '1MB'), ('16 MB', '16MB')]

    print('| 输入大小 | Go (bytes) | TinyGo (bytes) | Rust (bytes) |')
    print('|----------|-----------|----------------|-------------|')
    for label, key in sizes:
        rss = _load_wasi_rss('sha256', key)
        print(f'| {label} | {fmt_int(rss["Go"])} | {fmt_int(rss["TinyGo"])} | {fmt_int(rss["Rust"])} |')


def table_b4_r4():
    print('\n## 6.4.2 B4 冷启动时间（R4）\n')
    ns = [('100', '100'), ('1,000', '1000'), ('10,000', '10000')]

    print('| 记录数 N | Go 均值 (ms) | TinyGo 均值 (ms) | Rust 均值 (ms) |')
    print('|----------|-------------|-----------------|---------------|')
    for label, key in ns:
        cold = _load_wasi_cold('json', key)
        go_s = f'{cold["Go"]["mean"]:.1f} ± {cold["Go"]["stddev"]:.1f}'
        tg_s = f'{cold["TinyGo"]["mean"]:.1f} ± {cold["TinyGo"]["stddev"]:.1f}'
        rs_s = f'{cold["Rust"]["mean"]:.1f} ± {cold["Rust"]["stddev"]:.1f}'
        print(f'| {label} | {go_s} | {tg_s} | {rs_s} |')


def table_b4_r5():
    print('\n## 6.4.2 B4 暖执行时间（R5）\n')
    ns = [('100', '100'), ('1,000', '1000'), ('10,000', '10000')]

    print('| 记录数 N | Go 均值 (ms) | Go 标准差 | TinyGo 均值 (ms) | TinyGo 标准差 | '
          'Rust 均值 (ms) | Rust 标准差 | p 值 (Go vs Rust) |')
    print('|----------|-------------|----------|-----------------|--------------|'
          '---------------|------------|------------------|')
    for label, key in ns:
        warm = _load_wasi_warm('json', key)
        go_v, tg_v, rs_v = warm['Go'], warm['TinyGo'], warm['Rust']
        p = mwu(go_v, rs_v)
        print(f'| {label} | {np.mean(go_v):.4f} | {np.std(go_v, ddof=1):.4f} | '
              f'{np.mean(tg_v):.4f} | {np.std(tg_v, ddof=1):.4f} | '
              f'{np.mean(rs_v):.4f} | {np.std(rs_v, ddof=1):.4f} | '
              f'{p_str(p)} |')


def table_b4_r6():
    print('\n## 6.4.2 B4 峰值内存（R6）\n')
    ns = [('100', '100'), ('1,000', '1000'), ('10,000', '10000')]

    print('| 记录数 N | Go (bytes) | TinyGo (bytes) | Rust (bytes) |')
    print('|----------|-----------|----------------|-------------|')
    for label, key in ns:
        rss = _load_wasi_rss('json', key)
        print(f'| {label} | {fmt_int(rss["Go"])} | {fmt_int(rss["TinyGo"])} | {fmt_int(rss["Rust"])} |')


def table_cross_scenario(browser):
    print('\n## 6.4.3 B2 与 B4 跨场景对比（中位数）\n')
    ns = [100, 1000, 10000]

    print('| 记录数 N | B2 Go (ms) | B4 Go (ms) | B2 TinyGo (ms) | B4 TinyGo (ms) | '
          'B2 Rust (ms) | B4 Rust (ms) |')
    print('|----------|-----------|-----------|---------------|---------------|'
          '-------------|-------------|')
    for n in ns:
        go_b2 = browser_filter(browser, 'json', 'go', n=n)[0]['execution']['median']
        tg_b2 = browser_filter(browser, 'json', 'tinygo', n=n)[0]['execution']['median']
        rs_b2 = browser_filter(browser, 'json', 'rust', n=n)[0]['execution']['median']

        warm = _load_wasi_warm('json', str(n))
        go_b4 = float(np.median(warm['Go']))
        tg_b4 = float(np.median(warm['TinyGo']))
        rs_b4 = float(np.median(warm['Rust']))

        n_label = fmt_int(n)
        print(f'| {n_label} | {go_b2:.3f} | {go_b4:.3f} | {tg_b2:.3f} | {tg_b4:.3f} | '
              f'{rs_b2:.3f} | {rs_b4:.3f} |')


def table_significance(browser):
    print('\n## 6.6.2 统计显著性汇总\n')

    rows = []

    # B1 R2 (1920×1080, K5)
    go = browser_filter(browser, 'conv', 'go', w=1920, h=1080, k=5)[0]['execution']['values']
    tg = browser_filter(browser, 'conv', 'tinygo', w=1920, h=1080, k=5)[0]['execution']['values']
    rs = browser_filter(browser, 'conv', 'rust', w=1920, h=1080, k=5)[0]['execution']['values']
    rows.append(('B1 R2 (1920×1080, K5)', mwu(go, rs), mwu(tg, rs), mwu(go, tg)))

    # B2 R2 (N=10000)
    go = browser_filter(browser, 'json', 'go', n=10000)[0]['execution']['values']
    tg = browser_filter(browser, 'json', 'tinygo', n=10000)[0]['execution']['values']
    rs = browser_filter(browser, 'json', 'rust', n=10000)[0]['execution']['values']
    rows.append(('B2 R2 (N=10000)', mwu(go, rs), mwu(tg, rs), mwu(go, tg)))

    # B3 R5 (16 MB)
    warm_b3 = _load_wasi_warm('sha256', '16MB')
    go_v, tg_v, rs_v = warm_b3['Go'], warm_b3['TinyGo'], warm_b3['Rust']
    rows.append(('B3 R5 (16 MB)', mwu(go_v, rs_v), mwu(tg_v, rs_v), mwu(go_v, tg_v)))

    # B3 R5 (64 KB)
    warm_b3_64 = _load_wasi_warm('sha256', '64KB')
    go_v, tg_v, rs_v = warm_b3_64['Go'], warm_b3_64['TinyGo'], warm_b3_64['Rust']
    rows.append(('B3 R5 (64 KB)', mwu(go_v, rs_v), mwu(tg_v, rs_v), mwu(go_v, tg_v)))

    # B4 R5 (N=10000)
    warm_b4 = _load_wasi_warm('json', '10000')
    go_v, tg_v, rs_v = warm_b4['Go'], warm_b4['TinyGo'], warm_b4['Rust']
    rows.append(('B4 R5 (N=10000)', mwu(go_v, rs_v), mwu(tg_v, rs_v), mwu(go_v, tg_v)))

    def p_fmt(p):
        if p < 0.001:
            return _sci_unicode(p)
        else:
            return f'{p:.3f}'

    def sig_summary(p_gr, p_tr, p_gt):
        parts = []
        parts.append(f'Go/Rust {"***" if p_gr < 0.001 else "n.s."}')
        parts.append(f'TinyGo/Rust {"***" if p_tr < 0.001 else "n.s."}')
        parts.append(f'Go/TinyGo {"***" if p_gt < 0.001 else "n.s."}')
        if all(p < 0.001 for p in [p_gr, p_tr, p_gt]):
            return '全部 ***'
        return '，'.join(parts)

    print('| 指标 | Go vs Rust p 值 | TinyGo vs Rust p 值 | Go vs TinyGo p 值 | 显著性判定 |')
    print('|------|----------------|--------------------|--------------------|-----------|')
    for label, p_gr, p_tr, p_gt in rows:
        print(f'| {label} | {p_fmt(p_gr)} | {p_fmt(p_tr)} | {p_fmt(p_gt)} | {sig_summary(p_gr, p_tr, p_gt)} |')


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    metrics = load_json('build-metrics.json')
    browser = load_json('browser/results.json')

    table_c1(metrics)
    table_c2(metrics)
    table_b1_r1(browser)
    table_b1_r2(browser)
    table_b1_r3(browser)
    table_b2_r1(browser)
    table_b2_r2(browser)
    table_b2_r3(browser)
    table_b3_r4()
    table_b3_r5()
    table_b3_r6()
    table_b4_r4()
    table_b4_r5()
    table_b4_r6()
    table_cross_scenario(browser)
    table_significance(browser)
    table_radar_raw(browser, metrics)


def table_radar_raw(browser, metrics):
    print('\n## 6.6.1 雷达图原始数据\n')

    sizes = metrics['binary_sizes']
    bt = metrics['build_times']

    c1 = {}
    for tc_key, tc in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        c1[tc] = np.mean([sizes[f'{t}-{tc_key}.wasm']
                          for t in ['conv-browser', 'json-browser', 'conv-wasi', 'json-wasi', 'sha-wasi']])

    c2 = {
        'Go': sum(bt[f'go-{t}']['median'] for t in ['conv-browser', 'json-browser', 'conv-wasi', 'json-wasi', 'sha-wasi']),
        'TinyGo': sum(bt[f'tinygo-{t}']['median'] for t in ['conv-browser', 'json-browser', 'conv-wasi', 'json-wasi', 'sha-wasi']),
        'Rust': bt['rust-browser']['median'] + bt['rust-wasi']['median'],
    }

    r1b1 = {}
    for tc_key, tc in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        r1b1[tc] = browser_filter(browser, 'conv', tc_key, w=1920, h=1080, k=3)[0]['initTimeMs']

    r2b1 = {}
    for tc_key, tc in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        r2b1[tc] = browser_filter(browser, 'conv', tc_key, w=1920, h=1080, k=3)[0]['execution']['mean']

    r3b1 = {}
    for tc_key, tc in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        r3b1[tc] = browser_filter(browser, 'conv', tc_key, w=1920, h=1080, k=3)[0]['memoryDelta']

    r2b2 = {}
    for tc_key, tc in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        r2b2[tc] = browser_filter(browser, 'json', tc_key, n=10000)[0]['execution']['mean']

    cold_b3 = _load_wasi_cold('sha256', '16MB')
    r4b3 = {tc: cold_b3[tc]['mean'] for tc in ['Go', 'TinyGo', 'Rust']}

    warm_b3 = _load_wasi_warm('sha256', '16MB')
    r5b3 = {tc: np.mean(warm_b3[tc]) for tc in ['Go', 'TinyGo', 'Rust']}

    warm_b4 = _load_wasi_warm('json', '10000')
    r5b4 = {tc: np.mean(warm_b4[tc]) for tc in ['Go', 'TinyGo', 'Rust']}

    rss_b3 = _load_wasi_rss('sha256', '16MB')

    e1 = {'Go': 274, 'TinyGo': 274, 'Rust': 185}
    e2 = {'Go': 0, 'TinyGo': 0, 'Rust': 4}

    dims = [
        ('C1 二进制体积（平均，bytes）', c1, '{:,.0f}'),
        ('C2 构建时间（合计，s）', c2, '{:.4f}'),
        ('R1-B1 卷积初始化时间（1920×1080 K3，ms）', r1b1, '{:.3f}'),
        ('R2-B1 卷积执行时间（1920×1080 K3，ms）', r2b1, '{:.3f}'),
        ('R3-B1 卷积内存增量（1920×1080 K3，bytes）', r3b1, '{:,.0f}'),
        ('R2-B2 JSON 执行时间（N=10000，ms）', r2b2, '{:.3f}'),
        ('R4-B3 SHA-256 冷启动时间（16 MB，ms）', r4b3, '{:.1f}'),
        ('R5-B3 SHA-256 暖执行时间（16 MB，ms）', r5b3, '{:.4f}'),
        ('R5-B4 JSON WASI 暖执行时间（N=10000，ms）', r5b4, '{:.4f}'),
        ('R6-B3 SHA-256 峰值内存（16 MB，bytes）', rss_b3, '{:,.0f}'),
        ('E1 代码行数（SLOC）', e1, '{:d}'),
        ('E2 工具链复杂度（第三方依赖数）', e2, '{:d}'),
    ]

    print('| 维度 | Go | TinyGo | Rust | 最优 |')
    print('|------|-----|--------|------|------|')
    for label, data, fmt in dims:
        go_v, tg_v, rs_v = data['Go'], data['TinyGo'], data['Rust']
        min_val = min(data.values())
        best = ', '.join(tc for tc in ['Go', 'TinyGo', 'Rust'] if data[tc] == min_val)
        print(f'| {label} | {fmt.format(go_v)} | {fmt.format(tg_v)} | {fmt.format(rs_v)} | {best} |')


if __name__ == '__main__':
    main()
