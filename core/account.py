#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账户管理 - 基于第一性原理
T+1规则、交易成本、资金管理
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
        self.cash = initial_cash
        self.frozen_cash = 0.0
        self.positions: Dict[str, Position] = {}  # 持仓字典：代码→Position对象
        self.trade_history = []
        
        # 交易成本参数
        self.commission_rate = 0.00025   # 佣金万2.5
        self.stamp_duty_rate = 0.001      # 印花税千1（仅卖出）
        self.transfer_fee_rate = 0.00001  # 过户费（沪市）
        
    def calculate_trading_costs(
        self,
        side: str,
        price: float,
        qty: int,
        stock_code: str
    ) -> float:
        """计算交易成本"""
        amount = price * qty
        costs = 0.0
        
        # 佣金（最低5元）
        commission = max(5.0, amount * self.commission_rate)
        costs += commission
        
        # 印花税（仅卖出）
        if side.upper() == 'SELL':
            stamp_duty = amount * self.stamp_duty_rate
            costs += stamp_duty
            
        # 过户费（仅沪市，最低1元）
        if stock_code.startswith('sh'):
            transfer_fee = max(1.0, amount * self.transfer_fee_rate)
            costs += transfer_fee
            
        return costs
        
    def apply_buy_order(self, price: float, qty: int, stock_code: str) -> bool:
        """应用买入订单"""
        amount = price * qty
        costs = self.calculate_trading_costs('BUY', price, qty, stock_code)
        total = amount + costs
        
        if self.cash < total:
            return False
            
        self.cash -= total
        
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
        """应用卖出订单，返回(是否成功, 盈亏金额)"""
        pos = self.positions.get(stock_code)
        if not pos or pos.available_qty < qty:
            return False, 0.0
            
        amount = price * qty
        costs = self.calculate_trading_costs('SELL', price, qty, stock_code)
        net = amount - costs
        
        # 计算盈亏：（卖出价 - 成本价）* 数量 - 卖出成本
        pnl = (price - pos.cost_basis) * qty - costs
        
        self.cash += net
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
        
    def get_position(self, stock_code: str) -> Optional[Position]:
        """获取持仓（兼容旧接口）"""
        qty = self.positions.get(stock_code, 0)
        return Position(
            stock_code=stock_code,
            total_qty=qty,
            available_qty=qty
        )
        
    def get_total_asset(self, prices: Dict[str, float]) -> float:
        """计算总资产"""
        total = self.cash
        for code, qty in self.positions.items():
            if code in prices and qty > 0:
                total += prices[code] * qty
        return total
        
    def get_portfolio_summary(self, prices: Dict[str, float]) -> Dict:
        """获取投资组合摘要"""
        total_asset = self.get_total_asset(prices)
        pnl = total_asset - self.initial_cash
        pnl_pct = pnl / self.initial_cash * 100 if self.initial_cash > 0 else 0
        
        return {
            'cash': self.cash,
            'total_asset': total_asset,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'positions': dict(self.positions)
        }
