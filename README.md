# shuyizhou

## 美股量化回测框架

一个简洁的 Python 回测框架，内置双均线（SMA Cross）策略。

### 目录结构

```
quant/
  data.py       # 行情获取（yfinance，本地 CSV 缓存）
  strategy.py   # 策略：Strategy 基类 + SmaCross 双均线
  backtest.py   # 向量化回测引擎（含交易成本、次日执行）
  metrics.py    # 绩效指标：收益、年化、波动、夏普、最大回撤、胜率
  plot.py       # 价格/均线/买卖点、净值对比、回撤图
run_backtest.py # 命令行入口
data/           # 示例数据：SPY 日线（2021-10 ~ 2026-10，来自 IBKR，未做分红复权）
tests/          # 单元测试
```

### 使用

```bash
pip install -r requirements.txt

# 在线下载数据（yfinance）
python run_backtest.py --symbol AAPL --start 2015-01-01 --fast 20 --slow 60

# 使用本地 CSV
python run_backtest.py --symbol SPY --csv data/SPY_daily.csv --fast 50 --slow 200

# 运行测试
python -m pytest -q
```

结果输出到 `output/`：一张图表（`.png`）和每笔交易明细（`.trades.csv`）。

### 策略规则（SmaCross）

- 短期均线 > 长期均线：满仓持有；否则空仓（只做多）
- 信号用当日收盘价计算，**次日**执行，避免未来函数
- 每次换仓扣除单边成本 `--cost-bps`（默认 5bp = 0.05%）

### 示例结果：SPY 2021-10 ~ 2026-10

| 参数 | 年化收益 | 夏普 | 最大回撤 | 交易次数 |
|---|---|---|---|---|
| SMA(10,30) | 6.30% | 0.62 | -18.04% | 20 |
| SMA(20,60) | 2.81% | 0.31 | -27.63% | 12 |
| SMA(50,200) | 10.04% | 0.84 | -19.00% | 2 |
| 买入持有 | 11.54% | 0.72 | -25.36% | - |

注意：参数之间的结果差别很大，这说明有过拟合风险。不要只挑回测最好的那组参数，应该用样本外数据验证。

### 添加新策略

继承 `Strategy`，实现 `generate_positions(prices) -> pd.Series`（取值 0~1 的目标仓位），然后传给 `run_backtest` 即可。
