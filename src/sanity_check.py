"""Step 3：随机性与平衡性检查（SRM + 分流前指标平衡 + 分组构成）。

意义：如果随机化有问题，后面所有结论都不可信。
1. SRM 检查：两组人数是否符合 50/50（卡方拟合优度），p > 0.001 视为通过；
2. 分流前指标平衡：pre_30d_orders / pre_30d_gmv 的均值差异（Welch t 检验）；
3. 分组构成：segment / device / city 的分布是否一致（卡方独立性检验）。
"""
import pandas as pd
from scipy import stats

from . import config


def _verdict(p, threshold=0.05, srm=False):
    if srm:
        return "PASS" if p > 0.001 else "FAIL"
    return "PASS" if p > threshold else "WARN"


def check_srm(df):
    n_control = (df["group"] == config.CONTROL).sum()
    n_treatment = (df["group"] == config.TREATMENT).sum()
    n = len(df)
    chi2, p = stats.chisquare([n_control, n_treatment], [n / 2, n / 2])
    print("[检查1] SRM（样本比例）")
    print(f"  control={n_control}, treatment={n_treatment}, 比例={n_control/n:.3f}:{n_treatment/n:.3f}")
    print(f"  卡方统计量={chi2:.3f}, p={p:.4f}  ->  {_verdict(p, srm=True)}")
    return _verdict(p, srm=True), p


def check_balance(df):
    print("[检查2] 分流前指标平衡（Welch t 检验）")
    verdicts = []
    for col in ["pre_30d_orders", "pre_30d_gmv"]:
        c = df[df["group"] == config.CONTROL][col]
        t = df[df["group"] == config.TREATMENT][col]
        tstat, p = stats.ttest_ind(c, t, equal_var=False)
        v = _verdict(p)
        verdicts.append(v)
        print(f"  {col}: control 均值={c.mean():.3f}, treatment 均值={t.mean():.3f}, "
              f"t={tstat:.3f}, p={p:.4f}  ->  {v}")
    return "PASS" if all(v == "PASS" for v in verdicts) else "WARN"


def check_composition(df):
    print("[检查3] 分组构成（segment / device / city 分布一致性）")
    verdicts = []
    for col in ["segment", "device", "city"]:
        ct = pd.crosstab(df["group"], df[col])
        chi2, p, _, _ = stats.chi2_contingency(ct)
        v = _verdict(p)
        verdicts.append(v)
        print(f"  {col}: 卡方 p={p:.4f}  ->  {v}")
    return "PASS" if all(v == "PASS" for v in verdicts) else "WARN"


def main():
    df = pd.read_csv(config.EXPERIMENT_CSV)
    print("=" * 60)
    print("随机性与平衡性检查报告")
    print("=" * 60)

    v1, _ = check_srm(df)
    v2 = check_balance(df)
    v3 = check_composition(df)

    print("-" * 60)
    results = [v1, v2, v3]
    print(f"汇总: SRM={v1}, 平衡性={v2}, 构成={v3}")
    if "FAIL" in results:
        print("存在 FAIL：随机化可能有问题，后续结论不可信，请先排查分流。")
    else:
        print("随机化有效：可进入主指标检验。")


if __name__ == "__main__":
    main()
