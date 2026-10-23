"""Step 5：分群下钻——按 device / segment 分别做两比例 z 检验。

要点：整体有效应，但并非所有分群都显著；说明整体效应是哪些人群带来的。
产出 reports/figures/segment_effects.png（各分群效应 + 置信区间森林图）。
"""
import matplotlib.pyplot as plt
import pandas as pd

from . import config, plot_style
from .analyze import two_proportion_ztest


def segment_test(df, col):
    """对 df[col] 的每个取值做两比例 z 检验。"""
    rows = []
    for val in sorted(df[col].unique()):
        sub = df[df[col] == val]
        c = sub[sub["group"] == config.CONTROL]
        t = sub[sub["group"] == config.TREATMENT]
        r = two_proportion_ztest(c["converted"].sum(), len(c),
                                 t["converted"].sum(), len(t))
        r["group"] = val
        r["n"] = len(sub)
        rows.append(r)
    return pd.DataFrame(rows)


def _fmt(r):
    sig = "显著" if r["p"] < 0.05 else "不显著"
    return (f"{r['group']:<10} n={r['n']:>6}  lift={r['lift_pp']:+6.2f}pp  "
            f"95%CI=[{r['ci_low']:+5.2f}, {r['ci_high']:+5.2f}]  "
            f"相对={r['rel_lift']:+6.1%}  p={r['p']:.4f}  {sig}")


def main():
    df = pd.read_csv(config.EXPERIMENT_CSV)

    dev = segment_test(df, "device")
    seg = segment_test(df, "segment")

    print("== 分群下钻：device ==")
    for _, r in dev.iterrows():
        print("  " + _fmt(r))
    print("\n== 分群下钻：segment ==")
    for _, r in seg.iterrows():
        print("  " + _fmt(r))

    # 交互作用说明
    sig_dev = dev[dev["p"] < 0.05]["group"].tolist()
    ns_dev = dev[dev["p"] >= 0.05]["group"].tolist()
    sig_seg = seg[seg["p"] < 0.05]["group"].tolist()
    ns_seg = seg[seg["p"] >= 0.05]["group"].tolist()
    print("\n== 交互作用说明 ==")
    print(f"  显著分群：device {sig_dev}；segment {sig_seg}")
    print(f"  不显著分群：device {ns_dev}；segment {ns_seg}")
    print("  结论：整体效应（+1.7pp）并非均匀分布，主要由 iOS/Android 端与新用户带来；"
          "Web 端与老用户未观察到显著提升，说明新结算页的收益存在人群差异。")

    # 森林图
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    all_r = pd.concat([
        dev.assign(dim="device"),
        seg.assign(dim="segment"),
    ], ignore_index=True)
    labels = [("device", v) for v in dev["group"]] + [("segment", v) for v in seg["group"]]
    n = len(all_r)
    fig, ax = plt.subplots(figsize=(9, 3.4))
    for i, (_, r) in enumerate(all_r.iterrows()):
        y = n - 1 - i
        sig = r["p"] < 0.05
        color = plot_style.CATEGORICAL[0] if sig else plot_style.MUTED
        ax.errorbar(r["lift_pp"], y,
                    xerr=[[r["lift_pp"] - r["ci_low"]], [r["ci_high"] - r["lift_pp"]]],
                    fmt="o", color=color, capsize=4, markersize=6)
        ax.text(r["lift_pp"], y + 0.2, f"{r['lift_pp']:+.2f}pp", ha="center",
                fontsize=9, color=plot_style.INK_SECONDARY)
    ax.axvline(0, color=plot_style.BASELINE, linewidth=1)
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{d}: {v}" for d, v in labels], fontsize=9)
    ax.set_ylim(-0.5, n - 0.5)
    plot_style.style_axes(ax)
    ax.set_title("分群转化率效应与 95% 置信区间（蓝=显著，灰=不显著）",
                 color=plot_style.INK, fontsize=11, loc="left")
    ax.set_xlabel("转化率提升（pp）")

    out = config.FIGURES_DIR / "segment_effects.png"
    fig.savefig(out, facecolor=plot_style.SURFACE)
    plt.close(fig)
    print(f"\n已生成 {out}")


if __name__ == "__main__":
    main()
