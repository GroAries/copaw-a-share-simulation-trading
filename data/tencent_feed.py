import time
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time


@dataclass
class Quote:
    """股票报价数据结构（支持回测模式的最小字段集）"""
    code: str           # 股票代码 (如 sh600000)
    current_price: float  # 当前价（必填）
    trade_time: str      # 交易时间（必填）
    
    # 可选字段（实时模式需要，回测模式可选）
    name: str = ""        # 股票名称
    open_price: float = 0.0  # 开盘价
    high_price: float = 0.0  # 最高价
    low_price: float = 0.0  # 最低价
    pre_close: float = 0.0  # 昨收价
    volume: int = 0         # 成交量 (股)
    amount: float = 0.0     # 成交额 (元)
    change_pct: float = 0.0 # 涨跌幅 (%)
    
    # 五档盘口数据
    bid_prices: List[float] = field(default_factory=list)
    bid_volumes: List[int] = field(default_factory=list)
    ask_prices: List[float] = field(default_factory=list)
    ask_volumes: List[int] = field(default_factory=list)
    
    @property
    def market(self) -> str:
        """市场标识 (sh/sz)"""
        return self.code[:2] if len(self.code) >= 2 else ""
    
    @property
    def stock_code(self) -> str:
        """纯股票代码"""
        return self.code[2:] if len(self.code) > 2 else self.code
    
    @property
    def is_limit_up(self) -> bool:
        """是否涨停"""
        if self.pre_close <= 0:
            return False
        limit_price = round(self.pre_close * 1.095, 2)
        return abs(self.current_price - limit_price) < 0.01
    
    @property
    def is_limit_down(self) -> bool:
        """是否跌停"""
        if self.pre_close <= 0:
            return False
        limit_price = round(self.pre_close * 0.905, 2)
        return abs(self.current_price - limit_price) < 0.01
    
    @property
    def timestamp(self) -> Optional[datetime]:
        """转换为 datetime 对象"""
        try:
            return datetime.strptime(self.trade_time, "%Y%m%d%H%M%S")
        except:
            return None


class TencentDataFeed:
    """
    腾讯财经实时数据推送
    核心原则：所有时间判断以数据时间戳为准
    """
    
    # 字段映射（根据实测验证 2026-04-01）
    FIELD_MAP = {
        "name": 1,               # 股票名称
        "stock_code_raw": 2,     # 纯股票代码
        "current_price": 3,      # 当前价
        "open_price": 4,         # 开盘价
        "high_price": 5,         # 最高价
        "low_price": 6,          # 最低价
        "volume": 7,             # 成交量（手）→ 需 ×100
        "amount": 8,             # 成交额（元）
        "pre_close": 9,          # 昨收价
        
        # 五档买盘（从索引9开始）
        'bid1_price': 9, 'bid1_volume': 10,
        'bid2_price': 11, 'bid2_volume': 12,
        'bid3_price': 13, 'bid3_volume': 14,
        'bid4_price': 15, 'bid4_volume': 16,
        'bid5_price': 17, 'bid5_volume': 18,
        
        # 五档卖盘（从索引19开始）
        'ask1_price': 19, 'ask1_volume': 20,
        'ask2_price': 21, 'ask2_volume': 22,
        'ask3_price': 23, 'ask3_volume': 24,
        'ask4_price': 25, 'ask4_volume': 26,
        'ask5_price': 27, 'ask5_volume': 28,
        
        "trade_time": 30,        # 交易时间
        "change_pct": 31         # 涨跌幅 (%)
    }
    
    def __init__(self, cache_ttl: int = 5):
        self.cache: Dict[str, Quote] = {}
        self.cache_time: Dict[str, float] = {}
        self.cache_ttl = cache_ttl
        self.stock_pool: List[str] = []
        
    def set_stock_pool(self, codes: List[str]):
        """设置监控的股票池（代码需带市场前缀，如 sh600000）"""
        self.stock_pool = [c if c[:2] in ['sh', 'sz'] else f"sh{c}" for c in codes]
        
    def _safe_float(self, s: str) -> float:
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    def _safe_int(self, s: str) -> int:
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return 0

    def _parse_response(self, response: str) -> Dict[str, Quote]:
        """解析腾讯财经批量API响应"""
        results = {}
        
        for line in response.split('\n'):
            if not line.strip():
                continue
            
            if '=' not in line:
                continue
                
            parts = line.split('=', 1)
            code = parts[0][2:]  # 移除前缀 v_ (得到 "sh600000")
            
            if not parts[1].strip() or parts[1] == '""':
                continue
                
            # 移除引号并分割字段（腾讯API使用~分隔）
            fields = parts[1].strip('"; ').split('~')
            
            if len(fields) < 32:
                continue

            # 构建五档盘口
            bid_prices = []
            bid_volumes = []
            ask_prices = []
            ask_volumes = []
            
            for i in range(1, 6):
                # 买盘
                b_price = self._safe_float(fields[self.FIELD_MAP[f'bid{i}_price']])
                b_volume = self._safe_int(fields[self.FIELD_MAP[f'bid{i}_volume']])
                if b_price > 0 and b_volume > 0:
                    bid_prices.append(b_price)
                    bid_volumes.append(b_volume)
                
                # 卖盘
                a_price = self._safe_float(fields[self.FIELD_MAP[f'ask{i}_price']])
                a_volume = self._safe_int(fields[self.FIELD_MAP[f'ask{i}_volume']])
                if a_price > 0 and a_volume > 0:
                    ask_prices.append(a_price)
                    ask_volumes.append(a_volume)

            # 涨跌幅处理
            change_pct = self._safe_float(fields[self.FIELD_MAP['change_pct']])
            
            # 成交量转换（手→股）
            volume = self._safe_int(fields[self.FIELD_MAP['volume']]) * 100
            
            # 创建Quote对象
            quote = Quote(
                code=code,
                name=fields[self.FIELD_MAP['name']],
                current_price=self._safe_float(fields[self.FIELD_MAP['current_price']]),
                open_price=self._safe_float(fields[self.FIELD_MAP['open_price']]),
                high_price=self._safe_float(fields[self.FIELD_MAP['high_price']]),
                low_price=self._safe_float(fields[self.FIELD_MAP['low_price']]),
                pre_close=self._safe_float(fields[self.FIELD_MAP['pre_close']]),
                volume=volume,
                amount=self._safe_float(fields[self.FIELD_MAP['amount']]),
                change_pct=change_pct,
                trade_time=fields[self.FIELD_MAP['trade_time']],
                bid_prices=bid_prices,
                bid_volumes=bid_volumes,
                ask_prices=ask_prices,
                ask_volumes=ask_volumes
            )
            
            results[code] = quote
            print(f"[调试] 成功解析 {code} 行情: {quote.current_price:.2f} 买1: {bid_prices[0] if bid_prices else '无'} 卖1: {ask_prices[0] if ask_prices else '无'}")
            
        return results
        
    def get_quote(self) -> Dict[str, Quote]:
        """获取最新行情"""
        if not self.stock_pool:
            return {}
            
        # 批量查询
        url = f"https://qt.gtimg.cn/mq={','.join(self.stock_pool)}"
        print(f"[调试] 请求URL: {url}")
        
        try:
            response = requests.get(url, timeout=3)
            response.encoding = 'gbk'
            print(f"[调试] 响应内容: {response.text[:300]}...")
        except Exception as e:
            print(f"[错误] 请求失败: {e}")
            return self.cache
            
        new_quotes = self._parse_response(response.text)
        
        # 更新缓存
        now = time.time()
        for code, quote in new_quotes.items():
            self.cache[code] = quote
            self.cache_time[code] = now
            
        # 清理过期缓存
        expired = [c for c, t in self.cache_time.items() if now - t > self.cache_ttl]
        for c in expired:
            self.cache.pop(c, None)
            self.cache_time.pop(c, None)
            
        print(f"[调试] 成功解析 {len(new_quotes)} 条行情")
        return {code: self.cache[code] for code in self.stock_pool if code in self.cache}
        
    def get_latest_timestamp(self) -> Optional[datetime]:
        """获取最新时间戳（从缓存数据）"""
        timestamps = [q.timestamp for q in self.cache.values() if q.timestamp]
        return max(timestamps) if timestamps else None
