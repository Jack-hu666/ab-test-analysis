"""项目级配置：路径、常量、实验参数。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
EXPERIMENT_CSV = DATA_DIR / "experiment.csv"

# 固定随机种子：保证 clone 后可复现完全相同的数据
SEED = 42

CONTROL = "control"
TREATMENT = "treatment"
DEVICES = ["ios", "android", "web"]
SEGMENTS = ["new", "returning"]
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "其他"]

# 实验设计参数
BASELINE_CONVERSION = 0.08   # 对照组基线转化率
MDE = 0.01                   # 最小可检测效应（绝对百分点）
ALPHA = 0.05                 # 显著性水平
POWER = 0.80                 # 统计功效
N_PER_GROUP = 12208          # 每组样本量：由 design.py 功效分析反推（MDE=1pp, α=0.05, power=0.8）
N_DAYS = 14                  # 实验周期（天）
EXPOSED_START = "2024-06-01"
