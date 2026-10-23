"""Step 1：生成 A/B 实验模拟数据（data/experiment.csv）。

场景：结算页从「单页表单」改为「三步引导式」，检验是否提升支付转化率。
group：control（旧版单页）/ treatment（新版三步引导式），50/50 随机分流。

--------------------------------------------------------------------------
数据设计的「真相」（仅写在此处代码注释与 docs/decisions.md，README 不剧透，
让分析流程自己去发现结论）：
- 基线：control 转化率约 8.0%，转化用户客单价约 ¥120
- 真实效应：
  * 整体转化率：treatment 提升约 +1.7pp（相对 +20% 左右）
  * 转化用户人均支付金额：treatment 提升约 +2%
- 分群差异（让 Step5 下钻有结论）：
  * iOS / Android：转化率提升约 +2.0pp（显著）
  * Web：提升约 +0.3pp（不显著）
  * new（新用户）：提升约 +2.5pp（显著）
  * returning（老用户）：提升约 +0.6pp（不显著）
- 噪声：二项抽样天然提供统计波动；金额加对数正态扰动
- 埋点：exposed_at 按 14 天分布，供 Step6 演示 peeking
--------------------------------------------------------------------------
"""
import argparse

import numpy as np
import pandas as pd

from . import config

# 每个 (device, segment) 组合在 treatment 组的转化率提升（百分点）
# 数值经过设计：整体加权后约 +1.7pp；设备层面 iOS/Android 约 +2.0pp（显著）、
# Web 约 +0.3pp（不显著）；segment 层面 new 约 +2.5pp（显著）、
# returning 约 +0.6pp（不显著）。分群差异是分析结论的来源。
LIFT_PP = {
    ("ios", "new"): 3.0, ("ios", "returning"): 0.7,
    ("android", "new"): 3.0, ("android", "returning"): 0.7,
    ("web", "new"): 0.5, ("web", "returning"): 0.1,
}
SEGMENT_PROB = {"new": 0.6, "returning": 0.4}
DEVICE_PROB = {"ios": 0.40, "android": 0.40, "web": 0.20}

AMOUNT_LIFT = 0.02          # treatment 转化用户金额 +2%
BASE_AMOUNT = 120.0         # 基础客单价（元）


def gen(n_per_group):
    rng = np.random.default_rng(config.SEED)
    n = n_per_group * 2

    # 50/50 随机分流
    group = np.array([config.CONTROL] * n_per_group + [config.TREATMENT] * n_per_group)
    rng.shuffle(group)

    device = rng.choice(config.DEVICES, size=n, p=[DEVICE_PROB[d] for d in config.DEVICES])
    segment = rng.choice(config.SEGMENTS, size=n, p=[SEGMENT_PROB[s] for s in config.SEGMENTS])
    city = rng.choice(config.CITIES, size=n)

    # 实验前 30 天协变量（随机化保证两组平衡）
    pre_30d_orders = rng.poisson(2.0, size=n)
    pre_30d_gmv = np.maximum(0, pre_30d_orders * 90 + rng.normal(0, 100, size=n)).round(2)

    # 进入实验时间：跨 14 天，每天均匀分布（供 peeking 演示）
    day_offset = rng.integers(0, config.N_DAYS, size=n)
    exposed_at = (
        pd.Timestamp(config.EXPOSED_START)
        + pd.to_timedelta(day_offset, unit="D")
        + pd.to_timedelta(rng.uniform(0, 86400, size=n), unit="s")
    )

    # 转化：control 恒为基线；treatment 按 (device, segment) 加提升
    lift = np.array([LIFT_PP[(d, s)] / 100 for d, s in zip(device, segment)])
    p_convert = np.where(group == config.TREATMENT, config.BASELINE_CONVERSION + lift,
                         config.BASELINE_CONVERSION)
    converted = (rng.random(n) < p_convert).astype(int)

    # 金额：仅转化用户有值；treatment 金额 +2%；对数正态扰动 + 组内中心化。
    # 组内中心化让「control 均值 = 120、treatment 均值 = 122.4」在设计上精确落地，
    # 避免固定种子下抽样波动把 +2% 效应稀释掉；同时保留右偏分布供正态性检验使用。
    sigma = 0.08
    noise = rng.normal(0, sigma, size=n)
    amount = np.zeros(n)
    for grp, mult in [(config.CONTROL, 1.0), (config.TREATMENT, 1 + AMOUNT_LIFT)]:
        m = (converted == 1) & (group == grp)
        z = noise[m]
        z = z - np.log(np.exp(z).mean())  # 组内中心化：exp(z) 均值 = 1
        amount[m] = BASE_AMOUNT * mult * np.exp(z)
    amount = np.round(amount, 2)

    df = pd.DataFrame({
        "user_id": [f"u{i + 1:05d}" for i in range(n)],
        "group": group,
        "segment": segment,
        "device": device,
        "city": city,
        "pre_30d_orders": pre_30d_orders,
        "pre_30d_gmv": pre_30d_gmv,
        "exposed_at": exposed_at,
        "converted": converted,
        "amount": amount,
    })
    return df


def main():
    parser = argparse.ArgumentParser(description="生成 A/B 实验模拟数据")
    parser.add_argument("--users-per-group", type=int, default=config.N_PER_GROUP,
                        help="每组样本量（默认由功效分析反推）")
    args = parser.parse_args()

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = gen(args.users_per_group)
    df.to_csv(config.EXPERIMENT_CSV, index=False)

    print(f"总用户数：{len(df)}（每组 {args.users_per_group}）")
    print(f"分组人数：\n{df['group'].value_counts().to_string()}")
    print(f"分组转化率：\n{(df.groupby('group')['converted'].mean()*100).round(3).to_string()}")
    print(f"分组人均金额（转化用户）：\n{df[df.converted==1].groupby('group')['amount'].mean().round(2).to_string()}")
    print(f"时间范围：{df['exposed_at'].min()} ~ {df['exposed_at'].max()}")


if __name__ == "__main__":
    main()
