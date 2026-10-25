# A/B 测试设计与效果评估

> 数据为脚本模拟生成，实验分析方法为真实实现。

## 技术栈

Python · pandas · numpy · scipy.stats（z 检验 / t 检验 / Mann-Whitney U / 卡方 / Shapiro-Wilk / Levene / bootstrap）· matplotlib · SQLite · Git

## 项目简介

从「结算页改版」这个假设出发，走一遍「实验设计 → 随机性校验 → 主指标检验 → 分群下钻 → 决策建议 → 陷阱复盘」的完整实验分析。和「画个图算个转化率」的区别在于统计功底：不只回答「有没有效果」，还要回答「这个结论凭什么可信」。

## 实验设计

- **假设**：结算页从「单页表单」改成「三步引导式」，能不能提升支付转化率？
- **分组**：control（旧版单页）/ treatment（新版三步引导式），50/50 随机分流
- **主指标**：支付转化率；辅助指标：转化用户人均支付金额
- **样本量**：用两比例 z 检验的样本量公式，基线 8%、MDE=1pp、α=0.05、power=0.8 反推，每组 12208 人、共 24416 人、约 14 天（公式推导在 `src/design.py`）

## 分析流程

校验 → 主指标 → 分群 → 陷阱。先验证分流干不干净（不干净后面全白做），再测主指标，再拆人群看效应是谁带来的，最后复盘 peeking 和多重比较两个常见坑。

## 核心结论

- 转化率：control 7.96% → treatment 9.71%，**+1.74pp（相对 +21.9%）**，95% CI [1.03, 2.46]pp
- 客单价：转化用户人均支付金额 **+2.00%**，bootstrap 95% CI [1.30%, 2.68%]
- 收益分布不均：新用户（+2.72pp）和 iOS/Android（+1.2~+2.6pp）是主要受益人群；**Web（+1.00pp）和老用户（+0.29pp）不显著**
- 随机化校验（SRM + 分流前指标平衡）全部通过

> 完整报告见 [reports/analysis.md](reports/analysis.md)，给业务看的见 [reports/decision.md](reports/decision.md)。

## 决策建议

分阶段、分人群上线：先在新用户 + iOS/Android 全量上；Web 端和老用户暂缓，继续观察或单独优化。

## 图表

图都在 reports/figures/ 下：

- power_curve.png：MDE 越小样本量越大，1pp 对应每组 12208 人
- conversion_ci.png：两个主指标的效应量 + 置信区间
- segment_effects.png：分群效应森林图，Web/老用户置信区间跨 0
- peeking_curve.png：累计 p 值随天数波动

## 快速开始

命令按顺序跑就行，中间报错八成是依赖没装全：

```bash
pip install -r requirements.txt
python -m src.gen_data && python -m src.design && python -m src.sanity_check && python -m src.analyze && python -m src.segment && python -m src.pitfalls && python -m src.report
```

## 方法说明与取舍（重点）

1. **转化率为什么用 z 检验**：比例指标、样本量上万，二项分布可用正态近似；z 检验能直接给方向和置信区间。
2. **为什么双侧**：只关心「有没有差异」，不预先假设新版本一定更好，取双侧 α=0.05 更保守。
3. **金额为什么用 Mann-Whitney U**：金额右偏，Shapiro-Wilk 拒绝正态，t 检验前提不成立；Mann-Whitney U 非参数、只用秩，更稳。
4. **「人均支付金额」怎么定义**：取转化用户的客单价，不是全员平均（含 0）。因为转化率已经单独做主指标，金额指标要隔离「金额本身」的效应（+2%），不然会被 +22% 的转化率效应盖掉。
5. **分群结论要不要校正**：设备/新老用户是预指定的次级假设，不校正；城市这种探索性分群才用 Bonferroni / FDR（见 `src/pitfalls.py`）。

## 局限

- 只有 14 天观察期，没覆盖长期留存和复购
- 金额结论基于转化用户，有选择偏差
- 数据是模拟的，效应量是「为演示分析流程而设计」的，不能外推成真实业务收益

> 数据生成的「真实效应」设定见 [docs/decisions.md](docs/decisions.md)，README 不剧透，让分析流程自己去发现结论。
