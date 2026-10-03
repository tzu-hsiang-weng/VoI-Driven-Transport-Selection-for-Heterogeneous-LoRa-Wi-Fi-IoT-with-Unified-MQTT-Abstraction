#!/usr/bin/env python3
"""
plot_paper_figs.py — 一鍵生成 GCCE 論文 Fig 3 和 Fig 5

不需要 experiments/ 資料夾,資料已 hardcode 在程式裡(你的真實實驗結果)

使用方式:
    python plot_paper_figs.py

產出:
    fig3_strategy_comparison.pdf
    fig3_strategy_comparison.png
    fig5_link_class_distribution.pdf
    fig5_link_class_distribution.png

依賴:
    pip install matplotlib numpy
"""

import sys
try:
    import numpy as np
    import matplotlib.pyplot as plt
except ImportError:
    print("[ERROR] 請先安裝: pip install matplotlib numpy")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# 你的真實實驗資料 (從 compute_energy.py 跑出的結果)
# ═══════════════════════════════════════════════════════════════
DATA = [
    {
        "strategy": "Always-LoRa",
        "avg_power_mw": 64.51,
        "battery_days": 8.4,
        "lc_counts": {"B": 216, "D": 373},   # 只用 B/D
    },
    {
        "strategy": "Always-WiFi",
        "avg_power_mw": 177.85,
        "battery_days": 3.0,
        "lc_counts": {"A": 821, "C": 427},   # 只用 A/C
    },
    {
        "strategy": "Periodic",
        "avg_power_mw": 31.70,
        "battery_days": 17.0,
        "lc_counts": {"A": 12, "B": 199, "D": 329},  # A/B/D 三種
    },
    {
        "strategy": "VoI-Driven",
        "avg_power_mw": 86.08,
        "battery_days": 6.3,
        "lc_counts": {"A": 35, "B": 84, "C": 251, "D": 369},  # 全部 4 種
    },
]

# ═══════════════════════════════════════════════════════════════
# IEEE 風格設定
# ═══════════════════════════════════════════════════════════════
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})

# 4 策略統一配色 (色盲友善)
COLORS = {
    "Always-LoRa":  "#2E7D32",   # 綠
    "Always-WiFi":  "#C62828",   # 紅
    "Periodic":     "#F9A825",   # 黃
    "VoI-Driven":   "#1565C0",   # 藍 (主角)
}

# Link class 配色與標籤
LC_COLORS = {
    "A": "#C62828",  # WiFi-STD 紅
    "B": "#43A047",  # LoRa-1x 綠
    "C": "#FB8C00",  # WiFi-ECO 橘
    "D": "#1E88E5",  # LoRa-2x 藍
}
LC_LABELS = {
    "A": "A: WiFi-STD",
    "B": r"B: LoRa-1$\times$",
    "C": "C: WiFi-ECO",
    "D": r"D: LoRa-2$\times$ (TimeDiv)",
}


# ═══════════════════════════════════════════════════════════════
# Fig 3: 4 策略 Avg Power + Battery Life (雙 y 軸)
# ═══════════════════════════════════════════════════════════════
def plot_fig3():
    fig, ax1 = plt.subplots(figsize=(5.5, 3.2))

    strategies = [d["strategy"] for d in DATA]
    powers = [d["avg_power_mw"] for d in DATA]
    batteries = [d["battery_days"] for d in DATA]
    colors = [COLORS[s] for s in strategies]

    x = np.arange(len(strategies))
    width = 0.55

    # 主柱狀: Avg Power
    bars = ax1.bar(x, powers, width, color=colors, edgecolor="black",
                   linewidth=0.5, alpha=0.9, zorder=3)
    ax1.set_xlabel("Strategy", fontweight="bold")
    ax1.set_ylabel("Average Power (mW)", color="#333", fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(strategies)
    ax1.tick_params(axis="y", labelcolor="#333")
    ax1.grid(axis="y", linestyle=":", alpha=0.4, zorder=0)
    ax1.set_axisbelow(True)
    ax1.set_ylim(0, max(powers) * 1.18)

    # 在柱上方標 mW
    for bar, p in zip(bars, powers):
        ax1.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + max(powers)*0.02,
                 f"{p:.1f}", ha="center", va="bottom",
                 fontsize=8, fontweight="bold")

    # 第二 y 軸: Battery Life
    ax2 = ax1.twinx()
    ax2.plot(x, batteries, "o-", color="#444", linewidth=1.6,
             markersize=7, markerfacecolor="white",
             markeredgecolor="#444", markeredgewidth=1.5,
             label="Battery Life", zorder=5)
    ax2.set_ylabel("Battery Life (days)", color="#222", fontweight="bold")
    ax2.tick_params(axis="y", labelcolor="#222")
    ax2.set_ylim(0, max(batteries) * 1.18)

    # 在點旁邊標天數
    for xi, b in zip(x, batteries):
        ax2.text(xi + 0.16, b, f"{b:.1f}d", fontsize=7,
                 va="center", color="#222")

    ax1.set_title("Fig. 3. Four-Strategy Energy and Battery Life Comparison\n"
                  "(30-min Steady-State Operation, Model-Based Estimation)",
                  fontsize=9.5, pad=10)

    # VoI 標粗藍
    for tick_label in ax1.get_xticklabels():
        if "VoI" in tick_label.get_text():
            tick_label.set_fontweight("bold")
            tick_label.set_color(COLORS["VoI-Driven"])

    plt.tight_layout()
    for ext in ("pdf", "png"):
        path = f"fig3_strategy_comparison.{ext}"
        plt.savefig(path)
        print(f"  → {path}")
    plt.close()


# ═══════════════════════════════════════════════════════════════
# Fig 5: Link Class Distribution (堆疊百分比)
# ═══════════════════════════════════════════════════════════════
def plot_fig5():
    fig, ax = plt.subplots(figsize=(5.8, 3.3))

    strategies = [d["strategy"] for d in DATA]
    x = np.arange(len(strategies))
    width = 0.6

    # 計算每個策略的百分比分布
    lc_order = ["A", "C", "B", "D"]   # WiFi 系列在下,LoRa 系列在上
    bottoms = np.zeros(len(strategies))

    for lc in lc_order:
        values = []
        for d in DATA:
            total = sum(d["lc_counts"].values()) or 1
            pct = d["lc_counts"].get(lc, 0) / total * 100
            values.append(pct)
        if max(values) < 0.1:
            continue   # 完全沒用到的 lc 不畫

        ax.bar(x, values, width, bottom=bottoms,
               color=LC_COLORS[lc], edgecolor="white", linewidth=0.8,
               label=LC_LABELS[lc], zorder=3)

        # 在每段中央標百分比 (>=5% 才標,避免擁擠)
        for xi, v, b in zip(x, values, bottoms):
            if v >= 5.0:
                ax.text(xi, b + v/2, f"{v:.0f}%",
                        ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
        bottoms += np.array(values)

    ax.set_xlabel("Strategy", fontweight="bold")
    ax.set_ylabel("Link Class Distribution (%)", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(strategies)
    ax.set_ylim(0, 105)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.grid(axis="y", linestyle=":", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18),
              ncol=4, frameon=False, fontsize=7.5)

    # VoI 標粗藍
    for tick_label in ax.get_xticklabels():
        if "VoI" in tick_label.get_text():
            tick_label.set_fontweight("bold")
            tick_label.set_color(COLORS["VoI-Driven"])

    ax.set_title("Fig. 5. Link Class Distribution Across Strategies\n"
                 "(VoI-Driven Adaptively Allocates Transport per State)",
                 fontsize=9.5, pad=10)

    plt.tight_layout()
    for ext in ("pdf", "png"):
        path = f"fig5_link_class_distribution.{ext}"
        plt.savefig(path)
        print(f"  → {path}")
    plt.close()


# ═══════════════════════════════════════════════════════════════
def main():
    print("[plot] generating GCCE paper figures from hardcoded data\n")

    print("[Fig 3] Strategy Comparison (Avg Power + Battery Life)")
    plot_fig3()

    print("\n[Fig 5] Link Class Distribution")
    plot_fig5()

    print("\n[plot] done!")
    print("  - fig3_strategy_comparison.pdf  (放進 LaTeX 用)")
    print("  - fig3_strategy_comparison.png  (預覽用)")
    print("  - fig5_link_class_distribution.pdf")
    print("  - fig5_link_class_distribution.png")


if __name__ == "__main__":
    main()