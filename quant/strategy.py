"""策略定义。每个策略根据行情生成目标仓位（0 = 空仓，1 = 满仓）。"""
import pandas as pd


class Strategy:
    name = "base"

    def generate_positions(self, prices: pd.DataFrame) -> pd.Series:
        """返回与 prices 同索引的目标仓位序列，基于当天收盘价计算。"""
        raise NotImplementedError


class SmaCross(Strategy):
    """双均线策略：短期均线在长期均线上方时持仓，否则空仓（只做多）。"""

    def __init__(self, fast: int = 20, slow: int = 60):
        if fast >= slow:
            raise ValueError("fast 必须小于 slow")
        self.fast = fast
        self.slow = slow
        self.name = f"SMA({fast},{slow})"

    def generate_positions(self, prices: pd.DataFrame) -> pd.Series:
        close = prices["close"]
        fast_ma = close.rolling(self.fast).mean()
        slow_ma = close.rolling(self.slow).mean()
        # 均线数据不足的前几天保持空仓
        positions = (fast_ma > slow_ma).astype(float)
        positions[slow_ma.isna()] = 0.0
        return positions
