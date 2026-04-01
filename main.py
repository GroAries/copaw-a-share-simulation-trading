#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟盘主程序
Phase 3: 支持条件单/止损止盈 + 回测对接
第一性原理：条件单是系统层的延迟执行普通订单
"""

import time
import sys
import json
import csv
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from pathlib import Path

# 导入内部模块
from data.tencent_feed import TencentDataFeed, Quote
from core.account import Account, Position
from engine.matching import MatchingEngine
from engine.strategy_adapter import adapt_quote_for_strategy, validate_strategy_data
from strategies.test_strategy import TestStrategy


@dataclass
class ConditionOrder:
    """条件单数据结构（第一性原理：最终转化为普通订单）"""
    stock_code: str
    side: str  # 'BUY' or 'SELL'
    qty: int
    limit_price: Optional[float] = None  # None表示市价单
    condition_type: str = 'price'  # 'price', 'time' 等
    condition_value: Any = None  # 触发条件值
    condition_operator: str = '>='  # 比较运算符：'>=', '<=', '>', '<', '=='
    is_active: bool = True  # 是否激活
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class RiskControlRules:
    """风控规则配置（第一性原理：只做合规检查，不干预交易决策）"""
    # 单只股票最大仓位比例（0.1=10%）
    max_single_position_ratio: float = 0.2
    # 总仓位最大比例（0.8=80%，即最高20%现金）
    max_total_position_ratio: float = 0.8
    # 是否启用风控
    enabled: bool = True


class PerformanceAttribution:
    """绩效归因模块（第一性原理：核心公式最小实现）"""
    
    @staticmethod
    def calculate_brinson(portfolio_returns: Dict, benchmark_returns: Dict, weights: Dict) -> Dict:
        """
        Brinson归因简化版：拆解收益来源
        返回：选股收益、择时收益、交互收益、总超额收益
        """
        if not portfolio_returns or not benchmark_returns:
            return {
                'stock_selection': 0.0,
                'market_timing': 0.0,
                'interaction': 0.0,
                'total_excess': 0.0
            }
        
        total_portfolio_return = sum(w * r for w, r in zip(weights.values(), portfolio_returns.values()))
        total_benchmark_return = sum(1/len(benchmark_returns) * r for r in benchmark_returns.values())
        
        # 简化计算（假设基准是等权重）
        active_weight = {k: weights.get(k, 0) - 1/len(benchmark_returns) for k in benchmark_returns.keys()}
        excess_return = {k: portfolio_returns.get(k, 0) - benchmark_returns.get(k, 0) for k in benchmark_returns.keys()}
        
        stock_selection = sum(1/len(benchmark_returns) * excess_return.get(k, 0) for k in benchmark_returns.keys())
        market_timing = sum(active_weight.get(k, 0) * benchmark_returns.get(k, 0) for k in benchmark_returns.keys())
        interaction = sum(active_weight.get(k, 0) * excess_return.get(k, 0) for k in benchmark_returns.keys())
        total_excess = total_portfolio_return - total_benchmark_return
        
        return {
            'stock_selection': round(stock_selection * 100, 2),
            'market_timing': round(market_timing * 100, 2),
            'interaction': round(interaction * 100, 2),
            'total_excess': round(total_excess * 100, 2)
        }
    
    @staticmethod
    def calculate_factor_attribution(returns: float, beta: float = 1.0, market_return: float = 0.0, 
                                    industry_return: float = 0.0, size_factor: float = 0.0) -> Dict:
        """
        因子归因简化版：拆解收益来源
        返回：市场收益、行业收益、风格收益、阿尔法收益
        """
        market_contribution = beta * market_return
        industry_contribution = industry_return
        size_contribution = size_factor
        alpha = returns - market_contribution - industry_contribution - size_contribution
        
        return {
            'market': round(market_contribution * 100, 2),
            'industry': round(industry_contribution * 100, 2),
            'size': round(size_contribution * 100, 2),
            'alpha': round(alpha * 100, 2)
        }


class SimulationTradingSystem:
    """模拟盘系统"""
    
    def __init__(
        self,
        initial_cash: float = 1000000,
        update_interval: float = 3.0
    ):
        self.data_feed = TencentDataFeed(cache_ttl=5)
        self.account = Account(initial_cash=initial_cash)
        self.matching_engine = MatchingEngine()
        self.strategies: Dict[str, object] = {}
        self.running = False
        self.update_interval = update_interval
        self.tick_count = 0
        self.trade_log: List[Dict] = []
        self.condition_orders: List[ConditionOrder] = []  # 条件单池
        self.risk_control = RiskControlRules()  # 风控规则
        self.performance_attribution = PerformanceAttribution()  # 绩效归因
        # 基准收益（默认沪深300）
        self.benchmark_returns: Dict[str, float] = {}
        # 因子数据
        self.market_return: float = 0.0
        self.industry_returns: Dict[str, float] = {}
        # 每日净值记录（用于回撤和归因计算）
        self.daily_net_value: List[float] = []
        
    def register_strategy(self, strategy: TestStrategy):
        """注册策略"""
        self.strategies[strategy.name] = strategy
        print(f"[系统] 策略已注册：{strategy.name}")
        
    def set_stock_pool(self, codes: List[str]):
        """设置股票池"""
        self.data_feed.set_stock_pool(codes)
        print(f"[系统] 股票池设置：{codes}")
        
    def add_condition_order(self, condition_order: ConditionOrder):
        """添加条件单"""
        self.condition_orders.append(condition_order)
        print(f"[系统] 条件单已添加：{condition_order.stock_code} {condition_order.side} {condition_order.qty}股 @ {condition_order.condition_operator}{condition_order.condition_value}")
        
    def add_stop_loss_order(self, stock_code: str, qty: int, stop_price: float):
        """快捷添加止损单（第一性原理：止损是条件单的特殊情况）"""
        co = ConditionOrder(
            stock_code=stock_code,
            side='SELL',
            qty=qty,
            limit_price=None,  # 市价止损
            condition_type='price',
            condition_value=stop_price,
            condition_operator='<='
        )
        self.add_condition_order(co)
        
    def add_take_profit_order(self, stock_code: str, qty: int, target_price: float):
        """快捷添加止盈单（第一性原理：止盈是条件单的特殊情况）"""
        co = ConditionOrder(
            stock_code=stock_code,
            side='SELL',
            qty=qty,
            limit_price=None,  # 市价止盈
            condition_type='price',
            condition_value=target_price,
            condition_operator='>='
        )
        self.add_condition_order(co)
        
    def _check_condition_orders(self, quotes: Dict[str, Quote]):
        """检查并触发条件单（第一性原理：只依赖市场数据）"""
        to_remove = []
        
        for co in self.condition_orders:
            if not co.is_active:
                continue
                
            quote = quotes.get(co.stock_code)
            if not quote:
                continue
                
            # 价格条件判断
            if co.condition_type == 'price':
                current_price = quote.current_price
                condition_met = False
                
                if co.condition_operator == '>=':
                    condition_met = current_price >= co.condition_value
                elif co.condition_operator == '<=':
                    condition_met = current_price <= co.condition_value
                elif co.condition_operator == '>':
                    condition_met = current_price > co.condition_value
                elif co.condition_operator == '<':
                    condition_met = current_price < co.condition_value
                elif co.condition_operator == '==':
                    condition_met = abs(current_price - co.condition_value) < 0.001
                    
                if condition_met:
                    print(f"[*] 条件单触发：{co.stock_code} {co.side} {co.qty}股 @ {current_price:.2f}")
                    # 转化为普通订单执行
                    signal = {
                        'stock_code': co.stock_code,
                        'side': co.side,
                        'qty': co.qty,
                        'limit_price': co.limit_price
                    }
                    self._execute_signal(signal, quotes)
                    co.is_active = False
                    to_remove.append(co)
        
        # 清理已触发的条件单
        for co in to_remove:
            self.condition_orders.remove(co)
            
    def _risk_check(self, signal: Dict, quotes: Dict[str, Quote]) -> (bool, str):
        """
        合规风控检查（第一性原理：只做合规检查，不干预交易决策）
        返回：(是否通过, 拒绝原因)
        """
        if not self.risk_control.enabled:
            return True, ""
            
        stock_code = signal['stock_code']
        side = signal['side'].upper()
        qty = signal['qty']
        limit_price = signal.get('limit_price')
        
        quote = quotes.get(stock_code)
        if not quote:
            return False, "无行情数据"
            
        current_price = limit_price if limit_price is not None else quote.current_price
        order_amount = current_price * qty
        total_asset = self.account.cash
        
        # 计算当前总持仓市值
        for code, pos in self.account.positions.items():
            if code in quotes:
                total_asset += quotes[code].current_price * pos.total_qty
        
        # 1. 总敞口检查（仅买入时）
        if side == 'BUY':
            current_total_position_value = total_asset - self.account.cash
            new_total_position_value = current_total_position_value + order_amount
            total_position_ratio = new_total_position_value / total_asset if total_asset > 0 else 0
            if total_position_ratio > self.risk_control.max_total_position_ratio:
                return False, f"总仓位超过限制：当前{total_position_ratio:.1%} > 限制{self.risk_control.max_total_position_ratio:.1%}"
        
        # 2. 单只股票仓位检查（仅买入时）
        if side == 'BUY':
            current_position_value = self.account.positions.get(stock_code, Position(stock_code=stock_code)).total_qty * current_price
            new_position_value = current_position_value + order_amount
            single_position_ratio = new_position_value / total_asset if total_asset > 0 else 0
            if single_position_ratio > self.risk_control.max_single_position_ratio:
                return False, f"单票仓位超过限制：当前{single_position_ratio:.1%} > 限制{self.risk_control.max_single_position_ratio:.1%}"
        
        return True, ""
        
    def _on_new_tick(self, quotes: Dict[str, Quote]):
        """处理新 tick 数据"""
        self.tick_count += 1
        
        # 第一性原理：系统只做市场环境模拟，条件单是策略在系统层的延迟触发
        self._check_condition_orders(quotes)
        
        # 然后执行策略
        for name, strategy in self.strategies.items():
            try:
                # 第一性原理：策略只应接收标准化数据，系统负责转换
                adapted_quotes = {}
                for code, quote in quotes.items():
                    adapted = adapt_quote_for_strategy(quote)
                    if validate_strategy_data(adapted):
                        adapted_quotes[code] = adapted
                
                if adapted_quotes:
                    signal = strategy.on_tick(adapted_quotes)
                    if signal:
                        self._execute_signal(signal, quotes)
                        
            except Exception as e:
                print(f"[警告] 策略 {name} 出错：{e}")
                import traceback
                print(f"[DEBUG] 完整错误堆栈:")
                traceback.print_exc()
                
    def _execute_signal(
        self,
        signal: Dict,
        quotes: Dict[str, Quote]
    ):
        """执行交易信号"""
        stock_code = signal['stock_code']
        side = signal['side'].upper()
        qty = signal['qty']
        limit_price = signal.get('limit_price')
        
        # 第一性原理：先风控检查，再执行订单
        risk_pass, risk_reason = self._risk_check(signal, quotes)
        if not risk_pass:
            print(f"[风控] 订单拒绝：{risk_reason}")
            return
        
        quote = quotes.get(stock_code)
        if not quote:
            return
            
        # 检查 T+1（卖出时）
        if side == 'SELL':
            pos = self.account.positions.get(stock_code, 0)
            if pos < qty:
                print(f"[风控] 卖出失败：持仓不足")
                return
                
        # 资金检查（买入时）
        if side == 'BUY':
            price = limit_price if limit_price else quote.current_price
            estimated_cost = price * qty
            if estimated_cost > self.account.cash:
                print(f"[风控] 买入失败：资金不足")
                return
        
        # 执行撮合
        try:
            if limit_price:
                success, fill_price, fill_qty, reason = self.matching_engine.simulate_limit_order(
                    stock_code=stock_code,
                    side=side,
                    qty=qty,
                    limit_price=limit_price,
                    quote=quote
                )
            else:
                success, fill_price, fill_qty, reason = self.matching_engine.simulate_market_order(
                    stock_code=stock_code,
                    side=side,
                    qty=qty,
                    quote=quote
                )
                
        except Exception as e:
            print(f"[系统错误] 撮合失败：{e}")
            return
            
        # 处理成交结果
        if success:
            # 使用简化的账户管理
            if side == 'BUY':
                ok = self.account.apply_buy_order(fill_price, fill_qty, stock_code)
                if ok:
                    print(f"[*] {side} {stock_code}: {fill_qty}股 @ {fill_price:.2f} ({reason})")
                    self.trade_log.append({
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'stock': stock_code,
                        'side': side,
                        'qty': fill_qty,
                        'price': fill_price,
                        'reason': reason
                    })
                    # 第一性原理：自动添加策略指定的止损止盈条件单
                    if 'stop_loss' in signal and signal['stop_loss'] is not None:
                        self.add_stop_loss_order(stock_code, fill_qty, signal['stop_loss'])
                    if 'take_profit' in signal and signal['take_profit'] is not None:
                        self.add_take_profit_order(stock_code, fill_qty, signal['take_profit'])
            else:
                ok, pnl = self.account.apply_sell_order(fill_price, fill_qty, stock_code)
                if ok:
                    print(f"[*] {side} {stock_code}: {fill_qty}股 @ {fill_price:.2f} ({reason}) | 盈亏: ¥{pnl:,.2f}")
                    self.trade_log.append({
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'stock': stock_code,
                        'side': side,
                        'qty': fill_qty,
                        'price': fill_price,
                        'pnl': pnl,
                        'reason': reason
                    })
        else:
            print(f"[!] 未成交: {reason}")
            
    def _save_trade_log(self, output_dir: str = "output"):
        """保存交易日志到文件"""
        if not self.trade_log:
            return
            
        # 创建输出目录
        Path(output_dir).mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存JSON格式
        json_path = f"{output_dir}/trade_log_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.trade_log, f, ensure_ascii=False, indent=2)
        print(f"[日志] 交易日志已保存到: {json_path}")
        
        # 保存CSV格式
        csv_path = f"{output_dir}/trade_log_{timestamp}.csv"
        if self.trade_log:
            fieldnames = self.trade_log[0].keys()
            with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.trade_log)
        print(f"[日志] CSV日志已保存到: {csv_path}")
        
    def _calculate_performance(self) -> Dict:
        """计算绩效指标"""
        performance = {
            'total_trades': len(self.trade_log),
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'total_pnl': 0.0,
            'total_pnl_pct': 0.0,
            'brinson': {},
            'factor_attribution': {}
        }
        
        if not self.trade_log and not self.account.positions:
            return performance
            
        # 计算总盈亏
        prices = {q.code: q.current_price for q in self.data_feed.cache.values()}
        final_asset = self.account.cash
        portfolio_weights = {}
        portfolio_returns = {}
        for code, pos in self.account.positions.items():
            if code in prices:
                position_value = prices[code] * pos.total_qty
                final_asset += position_value
                portfolio_weights[code] = position_value / final_asset if final_asset > 0 else 0
                portfolio_returns[code] = (prices[code] - pos.cost_basis) / pos.cost_basis if pos.cost_basis > 0 else 0
                
        performance['total_pnl'] = final_asset - self.account.initial_cash
        performance['total_pnl_pct'] = performance['total_pnl'] / self.account.initial_cash * 100 if self.account.initial_cash > 0 else 0
        
        # 计算胜率和盈亏比
        completed_trades = [t for t in self.trade_log if t['side'] == 'SELL']
        if completed_trades:
            win_trades = sum(1 for t in completed_trades if t['pnl'] > 0)
            performance['win_rate'] = win_trades / len(completed_trades) * 100
            
            total_profit = sum(t['pnl'] for t in completed_trades if t['pnl'] > 0)
            total_loss = sum(-t['pnl'] for t in completed_trades if t['pnl'] < 0)
            if total_loss > 0:
                performance['profit_factor'] = total_profit / total_loss
                
        # 计算最大回撤（精确版：基于净值曲线）
        if self.daily_net_value:
            peak = self.daily_net_value[0]
            max_dd = 0.0
            for nv in self.daily_net_value:
                if nv > peak:
                    peak = nv
                dd = (peak - nv) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
            performance['max_drawdown'] = round(max_dd * 100, 2)
        
        # Brinson归因（默认基准为等权重）
        if portfolio_returns:
            benchmark_returns = {k: 0.05 for k in portfolio_returns.keys()}  # 简化：基准默认5%收益
            performance['brinson'] = self.performance_attribution.calculate_brinson(
                portfolio_returns, benchmark_returns, portfolio_weights
            )
        
        # 因子归因（简化版，默认参数）
        performance['factor_attribution'] = self.performance_attribution.calculate_factor_attribution(
            returns=performance['total_pnl_pct']/100,
            market_return=self.market_return,
            industry_return=self.industry_returns.get(stock_code, 0) if 'stock_code' in locals() else 0
        )
        
        return performance
        
    def _print_summary(self):
        """打印总结报告"""
        print("\n" + "="*60)
        print("📊 模拟盘总结报告")
        print("="*60)
        
        # 计算绩效
        perf = self._calculate_performance()
        
        total_trades = perf['total_trades']
        buys = sum(1 for t in self.trade_log if t['side'] == 'BUY')
        sells = sum(1 for t in self.trade_log if t['side'] == 'SELL')
        
        print(f"总交易次数: {total_trades}")
        print(f"  买入: {buys} 笔")
        print(f"  卖出: {sells} 笔")
        
        print(f"\n收益表现:")
        print(f"  总盈亏: ¥{perf['total_pnl']:,.2f} ({perf['total_pnl_pct']:+.2f}%)")
        print(f"  最大回撤: {perf['max_drawdown']:.2f}%")
        print(f"  胜率: {perf['win_rate']:.1f}%")
        print(f"  盈亏比: {perf['profit_factor']:.2f}" if perf['profit_factor'] > 0 else "  盈亏比: 无完成交易")
        
        # 合规风控状态
        print(f"\n合规风控状态:")
        print(f"  单票最大仓位: {self.risk_control.max_single_position_ratio:.0%}")
        print(f"  总仓位最大比例: {self.risk_control.max_total_position_ratio:.0%}")
        
        # Brinson归因
        if perf['brinson']:
            print(f"\n📊 Brinson收益归因:")
            brinson = perf['brinson']
            print(f"  选股收益: {brinson['stock_selection']:+.2f}%")
            print(f"  择时收益: {brinson['market_timing']:+.2f}%")
            print(f"  交互收益: {brinson['interaction']:+.2f}%")
            print(f"  总超额收益: {brinson['total_excess']:+.2f}%")
        
        # 因子归因
        if perf['factor_attribution']:
            print(f"\n🔍 因子收益归因:")
            factor = perf['factor_attribution']
            print(f"  市场beta收益: {factor['market']:+.2f}%")
            print(f"  行业收益: {factor['industry']:+.2f}%")
            print(f"  风格因子收益: {factor['size']:+.2f}%")
            print(f"  阿尔法收益: {factor['alpha']:+.2f}%")
        
        print("\n当前持仓:")
        for code, pos in self.account.positions.items():
            if pos.total_qty > 0:
                current_price = 0.0
                for q in self.data_feed.cache.values():
                    if q.code == code:
                        current_price = q.current_price
                        break
                if current_price > 0 and pos.cost_basis > 0:
                    pnl_pct = (current_price - pos.cost_basis) / pos.cost_basis * 100
                    print(f"  {code}: {pos.total_qty}股 (成本价: ¥{pos.cost_basis:.2f} | 当前价: ¥{current_price:.2f} | 浮盈: {pnl_pct:+.2f}%)")
                else:
                    print(f"  {code}: {pos.total_qty}股 (成本价: ¥{pos.cost_basis:.2f})")
        
        # 保存日志
        self._save_trade_log()
        
        print("="*60)
        
    def run(self, duration_seconds: Optional[float] = None):
        """启动实时模拟盘"""
        if not self.data_feed.stock_pool:
            print("[错误] 请先设置股票池!")
            return
            
        self.running = True
        start_time = time.time()
        
        print("\n" + "="*60)
        print("🚀 模拟盘系统启动（实时模式）")
        print(f"初始资金: ¥{self.account.initial_cash:,.2f}")
        print(f"股票池: {self.data_feed.stock_pool}")
        print(f"刷新频率: {self.update_interval}秒/次")
        print("="*60 + "\n")
        
        try:
            while self.running:
                quotes = self.data_feed.get_quote()
                if quotes:
                    self._on_new_tick(quotes)
                else:
                    print("[警告] 未获取到行情数据")
                    
                elapsed = time.time() - start_time
                if duration_seconds and elapsed >= duration_seconds:
                    print("\n[系统] 达到运行时长，停止")
                    break
                    
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            print("\n[系统] 用户中断，停止运行")
        finally:
            self.running = False
            self._print_summary()
            
    def run_backtest(self, backtest_data: Dict):
        """
        回测模式：从回测系统数据回放（第一性原理：和实时模式共用一套逻辑）
        
        Args:
            backtest_data: 回测数据字典，格式：
                {
                    'stock_code': '600519.SH',
                    'dates': ['2020-01-01', ...],
                    'open': [100.0, ...],
                    'high': [105.0, ...],
                    'low': [98.0, ...],
                    'close': [102.0, ...],
                    'volumes': [100000, ...]
                }
        """
        self.running = True
        
        print("\n" + "="*60)
        print("🔙 模拟盘系统启动（回测模式）")
        print(f"初始资金: ¥{self.account.initial_cash:,.2f}")
        print(f"回测标的: {backtest_data.get('stock_code', 'unknown')}")
        print(f"回测周期: {len(backtest_data.get('dates', []))} 个交易日")
        print("="*60 + "\n")
        
        try:
            # 第一性原理：复用实时模式的_on_new_tick逻辑，只需构造Quote对象
            dates = backtest_data.get('dates', [])
            opens = backtest_data.get('open', [])
            highs = backtest_data.get('high', [])
            lows = backtest_data.get('low', [])
            closes = backtest_data.get('close', [])
            volumes = backtest_data.get('volumes', [])
            stock_code = backtest_data.get('stock_code', 'unknown')
            
            for i in range(len(dates)):
                # 构造回测用Quote对象
                quote = Quote(
                    code=stock_code,
                    name='',
                    current_price=closes[i],
                    open_price=opens[i],
                    high_price=highs[i],
                    low_price=lows[i],
                    volume=volumes[i],
                    trade_time=dates[i]
                )
                quotes = {stock_code: quote}
                
                self._on_new_tick(quotes)
                
        except KeyboardInterrupt:
            print("\n[系统] 用户中断，停止运行")
        finally:
            self.running = False
            self._print_summary()


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description="模拟盘交易系统")
    parser.add_argument("--stocks", type=str, default="sh600000", help="股票代码，多个用逗号分隔")
    parser.add_argument("--duration", type=float, default=60.0, help="运行时长（秒）")
    args = parser.parse_args()
    
    # 创建系统实例
    system = SimulationTradingSystem(initial_cash=1000000)
    
    # 设置股票池
    stock_codes = [s.strip() for s in args.stocks.split(",")]
    system.set_stock_pool(stock_codes)
    
    # 注册策略
    strategy = TestStrategy()
    system.register_strategy(strategy)
    
    # 运行
    system.run(duration_seconds=args.duration)


if __name__ == "__main__":
    main()
