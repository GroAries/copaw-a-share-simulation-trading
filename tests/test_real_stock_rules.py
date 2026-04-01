#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对照实盘强制标准验证模拟盘规则
"""

import sys
from datetime import time

sys.path.insert(0, '..')

from core.account import Account
from engine.matching import MatchingEngine, Order


def test_rule_1_price_limits_by_board():
    """规则1：区分涨跌停板块幅度"""
    print("[测试1] 区分涨跌停板块幅度")
    engine = MatchingEngine()
    pre_close = 100.0
    
    # 主板10%
    limit_up, limit_down = engine.get_price_limit('sh600000', pre_close)
    assert abs(limit_up - 110.0) < 0.01, f"主板涨停错误: {limit_up}"
    assert abs(limit_down - 90.0) < 0.01, f"主板跌停错误: {limit_down}"
    print("  ✅ 主板10%涨跌停")
    
    # 科创板20%
    limit_up, limit_down = engine.get_price_limit('688981', pre_close)
    assert abs(limit_up - 120.0) < 0.01, f"科创板涨停错误: {limit_up}"
    assert abs(limit_down - 80.0) < 0.01, f"科创板跌停错误: {limit_down}"
    print("  ✅ 科创板20%涨跌停")
    
    # 创业板20%
    limit_up, limit_down = engine.get_price_limit('300750', pre_close)
    assert abs(limit_up - 120.0) < 0.01, f"创业板涨停错误: {limit_up}"
    assert abs(limit_down - 80.0) < 0.01, f"创业板跌停错误: {limit_down}"
    print("  ✅ 创业板20%涨跌停")
    print("✅ [测试1] 全部通过\n")


def test_rule_2_order_outside_limit_is_rejected():
    """规则2：超涨跌停挂单废单"""
    print("[测试2] 超涨跌停挂单废单")
    engine = MatchingEngine()
    account = Account(initial_cash=1000000)
    pre_close = 10.0
    limit_up = 11.0
    limit_down = 9.0
    current_price = 10.5
    trade_time = time(10, 0, 0)
    volume = 1000000
    
    # 超涨停买单
    order = Order(order_id="1", side="BUY", stock_code="sh600000", order_type="LIMIT", price=11.01, qty=100, timestamp=0)
    matched, exec_price, reason = engine.match_order(order, current_price, pre_close, trade_time, volume)
    assert not matched, "超涨停买单应该被拒绝"
    assert "涨停板" in reason or "超涨停" in reason, f"拒绝原因错误: {reason}"
    print("  ✅ 超涨停买单废单")
    
    # 超跌停卖单
    order = Order(order_id="2", side="SELL", stock_code="sh600000", order_type="LIMIT", price=8.99, qty=100, timestamp=0)
    matched, exec_price, reason = engine.match_order(order, current_price, pre_close, trade_time, volume)
    assert not matched, "超跌停卖单应该被拒绝"
    assert "跌停板" in reason or "超跌停" in reason, f"拒绝原因错误: {reason}"
    print("  ✅ 超跌停卖单废单")
    print("✅ [测试2] 全部通过\n")


def test_rule_3_limit_up_cannot_buy_limit_down_cannot_sell():
    """规则3：封涨跌停完全禁止成交"""
    print("[测试3] 封涨跌停完全禁止成交")
    engine = MatchingEngine()
    pre_close = 10.0
    limit_up = 11.0
    limit_down = 9.0
    trade_time = time(10, 0, 0)
    volume = 1000000
    
    # 涨停时买入
    order = Order(order_id="1", side="BUY", stock_code="sh600000", order_type="MARKET", price=0, qty=100, timestamp=0)
    matched, exec_price, reason = engine.match_order(order, limit_up, pre_close, trade_time, volume)
    assert not matched, "涨停时不能买入"
    assert "涨停板无法买入" in reason, f"拒绝原因错误: {reason}"
    print("  ✅ 涨停无法买入")
    
    # 跌停时卖出
    order = Order(order_id="2", side="SELL", stock_code="sh600000", order_type="MARKET", price=0, qty=100, timestamp=0)
    matched, exec_price, reason = engine.match_order(order, limit_down, pre_close, trade_time, volume)
    assert not matched, "跌停时不能卖出"
    assert "跌停板无法卖出" in reason, f"拒绝原因错误: {reason}"
    print("  ✅ 跌停无法卖出")
    print("✅ [测试3] 全部通过\n")


def test_rule_4_no_counterparty_no_deal():
    """规则4：无对手盘不成交"""
    print("[测试4] 无对手盘不成交")
    engine = MatchingEngine()
    pre_close = 10.0
    current_price = 10.5
    trade_time = time(10, 0, 0)
    volume = 0  # 无成交量
    
    order = Order(order_id="1", side="BUY", stock_code="sh600000", order_type="MARKET", price=0, qty=100, timestamp=0)
    matched, exec_price, reason = engine.match_order(order, current_price, pre_close, trade_time, volume)
    assert not matched, "无对手盘不能成交"
    assert "无对手盘" in reason, f"拒绝原因错误: {reason}"
    print("  ✅ 无对手盘不成交")
    print("✅ [测试4] 全部通过\n")


def test_rule_5_trading_period():
    """规则5：交易时段匹配"""
    print("[测试5] 交易时段匹配")
    engine = MatchingEngine()
    pre_close = 10.0
    current_price = 10.5
    volume = 1000000
    
    # 非交易时段
    non_trade_time = time(8, 0, 0)
    order = Order(order_id="1", side="BUY", stock_code="sh600000", order_type="MARKET", price=0, qty=100, timestamp=0)
    matched, exec_price, reason = engine.match_order(order, current_price, pre_close, non_trade_time, volume)
    assert not matched, "非交易时段不能成交"
    assert "非交易时段" in reason, f"拒绝原因错误: {reason}"
    print("  ✅ 非交易时段拒绝")
    
    # 交易时段
    trade_time = time(10, 0, 0)
    order = Order(order_id="2", side="BUY", stock_code="sh600000", order_type="MARKET", price=0, qty=100, timestamp=0)
    matched, exec_price, reason = engine.match_order(order, current_price, pre_close, trade_time, volume)
    assert matched, "交易时段应该成交"
    print("  ✅ 交易时段允许")
    print("✅ [测试5] 全部通过\n")


def test_rule_6_freeze_unfreeze_cash():
    """规则6：资金冻结/解冻"""
    print("[测试6] 资金冻结/解冻")
    account = Account(initial_cash=100000)
    amount = 10000
    
    # 冻结资金
    assert account.freeze_cash(amount), "冻结资金应该成功"
    assert abs(account.frozen_cash - amount) < 0.01, f"冻结金额错误: {account.frozen_cash}"
    assert abs(account.available_cash - (100000 - amount)) < 0.01, f"可用金额错误: {account.available_cash}"
    print("  ✅ 资金冻结")
    
    # 解冻资金
    account.unfreeze_cash(amount)
    assert abs(account.frozen_cash) < 0.01, f"解冻后冻结金额错误: {account.frozen_cash}"
    assert abs(account.available_cash - 100000) < 0.01, f"解冻后可用金额错误: {account.available_cash}"
    print("  ✅ 资金解冻")
    print("✅ [测试6] 全部通过\n")


def test_rule_7_no_overdraft():
    """规则7：透支拦截"""
    print("[测试7] 透支拦截")
    account = Account(initial_cash=10000)
    price = 100.0
    qty = 200  # 需要20000元 + 成本，超过10000
    stock_code = "sh600000"
    
    success = account.apply_buy_order(price, qty, stock_code)
    assert not success, "透支应该被拦截"
    assert abs(account.available_cash - 10000) < 0.01, "资金不应该减少"
    print("  ✅ 透支拦截")
    print("✅ [测试7] 全部通过\n")


def test_rule_8_min_commission_5_yuan():
    """规则8：佣金最低5元"""
    print("[测试8] 佣金最低5元")
    account = Account(initial_cash=100000)
    price = 10.0
    qty = 100  # 1000元，佣金万2.5=0.25元，应该收5元
    stock_code = "sh600000"
    
    costs = account.calculate_trading_costs('BUY', price, qty, stock_code)
    # 佣金5 + 过户费1 = 6元
    assert abs(costs - 6.0) < 0.01, f"佣金计算错误: {costs}"
    print("  ✅ 佣金最低5元")
    print("✅ [测试8] 全部通过\n")


def test_rule_9_transfer_fee_all_markets():
    """规则9：过户费全市场覆盖（双向）"""
    print("[测试9] 过户费全市场覆盖（双向）")
    account = Account(initial_cash=100000)
    price = 10.0
    qty = 100  # 1000元，佣金万2.5=0.25元→收5元，过户费万0.1=0.01元→收1元
    stock_code_sh = "sh600000"
    stock_code_sz = "sz000001"
    
    # 沪市买入
    costs_sh_buy = account.calculate_trading_costs('BUY', price, qty, stock_code_sh)
    # 佣金5元 + 过户费1元 = 6元
    assert abs(costs_sh_buy - 6.0) < 0.01, f"沪市买入成本错误: {costs_sh_buy}"
    print("  ✅ 沪市买入过户费")
    
    # 沪市卖出
    costs_sh_sell = account.calculate_trading_costs('SELL', price, qty, stock_code_sh)
    # 佣金5 + 印花税1 + 过户费1 = 7元
    assert abs(costs_sh_sell - 7.0) < 0.01, f"沪市卖出成本错误: {costs_sh_sell}"
    print("  ✅ 沪市卖出过户费")
    
    # 深市买入
    costs_sz_buy = account.calculate_trading_costs('BUY', price, qty, stock_code_sz)
    assert abs(costs_sz_buy - 6.0) < 0.01, f"深市买入成本错误: {costs_sz_buy}"
    print("  ✅ 深市买入过户费")
    
    # 深市卖出
    costs_sz_sell = account.calculate_trading_costs('SELL', price, qty, stock_code_sz)
    assert abs(costs_sz_sell - 7.0) < 0.01, f"深市卖出成本错误: {costs_sz_sell}"
    print("  ✅ 深市卖出过户费")
    print("✅ [测试9] 全部通过\n")


def main():
    print("="*60)
    print("对照实盘强制标准验证")
    print("="*60 + "\n")
    
    tests = [
        test_rule_1_price_limits_by_board,
        test_rule_2_order_outside_limit_is_rejected,
        test_rule_3_limit_up_cannot_buy_limit_down_cannot_sell,
        test_rule_4_no_counterparty_no_deal,
        test_rule_5_trading_period,
        test_rule_6_freeze_unfreeze_cash,
        test_rule_7_no_overdraft,
        test_rule_8_min_commission_5_yuan,
        test_rule_9_transfer_fee_all_markets
    ]
    
    all_passed = True
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ {test.__name__} 失败: {e}")
            all_passed = False
            
    print("="*60)
    if all_passed:
        print("✅ 所有测试通过！")
    else:
        print("❌ 部分测试失败！")
    print("="*60)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
