'''
撮合引擎 - 模拟真实交易所的订单匹配
核心原则：价格优先、时间优先、成交量最大化
'''

import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from data.tencent_feed import Quote


@dataclass
class OrderBook:
    '''
    五档盘口数据模型
    基于Quote对象构建，反映真实市场流动性
    '''
    stock_code: str
    timestamp: Optional[datetime] = None
    bids: List[Tuple[float, int]] = field(default_factory=list)  # (价格, 量)列表，降序
    asks: List[Tuple[float, int]] = field(default_factory=list)  # (价格, 量)列表，升序

    @property
    def best_bid(self) -> Optional[Tuple[float, int]]:
        '''买一价和量'''
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[Tuple[float, int]]:
        '''卖一价和量'''
        return self.asks[0] if self.asks else None


class MatchingEngine:
    '''
    撮合引擎 - 基于第一性原理
    价格优先、时间优先、涨跌停排队机制
    '''
    
    def __init__(self):
        self.volume_history: Dict[str, int] = {}
    
    def set_volume_history(self, stock_code: str, avg_volume: int):
        '''设置股票的平均日成交量'''
        self.volume_history[stock_code] = avg_volume

    def _build_order_book(self, quote: Quote) -> OrderBook:
        '''从Quote构建五档盘口'''
        book = OrderBook(
            stock_code=quote.code,
            timestamp=quote.timestamp
        )
        
        # 构建买单（降序）
        book.bids = [
            (quote.bid_prices[i], quote.bid_volumes[i]) 
            for i in range(min(5, len(quote.bid_prices)))
            if quote.bid_prices[i] > 0 and quote.bid_volumes[i] > 0
        ]
        book.bids.sort(key=lambda x: x[0], reverse=True)

        # 构建卖单（升序）
        book.asks = [
            (quote.ask_prices[i], quote.ask_volumes[i]) 
            for i in range(min(5, len(quote.ask_prices)))
            if quote.ask_prices[i] > 0 and quote.ask_volumes[i] > 0
        ]
        book.asks.sort(key=lambda x: x[0])

        return book

    def _calculate_limit_hit_rate(self, quote: Quote, side: str) -> float:
        '''
        计算涨跌停成交概率
        公式: hit_rate = min(0.002, 50000 / max(total_volume, 1))
        '''
        if side == 'buy':
            total_volume = sum(quote.bid_volumes) if quote.bid_volumes else 0
        else:
            total_volume = sum(quote.ask_volumes) if quote.ask_volumes else 0
            
        return min(0.002, 50000 / max(total_volume, 1))

    def simulate_market_order(
        self,
        stock_code: str,
        side: str,
        qty: int,
        quote: Quote
    ) -> Tuple[bool, float, int, str]:
        '''模拟市价单撮合'''
        side = side.upper()
        book = self._build_order_book(quote)
        
        print(f"[调试] 市价单 {side} {stock_code} {qty}股, 盘口: 买={len(book.bids)}档, 卖={len(book.asks)}档")
        
        # 涨跌停特殊处理
        if quote.is_limit_up and side == 'BUY':
            return self._handle_limit_condition(book, qty, quote, side)
        if quote.is_limit_down and side == 'SELL':
            return self._handle_limit_condition(book, qty, quote, side)

        # 正常市场撮合
        if side == 'BUY':
            if not book.asks:
                # 没有卖盘，使用当前价
                return True, quote.current_price, qty, "市价成交（无卖盘，使用当前价）"
            return self._execute_buy_market(book, qty)
        else:
            if not book.bids:
                # 没有买盘，使用当前价
                return True, quote.current_price, qty, "市价成交（无买盘，使用当前价）"
            return self._execute_sell_market(book, qty)

    def simulate_limit_order(
        self,
        stock_code: str,
        side: str,
        qty: int,
        limit_price: float,
        quote: Quote
    ) -> Tuple[bool, float, int, str]:
        '''模拟限价单撮合'''
        side = side.upper()
        book = self._build_order_book(quote)
        
        print(f"[调试] 限价单 {side} {stock_code} {qty}股 @ {limit_price:.2f}")
        
        # 涨跌停特殊处理
        if quote.is_limit_up and side == 'BUY':
            if limit_price >= quote.current_price:
                return self._handle_limit_condition(book, qty, quote, side)
            return False, 0.0, 0, "限价低于涨停价，无法成交"
            
        if quote.is_limit_down and side == 'SELL':
            if limit_price <= quote.current_price:
                return self._handle_limit_condition(book, qty, quote, side)
            return False, 0.0, 0, "限价高于跌停价，无法成交"
            
        # 正常限价单撮合
        if side == 'BUY':
            if not book.asks or book.asks[0][0] > limit_price:
                return False, 0.0, 0, f"卖一价 {book.asks[0][0] if book.asks else '无'} > 限价 {limit_price:.2f}"
            return self._execute_buy_limit(book, qty, limit_price)
        else:
            if not book.bids or book.bids[0][0] < limit_price:
                return False, 0.0, 0, f"买一价 {book.bids[0][0] if book.bids else '无'} < 限价 {limit_price:.2f}"
            return self._execute_sell_limit(book, qty, limit_price)

    def _handle_limit_condition(
        self, 
        book: OrderBook, 
        qty: int, 
        quote: Quote, 
        side: str
    ) -> Tuple[bool, float, int, str]:
        '''处理涨跌停情况'''
        hit_rate = self._calculate_limit_hit_rate(quote, side)
        print(f"[调试] 涨跌停成交概率: {hit_rate:.4f}")
        
        if random.random() < hit_rate:
            fill_qty = min(qty, int(qty * hit_rate * 10))  # 提高一点成交概率
            return True, quote.current_price, fill_qty, f"{'涨' if side=='BUY' else '跌'}停成交 {fill_qty}/{qty}股"
        return False, 0.0, 0, f"{'涨' if side=='BUY' else '跌'}停排队失败"

    def _execute_buy_market(
        self, 
        book: OrderBook, 
        qty: int
    ) -> Tuple[bool, float, int, str]:
        '''执行市价买入'''
        fill_qty = min(qty, sum(v for _, v in book.asks))
        if fill_qty <= 0:
            return False, 0.0, 0, "卖盘不足"
            
        total_cost = 0
        remaining = fill_qty
        for price, volume in book.asks:
            if remaining <= 0:
                break
            take = min(remaining, volume)
            total_cost += price * take
            remaining -= take
            
        fill_price = total_cost / fill_qty
        return True, fill_price, fill_qty, f"市价成交 {fill_qty}/{qty}股"

    def _execute_sell_market(
        self, 
        book: OrderBook, 
        qty: int
    ) -> Tuple[bool, float, int, str]:
        '''执行市价卖出'''
        fill_qty = min(qty, sum(v for _, v in book.bids))
        if fill_qty <= 0:
            return False, 0.0, 0, "买盘不足"
            
        total_value = 0
        remaining = fill_qty
        for price, volume in book.bids:
            if remaining <= 0:
                break
            take = min(remaining, volume)
            total_value += price * take
            remaining -= take
            
        fill_price = total_value / fill_qty
        return True, fill_price, fill_qty, f"市价成交 {fill_qty}/{qty}股"

    def _execute_buy_limit(
        self, 
        book: OrderBook, 
        qty: int,
        limit_price: float
    ) -> Tuple[bool, float, int, str]:
        '''执行限价买入'''
        fill_qty = 0
        total_cost = 0
        for price, volume in book.asks:
            if price > limit_price:
                break
            if fill_qty >= qty:
                break
            take = min(qty - fill_qty, volume)
            total_cost += price * take
            fill_qty += take
            
        if fill_qty <= 0:
            return False, 0.0, 0, f"无卖盘满足限价 {limit_price:.2f}"
            
        fill_price = total_cost / fill_qty
        return True, fill_price, fill_qty, f"限价成交 {fill_qty}/{qty}股 @ {limit_price:.2f}"

    def _execute_sell_limit(
        self, 
        book: OrderBook, 
        qty: int,
        limit_price: float
    ) -> Tuple[bool, float, int, str]:
        '''执行限价卖出'''
        fill_qty = 0
        total_value = 0
        for price, volume in book.bids:
            if price < limit_price:
                break
            if fill_qty >= qty:
                break
            take = min(qty - fill_qty, volume)
            total_value += price * take
            fill_qty += take
            
        if fill_qty <= 0:
            return False, 0.0, 0, f"无买盘满足限价 {limit_price:.2f}"
            
        fill_price = total_value / fill_qty
        return True, fill_price, fill_qty, f"限价成交 {fill_qty}/{qty}股 @ {limit_price:.2f}"
