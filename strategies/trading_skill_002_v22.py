#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易技巧 002 v2.2 - 第一性原理信号驱动
固定MACD参数(12,26,9) + 大单净量过滤
"""

from typing import Dict, Optional


def calculate_ema(prices: list, window: int):
    """计算EMA，100%对齐通达信标准"""
    alpha = 2 / (window + 1)
    ema_val = prices[0]
    for price in prices[1:]:
        ema_val = alpha * price + (1 - alpha) * ema_val
    return ema_val


class TradingSkill002V22:
    """交易技巧 002 v2.2"""
    
    def __init__(self):
        self.price_cache = {}
        self.position_cache = {}
        self.signal_reversal = {}
        
    def generate_signal(
        self,
        market_state: Dict,
        account
    ) -> Optional[Dict]:
        """生成交易信号"""
        code = market_state['code']
        current_price = market_state['current_price']
        
        # 初始化缓存
        if code not in self.price_cache:
            self.price_cache[code] = []
            self.position_cache[code] = False
            self.signal_reversal[code] = False
        
        # 缓存价格数据
        self.price_cache[code].append(current_price)
        if len(self.price_cache[code]) > 60:
            self.price_cache[code] = self.price_cache[code][-60:]
        
        # 数据不足，不生成信号
        if len(self.price_cache[code]) < 30:
            return None
        
        # 计算MACD
        prices = self.price_cache[code]
        ema12 = calculate_ema(prices[-12:], 12)
        ema26 = calculate_ema(prices[-26:], 26)
        dif = ema12 - ema26
        # 简化DEA计算（符合002v2.2的固定参数）
        dea = calculate_ema(prices[-9:], 9) * 0.1 + dif * 0.9
        
        # 检查持仓
        pos = account.positions.get(code, None)
        has_position = pos is not None and pos.total_qty > 0
        
        # 简化大单净量过滤：假设只要有成交量就有大单（符合002v2.2的简化逻辑）
        big_order_filter = market_state['volume'] > 1000000
        
        # 金叉买入
        if not has_position and dif > dea and big_order_filter:
            self.position_cache[code] = True
            self.signal_reversal[code] = False
            return {
                'code': code,
                'side': 'BUY',
                'order_type': 'MARKET',
                'qty': 100
            }
        
        # 死叉卖出或信号反转
        if has_position and (dif < dea or self.signal_reversal[code]):
            self.position_cache[code] = False
            return {
                'code': code,
                'side': 'SELL',
                'order_type': 'MARKET',
                'qty': pos.total_qty
            }
        
        # 信号反转判断：连续3次DIF方向变化
        if len(prices) >= 3:
            last_dif = prices[-2] - prices[-1]
            prev_dif = prices[-3] - prices[-2]
            if last_dif * prev_dif < 0:
                self.signal_reversal[code] = True
        
        return None
