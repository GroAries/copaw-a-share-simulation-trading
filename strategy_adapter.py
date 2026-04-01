#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略适配层 - 第一性原理：兼容所有基于BaseStrategy的现有策略，不修改任何策略原代码
将模拟盘接口转换为回测系统BaseStrategy标准接口
"""
import sys
import os
from typing import Dict, List, Optional

# 导入回测系统基类
sys.path.insert(0, os.path.abspath('/Users/xy23050701/.copaw/workspaces/default/skills/a_share_backtest_system-active'))
from strategies import BaseStrategy, Signal, TradeSignal

class StrategyAdapter:
    """通用策略适配器，将BaseStrategy适配到模拟盘接口"""
    
    def __init__(self, strategy: BaseStrategy, max_history: int = 100):
        self.strategy = strategy
        self.name = strategy.name
        self.max_history = max_history
        # 历史数据缓存，每个股票单独存储
        self.price_history: Dict[str, List[float]] = {}
        self.volume_history: Dict[str, List[float]] = {}
    
    def generate_signal(self, market_state: Dict, account) -> Optional[Dict]:
        """
        模拟盘接口 -> 转换为BaseStrategy接口 -> 转换回模拟盘信号
        """
        stock_code = market_state['code']
        current_price = market_state['current_price']
        current_volume = market_state['volume']
        
        # 初始化历史数据
        if stock_code not in self.price_history:
            self.price_history[stock_code] = []
            self.volume_history[stock_code] = []
        
        # 更新历史数据
        self.price_history[stock_code].append(current_price)
        self.volume_history[stock_code].append(current_volume)
        
        # 保留最多max_history条数据
        if len(self.price_history[stock_code]) > self.max_history:
            self.price_history[stock_code] = self.price_history[stock_code][-self.max_history:]
            self.volume_history[stock_code] = self.volume_history[stock_code][-self.max_history:]
        
        # 计算当前仓位比例
        total_assets = account.total_cash
        if stock_code in account.positions:
            position_value = account.positions[stock_code].total_qty * current_price
            total_assets += position_value
            current_position = position_value / total_assets if total_assets > 0 else 0.0
        else:
            current_position = 0.0
        
        # 调用原始策略生成信号
        trade_signal: TradeSignal = self.strategy.generate_signal(
            price_history=self.price_history[stock_code],
            volume_history=self.volume_history[stock_code],
            current_price=current_price,
            current_position=current_position,
            current_capital=account.available_cash
        )
        
        # 转换为模拟盘信号格式
        if trade_signal.signal == Signal.BUY and current_position < trade_signal.position_size:
            # 计算可买数量
            available_cash = account.available_cash * (trade_signal.position_size - current_position)
            max_buy_quantity = int(available_cash * 0.99 / current_price / 100) * 100
            
            if max_buy_quantity >= 100:
                return {
                    'side': "BUY",
                    'qty': max_buy_quantity,
                    'price': current_price,
                    'reason': trade_signal.reason
                }
        
        elif trade_signal.signal == Signal.SELL and current_position > 0:
            # 计算可卖数量
            if stock_code in account.positions:
                available_qty = account.positions[stock_code].available_qty
                sell_qty = int(available_qty * (1 - trade_signal.position_size))
                if sell_qty >= 100:
                    return {
                        'side': "SELL",
                        'qty': sell_qty,
                        'price': current_price,
                        'reason': trade_signal.reason
                    }
        
        # 持有/观望信号不生成订单
        return None
