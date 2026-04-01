#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟盘Web可视化Dashboard
第一性原理：最小化依赖，只展示核心数据
"""

import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime


def load_trade_logs():
    """加载交易日志（第一性原理：直接读取输出目录）"""
    log_dir = Path("output")
    if not log_dir.exists():
        return None, None
        
    # 找到最新的JSON日志
    json_files = sorted(log_dir.glob("trade_log_*.json"), reverse=True)
    csv_files = sorted(log_dir.glob("trade_log_*.csv"), reverse=True)
    
    trade_log = None
    if json_files:
        with open(json_files[0], 'r', encoding='utf-8') as f:
            trade_log = json.load(f)
    
    return trade_log, csv_files[0] if csv_files else None


def main():
    st.set_page_config(page_title="模拟盘Dashboard", page_icon="📈", layout="wide")
    st.title("📈 A股模拟盘可视化Dashboard")
    st.markdown("基于第一性原理设计的简洁Dashboard")
    
    # 侧边栏
    st.sidebar.header("设置")
    initial_cash = st.sidebar.number_input("初始资金（元）", value=1000000.0, step=10000.0)
    
    # 加载数据
    trade_log, csv_path = load_trade_logs()
    
    if not trade_log:
        st.warning("⚠️ 未找到交易日志，请先运行模拟盘生成数据")
        st.info("运行命令：`python main.py --stocks sh600000 --duration 30`")
        return
    
    # 1. 顶部指标卡片
    st.header("📊 核心指标")
    col1, col2, col3, col4 = st.columns(4)
    
    # 模拟计算最终资产（简化版）
    # 后续可以从日志中提取更精确的数据
    final_cash = initial_cash
    for trade in trade_log:
        if trade['side'] == 'BUY':
            final_cash -= trade['price'] * trade['qty']
            final_cash -= 10  # 简化交易成本
        elif trade['side'] == 'SELL':
            final_cash += trade['price'] * trade['qty']
            final_cash -= 10  # 简化交易成本
            if 'pnl' in trade:
                final_cash += trade['pnl'] - (trade['price'] * trade['qty'])  # 修正
    
    total_pnl = final_cash - initial_cash
    pnl_pct = total_pnl / initial_cash * 100 if initial_cash > 0 else 0
    
    with col1:
        st.metric(label="最终资产", value=f"¥{final_cash:,.2f}")
    with col2:
        st.metric(label="总盈亏", value=f"¥{total_pnl:,.2f}", delta=f"{pnl_pct:+.2f}%")
    with col3:
        st.metric(label="交易次数", value=len(trade_log))
    with col4:
        buys = sum(1 for t in trade_log if t['side'] == 'BUY')
        sells = sum(1 for t in trade_log if t['side'] == 'SELL')
        st.metric(label="买入/卖出", value=f"{buys}/{sells}")
    
    # 2. 资金曲线（简化版）
    st.header("📈 资金曲线")
    # 生成简化的资金曲线数据
    dates = []
    net_values = []
    current_nv = initial_cash
    for i, trade in enumerate(trade_log):
        dates.append(datetime.now().strftime("%H:%M:%S"))
        net_values.append(current_nv)
        if trade['side'] == 'BUY':
            current_nv -= trade['price'] * trade['qty'] + 10
        elif trade['side'] == 'SELL':
            current_nv += trade['price'] * trade['qty'] - 10
            if 'pnl' in trade:
                current_nv += trade['pnl'] - (trade['price'] * trade['qty'])
    dates.append("当前")
    net_values.append(current_nv)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=net_values, mode='lines+markers', name='净值曲线'))
    fig.update_layout(title="资金净值曲线", xaxis_title="时间", yaxis_title="净值（元）")
    st.plotly_chart(fig, use_container_width=True)
    
    # 3. 交易记录
    st.header("📋 交易记录")
    if trade_log:
        df = pd.DataFrame(trade_log)
        st.dataframe(df, use_container_width=True)
        
        # 下载按钮
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="下载交易记录CSV",
            data=csv,
            file_name="trade_log.csv",
            mime="text/csv"
        )
    else:
        st.info("暂无交易记录")
    
    # 4. 当前持仓（简化版）
    st.header("💼 当前持仓")
    # 从交易记录计算持仓
    positions = {}
    for trade in trade_log:
        code = trade.get('stock', trade.get('stock_code'))
        if not code:
            continue
        if code not in positions:
            positions[code] = 0
        if trade['side'] == 'BUY':
            positions[code] += trade['qty']
        elif trade['side'] == 'SELL':
            positions[code] -= trade['qty']
    
    if positions:
        pos_df = pd.DataFrame({
            '股票代码': [k for k, v in positions.items() if v > 0],
            '持仓数量': [v for k, v in positions.items() if v > 0]
        })
        st.dataframe(pos_df, use_container_width=True)
    else:
        st.info("暂无持仓")


if __name__ == "__main__":
    main()
