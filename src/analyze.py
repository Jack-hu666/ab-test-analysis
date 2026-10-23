"""Step 4：主指标检验（转化率 + 人均支付金额），并与 SQL 汇总交叉验证。

两个主指标：
1. 转化率（比例指标）：两比例 z 检验，双侧；
2. 人均支付金额（连续指标，转化用户客单价）：先做正态性/方差齐性判断，
   再选择 t 检验或 Mann-Whitney U。

产出 reports/figures/conversion_ci.png（效应量 + 置信区间）。
"""
import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from . import config, plot_style
from .sql_utils import load_queries


# ---------------------------------------------------------------------------
# 转化率：两比例 z 检验（双侧）
# 原假设 H0：两组转化率无差异 p1 = p0；备择假设 H1：p1 != p0。
# 用双侧是因为我们只关心「是否有差异」，不预先假设新结算页一定更好（保守）。
# ---------------------------------------------------------------------------
def two_proportion_ztest(c0, n0, c1, n1, alpha=0.05):
    p0 = c0 / n0
    p1 = c1 / n1
    p_pool = (c0 + c1) / (n0 + n1)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n0 + 1 / n1))
    z = (p1 - p0) / se_pool
    p = 2 * (1 - stats.norm.cdf(abs(z)))

    # 置信区间用「非合并」标准误（两比例差的常用做法）
    se_diff = np.sqrt(p0 * (1 - p0) / n0 + p1 * (1 - p1) / n1)
    z_a = stats.norm.ppf(1 - alpha / 2)
    lift_pp = (p1 - p0) * 100
    ci_low = (p1 - p0 - z_a * se_diff) * 100
    ci_high = (p1 - p0 + z_a * se_diff) * 100
    return {
        "p0": p0, "p1": p1, "lift_pp": lift_pp,
        "rel_lift": (p1 - p0) / p0, "z": z, "p": p,
        "ci_low": ci_low, "ci_high": ci_high,
    }


def amount_test(ctrl, trt):
    """连续指标检验：正态性 -> 方差齐性 -> 选检验方法。"""
    # 正态性（Shapiro-Wilk）
    sh_p0 = stats.shapiro(ctrl).pvalue
    sh_p1 = stats.shapiro(trt).pvalue
    normal = sh_p0 > 0.05 and sh_p1 > 0.05
    # 方差齐性（Levene）
    lev_p = stats.levene(ctrl, trt).pvalue
    equal_var = lev_p > 0.05

    if normal and equal_var:
        method = "Student t 检验（正态且方差齐）"
        stat, p = stats.ttest_ind(ctrl, trt, equal_var=True)
    elif normal:
        method = "Welch t 检验（正态但方差不齐）"
        stat, p = stats.ttest_ind(ctrl, trt, equal_var=False)
    else:
        method = "Mann-Whitney U 检验（非正态，非参数）"
        stat, p = stats.mannwhitneyu(ctrl, trt, alternative="two-sided")

    # 效应量：相对提升 + bootstrap 95% CI
    rel = (trt.mean() - ctrl.mean()) / ctrl.mean()
    rng = np.random.default_rng(0)
    diffs = []
    for _ in range(2000):
        bc = rng.choice(ctrl, size=len(ctrl), replace=True)
        bt = rng.choice(trt, size=len(trt), replace=True)
        diffs.append((bt.mean() - bc.mean()) / bc.mean())
    ci = np.percentile(diffs, [2.5, 97.5])
    return {
        "method": method, "p": p, "stat": stat,
        "mean_ctrl": ctrl.mean(), "mean_trt": trt.mean(),
        "rel_lift": rel, "ci_low": ci[0], "ci_high": ci[1],
        "shapiro_p": (sh_p0, sh_p1), "levene_p": lev_p,
    }


def sql_crosscheck(df):
    """把数据写入内存 SQLite，跑 sql/summary.sql，与 pandas 结果核对。"""
    conn = sqlite3.connect(":memory:")
    df.to_sql("experiment", conn, index=False)
    q = load_queries(config.ROOT / "sql" / "summary.sql")

    sql_cvr = pd.read_sql(q["conversion_by_group"], conn).set_index("group")
    sql_aov = pd.read_sql(q["amount_converted_by_group"], conn).set_index("group")
    conn.close()

    pd_cvr = df.groupby("group").agg(n=("converted", "count"),
                                     converted=("converted", "sum"))
    pd_cvr["cvr"] = pd_cvr["converted"] / pd_cvr["n"]
    pd_aov = df[df.converted == 1].groupby("group").agg(
        n_converted=("amount", "count"), avg_aov=("amount", "mean"))

    ok_cvr = np.allclose(sql_cvr["cvr"].sort_index(), pd_cvr["cvr"].sort_index(), atol=1e-6)
    ok_aov = np.allclose(sql_aov["avg_aov"].sort_index(), pd_aov["avg_aov"].sort_index(), atol=1e-3)
    print(f"[SQL 交叉验证] 转化率一致={ok_cvr}, 人均金额一致={ok_aov}")
    return sql_cvr, sql_aov


def main():
    df = pd.read_csv(config.EXPERIMENT_CSV)
    ctrl = df[df["group"] == config.CONTROL]
    trt = df[df["group"] == config.TREATMENT]

    # 1. 转化率
    r = two_proportion_ztest(ctrl["converted"].sum(), len(ctrl),
                             trt["converted"].sum(), len(trt))
    print("== 主指标 1：转化率 ==")
    print(f"  control: {r['p0']:.4%}   treatment: {r['p1']:.4%}")
    print(f"  绝对提升: {r['lift_pp']:.3f}pp   相对提升: {r['rel_lift']:.2%}")
    print(f"  95% CI: [{r['ci_low']:.3f}, {r['ci_high']:.3f}]pp")
    print(f"  z={r['z']:.3f}, p={r['p']:.5f}  ->  {'显著' if r['p'] < 0.05 else '不显著'}")

    # 2. 人均支付金额（转化用户）
    a = amount_test(ctrl[ctrl.converted == 1]["amount"], trt[trt.converted == 1]["amount"])
    print("\n== 主指标 2：人均支付金额（转化用户）==")
    print(f"  Shapiro p: control={a['shapiro_p'][0]:.4f}, treatment={a['shapiro_p'][1]:.4f} -> "
          f"{'正态' if a['shapiro_p'][0] > 0.05 and a['shapiro_p'][1] > 0.05 else '非正态'}")
    print(f"  Levene p={a['levene_p']:.4f}")
    print(f"  选择方法: {a['method']}")
    print(f"  control 均值={a['mean_ctrl']:.2f}, treatment 均值={a['mean_trt']:.2f}")
    print(f"  相对提升: {a['rel_lift']:.3%}, 95% CI(bootstrap): [{a['ci_low']:.3%}, {a['ci_high']:.3%}]")
    print(f"  p={a['p']:.5f}  ->  {'显著' if a['p'] < 0.05 else '不显著'}")

    # 3. SQL 交叉验证
    print("\n== SQL 交叉验证 ==")
    sql_cvr, sql_aov = sql_crosscheck(df)
    print(sql_cvr.to_string())
    print(sql_aov.to_string())

    # 4. 图：效应量 + 置信区间（森林图）
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 3.2))
    rows = [
        ("转化率提升（pp）", r["lift_pp"], r["ci_low"], r["ci_high"]),
        ("人均金额提升（%）", a["rel_lift"] * 100, a["ci_low"] * 100, a["ci_high"] * 100),
    ]
    for i, (label, est, lo, hi) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.errorbar(est, y, xerr=[[est - lo], [hi - est]], fmt="o",
                    color=plot_style.CATEGORICAL[0], capsize=4, markersize=6)
        ax.text(est, y + 0.18, f"{est:.2f} [{lo:.2f}, {hi:.2f}]",
                ha="center", fontsize=9, color=plot_style.INK_SECONDARY)
    ax.axvline(0, color=plot_style.BASELINE, linewidth=1)
    ax.set_yticks([0, 1])
    ax.set_yticklabels([rows[1][0], rows[0][0]], fontsize=9)
    ax.set_ylim(-0.5, 1.5)
    plot_style.style_axes(ax)
    ax.set_title("主指标效应量与 95% 置信区间", color=plot_style.INK, fontsize=12, loc="left")
    ax.set_xlabel("效应量（pp / %）")

    out = config.FIGURES_DIR / "conversion_ci.png"
    fig.savefig(out, facecolor=plot_style.SURFACE)
    plt.close(fig)
    print(f"\n已生成 {out}")


if __name__ == "__main__":
    main()
