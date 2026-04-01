#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
撮合引擎 - 第一性原理：完全对齐A股实盘撮合规则
基于五档盘口、价格优先时间优先队列、无虚假成交
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
from datetime import time
import heapq
import time as sys_time


# 交易时段定义
TRADING_PERIODS = [
    (time(9, 15), time(9, 25)),  # 集合竞价
    (time(9, 30), time(11, 30)),  # 上午连续竞价
    (time(13, 0), time(15, 0))     # 下午连续竞价
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
    remaining_qty: int
    timestamp: float    # Unix时间戳，用于时间优先
    status: str = 'PENDING'  # PENDING/PARTIAL_FILLED/FILLED/CANCELLED/REJECTED


class OrderBook:
    """订单簿 - 实现价格优先、时间优先"""
    
    def __init__(self):
        # 买单堆（用负价格实现最大堆）
        self.bid_heap: List[Tuple[float, float, int, Order]] = []
        # 卖单堆（最小堆）
        self.ask_heap: List[Tuple[float, float, int, Order]] = []
        # 订单ID映射，方便撤单
        self.order_map: Dict[str, Order] = {}
        
    def add_order(self, order: Order):
        """添加订单到订单簿"""
        self.order_map[order.order_id] = order
        if order.side == 'BUY':
            # 买单：用负价格实现最大堆，相同价格按时间戳排序
            heapq.heappush(self.bid_heap, (-order.price, order.timestamp, id(order), order))
        else:
            # 卖单：最小堆
            heapq.heappush(self.ask_heap, (order.price, order.timestamp, id(order), order))
            
    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        order = self.order_map.get(order_id)
        if not order or order.status in ['FILLED', 'REJECTED']:
            return False
        order.status = 'CANCELLED'
        return True
        
    def get_best_bid(self) -> Optional[Order]:
        """获取最优买单"""
        while self.bid_heap:
            neg_price, ts, _, order = self.bid_heap[0]
            if order.status not in ['PENDING', 'PARTIAL_FILLED']:
                heapq.heappop(self.bid_heap)
                continue
            return order
        return None
        
    def get_best_ask(self) -> Optional[Order]:
        """获取最优卖单"""
        while self.ask_heap:
            price, ts, _, order = self.ask_heap[0]
            if order.status not in ['PENDING', 'PARTIAL_FILLED']:
                heapq.heappop(self.ask_heap)
                continue
            return order
        return None


class MatchingEngine:
    """撮合引擎"""
    
    def __init__(self, slippage: float = 0.0):
        self.slippage = slippage
        # 每个股票一个订单簿
        self.order_books: Dict[str, OrderBook] = {}
        self.trades = []
        
    def get_order_book(self, stock_code: str) -> OrderBook:
        """获取或创建订单簿"""
        if stock_code not in self.order_books:
            self.order_books[stock_code] = OrderBook()
        return self.order_books[stock_code]
        
    def is_in_trading_period(self, trade_time: time) -> bool:
        """判断是否在交易时段内"""
        for start, end in TRADING_PERIODS:
            if start <= trade_time <= end:
                return True
        return False
        
    def match_order_with_orderbook(
        self,
        order: Order,
        quote: Dict
    ) -> Tuple[bool, Optional[float], Optional[int], Optional[str]]:
        """基于实盘五档盘口撮合订单（不依赖内部订单簿，直接用实盘数据）
        
        返回: (是否成交, 成交价格, 成交数量, 拒绝原因)
        """
        # 1. 检查交易时段
        trade_time_str = quote['time']
        if len(trade_time_str) >= 14:
            hour = int(trade_time_str[8:10])
            minute = int(trade_time_str[10:12])
            second = int(trade_time_str[12:14])
            trade_time = time(hour, minute, second)
        else:
            # 如果时间格式不对，默认允许
            trade_time = time(10, 0, 0)
            
        if not self.is_in_trading_period(trade_time):
            return False, None, None, "非交易时段"
            
        # 2. 检查停牌
        if quote['is_suspended']:
            return False, None, None, "股票停牌"
            
        # 3. 检查涨跌停限制
        limit_up = quote['limit_up']
        limit_down = quote['limit_down']
        
        # 超涨跌停挂单废单
        if order.side == 'BUY':
            if order.order_type == 'LIMIT' and order.price > limit_up:
                return False, None, None, "买单价格超涨停板"
        else:  # SELL
            if order.order_type == 'LIMIT' and order.price < limit_down:
                return False, None, None, "卖单价格超跌停板"
                
        # 4. 封涨跌停完全禁止成交
        # 涨停时：卖一为空或卖一价格等于涨停价，且买一价格等于涨停价，禁止买入
        if quote['current'] >= limit_up:
            if order.side == 'BUY':
                # 检查是否有卖单
                if not quote['asks'] or quote['asks'][0]['price'] >= limit_up:
                    return False, None, None, "涨停板无法买入"
        # 跌停时：买一为空或买一价格等于跌停价，且卖一价格等于跌停价，禁止卖出
        if quote['current'] <= limit_down:
            if order.side == 'SELL':
                if not quote['bids'] or quote['bids'][0]['price'] <= limit_down:
                    return False, None, None, "跌停板无法卖出"
                    
        # 5. 基于五档盘口撮合（无内部订单簿，直接用实盘数据）
        exec_price = None
        exec_qty = 0
        remaining_qty = order.qty
        
        if order.side == 'BUY':
            # 买入：从卖一到卖五依次匹配
            for ask in quote['asks']:
                if remaining_qty <= 0:
                    break
                # 限价单检查
                if order.order_type == 'LIMIT' and ask['price'] > order.price:
                    break
                # 计算可成交数量
                match_qty = min(remaining_qty, ask['volume'])
                exec_price = ask['price']
                exec_qty += match_qty
                remaining_qty -= match_qty
        else:  # SELL
            # 卖出：从买一到买五依次匹配
            for bid in quote['bids']:
                if remaining_qty <= 0:
                    break
                # 限价单检查
                if order.order_type == 'LIMIT' and bid['price'] < order.price:
                    break
                # 计算可成交数量
                match_qty = min(remaining_qty, bid['volume'])
                exec_price = bid['price']
                exec_qty += match_qty
                remaining_qty -= match_qty
                
        # 6. 如果完全没成交，返回失败
        if exec_qty <= 0:
            return False, None, None, "无对手盘"
            
        # 7. 应用滑点（仅市价单）
        if order.order_type == 'MARKET' and self.slippage > 0:
            if order.side == 'BUY':
                exec_price *= (1 + self.slippage)
            else:
                exec_price *= (1 - self.slippage)
                
        # 8. 确保成交价在涨跌停范围内
        exec_price = max(limit_down, min(limit_up, round(exec_price, 2)))
        
        # 更新订单状态
        if exec_qty == order.qty:
            order.status = 'FILLED'
        else:
            order.status = 'PARTIAL_FILLED'
            order.remaining_qty = remaining_qty
            
        self.trades.append({
            'order_id': order.order_id,
            'side': order.side,
            'stock_code': order.stock_code,
            'price': exec_price,
            'qty': exec_qty,
            'time': quote['time']
        })
        
        return True, exec_price, exec_qty, None
