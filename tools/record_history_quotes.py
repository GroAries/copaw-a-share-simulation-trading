#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史行情录制工具 - 录制腾讯财经实盘五档行情，用于回放测试
第一性原理：完全录制原始数据，不做任何修改，保证回放时和实盘完全一致
"""

import argparse
import json
import time
import os
from datetime import datetime
import sys

sys.path.insert(0, '..')

from data.tencent_feed import TencentRealtimeFeed


def main():
    parser = argparse.ArgumentParser(description='历史行情录制工具')
    parser.add_argument('--stocks', type=str, default='sh600000,sz300750,688981', help='股票代码，逗号分隔')
    parser.add_argument('--duration', type=int, default=3600, help='录制时长（秒，默认1小时）')
    parser.add_argument('--interval', type=int, default=3, help='录制间隔（秒）')
    parser.add_argument('--output', type=str, default='history_quotes.json', help='输出文件路径')
    args = parser.parse_args()
    
    stock_list = args.stocks.split(',')
    feed = TencentRealtimeFeed()
    records = []
    
    print(f"[*] 开始录制行情，标的: {stock_list}, 时长: {args.duration}秒, 间隔: {args.interval}秒")
    print(f"[*] 输出文件: {args.output}")
    
    start_time = time.time()
    count = 0
    
    try:
        while time.time() - start_time < args.duration:
            timestamp = time.time()
            datetime_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            
            quotes = feed.get_quotes(stock_list)
            
            if quotes:
                records.append({
                    'timestamp': timestamp,
                    'datetime': datetime_str,
                    'quotes': quotes
                })
                count += 1
                print(f"\r[*] 已录制 {count} 条数据，当前时间: {datetime_str}", end='', flush=True)
                
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n[!] 录制中断")
    
    # 保存文件
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 录制完成，共 {len(records)} 条数据，保存到 {args.output}")
    

if __name__ == '__main__':
    main()
