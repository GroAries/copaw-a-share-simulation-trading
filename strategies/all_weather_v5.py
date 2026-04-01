#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全天候交易系统 v5.0 - 第一性原理设计
集成牛市识别+趋势增强+全仓自适应策略
"""

import math
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


class AllWeatherStrategyV5:
    """全天候交易系统 v5.0"""
    
    def __init__(self):
        self.price_cache = {}
        self.signal_cache = {}
        
    def generate_signal(
        self,
        market_state: Dict,
        account
    ) -> Optional[Dict]:
        """生成交易信号"""
        code = market_state['code']
        current_price = market_state['current_price']
        pre_close = market_state['pre_close']
        
        # 更新价格缓存
        if code not in self.price_cache:
            self.price_cache[code] = []
        self.price_cache[code].append(current_price)
        
        # 至少需要30条价格
        if len(self.price_cache[code]) < 30:
            return None
            
        prices = self.price_cache[code]
        
        # 1. 牛市识别：MA20方向
        ma20 = calculate_sma(prices, 20)
        if not ma20:
            return None
            
        ma20_prev = calculate_sma(prices[:-1], 20) if len(prices[:-1]) >= 20 else ma20
        
        # 判断趋势
        is_bull_market = ma20 > ma20_prev * 1.001  # 向上
        is_bear_market = ma20 < ma20_prev * 0.999  # 向下
        is_range_market = not is_bull_market and not is_bear_market
        
        # 2. 趋势增强：MACD确认
        def calculate_macd(ps, fast=12, slow=26, signal=9):
            if len(ps) < slow:
                return None, None, None
            ef = calculate_ema(ps[-fast:], fast)
            es = calculate_ema(ps[-slow:], slow)
            dif = ef - es
            dea_list = []
            for i in range(len(ps) - slow + 1):
                efi = calculate_ema(ps[i:i+fast], fast)
                esi = calculate_ema(ps[i:i+slow], slow)
                dea_list.append(efi - esi)
            if len(dea_list) < signal:
                dea = 0
            else:
                dea = calculate_ema(dea_list[-signal:], signal)
            return dif, dea, (dif - dea)*2
            
        dif, dea, macd_bar = calculate_macd(prices)
        if dif is None:
            return None
            
        # 3. 获取当前持仓
        pos = account.positions.get(code)
        current_available = pos.available_qty if pos else 0
        
        # 4. 自适应策略
        max_qty = int((account.total_cash * 0.95) // current_price // 100 * 100)
        
        if is_bull_market:
            # 牛市：全仓
            if current_available <= 0 and max_qty >= 100 and dif > dea:
                return {
                    'code': code,
                    'side': 'BUY',
                    'order_type': 'MARKET',
                    'qty': max_qty,
                    'price': None
                }
        elif is_bear_market:
            # 熊市：空仓
            if current_available >= 100 and dif < dea:
                return {
                    'code': code,
                    'side': 'SELL',
                    'order_type': 'MARKET',
                    'qty': current_available,
                    'price': None
                }
        else:
            # 震荡市：轻仓或空仓
            if current_available >= 100 and abs(macd_bar) < 0.1:
                return {
                    'code': code,
                    'side': 'SELL',
                    'order_type': 'MARKET',
                    'qty': current_available,
                    'price': None
                }
        
        return None
