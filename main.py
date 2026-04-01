#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟盘主入口 - 第一性原理：系统只提供数据、规则、执行，不干预决策
整合腾讯实时行情（含五档盘口/停牌/ST）、账户管理、撮合引擎（集合竞价/隔夜单/偷价防护）
"""

import argparse
import time
from datetime import datetime, time as dt_time

from data.tencent_feed import TencentRealtimeFeed
from core.account import Account
from engine.matching import MatchingEngine, Order
from strategies.random_strategy import RandomStrategy


def parse_trade_time(trade_time_str: str) -> dt_time:
    """解析腾讯API的trade_time字符串为time对象
    
    腾讯格式: "20260327120106"
    """
    # 去掉日期部分，只取时间
    # 20260327120106 -> 12:01:06
    hour = int(trade_time_str[8:10])
    minute = int(trade_time_str[10:12])
    second = int(trade_time_str[12:14])
    return dt_time(hour, minute, second)


def main():
    parser = argparse.ArgumentParser(description='A股模拟盘 - 第一性原理')
    parser.add_argument('--stocks', type=str, default='sh600000,sz000001', help='股票代码，逗号分隔')
    parser.add_argument('--initial-cash', type=float, default=1000000.0, help='初始资金')
    parser.add_argument('--duration', type=int, default=60, help='运行时长（秒）')
    parser.add_argument('--interval', type=int, default=3, help='行情刷新间隔（秒）')
    parser.add_argument('--allow-overnight', action='store_true', help='允许挂隔夜单')
    args = parser.parse_args()
    
    stock_list = args.stocks.split(',')
    
    feed = TencentRealtimeFeed()
    account = Account(initial_cash=args.initial_cash)
    engine = MatchingEngine(slippage=0.001)
    strategy = RandomStrategy()
    
    print(f"[*] 模拟盘启动 - 第一性原理")
    print(f"    股票池: {stock_list}")
    print(f"    初始资金: ¥{account.initial_cash:,.2f}")
    print(f"    运行时长: {args.duration}秒")
    print(f"    隔夜单: {'允许' if args.allow_overnight else '禁止'}")
    print("="*60)
    
    start_time = time.time()
    prev_positions = {}
    
    try:
        while time.time() - start_time < args.duration:
            # 获取行情
            quotes = feed.get_quotes(stock_list)
            
            for stock_code, quote in quotes.items():
                # 第一性原理：系统从不给出买卖建议，只提供行情数据
                # 决策完全由策略做出
                
                # 构造市场状态
                market_state = {
                    'code': stock_code,
                    'name': quote['name'],
                    'current_price': quote['current'],
                    'pre_close': quote['pre_close'],
                    'volume': quote['volume'],
                    'amount': quote['amount'],
                    'change_pct': quote['change_pct'],
                    'time': quote['time'],
                    'is_suspended': quote['is_suspended'],
                    'is_st': quote['is_st'],
                    'bids': quote['bids'],
                    'asks': quote['asks'],
                    'limit_up': quote['limit_up'],
                    'limit_down': quote['limit_down']
                }
                
                # 调用策略（系统不干预）
                signal = strategy.generate_signal(market_state, account)
                
                if signal:
                    side = signal['side']
                    qty = signal['qty']
                    price = signal.get('price')
                    order_type = 'LIMIT' if price else 'MARKET'
                    is_overnight = signal.get('is_overnight', False) and args.allow_overnight
                    
                    # 创建订单
                    order = Order(
                        order_id=f"ORD_{int(time.time()*1000000)}",
                        side=side,
                        stock_code=stock_code,
                        order_type=order_type,
                        price=price if price else 0.0,
                        qty=qty,
                        remaining_qty=qty,
                        timestamp=time.time(),
                        is_overnight=is_overnight
                    )
                    
                    # 撮合
                    matched, exec_price, exec_qty, reason = engine.match_order_with_orderbook(
                        order=order,
                        quote=quote
                    )
                    
                    if matched and exec_price and exec_qty:
                        if side == 'BUY':
                            # 检查可用资金
                            amount = exec_price * exec_qty
                            costs = account.calculate_trading_costs('BUY', exec_price, exec_qty, stock_code)
                            total = amount + costs
                            if account.available_cash < total:
                                print(f"[!] 资金不足，拒绝买入 {quote['name']} ({stock_code})")
                                continue
                            success = account.apply_buy_order(exec_price, exec_qty, stock_code)
                            if success:
                                print(f"[*] BUY {quote['name']} ({stock_code}): {exec_qty}股 @ ¥{exec_price:.2f}")
                        else:
                            success, pnl = account.apply_sell_order(exec_price, exec_qty, stock_code)
                            if success:
                                print(f"[*] SELL {quote['name']} ({stock_code}): {exec_qty}股 @ ¥{exec_price:.2f} | 盈亏: ¥{pnl:.2f}")
                    else:
                        if reason:
                            print(f"[!] 订单状态 {quote['name']} ({stock_code}): {reason}")
            
            # 打印当前状态
            print("-"*60)
            print(f"账户可用资金: ¥{account.available_cash:,.2f}")
            print(f"账户总资金: ¥{account.total_cash:,.2f}")
            print(f"账户冻结资金: ¥{account.frozen_cash:,.2f}")
            print("持仓:")
            for code, pos in account.positions.items():
                print(f"  {code}: 总{pos.total_qty}股, 可用{pos.available_qty}股, 成本¥{pos.cost_basis:.2f}")
            print("="*60)
            
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n[!] 模拟盘停止")
    
    # 计算最终市值
    final_quotes = feed.get_quotes(stock_list)
    market_value = 0.0
    for code, pos in account.positions.items():
        if code in final_quotes:
            market_value += pos.total_qty * final_quotes[code]['current']
    
    total_assets = account.total_cash + market_value
    total_return = (total_assets - account.initial_cash) / account.initial_cash * 100
    
    print("\n" + "="*60)
    print("模拟盘结束")
    print(f"初始资金: ¥{account.initial_cash:,.2f}")
    print(f"最终资产: ¥{total_assets:,.2f}")
    print(f"总收益率: {total_return:+.2f}%")
    print("="*60)


if __name__ == '__main__':
    main()
