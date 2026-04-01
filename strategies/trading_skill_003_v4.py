#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易技巧 003 v4 - 第一性原理多维度验证
双K线对比+MACD金叉+大单净量三重过滤
"""

from typing import Dict, Optional


def calculate_ema(prices: list, window: int):
    """计算EMA，100%对齐通达信标准"""
    alpha = 2 / (window + 1)
    ema_val = prices[0]
    for price in prices[1:]:
        ema_val = alpha * price + (1 - alpha) * ema_val
    return ema_val


def calculate_sma(prices: list, window: int):
    """计算SMA"""
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window


class TradingSkill003V4:
    """交易技巧 003 v4"""
    
    def __init__(self):
        self.price_cache = {}
        self.volume_cache = {}
        self.position_cache = {}
        
    def generate_signal(
        self,
        market_state: Dict,
        account
    ) -> Optional[Dict]:
        """生成交易信号"""
        code = market_state['code']
        current_price = market_state['current_price']
        current_volume = market_state['volume']
        open_price = market_state['open_price']
        high_price = market_state['high_price']
        low_price = market_state['low_price']
        
        # 初始化缓存
        if code not in self.price_cache:
            self.price_cache[code] = []
            self.volume_cache[code] = []
            self.position_cache[code] = False
        
        # 缓存价格和成交量数据
        self.price_cache[code].append(current_price)
        self.volume_cache[code].append(current_volume)
        if len(self.price_cache[code]) > 60:
            self.price_cache[code] = self.price_cache[code][-60:]
            self.volume_cache[code] = self.volume_cache[code][-60:]
        
        # 数据不足，不生成信号
        if len(self.price_cache[code]) < 40:
            return None
        
        # 检查持仓
        pos = account.positions.get(code, None)
        has_position = pos is not None and pos.total_qty > 0
        
        # === 三重过滤条件 ===
        # 条件1：双K线对比（当日阳线且收盘价高于昨日最高价）
        double_k_filter = False
        if len(self.price_cache[code]) >= 2 and current_price > open_price:
            yesterday_high = max(self.price_cache[code][-2], open_price) if len(self.price_cache[code]) >= 2 else current_price
            double_k_filter = current_price > yesterday_high
        
        # 条件2：MACD金叉（DIF上穿DEA且在0轴上方）
        macd_filter = False
        prices = self.price_cache[code]
        ema12 = calculate_ema(prices[-12:], 12)
        ema26 = calculate_ema(prices[-26:], 26)
        dif = ema12 - ema26
        dea = calculate_ema(prices[-9:], 9)
        if len(prices) >= 10:
            prev_dif = calculate_ema(prices[-13:-1], 12) - calculate_ema(prices[-27:-1], 26)
            prev_dea = calculate_ema(prices[-10:-1], 9)
            macd_filter = (prev_dif <= prev_dea) and (dif > dea) and (dif > 0)
        
        # 条件3：大单净量过滤（成交量是昨日的2倍以上）
        big_order_filter = False
        if len(self.volume_cache[code]) >= 2:
            yesterday_volume = self.volume_cache[code][-2]
            if yesterday_volume > 0:
                big_order_filter = current_volume / yesterday_volume >= 2
        
        # === 买入信号（三个条件同时满足） ===
        if not has_position and double_k_filter and macd_filter and big_order_filter:
            self.position_cache[code] = True
            return {
                'code': code,
                'side': 'BUY',
                'order_type': 'MARKET',
                'qty': 100
            }
        
        # === 卖出信号（MACD死叉或持仓浮亏10%） ===
        if has_position:
            # MACD死叉
            sell_signal_macd = False
            if len(prices) >= 10:
                prev_dif = calculate_ema(prices[-13:-1], 12) - calculate_ema(prices[-27:-1], 26)
                prev_dea = calculate_ema(prices[-10:-1], 9)
                sell_signal_macd = (prev_dif >= prev_dea) and (dif < dea)
            
            # 持仓浮亏10%
            cost_basis = pos.cost_basis
            sell_signal_stop_loss = current_price / cost_basis <= 0.9
            
            if sell_signal_macd or sell_signal_stop_loss:
                self.position_cache[code] = False
                return {
                    'code': code,
                    'side': 'SELL',
                    'order_type': 'MARKET',
                    'qty': pos.total_qty
                }
        
        return None
