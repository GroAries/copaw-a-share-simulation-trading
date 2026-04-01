---
name: a_share_simulation_trading
description: "A股模拟盘系统 - 第一性原理设计，专注个人策略验证，系统与策略严格解耦"
version: "1.0.0"
author: "GroAries"
created: "2026-04-01"
metadata:
  category: "trading"
  tags: ["A股", "模拟盘", "回测", "策略验证", "第一性原理"]
  requires: { "bins": ["python3"], "pip": ["requests", "streamlit", "pandas", "plotly"] }
  status: "active"
---

# Skill: a_share_simulation_trading

**A股模拟盘系统 - 第一性原理设计，专注个人策略验证，系统与策略严格解耦**

---

## 🎯 功能概述

这是一个**A股个人交易策略验证与实盘前测试工具**，基于第一性原理设计：
- 系统只做市场环境模拟器，绝不干预交易决策
- 系统与策略严格解耦，止损止盈、仓位管理等都由策略负责
- 专注A股，不扩展其他市场
- 源码完全开放，可深度定制

---

## ✨ 核心功能

| 功能 | 描述 |
|------|------|
| 实时行情对接 | 腾讯财经API，3秒刷新 |
| T+1规则模拟 | 严格遵循A股交易规则 |
| 滑点模型 | 动态计算市场冲击成本 |
| 市价/限价单 | 支持价格优先、时间优先撮合 |
| 涨跌停模拟 | 排队成交概率模型 |
| 合规风控 | 下单前检查单票仓位、总敞口限制 |
| 交易日志持久化 | JSON/CSV双格式 |
| 绩效统计 | 收益率、胜率、盈亏比、最大回撤 |
| 绩效归因 | 简化版Brinson归因、因子分析 |
| Web可视化Dashboard | Streamlit简洁界面 |
| 条件单/止损止盈 | 保留但暂停更新（应策略实现） |

---

## 📖 使用方法

### 1. 运行实时模拟盘
```bash
cd skills/a_share_simulation_trading-active
python main.py --stocks sh600000,sz000001 --duration 60
```

### 2. 启动Web可视化Dashboard
```bash
cd skills/a_share_simulation_trading-active
streamlit run dashboard.py
```

---

## 🧠 第一性原理设计

### 核心边界
```
系统 = 市场环境模拟器（只提供真实市场环境，不做交易决策）
策略 = 交易决策主体（所有交易相关的决策，包括止损止盈、仓位管理，都由策略负责）
二者严格解耦，永不越界！
```

### 系统职责
1. 提供真实市场行情
2. 执行交易（市价/限价单）
3. 管理账户（T+1、交易成本、持仓）
4. 模拟涨跌停、滑点
5. 下单前合规检查（单票仓位、总敞口限制）
6. 记录交易日志、计算绩效指标
7. 提供可视化Dashboard

---

## 📦 安装依赖

```bash
pip install requests streamlit pandas plotly
```

---

## 🔗 项目链接

GitHub仓库：https://github.com/GroAries/copaw-a-share-simulation-trading

---

**作者**: GroAries  
**首次发布**: 2026-04-01  
**版本**: v1.0.0
