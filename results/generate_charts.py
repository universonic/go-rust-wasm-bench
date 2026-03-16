#!/usr/bin/env python3
"""Generate all 20 thesis figures (Fig 6-1 to 6-20) from benchmark results."""

import json
import os
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, 'figures')
os.makedirs(OUT_DIR, exist_ok=True)

COLORS = {'Go': '#1f77b4', 'TinyGo': '#2ca02c', 'Rust': '#d62728'}
TOOLCHAINS = ['Go', 'TinyGo', 'Rust']


plt.rcParams.update({
    'font.family': 'Hiragino Sans GB',
    'axes.unicode_minus': False,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.labelsize': 11,
    'legend.fontsize': 9,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
})


# ── Data loading ────────────────────────────────────────────────────────────

def load_json(relpath):
    with open(os.path.join(SCRIPT_DIR, relpath)) as f:
        return json.load(f)


def load_browser_results():
    return load_json('browser/results.json')


def load_build_metrics():
    return load_json('build-metrics.json')


def parse_warm_txt(relpath):
    """Parse 'iteration N: X.XXX ms' lines, return list of float (ms)."""
    path = os.path.join(SCRIPT_DIR, relpath)
    vals = []
    with open(path) as f:
        for line in f:
            m = re.search(r':\s*([\d.]+)\s*ms', line)
            if m:
                vals.append(float(m.group(1)))
    return vals


def load_rss(relpath):
    """Read single-line RSS file (bytes)."""
    with open(os.path.join(SCRIPT_DIR, relpath)) as f:
        return int(f.read().strip())


def _browser_filter(data, test, toolchain=None, **params):
    """Filter browser results.json entries."""
    out = []
    for entry in data:
        if entry['test'] != test:
            continue
        if toolchain and entry['toolchain'] != toolchain:
            continue
        match = True
        for k, v in params.items():
            if entry['params'].get(k) != v:
                match = False
                break
        if match:
            out.append(entry)
    return out


def savefig(fig, name):
    fig.savefig(os.path.join(OUT_DIR, name))
    plt.close(fig)
    print(f'  ✓ {name}')


# ── Figure 6-1: Binary size bar chart ───────────────────────────────────────

def fig_6_1(metrics):
    sizes = metrics['binary_sizes']
    targets = ['conv-browser', 'json-browser', 'conv-wasi', 'json-wasi', 'sha-wasi']
    labels = targets[:]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(targets))
    w = 0.25

    for i, tc in enumerate(TOOLCHAINS):
        tc_key = {'Go': 'go', 'TinyGo': 'tinygo', 'Rust': 'rust'}[tc]
        vals = []
        for t in targets:
            key = f'{t}-{tc_key}.wasm'
            vals.append(sizes.get(key, 0) / 1024)
        bars = ax.bar(x + (i - 1) * w, vals, w, label=tc,
                      color=COLORS[tc], edgecolor='black', linewidth=0.5)
        for bar, v in zip(bars, vals):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        f'{v:.0f}' if v >= 10 else f'{v:.1f}',
                        ha='center', va='bottom', fontsize=7)

    ax.set_xlabel('构建目标')
    ax.set_ylabel('文件大小 (KB)')
    ax.set_title('图 6-1：二进制体积对比')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_yscale('log')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_1_binary_size.png')


# ── Figure 6-2: Build time bar chart ───────────────────────────────────────

def fig_6_2(metrics):
    bt = metrics['build_times']

    groups = ['浏览器目标合计', 'WASI 目标合计']
    go_browser = bt['go-conv-browser']['median'] + bt['go-json-browser']['median']
    go_wasi = bt['go-conv-wasi']['median'] + bt['go-json-wasi']['median'] + bt['go-sha-wasi']['median']
    tg_browser = bt['tinygo-conv-browser']['median'] + bt['tinygo-json-browser']['median']
    tg_wasi = bt['tinygo-conv-wasi']['median'] + bt['tinygo-json-wasi']['median'] + bt['tinygo-sha-wasi']['median']
    rs_browser = bt['rust-browser']['median']
    rs_wasi = bt['rust-wasi']['median']

    data = {
        'Go': [go_browser, go_wasi],
        'TinyGo': [tg_browser, tg_wasi],
        'Rust': [rs_browser, rs_wasi],
    }

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(groups))
    w = 0.25
    for i, tc in enumerate(TOOLCHAINS):
        bars = ax.bar(x + (i - 1) * w, data[tc], w, label=tc,
                      color=COLORS[tc], edgecolor='black', linewidth=0.5)
        for bar, v in zip(bars, data[tc]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f'{v:.2f}s', ha='center', va='bottom', fontsize=8)

    ax.set_ylabel('中位构建时间 (秒)')
    ax.set_title('图 6-2：构建时间对比')
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_2_build_time.png')


# ── Figure 6-3: Compile efficiency scatter plot ────────────────────────────

def fig_6_3(metrics):
    bt = metrics['build_times']
    sizes = metrics['binary_sizes']

    fig, ax = plt.subplots(figsize=(8, 5))
    markers = {'Go': 'o', 'TinyGo': 's', 'Rust': '^'}

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
    rust_targets = [
        ('conv-browser-rust.wasm', 'rust-browser'),
        ('json-browser-rust.wasm', 'rust-browser'),
        ('conv-wasi-rust.wasm', 'rust-wasi'),
        ('json-wasi-rust.wasm', 'rust-wasi'),
        ('sha-wasi-rust.wasm', 'rust-wasi'),
    ]

    for label, bt_key in go_targets:
        t = bt[bt_key]['median']
        s = sizes[f'{label}-go.wasm'] / 1024
        ax.scatter(t, s, c=COLORS['Go'], marker=markers['Go'], s=60, zorder=3)
    ax.scatter([], [], c=COLORS['Go'], marker=markers['Go'], s=60, label='Go')

    for label, bt_key in tg_targets:
        t = bt[bt_key]['median']
        s = sizes[f'{label}-tinygo.wasm'] / 1024
        ax.scatter(t, s, c=COLORS['TinyGo'], marker=markers['TinyGo'], s=60, zorder=3)
    ax.scatter([], [], c=COLORS['TinyGo'], marker=markers['TinyGo'], s=60, label='TinyGo')

    for sz_key, bt_key in rust_targets:
        t = bt[bt_key]['median']
        s = sizes[sz_key] / 1024
        ax.scatter(t, s, c=COLORS['Rust'], marker=markers['Rust'], s=60, zorder=3)
    ax.scatter([], [], c=COLORS['Rust'], marker=markers['Rust'], s=60, label='Rust')

    ax.set_xlabel('构建时间 (秒)')
    ax.set_ylabel('二进制体积 (KB)')
    ax.set_title('图 6-3：编译效率散点图（构建时间 vs 产物体积）')
    ax.set_yscale('log')
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_3_compile_efficiency.png')


# ── Figure 6-4: B1 instantiation time bar chart ───────────────────────────

def fig_6_4(browser):
    conv_entries = _browser_filter(browser, 'conv')

    avg_init = {}
    for tc in ['go', 'tinygo', 'rust']:
        entries = [e for e in conv_entries if e['toolchain'] == tc]
        avg_init[tc] = np.mean([e['initTimeMs'] for e in entries])

    fig, ax = plt.subplots(figsize=(5, 4))
    x = np.arange(3)
    vals = [avg_init['go'], avg_init['tinygo'], avg_init['rust']]
    bars = ax.bar(x, vals, 0.5,
                  color=[COLORS[t] for t in TOOLCHAINS],
                  edgecolor='black', linewidth=0.5)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f'{v:.1f}', ha='center', va='bottom', fontsize=9)

    ax.set_ylabel('实例化时间 (ms)')
    ax.set_title('图 6-4：B1 模块实例化时间（R1）')
    ax.set_xticks(x)
    ax.set_xticklabels(TOOLCHAINS)
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_4_b1_init.png')


# ── Figure 6-5: B1 execution time box plot (1920×1080, K3 & K5) ───────────

def fig_6_5(browser):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharey=False)

    for idx, k in enumerate([3, 5]):
        ax = axes[idx]
        data_all = []
        labels = []
        colors_list = []
        for tc in ['go', 'tinygo', 'rust']:
            entries = _browser_filter(browser, 'conv', tc, w=1920, h=1080, k=k)
            if entries:
                data_all.append(entries[0]['execution']['values'])
                labels.append({'go': 'Go', 'tinygo': 'TinyGo', 'rust': 'Rust'}[tc])
                colors_list.append(COLORS[labels[-1]])

        bp = ax.boxplot(data_all, tick_labels=labels, patch_artist=True, widths=0.5)
        for patch, color in zip(bp['boxes'], colors_list):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
        for median in bp['medians']:
            median.set_color('black')
            median.set_linewidth(1.5)

        ax.set_ylabel('执行时间 (ms)')
        ax.set_title(f'K{k} (1920×1080)')
        ax.grid(axis='y', alpha=0.3)

    fig.suptitle('图 6-5：B1 执行时间分布（1920×1080）', fontsize=12)
    fig.tight_layout()
    savefig(fig, 'fig_6_5_b1_boxplot.png')


# ── Figure 6-6: B1 execution time line chart (by image size) ──────────────

def fig_6_6(browser):
    image_sizes = [(256, 256), (512, 512), (1024, 1024), (1920, 1080)]
    pixels = [w * h for w, h in image_sizes]
    size_labels = [f'{w}×{h}' for w, h in image_sizes]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    for idx, k in enumerate([3, 5]):
        ax = axes[idx]
        for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
            means = []
            for w, h in image_sizes:
                entries = _browser_filter(browser, 'conv', tc_key, w=w, h=h, k=k)
                means.append(entries[0]['execution']['mean'] if entries else 0)
            ax.plot(pixels, means, marker='o', label=tc_label,
                    color=COLORS[tc_label], linewidth=2, markersize=5)

        ax.set_xlabel('像素总数')
        ax.set_ylabel('平均执行时间 (ms)')
        ax.set_title(f'K{k}')
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.legend()
        ax.grid(alpha=0.3)
        ax.set_xticks(pixels)
        ax.set_xticklabels(size_labels, fontsize=8)

    fig.suptitle('图 6-6：B1 执行时间随图像尺寸变化', fontsize=12)
    fig.tight_layout()
    savefig(fig, 'fig_6_6_b1_line.png')


# ── Figure 6-7: B1 memory delta bar chart ─────────────────────────────────

def fig_6_7(browser):
    image_sizes = [(256, 256), (512, 512), (1024, 1024), (1920, 1080)]
    size_labels = [f'{w}×{h}' for w, h in image_sizes]
    k = 3

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(image_sizes))
    w_bar = 0.25

    for i, (tc_key, tc_label) in enumerate([('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]):
        vals = []
        for w, h in image_sizes:
            entries = _browser_filter(browser, 'conv', tc_key, w=w, h=h, k=k)
            vals.append(entries[0]['memoryDelta'] / 1024 if entries else 0)
        ax.bar(x + (i - 1) * w_bar, vals, w_bar, label=tc_label,
               color=COLORS[tc_label], edgecolor='black', linewidth=0.5)

    ax.set_xlabel('图像尺寸')
    ax.set_ylabel('内存增量 (KB)')
    ax.set_title('图 6-7：B1 内存增量（R3，K3）')
    ax.set_xticks(x)
    ax.set_xticklabels(size_labels)
    ax.set_yscale('log')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_7_b1_memory.png')


# ── Figure 6-8: B2 execution time line chart ─────────────────────────────

def fig_6_8(browser):
    ns = [100, 1000, 10000]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        means = []
        for n in ns:
            entries = _browser_filter(browser, 'json', tc_key, n=n)
            means.append(entries[0]['execution']['mean'] if entries else 0)
        ax.plot(ns, means, marker='o', label=tc_label,
                color=COLORS[tc_label], linewidth=2, markersize=6)

    ax.set_xlabel('记录数 N')
    ax.set_ylabel('平均执行时间 (ms)')
    ax.set_title('图 6-8：B2 执行时间随记录数变化')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_xticks(ns)
    ax.set_xticklabels(['100', '1,000', '10,000'])
    fig.tight_layout()
    savefig(fig, 'fig_6_8_b2_line.png')


# ── Figure 6-9: B2 execution time box plot (N=10000) ─────────────────────

def fig_6_9(browser):
    fig, ax = plt.subplots(figsize=(6, 4.5))
    data_all = []
    labels = []
    colors_list = []
    for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        entries = _browser_filter(browser, 'json', tc_key, n=10000)
        if entries:
            data_all.append(entries[0]['execution']['values'])
            labels.append(tc_label)
            colors_list.append(COLORS[tc_label])

    bp = ax.boxplot(data_all, tick_labels=labels, patch_artist=True, widths=0.5)
    for patch, color in zip(bp['boxes'], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    for median in bp['medians']:
        median.set_color('black')
        median.set_linewidth(1.5)

    ax.set_ylabel('执行时间 (ms)')
    ax.set_title('图 6-9：B2 执行时间分布（N=10,000）')
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_9_b2_boxplot.png')


# ── Figure 6-10: B2 memory delta bar chart ───────────────────────────────

def fig_6_10(browser):
    ns = [100, 1000, 10000]
    n_labels = ['100', '1,000', '10,000']

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(ns))
    w = 0.25

    for i, (tc_key, tc_label) in enumerate([('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]):
        vals = []
        for n in ns:
            entries = _browser_filter(browser, 'json', tc_key, n=n)
            vals.append(entries[0]['memoryDelta'] / 1024 if entries else 0)
        ax.bar(x + (i - 1) * w, vals, w, label=tc_label,
               color=COLORS[tc_label], edgecolor='black', linewidth=0.5)

    ax.set_xlabel('记录数 N')
    ax.set_ylabel('内存增量 (KB)')
    ax.set_title('图 6-10：B2 内存增量（R3）')
    ax.set_xticks(x)
    ax.set_xticklabels(n_labels)
    ax.set_yscale('log')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_10_b2_memory.png')


# ── WASI helpers ──────────────────────────────────────────────────────────

def load_wasi_cold(prefix, param_label):
    """Load cold start data. Returns {toolchain: {'mean': ms, 'times': [ms]}}."""
    data = load_json(f'wasi/{prefix}_{param_label}_cold.json')
    result = {}
    for r in data['results']:
        tc = r['command']
        tc_mapped = {'go': 'Go', 'tinygo': 'TinyGo', 'rust': 'Rust'}[tc]
        result[tc_mapped] = {
            'mean': r['mean'] * 1000,
            'stddev': r['stddev'] * 1000,
            'median': r['median'] * 1000,
            'times': [t * 1000 for t in r['times']],
        }
    return result


def load_wasi_warm(prefix, param_label):
    """Load warm execution data. Returns {toolchain: [ms values]}."""
    result = {}
    for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        vals = parse_warm_txt(f'wasi/{prefix}_{param_label}_warm_{tc_key}.txt')
        result[tc_label] = vals
    return result


def load_wasi_rss(prefix, param_label):
    """Load RSS data. Returns {toolchain: bytes}."""
    result = {}
    for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        result[tc_label] = load_rss(f'wasi/{prefix}_{param_label}_rss_{tc_key}.txt')
    return result


# ── Figure 6-11: B3 cold start bar chart ─────────────────────────────────

def fig_6_11():
    input_sizes = ['1KB', '64KB', '1MB', '16MB']
    input_labels = ['1 KB', '64 KB', '1 MB', '16 MB']

    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(input_sizes))
    w = 0.25

    for i, tc in enumerate(TOOLCHAINS):
        vals = []
        for sz in input_sizes:
            cold = load_wasi_cold('sha256', sz)
            vals.append(cold[tc]['mean'])
        ax.bar(x + (i - 1) * w, vals, w, label=tc,
               color=COLORS[tc], edgecolor='black', linewidth=0.5)

    ax.set_xlabel('输入大小')
    ax.set_ylabel('平均冷启动时间 (ms)')
    ax.set_title('图 6-11：B3 冷启动时间（R4）')
    ax.set_xticks(x)
    ax.set_xticklabels(input_labels)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_11_b3_cold.png')


# ── Figure 6-12: B3 warm execution time line chart ──────────────────────

def fig_6_12():
    input_sizes = ['1KB', '64KB', '1MB', '16MB']
    input_labels = ['1 KB', '64 KB', '1 MB', '16 MB']
    size_bytes = [1024, 65536, 1048576, 16777216]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for tc in TOOLCHAINS:
        means = []
        for sz in input_sizes:
            warm = load_wasi_warm('sha256', sz)
            means.append(np.mean(warm[tc]))
        ax.plot(size_bytes, means, marker='o', label=tc,
                color=COLORS[tc], linewidth=2, markersize=6)

    ax.set_xlabel('输入大小')
    ax.set_ylabel('平均暖执行时间 (ms)')
    ax.set_title('图 6-12：B3 暖执行时间随输入大小变化')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_xticks(size_bytes)
    ax.set_xticklabels(input_labels)
    fig.tight_layout()
    savefig(fig, 'fig_6_12_b3_warm_line.png')


# ── Figure 6-13: B3 cold vs warm dual bar (1 MB) ────────────────────────

def fig_6_13():
    cold = load_wasi_cold('sha256', '1MB')
    warm = load_wasi_warm('sha256', '1MB')

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(3)
    w = 0.3

    cold_vals = [cold[tc]['mean'] for tc in TOOLCHAINS]
    warm_vals = [np.mean(warm[tc]) for tc in TOOLCHAINS]

    bars1 = ax.bar(x - w / 2, cold_vals, w, label='冷启动 (R4)',
                   color='#90CAF9', edgecolor='black', linewidth=0.5)
    bars2 = ax.bar(x + w / 2, warm_vals, w, label='暖执行 (R5)',
                   color='#EF9A9A', edgecolor='black', linewidth=0.5)

    for bar, v in zip(bars1, cold_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f'{v:.1f}', ha='center', va='bottom', fontsize=8)
    for bar, v in zip(bars2, warm_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f'{v:.1f}', ha='center', va='bottom', fontsize=8)

    ax.set_ylabel('时间 (ms)')
    ax.set_title('图 6-13：B3 冷启动 vs 暖执行（1 MB）')
    ax.set_xticks(x)
    ax.set_xticklabels(TOOLCHAINS)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_13_b3_cold_warm.png')


# ── Figure 6-14: B3 peak memory bar chart ───────────────────────────────

def fig_6_14():
    input_sizes = ['1KB', '64KB', '1MB', '16MB']
    input_labels = ['1 KB', '64 KB', '1 MB', '16 MB']

    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(input_sizes))
    w = 0.25

    for i, tc in enumerate(TOOLCHAINS):
        vals = []
        for sz in input_sizes:
            rss = load_wasi_rss('sha256', sz)
            vals.append(rss[tc] / (1024 * 1024))
        ax.bar(x + (i - 1) * w, vals, w, label=tc,
               color=COLORS[tc], edgecolor='black', linewidth=0.5)

    ax.set_xlabel('输入大小')
    ax.set_ylabel('峰值 RSS (MB)')
    ax.set_title('图 6-14：B3 峰值内存（R6）')
    ax.set_xticks(x)
    ax.set_xticklabels(input_labels)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_14_b3_memory.png')


# ── Figure 6-15: B4 cold start bar chart ────────────────────────────────

def fig_6_15():
    ns = ['100', '1000', '10000']
    n_labels = ['100', '1,000', '10,000']

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(ns))
    w = 0.25

    for i, tc in enumerate(TOOLCHAINS):
        vals = []
        for n in ns:
            cold = load_wasi_cold('json', n)
            vals.append(cold[tc]['mean'])
        ax.bar(x + (i - 1) * w, vals, w, label=tc,
               color=COLORS[tc], edgecolor='black', linewidth=0.5)

    ax.set_xlabel('记录数 N')
    ax.set_ylabel('平均冷启动时间 (ms)')
    ax.set_title('图 6-15：B4 冷启动时间（R4）')
    ax.set_xticks(x)
    ax.set_xticklabels(n_labels)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_15_b4_cold.png')


# ── Figure 6-16: B4 warm execution time line chart ─────────────────────

def fig_6_16():
    ns = [100, 1000, 10000]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for tc in TOOLCHAINS:
        means = []
        for n in ns:
            warm = load_wasi_warm('json', str(n))
            means.append(np.mean(warm[tc]))
        ax.plot(ns, means, marker='o', label=tc,
                color=COLORS[tc], linewidth=2, markersize=6)

    ax.set_xlabel('记录数 N')
    ax.set_ylabel('平均暖执行时间 (ms)')
    ax.set_title('图 6-16：B4 暖执行时间随记录数变化')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_xticks(ns)
    ax.set_xticklabels(['100', '1,000', '10,000'])
    fig.tight_layout()
    savefig(fig, 'fig_6_16_b4_warm_line.png')


# ── Figure 6-17: B4 peak memory bar chart ──────────────────────────────

def fig_6_17():
    ns = ['100', '1000', '10000']
    n_labels = ['100', '1,000', '10,000']

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(ns))
    w = 0.25

    for i, tc in enumerate(TOOLCHAINS):
        vals = []
        for n in ns:
            rss = load_wasi_rss('json', n)
            vals.append(rss[tc] / (1024 * 1024))
        ax.bar(x + (i - 1) * w, vals, w, label=tc,
               color=COLORS[tc], edgecolor='black', linewidth=0.5)

    ax.set_xlabel('记录数 N')
    ax.set_ylabel('峰值 RSS (MB)')
    ax.set_title('图 6-17：B4 峰值内存（R6）')
    ax.set_xticks(x)
    ax.set_xticklabels(n_labels)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_17_b4_memory.png')


# ── Figure 6-18: B2 vs B4 cross-scenario comparison ───────────────────

def fig_6_18(browser):
    ns = [100, 1000, 10000]
    n_labels = ['100', '1,000', '10,000']

    b2_medians = {}
    for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        b2_medians[tc_label] = []
        for n in ns:
            entries = _browser_filter(browser, 'json', tc_key, n=n)
            b2_medians[tc_label].append(entries[0]['execution']['median'])

    b4_medians = {}
    for tc in TOOLCHAINS:
        b4_medians[tc] = []
        for n in ns:
            warm = load_wasi_warm('json', str(n))
            b4_medians[tc].append(float(np.median(warm[tc])))

    fig, ax = plt.subplots(figsize=(11, 5))
    n_groups = len(ns)
    n_tc = 3
    total_bars = n_groups * n_tc * 2
    group_gap = 1.5
    tc_gap = 0.6
    bar_w = 0.35

    positions_b2 = []
    positions_b4 = []
    tick_positions = []
    tick_labels_all = []

    pos = 0
    for gi in range(n_groups):
        group_start = pos
        for ti in range(n_tc):
            positions_b2.append(pos)
            positions_b4.append(pos + bar_w)
            pos += tc_gap
        tick_positions.append((group_start + pos - tc_gap) / 2)
        tick_labels_all.append(n_labels[gi])
        pos += group_gap

    tc_colors_alpha = {
        'Go': ('#1f77b4', '#aec7e8'),
        'TinyGo': ('#2ca02c', '#98df8a'),
        'Rust': ('#d62728', '#ff9896'),
    }

    for gi in range(n_groups):
        for ti, tc in enumerate(TOOLCHAINS):
            idx = gi * n_tc + ti
            b2_val = b2_medians[tc][gi]
            b4_val = b4_medians[tc][gi]
            solid, light = tc_colors_alpha[tc]

            ax.bar(positions_b2[idx], b2_val, bar_w, color=solid,
                   edgecolor='black', linewidth=0.5)
            ax.bar(positions_b4[idx], b4_val, bar_w, color=light,
                   edgecolor='black', linewidth=0.5)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='gray', edgecolor='black', label='B2（浏览器）'),
        Patch(facecolor='lightgray', edgecolor='black', label='B4（WASI）'),
    ]
    for tc in TOOLCHAINS:
        solid, _ = tc_colors_alpha[tc]
        legend_elements.append(Patch(facecolor=solid, edgecolor='black', label=tc))

    ax.set_xlabel('记录数 N')
    ax.set_ylabel('中位执行时间 (ms)')
    ax.set_title('图 6-18：B2（浏览器）vs B4（WASI）执行时间跨场景对比')
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels_all)
    ax.set_yscale('log')
    ax.legend(handles=legend_elements, fontsize=8)
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_18_b2_vs_b4.png')


# ── Figure 6-19: SLOC bar chart ─────────────────────────────────────────

def fig_6_19():
    categories = ['共享算法代码', '浏览器入口', 'WASI 入口', '合计']
    go_sloc = [100, 39, 135, 274]
    rust_sloc = [82, 14, 89, 185]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(categories))
    w = 0.3

    bars1 = ax.bar(x - w / 2, go_sloc, w, label='Go / TinyGo',
                   color=COLORS['Go'], edgecolor='black', linewidth=0.5)
    bars2 = ax.bar(x + w / 2, rust_sloc, w, label='Rust',
                   color=COLORS['Rust'], edgecolor='black', linewidth=0.5)

    for bar, v in zip(bars1, go_sloc):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                str(v), ha='center', va='bottom', fontsize=9)
    for bar, v in zip(bars2, rust_sloc):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                str(v), ha='center', va='bottom', fontsize=9)

    ax.set_ylabel('SLOC')
    ax.set_title('图 6-19：源代码行数（E1）对比')
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig(fig, 'fig_6_19_sloc.png')


# ── Figure 6-20: Radar chart ────────────────────────────────────────────

def fig_6_20(browser, metrics):
    """12 dimensions, min-max normalized 0-1 (0=best, 1=worst), smaller area = better."""
    dims = [
        'C1\n二进制体积',
        'C2\n构建时间',
        'R1-B1\n卷积初始化',
        'R2-B1\n卷积执行',
        'R3-B1\n卷积内存',
        'R2-B2\nJSON执行(浏览器)',
        'R4-B3\nSHA冷启动',
        'R5-B3\nSHA暖执行',
        'R5-B4\nJSON执行(WASI)',
        'R6-B3\nSHA峰值内存',
        'E1\n代码行数',
        'E2\n第三方依赖',
    ]

    sizes = metrics['binary_sizes']
    bt = metrics['build_times']

    c1_go = (sizes['conv-browser-go.wasm'] + sizes['json-browser-go.wasm'] +
             sizes['conv-wasi-go.wasm'] + sizes['json-wasi-go.wasm'] +
             sizes['sha-wasi-go.wasm']) / 5
    c1_tg = (sizes['conv-browser-tinygo.wasm'] + sizes['json-browser-tinygo.wasm'] +
             sizes['conv-wasi-tinygo.wasm'] + sizes['json-wasi-tinygo.wasm'] +
             sizes['sha-wasi-tinygo.wasm']) / 5
    c1_rs = (sizes['conv-browser-rust.wasm'] + sizes['json-browser-rust.wasm'] +
             sizes['conv-wasi-rust.wasm'] + sizes['json-wasi-rust.wasm'] +
             sizes['sha-wasi-rust.wasm']) / 5

    c2_go = (bt['go-conv-browser']['median'] + bt['go-json-browser']['median'] +
             bt['go-conv-wasi']['median'] + bt['go-json-wasi']['median'] +
             bt['go-sha-wasi']['median'])
    c2_tg = (bt['tinygo-conv-browser']['median'] + bt['tinygo-json-browser']['median'] +
             bt['tinygo-conv-wasi']['median'] + bt['tinygo-json-wasi']['median'] +
             bt['tinygo-sha-wasi']['median'])
    c2_rs = bt['rust-browser']['median'] + bt['rust-wasi']['median']

    # R1-B1: conv init time (1920×1080, K3)
    r1b1 = {}
    for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        entries = _browser_filter(browser, 'conv', tc_key, w=1920, h=1080, k=3)
        r1b1[tc_label] = entries[0]['initTimeMs']

    # R2-B1: conv execution time (1920×1080, K3 mean)
    r2b1 = {}
    for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        entries = _browser_filter(browser, 'conv', tc_key, w=1920, h=1080, k=3)
        r2b1[tc_label] = entries[0]['execution']['mean']

    # R3-B1: conv memory delta (1920×1080, K3)
    r3b1 = {}
    for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        entries = _browser_filter(browser, 'conv', tc_key, w=1920, h=1080, k=3)
        r3b1[tc_label] = entries[0]['memoryDelta']

    # R2-B2: JSON browser execution time (N=10000 mean)
    r2b2 = {}
    for tc_key, tc_label in [('go', 'Go'), ('tinygo', 'TinyGo'), ('rust', 'Rust')]:
        entries = _browser_filter(browser, 'json', tc_key, n=10000)
        r2b2[tc_label] = entries[0]['execution']['mean']

    # R4-B3: SHA-256 cold start (16 MB mean)
    cold_b3 = load_wasi_cold('sha256', '16MB')
    r4b3 = {tc: cold_b3[tc]['mean'] for tc in TOOLCHAINS}

    # R5-B3: SHA-256 warm execution (16 MB mean)
    warm_b3 = load_wasi_warm('sha256', '16MB')
    r5b3 = {tc: np.mean(warm_b3[tc]) for tc in TOOLCHAINS}

    # R5-B4: JSON WASI warm execution (N=10000 mean)
    warm_b4 = load_wasi_warm('json', '10000')
    r5b4 = {tc: np.mean(warm_b4[tc]) for tc in TOOLCHAINS}

    # R6-B3: SHA-256 peak RSS (16 MB)
    rss_b3 = load_wasi_rss('sha256', '16MB')

    # E1: SLOC
    e1 = {'Go': 274, 'TinyGo': 274, 'Rust': 185}

    # E2: toolchain complexity (third-party dependency count)
    e2 = {'Go': 0, 'TinyGo': 0, 'Rust': 4}

    raw = {
        'Go':     [c1_go, c2_go, r1b1['Go'], r2b1['Go'], r3b1['Go'], r2b2['Go'],
                   r4b3['Go'], r5b3['Go'], r5b4['Go'], rss_b3['Go'], e1['Go'], e2['Go']],
        'TinyGo': [c1_tg, c2_tg, r1b1['TinyGo'], r2b1['TinyGo'], r3b1['TinyGo'], r2b2['TinyGo'],
                   r4b3['TinyGo'], r5b3['TinyGo'], r5b4['TinyGo'], rss_b3['TinyGo'], e1['TinyGo'], e2['TinyGo']],
        'Rust':   [c1_rs, c2_rs, r1b1['Rust'], r2b1['Rust'], r3b1['Rust'], r2b2['Rust'],
                   r4b3['Rust'], r5b3['Rust'], r5b4['Rust'], rss_b3['Rust'], e1['Rust'], e2['Rust']],
    }

    n_dims = len(dims)
    normed = {tc: [0.0] * n_dims for tc in TOOLCHAINS}
    for d in range(n_dims):
        vals = [raw[tc][d] for tc in TOOLCHAINS]
        vmin, vmax = min(vals), max(vals)
        rng = vmax - vmin if vmax != vmin else 1
        for tc in TOOLCHAINS:
            normed[tc][d] = (raw[tc][d] - vmin) / rng

    angles = np.linspace(0, 2 * np.pi, n_dims, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    for tc in TOOLCHAINS:
        values = normed[tc] + normed[tc][:1]
        ax.plot(angles, values, 'o-', linewidth=2, label=tc,
                color=COLORS[tc], markersize=5)
        ax.fill(angles, values, alpha=0.1, color=COLORS[tc])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dims, fontsize=8)
    ax.set_ylim(0, 1.1)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(['0', '0.25', '0.5', '0.75', '1.0'], fontsize=7)
    ax.set_title('图 6-20：三条工具链综合评估雷达图\n（12 维度，0=最优，1=最差，面积越小越优）',
                 fontsize=11, pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    fig.tight_layout()
    savefig(fig, 'fig_6_20_radar.png')


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print('Loading data...')
    metrics = load_build_metrics()
    browser = load_browser_results()

    print('Generating figures...')
    fig_6_1(metrics)
    fig_6_2(metrics)
    fig_6_3(metrics)
    fig_6_4(browser)
    fig_6_5(browser)
    fig_6_6(browser)
    fig_6_7(browser)
    fig_6_8(browser)
    fig_6_9(browser)
    fig_6_10(browser)
    fig_6_11()
    fig_6_12()
    fig_6_13()
    fig_6_14()
    fig_6_15()
    fig_6_16()
    fig_6_17()
    fig_6_18(browser)
    fig_6_19()
    fig_6_20(browser, metrics)

    print(f'\nAll 20 figures saved to {OUT_DIR}/')


if __name__ == '__main__':
    main()
