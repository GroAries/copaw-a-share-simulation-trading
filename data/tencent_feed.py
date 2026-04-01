#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯财经实时行情数据源 - 第一性原理：真实市场数据
"""

import requests
from typing import Dict, List
from dataclasses import dataclass
from datetime import time as dt_time


@dataclass
class Quote:
    """股票报价数据结构 - 第一性原理：完全对齐实盘数据"""
    code: str
    name: str
    current_price: float
    pre_close: float
    open_price: float
    high_price: float
    low_price: float
    volume: int
    amount: float
    change_pct: float
    trade_time_str: str
    
    @property
    def trade_time(self) -> dt_time:
        """解析交易时间为time对象"""
        # 腾讯格式: "20260327120106"
        hour = int(self.trade_time_str[8:10])
        minute = int(self.trade_time_str[10:12])
        second = int(self.trade_time_str[12:14])
        return dt_time(hour, minute, second)
    
    @property
    def stock_type(self) -> str:
        """判断股票板块类型"""
        code = self.code
        if 'ST' in self.name or 'st' in self.name:
            return 'ST'
        if code.startswith('300') or code.startswith('301'):
            return 'CYB'  # 创业板
        if code.startswith('688') or code.startswith('689'):
            return 'KCB'  # 科创板
        return 'MB'  # 主板
    
    @property
    def limit_up_price(self) -> float:
        """计算涨停价"""
        if self.pre_close <= 0:
            return self.current_price
        if self.stock_type == 'ST':
            return round(self.pre_close * 1.05, 2)
        elif self.stock_type in ['CYB', 'KCB']:
            return round(self.pre_close * 1.20, 2)
        else:  # 主板
            return round(self.pre_close * 1.10, 2)
    
    @property
    def limit_down_price(self) -> float:
        """计算跌停价"""
        if self.pre_close <= 0:
            return self.current_price
        if self.stock_type == 'ST':
            return round(self.pre_close * 0.95, 2)
        elif self.stock_type in ['CYB', 'KCB']:
            return round(self.pre_close * 0.80, 2)
        else:  # 主板
            return round(self.pre_close * 0.90, 2)
    
    @property
    def is_limit_up(self) -> bool:
        """是否涨停（严格判断）"""
        if self.pre_close <= 0:
            return False
        return abs(self.current_price - self.limit_up_price) < 0.01
    
    @property
    def is_limit_down(self) -> bool:
        """是否跌停（严格判断）"""
        if self.pre_close <= 0:
            return False
        return abs(self.current_price - self.limit_down_price) < 0.01
    
    @property
    def is_suspended(self) -> bool:
        """是否停牌（简化判断：成交量为0且价格不变）"""
        # 简化判断：成交量为0且当前价等于昨收价
        return self.volume == 0 and abs(self.current_price - self.pre_close) < 0.01


class TencentRealtimeFeed:
    """腾讯财经实时数据源"""
    
    def __init__(self):
        # 字段映射（根据实测验证）
        self.FIELD_MAP = {
            "name": 2,
            "current": 3,
            "open": 5,
            "volume": 6,
            "amount": 7,
            "time": 30,
            "pre_close": 85,
            "high": 41,
            "low": 42,
            "change_pct": 38
        }
        
    def get_quotes(self, stock_codes: List[str]) -> Dict[str, Quote]:
        """获取股票实时行情
        
        Args:
            stock_codes: 股票代码列表，如 ['sh600000', 'sz000001']
            
        Returns:
            行情字典 {code: Quote对象}
        """
        # 腾讯API格式要求：直接用逗号分隔的代码
        url = f"https://qt.gtimg.cn/mq={','.join(stock_codes)}"
        
        try:
            response = requests.get(url, timeout=5)
            response.encoding = 'gbk'
        except Exception as e:
            print(f"[!] 请求失败: {e}")
            return {}
            
        results = {}
        
        # 解析响应
        lines = response.text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if '=' not in line:
                continue
                
            # 格式: v_sh600000="1~浦发银行~600000~10.19~10.22~10.19~495325~504827855~...~20260327120106"
            parts = line.split('=', 1)
            if len(parts) < 2:
                continue
                
            code_part = parts[0]
            # 去掉前缀 "v_"
            code = code_part[2:] if code_part.startswith('v_') else code_part
            
            data_part = parts[1].strip('";')
            fields = data_part.split('~')
            
            if len(fields) < max(self.FIELD_MAP.values()) + 1:
                continue
                
            name = fields[self.FIELD_MAP['name']]
            
            def safe_float(idx):
                try:
                    return float(fields[idx])
                except:
                    return 0.0
                    
            def safe_int(idx):
                try:
                    return int(fields[idx])
                except:
                    return 0
                    
            # 创建Quote对象
            quote = Quote(
                code=code,
                name=name,
                current_price=safe_float(self.FIELD_MAP['current']),
                pre_close=safe_float(self.FIELD_MAP['pre_close']),
                open_price=safe_float(self.FIELD_MAP['open']),
                high_price=safe_float(self.FIELD_MAP['high']),
                low_price=safe_float(self.FIELD_MAP['low']),
                volume=safe_int(self.FIELD_MAP['volume']),
                amount=safe_float(self.FIELD_MAP['amount']),
                change_pct=safe_float(self.FIELD_MAP['change_pct']),
                trade_time_str=fields[self.FIELD_MAP['time']]
            )
            
            results[code] = quote
            
        return results
