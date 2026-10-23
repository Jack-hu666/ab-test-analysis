# 任务指令：A/B 测试设计与效果评估

## 你的角色

你是这个项目的唯一实现者。目标是在 **1.5–2 周内**做出一份完整的实验分析作品：从一个实验假设出发，完成「实验设计 → 随机性校验 → 主指标检验 → 分群下钻 → 决策建议 → 陷阱复盘」的完整链路。

这个项目用于投递「数据分析实习生」岗位。**它的差异化在于统计功底**——大部分应届生会画图、会算转化率，但不会规范地做实验分析。这份作品要让面试官看到你懂「为什么这个结论可信」。

---

## 硬约束（违反任何一条都算失败）

1. **数据必须是脚本生成的模拟数据**，且 README 第一段必须写明：**「数据为脚本模拟生成，实验分析方法为真实实现」**。不得暗示是真实业务实验。
2. **生成脚本固定随机种子**，clone 后可复现完全相同的数据。
3. **不得编造结论**。所有 p 值、置信区间、效应量必须由代码算出，README 里的每个数字都要能复现。
4. **统计检验必须自己实现调用链**（scipy.stats 可以用，但不得直接抄网上的 `ttest_ind` 一行了事——要写清假设、检验方向、单双侧选择理由）。
5. **不能只报 p 值**，必须同时给置信区间和效应量。
6. **不做 Web 前端**，可视化用 matplotlib / seaborn + Streamlit。
7. **每完成一个 Step 就 `git commit`**，message 用中文。
8. **遇到阻塞先停下报告**。

---

## 目标仓库结构

```
ab-test-analysis/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── config.py          # 常量、路径、实验参数
│   ├── gen_data.py        # Step1: 生成实验数据
│   ├── design.py          # Step2: 样本量与功效计算
│   ├── sanity_check.py    # Step3: SRM + 平衡性检查
│   ├── analyze.py         # Step4: 主指标检验（转化率 + 金额）
│   ├── segment.py         # Step5: 分群下钻
│   ├── pitfalls.py        # Step6: 陷阱复盘（peeking / 多重比较）
│   └── report.py          # Step7: 汇总结论
├── sql/
│   └── summary.sql        # 用 SQL 做基础汇总，和 pandas 结果交叉验证
├── reports/
│   ├── figures/
│   ├── analysis.md        # 完整分析报告（核心交付物）
│   └── decision.md        # 决策建议
└── docs/
    └── decisions.md       # 口径与方法选择记录
```

---

## 实验场景与数据设计

### 场景

**假设**：把结算页从「单页表单」改为「三步引导式」，是否提升支付转化率？

- 对照组 `control`：旧版单页结算页
- 实验组 `treatment`：新版三步引导式结算页
- 分流：50% / 50%，随机分配

### 表结构 `experiment`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `user_id` | string | 用户 ID |
| `group` | string | `control` / `treatment` |
| `segment` | string | `new`（新用户）/ `returning`（老用户） |
| `device` | string | `ios` / `android` / `web` |
| `city` | string | 城市 |
| `pre_30d_orders` | int | 实验前 30 天订单数 |
| `pre_30d_gmv` | float | 实验前 30 天消费金额 |
| `exposed_at` | datetime | 进入实验时间（跨 14 天） |
| `converted` | int | 是否支付（1/0） |
| `amount` | float | 支付金额，未支付为 0 |

### 生成规则（必须体现这些效应，否则分析不出东西）

> **注意**：这些规则只写进代码注释和 `docs/decisions.md`，**不要在 README 里剧透**。README 只说明数据是模拟的，让分析自己去发现结论。

- **规模**：约 3 万用户，每组 1.5 万（样本量由 Step2 的功效计算反推，最终以计算值为准）
- **基线**：control 转化率约 **8.0%**，人均支付金额约 **¥120**
- **真实效应**（数据设计的真相）：
  - 整体转化率：treatment 提升约 **1.2 个百分点**（相对提升 15%）
  - 人均金额：treatment 提升约 **2%**
- **分群差异**（关键，让下钻有结论）：
  - `iOS` / `android`：转化率提升约 **+1.8pp**（显著）
  - `web`：提升约 **+0.3pp**（**不显著**）
  - `new` 用户：提升约 **+1.5pp**；`returning` 用户：提升约 **+0.6pp**（**不显著**）
- **噪声**：整体加随机扰动，保证有统计波动，不是完美数字
- **一个埋点**：`exposed_at` 按天分布，用于 Step6 演示「偷看数据（peeking）」问题

---

## 分析任务

### Step 1：生成数据
- `src/gen_data.py`，seed=42，输出 `data/experiment.csv`
- 参数 `--users-per-group` 可调

**验收**：
```bash
python -m src.gen_data
python -c "import pandas as pd; d=pd.read_csv('data/experiment.csv'); print(d.shape); print(d.group.value_counts()); print(d.groupby('group').converted.mean()); print(d.groupby('group').amount.mean())"
# 期望：约 3 万行，两组人数接近，转化率与金额有明显但不大幅的差异
```

### Step 2：实验设计（功效分析）
- `src/design.py`：
  - 输入：基线转化率 8%、最小可检测效应 MDE=1pp、α=0.05、power=0.8
  - 计算每组所需样本量（用两比例检验的样本量公式，**自己写公式并解释每一项**）
  - 输出：所需样本量、总样本量、预计实验周期
- **必须输出一张「MDE vs 样本量」曲线图**（`reports/figures/power_curve.png`）

**验收**：
```bash
python -m src.design
# 期望：打印每组样本量，并在 reports/figures/ 生成曲线
# 说明：这个数字要和 gen_data.py 的规模对得上
```

### Step 3：随机性与平衡性检查
- `src/sanity_check.py`：
  1. **SRM 检查**：两组人数是否符合预期占比（卡方检验），p 值 > 0.001 视为通过
  2. **分流前指标平衡**：对比两组 `pre_30d_orders`、`pre_30d_gmv` 的均值和分布，做 t 检验
  3. **分组构成**：`segment` / `device` / `city` 的分布是否一致
- 输出 3 项结论 + PASS/FAIL

**验收**：
```bash
python -m src.sanity_check
# 期望：SRM PASS，平衡性检查各组 p > 0.05
```

> 这一步的意义：**如果随机化有问题，后面所有结论都不可信**。面试官问「你怎么验证实验有效」，答案就在这里。

### Step 4：主指标检验
- `src/analyze.py`：
  1. **转化率**（比例指标）：两比例 z 检验，输出 lift、绝对提升（pp）、相对提升（%）、95% 置信区间、p 值
  2. **人均支付金额**（连续指标）：先做正态性/方差齐性判断，选择 t 检验或 Mann-Whitney U，说明理由
  3. **交叉验证**：用 `sql/summary.sql` 算一遍基础汇总，和 pandas 结果核对一致
- 输出：`reports/figures/conversion_ci.png`（效应量和置信区间图）

**验收**：
```bash
python -m src.analyze
# 期望：转化率提升约 1.2pp，p < 0.05；金额提升约 2%
```

### Step 5：分群下钻
- `src/segment.py`：按 `device` 和 `segment`（新老用户）分别做检验
- **必须输出交互作用说明**：整体有效应，但在某些分群不显著
- 输出：`reports/figures/segment_effects.png`（各分群的效应 + 置信区间森林图）

**验收**：
```bash
python -m src.segment
# 期望：ios/android 显著，web 不显著；新用户显著、老用户不显著
# 并说明：这解释了"整体效应是哪些人群带来的"
```

### Step 6：陷阱复盘（这是本项目的加分项）
- `src/pitfalls.py`，用同一份数据演示两个常见错误：
  1. **Peeking（偷看数据）**：按天累计计算 p 值，画出「随着天数增加 p 值变化」的曲线，说明为什么「p<0.05 就停」会放大假阳性
  2. **多重比较**：对 8 个分群各做一次检验，不做校正时假阳性率是多少；用 Bonferroni 或 FDR 校正后结论有何变化
- 输出：`reports/figures/peeking_curve.png`

**验收**：
```bash
python -m src.pitfalls
# 期望：能看到 p 值随天数的波动；多重比较下至少 1 个分群"偶然显著"
```

### Step 7：结论与决策
- `src/report.py` 汇总成 `reports/analysis.md`，必须包含：
  1. 实验背景与假设
  2. 样本量与实验周期
  3. 随机性校验结果
  4. 主指标结论（含效应量、置信区间、p 值）
  5. 分群结论（谁受益最大）
  6. **决策建议**：是否全量上线？还是先在 iOS + 新用户群体上线？
  7. 局限与后续实验建议
- `reports/decision.md`：一页纸的决策结论，面向「不懂统计的业务方」

**验收**：
```bash
python -m src.report
# 期望：analysis.md 完整；decision.md 用业务语言写，不含 p 值术语
```

---

## README 必须包含的章节

```markdown
# A/B 测试设计与效果评估

> **数据为脚本模拟生成，实验分析方法为真实实现。**

## 项目简介
## 实验设计            (假设、指标、样本量怎么定的)
## 分析流程            (校验 → 主指标 → 分群 → 陷阱)
## 核心结论            (含效应量、置信区间)
## 决策建议
## 图表
## 快速开始
## 方法说明与取舍      (为什么用 z 检验、为什么用 Mann-Whitney、α 怎么取)
## 局限与后续实验建议
```

**「方法说明与取舍」是核心**——面试官会问「你凭什么用这个检验」。

---

## 完成定义（DoD）

- [ ] `git log` 至少 7 次提交
- [ ] 3 条命令从零跑通
- [ ] 固定 seed，可复现
- [ ] 功效分析有公式推导 + MDE 曲线
- [ ] SRM + 平衡性检查有结论
- [ ] 主指标同时给 lift、CI、p 值，且 SQL 与 pandas 结果一致
- [ ] 分群下钻有森林图，且指出哪些人群不显著
- [ ] peeking 曲线有多重比较的假阳性演示
- [ ] `reports/analysis.md` 完整，`reports/decision.md` 是业务语言
- [ ] `docs/decisions.md` 至少 5 条方法选择理由

---

## 工作方式

1. **先输出分析计划**（每个 Step 要验证什么、产出什么），等用户确认再动手
2. **一个 Step 做完立刻验证**，通过再进下一步
3. **结论必须由数据得出。** 如果你发现数据里没有显著效应，就如实报告「未发现显著差异」，不要为了好看而调整阈值或换检验方法
4. 全部完成后输出「实际结果汇总」：效应量、置信区间、p 值、分群结论，供用户填简历用
