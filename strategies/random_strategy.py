#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
随机策略 - 仅用于测试模拟盘系统
第一性原理：策略完全独立于系统，自主决策
"""

import random
from typing import Dict, Optional


class RandomStrategy:
    """随机策略 - 仅用于测试"""
    
    def __init__(self):
        self.traded_today = {}
        
    def generate_signal(
        self,
        market_state: Dict,
        account
    ) -> Optional[Dict]:
        """生成交易信号
        
        Args:
            market_state: 市场状态字典
            account: 账户对象
            
        Returns:
            信号字典或None
        """
        code = market_state['code']
        current_price = market_state['current_price']
        
        # 随机决策
        action = random.choice(['BUY', 'SELL', 'HOLD'])
        
        if action == 'HOLD':
            return None
            
        if action == 'BUY':
            # 每次买100股
            qty = 100
            amount_needed = current_price * qty * 1.001  # 预留交易成本
            if account.available_cash >= amount_needed:
                return {
                    'side': 'BUY',
                    'qty': qty,
                    'price': None  # 市价单
                }
                
        elif action == 'SELL':
            # 卖100股
            qty = 100
            if code in account.positions and account.positions[code].available_qty >= qty:
                return {
                    'side': 'SELL',
                    'qty': qty,
                    'price': None
                }
                
        return None
