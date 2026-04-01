---
name: "a_share_simulation_trading"
description: "A股模拟盘系统 - 第一性原理设计，专注个人策略验证，系统与策略严格解耦，100%对齐实盘规则"
version: "1.0.0"
author: "GroAries"
created: "2026-04-01"
metadata:
  category: "finance"
  tags: ["A股", "模拟盘", "回测", "交易", "实盘规则"]
  requires: { "bins": [] }
  status: "active"
---

# A股模拟盘系统 v1.0

第一性原理设计：
- 系统 = 市场环境模拟器（只提供数据、规则、执行）
- 策略 = 交易决策主体（完全独立，自主决策）

## 核心特性

✅ 完全对齐实盘规则：
- 涨跌停限制（区分主板10%/科创板/创业板20%）
- T+1结算
- 交易成本（佣金万2.5、最低5元；印花税千1、仅卖出；过户费万0.1、最低1元、双向）
- 交易时段限制（9:30-11:30,13:00-15:00）
- 透支拦截
- 封涨跌停禁止成交
- 超涨跌停挂单废单
- 无对手盘不成交

✅ 实盘规则验证：
- 9条测试全部通过 ✅

## 快速开始

```bash
# 运行模拟盘
python main.py --stocks sh600000,sz000001 --initial-cash 1000000 --duration 60

# 验证实盘规则
cd tests && python test_real_stock_rules.py
```

## 目录结构

```
a_share_simulation_trading/
├── data/
│   └── tencent_feed.py  # 腾讯实时行情数据源
├── core/
│   └── account.py        # 账户管理（T+1、交易成本）
├── engine/
│   └── matching.py       # 撮合引擎（市价单+滑点、涨跌停）
├── strategies/
│   └── random_strategy.py  # 随机策略（示例）
├── tests/
│   └── test_real_stock_rules.py  # 实盘规则验证
└── main.py  # 主入口
```

## 第一性原理边界

系统层绝不干预：
- 交易决策
- 止损止盈
- 仓位管理

策略层完全自主：
- 接收市场数据
- 生成交易信号
- 承担全部盈亏

## GitHub仓库

https://github.com/GroAries/copaw-a-share-simulation-trading
