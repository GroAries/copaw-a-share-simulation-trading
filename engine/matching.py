#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
撮合引擎 - 第一性原理：完全对齐A股实盘撮合规则
基于五档盘口、价格优先时间优先队列、集合竞价、隔夜单、偷价防护
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
from datetime import time, datetime
import heapq
import time as sys_time


# 交易时段定义
TRADING_PERIODS = {
    'CALL_AUCTION': (time(9, 15), time(9, 25)),  # 集合竞价
    'MORNING_CONTINUOUS': (time(9, 30), time(11, 30)),  # 上午连续竞价
    'AFTERNOON_CONTINUOUS': (time(13, 0), time(15, 0))     # 下午连续竞价
}


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
    is_overnight: bool = False  # 是否隔夜单
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
        # 偷价防护：记录每个订单的挂单时间，拒绝使用挂单前的价格成交
        self.order_submit_time: Dict[str, str] = {}
        
    def get_order_book(self, stock_code: str) -> OrderBook:
        """获取或创建订单簿"""
        if stock_code not in self.order_books:
            self.order_books[stock_code] = OrderBook()
        return self.order_books[stock_code]
        
    def get_trading_session(self, trade_time: time) -> Optional[str]:
        """获取当前交易时段"""
        for session, (start, end) in TRADING_PERIODS.items():
            if start <= trade_time <= end:
                return session
        # 检查是否可以挂隔夜单（收盘后）
        if trade_time >= time(15, 0) or trade_time < time(9, 15):
            return 'OVERNIGHT'
        return None
        
    def match_call_auction(self, stock_code: str, quote: Dict) -> List[Tuple[float, int]]:
        """集合竞价撮合：最大成交量原则（简化版）"""
        # 简化集合竞价：取卖一和买一的中间价，或者用昨收价
        # 实际更复杂的最大成交量撮合需要更完整的订单簿，这里先简化
        book = self.get_order_book(stock_code)
        best_bid = book.get_best_bid()
        best_ask = book.get_best_ask()
        
        if best_bid and best_ask:
            # 取中间价
            exec_price = (best_bid.price + best_ask.price) / 2
            exec_qty = min(best_bid.remaining_qty, best_ask.remaining_qty)
            return [(round(exec_price, 2), exec_qty)]
        elif quote['pre_close'] > 0:
            # 没有对手单，用昨收价
            return [(quote['pre_close'], 0)]
        else:
            return []
        
    def match_order_with_orderbook(
        self,
        order: Order,
        quote: Dict
    ) -> Tuple[bool, Optional[float], Optional[int], Optional[str]]:
        """撮合订单（含集合竞价、隔夜单、偷价防护）
        
        返回: (是否成交, 成交价格, 成交数量, 拒绝原因)
        """
        # 1. 解析交易时间
        trade_time_str = quote['time']
        if len(trade_time_str) >= 14:
            hour = int(trade_time_str[8:10])
            minute = int(trade_time_str[10:12])
            second = int(trade_time_str[12:14])
            trade_time = time(hour, minute, second)
        else:
            trade_time = time(10, 0, 0)
            
        session = self.get_trading_session(trade_time)
        
        # 2. 隔夜单处理
        if session == 'OVERNIGHT':
            if not order.is_overnight:
                # 非隔夜单，在非交易时段拒绝
                return False, None, None, "非交易时段，仅可挂隔夜单"
            # 隔夜单加入订单簿，暂不撮合
            book = self.get_order_book(order.stock_code)
            book.add_order(order)
            self.order_submit_time[order.order_id] = trade_time_str
            order.status = 'PENDING'
            return False, None, None, "隔夜单已添加，待次日开盘撮合"
            
        # 3. 检查停牌
        if quote['is_suspended']:
            return False, None, None, "股票停牌"
            
        # 4. 检查涨跌停限制
        limit_up = quote['limit_up']
        limit_down = quote['limit_down']
        
        # 超涨跌停挂单废单
        if order.side == 'BUY':
            if order.order_type == 'LIMIT' and order.price > limit_up:
                return False, None, None, "买单价格超涨停板"
        else:  # SELL
            if order.order_type == 'LIMIT' and order.price < limit_down:
                return False, None, None, "卖单价格超跌停板"
                
        # 5. 封涨跌停完全禁止成交
        if quote['current'] >= limit_up:
            if order.side == 'BUY':
                if not quote['asks'] or quote['asks'][0]['price'] >= limit_up:
                    return False, None, None, "涨停板无法买入"
        if quote['current'] <= limit_down:
            if order.side == 'SELL':
                if not quote['bids'] or quote['bids'][0]['price'] <= limit_down:
                    return False, None, None, "跌停板无法卖出"
                    
        # 6. 偷价防护：检查成交价格的时间
        # 这里简化：记录挂单时间，确保使用挂单之后的行情
        if order.order_id not in self.order_submit_time:
            self.order_submit_time[order.order_id] = trade_time_str
        else:
            # 确保quote的时间不早于挂单时间
            submit_time = self.order_submit_time[order.order_id]
            if trade_time_str < submit_time:
                return False, None, None, "偷价防护：禁止使用挂单前的历史价格"
                
        # 7. 分时段撮合
        exec_price = None
        exec_qty = 0
        remaining_qty = order.qty
        
        if session == 'CALL_AUCTION':
            # 集合竞价
            matches = self.match_call_auction(order.stock_code, quote)
            if matches:
                exec_price, exec_qty = matches[0]
        else:
            # 连续竞价：基于实盘五档盘口撮合
            if order.side == 'BUY':
                # 买入：从卖一到卖五依次匹配
                for ask in quote['asks']:
                    if remaining_qty <= 0:
                        break
                    if order.order_type == 'LIMIT' and ask['price'] > order.price:
                        break
                    match_qty = min(remaining_qty, ask['volume'])
                    exec_price = ask['price']
                    exec_qty += match_qty
                    remaining_qty -= match_qty
            else:  # SELL
                # 卖出：从买一到买五依次匹配
                for bid in quote['bids']:
                    if remaining_qty <= 0:
                        break
                    if order.order_type == 'LIMIT' and bid['price'] < order.price:
                        break
                    match_qty = min(remaining_qty, bid['volume'])
                    exec_price = bid['price']
                    exec_qty += match_qty
                    remaining_qty -= match_qty
                    
        # 8. 如果完全没成交，把限价单加入内部订单簿
        if exec_qty <= 0:
            if order.order_type == 'LIMIT':
                book = self.get_order_book(order.stock_code)
                book.add_order(order)
                order.status = 'PENDING'
            return False, None, None, "无对手盘"
            
        # 9. 应用滑点（仅市价单）
        if order.order_type == 'MARKET' and self.slippage > 0:
            if order.side == 'BUY':
                exec_price *= (1 + self.slippage)
            else:
                exec_price *= (1 - self.slippage)
                
        # 10. 确保成交价在涨跌停范围内
        exec_price = max(limit_down, min(limit_up, round(exec_price, 2)))
        
        # 更新订单状态
        if exec_qty == order.qty:
            order.status = 'FILLED'
        else:
            order.status = 'PARTIAL_FILLED'
            order.remaining_qty = remaining_qty
            # 剩余部分加入订单簿
            if order.order_type == 'LIMIT':
                book = self.get_order_book(order.stock_code)
                book.add_order(order)
            
        self.trades.append({
            'order_id': order.order_id,
            'side': order.side,
            'stock_code': order.stock_code,
            'price': exec_price,
            'qty': exec_qty,
            'time': quote['time'],
            'session': session
        })
        
        return True, exec_price, exec_qty, None
