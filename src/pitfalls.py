"""Step 6：陷阱复盘——Peeking（偷看数据）与多重比较。

1. Peeking：按天累计计算 p 值，画出「p 值随天数变化」曲线，说明为什么
   「p<0.05 就停」会放大假阳性（并用蒙特卡洛模拟量化）。
2. 多重比较：对多个分群各做一次检验，不做校正时的假阳性率；用 Bonferroni /
   FDR 校正后结论有何变化。

产出 reports/figures/peeking_curve.png。
"""
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

from . import config, plot_style
from .analyze import two_proportion_ztest


def peeking_curve(df):
    """按天累计的 p 值曲线（真实 treatment vs control）。"""
    d = df.copy()
    d["day"] = (pd.to_datetime(d["exposed_at"]) - pd.Timestamp(config.EXPOSED_START)).dt.days
    days = sorted(d["day"].unique())
    ps, ns = [], []
    for day in days:
        sub = d[d["day"] <= day]
        c = sub[sub["group"] == config.CONTROL]
        t = sub[sub["group"] == config.TREATMENT]
        r = two_proportion_ztest(c["converted"].sum(), len(c),
                                 t["converted"].sum(), len(t))
        ps.append(r["p"])
        ns.append(len(sub))
    return np.array(days), np.array(ps), np.array(ns)


def simulate_peeking_fpr(n_per_day=872, n_days=14, p=0.0796, n_sim=2000, seed=0):
    """蒙特卡洛量化 peeking 的假阳性率。

    模拟一个「无真实效应」的实验（两组转化率都 = p），每天偷看一次、
    一旦 p<0.05 就停，统计最终误判「显著」的比例。
    """
    rng = np.random.default_rng(seed)
    false_positive = 0
    for _ in range(n_sim):
        cA = cB = nA = nB = 0
        stopped = False
        for _ in range(n_days):
            cA += rng.binomial(n_per_day, p)
            cB += rng.binomial(n_per_day, p)
            nA += n_per_day
            nB += n_per_day
            p_pool = (cA + cB) / (nA + nB)
            se = math.sqrt(p_pool * (1 - p_pool) * (1 / nA + 1 / nB))
            z = abs((cA / nA - cB / nB) / se)
            pval = 2 * (1 - norm.cdf(z))
            if pval < 0.05:
                stopped = True
                break
        false_positive += stopped
    return false_positive / n_sim


def multiple_comparison(df):
    """对 3 设备 + 2 新老 + 7 城市共 12 个分群各做一次检验，演示多重比较。"""
    rows = []
    for col in ["device", "segment", "city"]:
        for val in sorted(df[col].unique()):
            sub = df[df[col] == val]
            c = sub[sub["group"] == config.CONTROL]
            t = sub[sub["group"] == config.TREATMENT]
            r = two_proportion_ztest(c["converted"].sum(), len(c),
                                     t["converted"].sum(), len(t))
            r["dim"] = col
            r["group"] = val
            rows.append(r)
    res = pd.DataFrame(rows)
    m = len(res)
    # Bonferroni 校正阈值
    res["bonf_sig"] = res["p"] < 0.05 / m
    # FDR（Benjamini-Hochberg）
    res = res.sort_values("p").reset_index(drop=True)
    res["rank"] = np.arange(1, m + 1)
    res["bh_threshold"] = 0.05 * res["rank"] / m
    res["fdr_sig"] = res["p"] <= res["bh_threshold"]
    return res


def main():
    df = pd.read_csv(config.EXPERIMENT_CSV)

    # ---- Peeking ----
    days, ps, ns = peeking_curve(df)
    print("== Peeking：p 值随累计天数的变化 ==")
    for d, p, n in zip(days, ps, ns):
        print(f"  第 {d + 1:>2} 天: 累计 n={n:>6}  p={p:.4f}  {'< 0.05' if p < 0.05 else ''}")

    fpr = simulate_peeking_fpr()
    print(f"\n蒙特卡洛模拟（无真实效应、每天偷看、p<0.05 就停）：")
    print(f"  假阳性率 = {fpr:.1%}（而非名义上的 5%）")
    print("  说明：反复偷看会让整体第一类错误率显著高于 α=0.05。")

    # peeking 曲线图
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(days + 1, ps, marker="o", color=plot_style.CATEGORICAL[0], linewidth=2)
    ax.axhline(0.05, color=plot_style.CATEGORICAL[3], linewidth=1.5, linestyle="--")
    ax.text(days[-1] * 0.7, 0.055, "α = 0.05", color=plot_style.CATEGORICAL[3], fontsize=9)
    plot_style.style_axes(ax)
    ax.set_title("Peeking：累计 p 值随实验天数的变化", color=plot_style.INK, fontsize=12, loc="left")
    ax.set_xlabel("实验天数")
    ax.set_ylabel("累计 p 值")
    ax.set_ylim(0, 1)

    out = config.FIGURES_DIR / "peeking_curve.png"
    fig.savefig(out, facecolor=plot_style.SURFACE)
    plt.close(fig)
    print(f"\n已生成 {out}")

    # ---- 多重比较 ----
    res = multiple_comparison(df)
    m = len(res)
    print(f"\n== 多重比较：{m} 个分群各做一次检验 ==")
    print("不做校正时 p<0.05 的分群：")
    raw_sig = res[res["p"] < 0.05]
    if raw_sig.empty:
        print("  （无）")
    for _, r in raw_sig.iterrows():
        print(f"  {r['dim']}:{r['group']}  lift={r['lift_pp']:+.2f}pp  p={r['p']:.4f}")
    print(f"\nBonferroni 校正（阈值 0.05/{m}={0.05/m:.5f}）后仍显著：")
    bonf = res[res["bonf_sig"]]
    if bonf.empty:
        print("  （无）")
    for _, r in bonf.iterrows():
        print(f"  {r['dim']}:{r['group']}  p={r['p']:.4f}")
    print(f"\nFDR（Benjamini-Hochberg）校正后仍显著：")
    fdr = res[res["fdr_sig"]]
    if fdr.empty:
        print("  （无）")
    for _, r in fdr.iterrows():
        print(f"  {r['dim']}:{r['group']}  p={r['p']:.4f}")

    # 期望「至少 1 个分群偶然显著」的说明
    print(f"\n不做校正时，{m} 次检验的「至少一次假阳性」概率 = {1 - 0.95**m:.1%}，"
          f"因此看到的个别显著分群可能只是偶然。")


if __name__ == "__main__":
    main()
