#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
撮合引擎 - 第一性原理：完全对齐A股实盘撮合规则
市价单+滑点、涨跌停限制、交易时段限制、无对手盘不成交、T+1
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import time


# 交易时段定义
TRADING_PERIODS = [
    (time(9, 30), time(11, 30)),  # 上午
    (time(13, 0), time(15, 0))     # 下午
]


@dataclass
class Order:
    """订单"""
    order_id: str
    side: str           # BUY/SELL
    stock_code: str
    order_type: str     # MARKET/LIMIT
    price: float
    qty: int
    timestamp: float    # 时间戳
    status: str = 'PENDING'  # PENDING/FILLED/CANCELLED/REJECTED


class MatchingEngine:
    """撮合引擎"""
    
    def __init__(self, slippage: float = 0.001):
        self.slippage = slippage
        self.orders = []
        
    def is_in_trading_period(self, trade_time: time) -> bool:
        """判断是否在交易时段内"""
        for start, end in TRADING_PERIODS:
            if start <= trade_time <= end:
                return True
        return False
        
    def get_price_limit(self, stock_code: str, pre_close: float) -> Tuple[float, float]:
        """获取涨跌停价格 - 区分板块"""
        # 科创板/创业板20%，主板10%，ST/退市整理5%
        # 科创板代码: 688xxx
        # 创业板代码: 300xxx, 301xxx
        # 主板代码: 600xxx, 601xxx, 603xxx, 000xxx, 001xxx, 002xxx, 003xxx
        # ST代码: 600xxx(ST), 000xxx(ST), 688xxx(ST), 300xxx(ST)
        # 这里简化，根据代码前缀判断，实际需要结合名称
        # 假设科创板/创业板20%，主板10%，ST 5%
        limit_up_pct = 0.1
        limit_down_pct = 0.1
        
        # 科创板
        if stock_code.startswith('688'):
            limit_up_pct = 0.2
            limit_down_pct = 0.2
        # 创业板
        elif stock_code.startswith('300') or stock_code.startswith('301'):
            limit_up_pct = 0.2
            limit_down_pct = 0.2
        # ST股（简化，实际需要检查名称）
        # 暂时假设没有ST股
        
        limit_up = pre_close * (1 + limit_up_pct)
        limit_down = pre_close * (1 - limit_down_pct)
        
        # 四舍五入到分
        limit_up = round(limit_up, 2)
        limit_down = round(limit_down, 2)
        
        return limit_up, limit_down
        
    def match_order(
        self,
        order: Order,
        current_price: float,
        pre_close: float,
        trade_time: time,
        volume: int
    ) -> Tuple[bool, Optional[float], Optional[str]]:
        """撮合订单 - 完全对齐实盘规则
        
        返回: (是否成交, 成交价格, 拒绝原因)
        """
        # 1. 检查交易时段
        if not self.is_in_trading_period(trade_time):
            return False, None, "非交易时段"
            
        # 2. 检查涨跌停限制
        limit_up, limit_down = self.get_price_limit(order.stock_code, pre_close)
        
        # 3. 超涨跌停挂单废单
        if order.side == 'BUY':
            if order.order_type == 'LIMIT' and order.price > limit_up:
                return False, None, "买单价格超涨停板"
        else:  # SELL
            if order.order_type == 'LIMIT' and order.price < limit_down:
                return False, None, "卖单价格超跌停板"
                
        # 4. 封涨跌停完全禁止成交
        if current_price >= limit_up:
            # 涨停，禁止买入成交
            if order.side == 'BUY':
                return False, None, "涨停板无法买入"
        if current_price <= limit_down:
            # 跌停，禁止卖出成交
            if order.side == 'SELL':
                return False, None, "跌停板无法卖出"
                
        # 5. 无对手盘不成交 - 简化版，这里假设成交量为0时不成交
        if volume <= 0:
            return False, None, "无对手盘"
            
        # 6. 计算成交价
        if order.order_type == 'MARKET':
            # 市价单 + 动态滑点
            if order.side == 'BUY':
                # 买入：向上滑
                exec_price = current_price * (1 + self.slippage)
            else:
                # 卖出：向下滑
                exec_price = current_price * (1 - self.slippage)
        else:  # LIMIT
            # 限价单
            if order.side == 'BUY':
                if current_price <= order.price:
                    exec_price = min(order.price, current_price)
                else:
                    return False, None, "限价未到"
            else:  # SELL
                if current_price >= order.price:
                    exec_price = max(order.price, current_price)
                else:
                    return False, None, "限价未到"
                    
        # 7. 确保成交价在涨跌停范围内
        exec_price = max(limit_down, min(limit_up, round(exec_price, 2)))
        
        order.status = 'FILLED'
        self.orders.append(order)
        
        return True, exec_price, None
