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
  indicators.py # 技术指标：MA、EMA、MACD、RSI、布林带、ATR、ADX
  patterns.py   # K 线形态：十字星、锤子线、射击之星、看涨/看跌吞没
  analysis.py   # 走势综合分析：趋势判断、支撑阻力、信号汇总
  kline_plot.py # K 线图：蜡烛图 + 均线 + 布林带 + 成交量 + MACD + RSI
  intraday.py   # 日内策略：开盘区间突破（ORB）、VWAP 均值回归
  risk_guard.py # 账户风控检查：仓位、止损、到期、交易频率、当日亏损
  price_action.py # 价格行为学：波段点、市场结构（HH/HL/LH/LL）、H1/H2/L1/L2 回测
  pa_plot.py    # 价格行为标注图
run_backtest.py # 回测入口
analyze_kline.py # K 线走势分析入口
run_intraday.py # 日内策略对比入口
run_price_action.py # 价格行为学 H1/H2 回测对比入口
data/           # 示例数据（来自 IBKR，未做分红复权）：SPY 日线 2021-10 ~ 2026-10，
                #   SPY/QQQ 30 分钟线 2026-06 ~ 2026-10
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

### K 线走势分析

```bash
python analyze_kline.py --symbol AAPL                       # 在线下载
python analyze_kline.py --symbol SPY --csv data/SPY_daily.csv --bars 120
```

输出一份文字报告和一张 K 线图（`output/<代码>_kline.png`，红涨绿跌）：

- **趋势判断**：根据价格与 MA20/60/120 的位置、均线排列、MA20 斜率、MACD 打出多空得分（-6 ~ +6），
  再用 ADX 判断趋势强弱；ADX < 20 或得分在 ±1 以内判为「震荡」
- **支撑 / 阻力位**：近 120 根 K 线中的局部高低点，相距 1% 以内的价位合并
- **指标提示**：RSI 超买/超卖、布林带突破、MACD 金叉/死叉
- **K 线形态**：近 5 日出现的十字星、锤子线、射击之星、吞没形态

### 日内策略对比

```bash
python run_intraday.py --symbols SPY QQQ --cost-bps 1
```

- **ORB 开盘区间突破**：开盘前 30/60 分钟的高低点构成区间，先突破哪边就往哪边做，止损放在区间另一侧或中点，收盘平仓
- **VWAP 均值回归**：价格偏离 VWAP 超过阈值时反向入场，目标回到 VWAP，带固定止损，收盘平仓
- 同一根 K 线内同时触及入场价和止损价时按亏损处理（保守假设）

2026-06-29 ~ 2026-10-14（76 个交易日）的结果：ORB 在 SPY 和 QQQ 上都亏损；VWAP 回归小幅盈利，
但 t 值都低于 2，统计上不显著。样本只有约 3 个月，结论仅供参考。

### 账户风控检查

```bash
python -m quant.risk_guard --summary summary.json --positions positions.json \
    --trades trades.json --start-nav 5000
```

输入是 IBKR 接口 `get_account_summary`、`get_account_positions`、`get_account_trades(TODAY)` 的 JSON。
默认规则（可在 `Rules` 里修改）：

| 规则 | 默认值 |
|---|---|
| 单个仓位成本占净值上限 | 5% |
| 同一标的合计占净值上限 | 10% |
| 期权浮亏止损 | 成本的 50% |
| 持有当天到期的期权 | 警报 |
| 每天订单数上限 | 5 |
| 当日亏损上限 | 3% |

有违规时输出警报并以退出码 1 结束。

### 价格行为学（Al Brooks 风格）

```bash
python run_price_action.py
```

- **波段点**：左右各 3 根 K 线内的最高/最低点，需要再走 3 根 K 线才能确认（不使用未来数据）
- **市场结构**：最近的波段高点是 HH 且波段低点是 HL 为上升趋势；LH + LL 为下降趋势；其余为区间
- **H2 / L2**：上升趋势（EMA20 向上且结构为 HH+HL）中，回调里第二次有 K 线突破前一根 K 线高点时入场；
  止损放在回调最低点，目标 1R 或 2R。L2 是下降趋势中的镜像。H1/L1 是第一次突破就入场
- 输出 `output/SPY_price_action.png`：标注波段点、趋势背景色和每笔 H2/L2 交易

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
