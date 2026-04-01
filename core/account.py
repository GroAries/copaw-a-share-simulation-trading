#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账户管理 - 第一性原理：完全对齐实盘券商规则
T+1规则、交易成本、资金冻结/解冻、持仓管理
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Position:
    """持仓记录"""
    stock_code: str
    total_qty: int = 0       # 总持仓
    available_qty: int = 0   # 可用持仓（T+1）
    cost_basis: float = 0.0  # 成本价


class Account:
    """账户管理"""
    
    def __init__(self, initial_cash: float = 1000000.0):
        self.initial_cash = initial_cash
        self.available_cash = initial_cash  # 可用资金
        self.frozen_cash = 0.0  # 冻结资金
        self.total_cash = initial_cash  # 总资金（可用+冻结）
        self.positions: Dict[str, Position] = {}  # 持仓字典：代码→Position对象
        self.trade_history = []
        
        # 交易成本参数
        self.commission_rate = 0.00025   # 佣金万2.5
        self.stamp_duty_rate = 0.001      # 印花税千1（仅卖出）
        self.transfer_fee_rate = 0.00001  # 过户费（双向，沪深都有，2023年后）
        
    def calculate_trading_costs(
        self,
        side: str,
        price: float,
        qty: int,
        stock_code: str
    ) -> float:
        """计算交易成本 - 完全对齐实盘"""
        amount = price * qty
        costs = 0.0
        
        # 佣金（双向，最低5元）
        commission = max(5.0, amount * self.commission_rate)
        costs += commission
        
        # 印花税（仅卖出）
        if side.upper() == 'SELL':
            stamp_duty = amount * self.stamp_duty_rate
            costs += stamp_duty
            
        # 过户费（双向，沪深都有，最低1元）
        transfer_fee = max(1.0, amount * self.transfer_fee_rate)
        costs += transfer_fee
            
        return costs
        
    def freeze_cash(self, amount: float) -> bool:
        """冻结资金 - 挂单时调用"""
        if self.available_cash < amount:
            return False
        self.available_cash -= amount
        self.frozen_cash += amount
        return True
        
    def unfreeze_cash(self, amount: float):
        """解冻资金 - 撤单时调用"""
        self.frozen_cash -= amount
        self.available_cash += amount
        self.total_cash = self.available_cash + self.frozen_cash
        
    def apply_buy_order(self, price: float, qty: int, stock_code: str) -> bool:
        """应用买入订单 - 完全对齐实盘"""
        amount = price * qty
        costs = self.calculate_trading_costs('BUY', price, qty, stock_code)
        total = amount + costs
        
        # 检查可用资金是否足够
        if self.available_cash < total:
            return False
            
        # 扣除资金
        self.available_cash -= total
        self.total_cash = self.available_cash + self.frozen_cash
        
        # 更新持仓成本（加权平均）
        if stock_code not in self.positions:
            self.positions[stock_code] = Position(
                stock_code=stock_code,
                total_qty=qty,
                available_qty=0,  # T+1，今日买入不可用
                cost_basis=price + costs/qty  # 成本价包含交易成本
            )
        else:
            pos = self.positions[stock_code]
            total_amount = pos.cost_basis * pos.total_qty + total
            total_qty = pos.total_qty + qty
            pos.total_qty = total_qty
            pos.cost_basis = total_amount / total_qty
        
        self.trade_history.append({
            'side': 'BUY',
            'code': stock_code,
            'price': price,
            'qty': qty,
            'amount': amount,
            'costs': costs
        })
        
        return True
        
    def apply_sell_order(self, price: float, qty: int, stock_code: str) -> (bool, float):
        """应用卖出订单，返回(是否成功, 盈亏金额) - 完全对齐实盘"""
        pos = self.positions.get(stock_code)
        if not pos or pos.available_qty < qty:
            return False, 0.0
            
        amount = price * qty
        costs = self.calculate_trading_costs('SELL', price, qty, stock_code)
        net = amount - costs
        
        # 计算盈亏：（卖出价 - 成本价）* 数量 - 卖出成本
        pnl = (price - pos.cost_basis) * qty - costs
        
        # 卖出资金当日可用
        self.available_cash += net
        self.total_cash = self.available_cash + self.frozen_cash
        
        pos.total_qty -= qty
        pos.available_qty -= qty
        
        # 如果持仓为0，删除记录
        if pos.total_qty <= 0:
            del self.positions[stock_code]
        
        self.trade_history.append({
            'side': 'SELL',
            'code': stock_code,
            'price': price,
            'qty': qty,
            'amount': amount,
            'costs': costs,
            'pnl': pnl
        })
        
        return True, pnl
        
    def daily_settle(self):
        """每日收盘结算 - T+1规则：今日买入转为可用"""
        for stock_code, pos in self.positions.items():
            # T+1：今日买入的持仓，今日不可用，明日可用
            # 这里简化处理：每日收盘后，所有总持仓转为可用
            # 实际更严谨的需要记录每日买入批次，但这里简化
            pos.available_qty = pos.total_qty
