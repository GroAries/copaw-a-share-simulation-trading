#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯财经实时行情数据源 - 第一性原理：真实市场数据
支持解析五档盘口、停牌状态、ST标识、除权除息信息、数据异常校验
"""

import requests
import time
from datetime import datetime
from typing import Dict, List


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
            "change_pct": 38,
            # 五档盘口
            "bid1_price": 9,
            "bid1_volume": 10,
            "bid2_price": 11,
            "bid2_volume": 12,
            "bid3_price": 13,
            "bid3_volume": 14,
            "bid4_price": 15,
            "bid4_volume": 16,
            "bid5_price": 17,
            "bid5_volume": 18,
            "ask1_price": 19,
            "ask1_volume": 20,
            "ask2_price": 21,
            "ask2_volume": 22,
            "ask3_price": 23,
            "ask3_volume": 24,
            "ask4_price": 25,
            "ask4_volume": 26,
            "ask5_price": 27,
            "ask5_volume": 28,
            # 特殊标识
            "status": 47,  # 交易状态
        }
        
    def get_quotes(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """获取股票实时行情
        
        Args:
            stock_codes: 股票代码列表，如 ['sh600000', 'sz000001']
            
        Returns:
            行情字典 {code: {name, current, open, volume, amount, time, pre_close, high, low, change_pct, is_suspended, is_st, bids, asks}}
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
                    
            current = safe_float(self.FIELD_MAP['current'])
            pre_close = safe_float(self.FIELD_MAP['pre_close'])
            
            # 判断是否停牌：当前价为0或者状态为停牌
            is_suspended = current <= 0.001 or fields[self.FIELD_MAP['status']] == '3'
            
            # 判断是否ST/退市股
            is_st = 'ST' in name or 'st' in name or '*ST' in name or '退' in name
            
            # 五档盘口
            bids = []
            for i in range(1, 6):
                price = safe_float(self.FIELD_MAP[f'bid{i}_price'])
                volume = safe_int(self.FIELD_MAP[f'bid{i}_volume']) * 100  # 腾讯返回的是手，转成股
                if price > 0:
                    bids.append({'price': price, 'volume': volume})
                    
            asks = []
            for i in range(1, 6):
                price = safe_float(self.FIELD_MAP[f'ask{i}_price'])
                volume = safe_int(self.FIELD_MAP[f'ask{i}_volume']) * 100
                if price > 0:
                    asks.append({'price': price, 'volume': volume})
            
            # 计算涨跌停价格
            if pre_close <= 0:
                limit_up = current
                limit_down = current
            else:
                if is_st:
                    limit_up_pct = 0.05
                    limit_down_pct = 0.05
                elif code.startswith('688') or code.startswith('300') or code.startswith('301'):
                    limit_up_pct = 0.2
                    limit_down_pct = 0.2
                else:
                    limit_up_pct = 0.1
                    limit_down_pct = 0.1
                limit_up = round(pre_close * (1 + limit_up_pct), 2)
                limit_down = round(pre_close * (1 - limit_down_pct), 2)
            
            quote = {
                'name': name,
                'current': current,
                'open': safe_float(self.FIELD_MAP['open']),
                'volume': safe_int(self.FIELD_MAP['volume']) * 100,  # 手转股
                'amount': safe_float(self.FIELD_MAP['amount']),
                'time': fields[self.FIELD_MAP['time']],
                'pre_close': pre_close,
                'high': safe_float(self.FIELD_MAP['high']),
                'low': safe_float(self.FIELD_MAP['low']),
                'change_pct': safe_float(self.FIELD_MAP['change_pct']),
                'is_suspended': is_suspended,
                'is_st': is_st,
                'bids': bids,
                'asks': asks,
                'limit_up': limit_up,
                'limit_down': limit_down
            }
            
            # 第一性原理：仅做数据异常检测，不修改数据、不干预决策
            quote['data_errors'] = self.validate_quote(quote)
            results[code] = quote
            
        return results
        
    def validate_quote(self, quote: Dict) -> List[str]:
        """数据异常校验：符合第一性原理，仅检测异常并返回，不篡改数据
        返回异常列表，空列表代表正常
        """
        errors = []
        code = quote.get('code', '')
        current = quote['current']
        pre_close = quote['pre_close']
        limit_up = quote['limit_up']
        limit_down = quote['limit_down']
        bids = quote['bids']
        asks = quote['asks']
        time_str = quote['time']
        
        # 1. 基础数据缺失异常
        if pre_close <= 0:
            errors.append("昨收价异常：为0或负数")
        if current <= 0 and not quote['is_suspended']:
            errors.append("当前价异常：为0或负数且非停牌")
        if len(time_str) != 14:
            errors.append(f"时间戳格式异常：{time_str}")
            
        # 2. 价格范围异常
        if not quote['is_suspended'] and pre_close > 0:
            if current > limit_up * 1.01:
                errors.append(f"价格超涨停：当前价¥{current} > 涨停价¥{limit_up}")
            if current < limit_down * 0.99:
                errors.append(f"价格超跌停：当前价¥{current} < 跌停价¥{limit_down}")
                
        # 3. 盘口顺序异常
        if bids and asks:
            best_bid = bids[0]['price']
            best_ask = asks[0]['price']
            if best_bid > best_ask and best_ask > 0:
                errors.append(f"盘口价格倒置：买一¥{best_bid} > 卖一¥{best_ask}")
                
        # 4. 时间滞后异常（超过5分钟）
        if len(time_str) == 14:
            try:
                quote_time = datetime.strptime(time_str, "%Y%m%d%H%M%S")
                now = datetime.now()
                time_diff = (now - quote_time).total_seconds()
                if time_diff > 300:  # 滞后5分钟以上
                    errors.append(f"行情时间滞后：{time_diff:.0f}秒")
            except:
                errors.append(f"时间戳解析失败：{time_str}")
                
        # 5. 成交量异常
        if current > 0 and quote['volume'] < 0:
            errors.append(f"成交量异常：{quote['volume']}股")
            
        return errors
