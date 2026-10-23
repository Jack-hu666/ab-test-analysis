"""Step 2：实验设计——样本量与功效计算。

两比例（two-proportion）z 检验的每组样本量公式：

    n = [ Z_{α/2}·√(2·p̄·(1-p̄)) + Z_β·√(p0·(1-p0) + p1·(1-p1)) ]² / (p1 - p0)²

其中：
  - p0 = 对照组基线转化率（8%）
  - p1 = p0 + MDE，最小可检测效应的目标转化率（9%）
  - p̄ = (p0 + p1)/2，两组的合并比例（8.5%）
  - Z_{α/2}：显著性水平 α 下的双侧分位数（α=0.05 → 1.96），
    控制「没有效应却误判显著」的第一类错误
  - Z_β：功效 power 对应的分位数（power=0.8 → 0.8416），
    控制「有效应却漏检」的第二类错误（β = 1 - power = 0.2）
  - 分子第一项是原假设下的抽样波动，第二项是备择假设下的抽样波动；
    分母 (p1-p0)² 是待检测的效应量平方。

输出：每组所需样本量、总样本量、预计实验周期，以及 MDE vs 样本量曲线。
"""
import math

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

from . import config, plot_style

DAILY_TRAFFIC = 1800  # 每日进入结算页的可用用户流（用于估算实验周期）


def required_n_per_group(p0, mde, alpha, power):
    """两比例 z 检验每组所需样本量（双侧）。"""
    p1 = p0 + mde
    pbar = (p0 + p1) / 2
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    numerator = z_alpha * math.sqrt(2 * pbar * (1 - pbar)) + \
        z_beta * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))
    return numerator ** 2 / (mde ** 2)


def main():
    p0 = config.BASELINE_CONVERSION
    alpha = config.ALPHA
    power = config.POWER
    mde = config.MDE

    n = required_n_per_group(p0, mde, alpha, power)
    total = 2 * n
    days = math.ceil(total / DAILY_TRAFFIC)

    print("== 实验设计（样本量与功效）==")
    print(f"基线转化率 p0       = {p0:.1%}")
    print(f"最小可检测效应 MDE  = {mde:.2%}（绝对 +1pp）")
    print(f"显著性水平 α        = {alpha}")
    print(f"统计功效 power      = {power}")
    print(f"每组所需样本量      = {n:.0f}")
    print(f"总样本量            = {total:.0f}")
    print(f"预计实验周期        = {days} 天（按日流量 {DAILY_TRAFFIC} 估算）")
    print(f"\n注：该数值与 gen_data.py 默认每组 {config.N_PER_GROUP} 人对得上。")

    # MDE vs 样本量曲线
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    mdes = np.linspace(0.003, 0.03, 200)
    ns = [required_n_per_group(p0, m, alpha, power) for m in mdes]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(mdes * 100, np.array(ns) / 1000, color=plot_style.CATEGORICAL[0], linewidth=2)
    # 标注当前设计点
    ax.scatter([mde * 100], [n / 1000], color=plot_style.CATEGORICAL[1], zorder=5, s=40)
    ax.annotate(f"MDE=1pp\n每组 {n:.0f} 人",
                xy=(mde * 100, n / 1000), xytext=(mde * 100 + 0.5, n / 1000 * 1.6),
                fontsize=9, color=plot_style.INK_SECONDARY,
                arrowprops=dict(arrowstyle="->", color=plot_style.MUTED))
    plot_style.style_axes(ax)
    ax.set_title("最小可检测效应（MDE）与每组样本量", color=plot_style.INK, fontsize=12, loc="left")
    ax.set_xlabel("MDE（绝对百分点）")
    ax.set_ylabel("每组样本量（千人）")

    out = config.FIGURES_DIR / "power_curve.png"
    fig.savefig(out, facecolor=plot_style.SURFACE)
    plt.close(fig)
    print(f"已生成 {out}")


if __name__ == "__main__":
    main()
