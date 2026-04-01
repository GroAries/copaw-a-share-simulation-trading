#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多策略同时测试脚本 - 第一性原理公平对比
三个策略共享同一份实时行情，各自独立账户和撮合引擎
"""

import argparse
import time
from datetime import datetime
import sys

sys.path.insert(0, '..')

from data.tencent_feed import TencentRealtimeFeed
from core.account import Account
from engine.matching import MatchingEngine, Order
from strategies.all_weather_v5 import AllWeatherStrategyV5
from strategies.trading_skill_002_v22 import TradingSkill002V22
from strategies.trading_skill_003_v4 import TradingSkill003V4


def main():
    parser = argparse.ArgumentParser(description='多策略同时对比测试')
    parser.add_argument('--stocks', type=str, default='sh600000', help='单个股票代码（公平对比用）')
    parser.add_argument('--initial-cash', type=float, default=1000000.0, help='初始资金')
    parser.add_argument('--duration', type=int, default=600, help='测试时长（秒，默认10分钟）')
    parser.add_argument('--interval', type=int, default=3, help='行情刷新间隔（秒）')
    args = parser.parse_args()
    
    print("="*80)
    print("多策略同时对比测试 - 第一性原理公平对比")
    print("="*80)
    print(f"标的: {args.stocks}")
    print(f"初始资金: ¥{args.initial_cash:,.2f}")
    print(f"测试时长: {args.duration}秒")
    print(f"行情刷新间隔: {args.interval}秒")
    print("="*80)
    
    # 初始化三个独立的策略、账户、撮合引擎
    strategies = {
        'all_weather_v5': (AllWeatherStrategyV5(), Account(args.initial_cash), MatchingEngine()),
        'trading_skill_002_v2.2': (TradingSkill002V22(), Account(args.initial_cash), MatchingEngine()),
        'trading_skill_003_v4': (TradingSkill003V4(), Account(args.initial_cash), MatchingEngine())
    }
    
    # 初始化数据源
    feed = TencentRealtimeFeed()
    stock_list = args.stocks.split(',')
    
    # 计时器
    start_time = time.time()
    end_time = start_time + args.duration
    
    print("\n[*] 开始测试...")
    
    while time.time() < end_time:
        # 获取同一份行情数据
        try:
            quotes = feed.get_quotes(stock_list)
        except Exception as e:
            print(f"⚠️ 获取行情失败: {e}")
            time.sleep(args.interval)
            continue
        
        # 遍历每个策略
        for strategy_name, (strategy, account, engine) in strategies.items():
            for code, quote in quotes.items():
                # 构造市场状态
                market_state = {
                    'code': code,
                    'current_price': quote['current'],
                    'open_price': quote['open'],
                    'high_price': quote['high'],
                    'low_price': quote['low'],
                    'volume': quote['volume'],
                    'amount': quote['amount'],
                    'time': quote['time'],
                    'is_suspended': quote['is_suspended'],
                    'is_st': quote['is_st'],
                    'bids': quote['bids'],
                    'asks': quote['asks'],
                    'limit_up': quote['limit_up'],
                    'limit_down': quote['limit_down']
                }
                
                # 策略生成信号
                try:
                    signal = strategy.generate_signal(market_state, account)
                except Exception as e:
                    print(f"⚠️ {strategy_name} 生成信号失败: {e}")
                    continue
                
                # 处理信号
                if signal:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {strategy_name}:")
                    print(f"  {signal['side']} {code} - {signal['order_type']} {signal['qty']}股 @ ¥{market_state['current_price']:.2f}")
                    
                    # 生成订单
                    order = Order(
                        order_id=f"{strategy_name}_{int(time.time()*1000)}",
                        side=signal['side'],
                        stock_code=code,
                        order_type=signal['order_type'],
                        price=signal.get('price', market_state['current_price']),
                        qty=signal['qty'],
                        remaining_qty=signal['qty'],
                        timestamp=time.time()
                    )
                    
                    # 撮合订单
                    filled, fill_price, fill_qty, reason = engine.match_order_with_orderbook(
                        order, quote
                    )
                    
                    if filled:
                        if order.side == 'BUY':
                            account.apply_buy_order(code, fill_price, fill_qty)
                        else:
                            account.apply_sell_order(code, fill_price, fill_qty)
                        
                        print(f"  ✅ 成交: {fill_qty}股 @ ¥{fill_price:.2f}")
                        
                        # 打印账户状态
                        print(f"  可用资金: ¥{account.available_cash:,.2f}")
                        pos = account.positions.get(code, None)
                        if pos:
                            print(f"  持仓: {pos.total_qty}股 (可用{pos.available_qty}股), 成本¥{pos.cost_basis:.2f}")
                    else:
                        print(f"  ❌ 未成交: {reason}")
        
        # 等待刷新间隔
        time.sleep(args.interval)
    
    # 测试结束，输出对比结果
    print("\n" + "="*80)
    print("多策略对比测试结果")
    print("="*80)
    
    # 计算持仓市值
    last_quotes = feed.get_quotes(stock_list) if quotes else {}
    for strategy_name, (strategy, account, engine) in strategies.items():
        total_market_value = account.available_cash
        for code, pos in account.positions.items():
            if code in last_quotes:
                current_price = last_quotes[code]['current']
                market_value = pos.total_qty * current_price
                total_market_value += market_value
        
        # 计算收益率
        total_return = (total_market_value - args.initial_cash) / args.initial_cash * 100
        
        print(f"\n{strategy_name}:")
        print(f"  最终总资产: ¥{total_market_value:,.2f}")
        print(f"  总收益率: {total_return:+.2f}%")
        print(f"  可用资金: ¥{account.available_cash:,.2f}")
        print(f"  持仓数量: {len(account.positions)}只")
        print(f"  交易次数: {len(account.trade_history)}笔")
    
    print("\n" + "="*80)
    print("测试结束")
    print("="*80)


if __name__ == "__main__":
    main()
