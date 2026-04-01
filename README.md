# 🎯 A 股模拟盘系统 v1.0

基于第一性原理设计的真实数据模拟交易框架。

---

## ✨ 核心特性

- ✅ **真实实时数据** - 腾讯财经 API 推送（3 秒刷新）
- ✅ **T+1 规则模拟** - 严格遵循 A 股交易规则
- ✅ **滑点模型** - 动态计算市场冲击成本
- ✅ **多策略支持** - 可并行运行全天候/002/003 策略
- ✅ **完整账户管理** - 现金、持仓、冻结资金、交易成本

---

## 🚀 快速开始

### 安装依赖

```bash
pip install requests
```

### 基础运行

```bash
cd simulation_trading
python main.py --stocks sh600000,sz000001,sh600519 --duration 60 --interval 3
```

### 参数说明

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--stocks` | `-s` | sh600000,sz000001 | 股票池（逗号分隔） |
| `--duration` | `-d` | 60 | 运行时长（秒） |
| `--interval` | `-i` | 3.0 | 刷新间隔（秒） |

---

## 📁 项目结构

```
simulation_trading/
├── main.py                    # 主控制器入口
├── data/
│   ├── __init__.py
│   └── tencent_feed.py        # 腾讯财经实时数据源
├── core/
│   ├── __init__.py
│   └── account.py             # 账户管理（T+1、交易成本）
├── engine/
│   ├── __init__.py
│   └── matching.py            # 撮合引擎 + 滑点模型
├── utils/
│   └── __init__.py
└── tests/
    └── __init__.py
```

---

## 🧠 设计原则（第一性原理）

### 1. 时间同步
- ❌ 不使用本地系统时间判断交易
- ✅ 以数据流的时间戳为准

### 2. T+1 规则
- 今日买入的股票 → 明天才能卖
- 区分：总持仓 vs 可用持仓 vs 今日买入

### 3. 真实滑点
```
滑点 = 市场冲击 + 延迟损耗 + 买卖价差
```
- 小盘股流动性差时滑点可达 0.5%-1%
- 大单会吃穿多档委托

### 4. 交易成本
- 佣金：万 2.5（最低 5 元）
- 印花税：卖出千 1
- 过户费：万分之 0.1

---

## 🔄 接入已有策略

### 步骤 1: 创建策略类

```python
from main import Strategy
from data.tencent_feed import Quote

class MyAllWeatherStrategy(Strategy):
    def __init__(self):
        super().__init__("全天候策略")
        
    def on_tick(self, quotes: Dict[str, Quote]) -> Dict:
        # 在这里实现你的策略逻辑
        # 返回交易信号或 None
        
        for code, quote in quotes.items():
            if self.should_buy(quote):
                return {
                    'stock_code': code,
                    'side': 'buy',
                    'qty': 100
                }
        return None
```

### 步骤 2: 注册到主程序

```python
controller = SimulationController()
controller.register_strategy(MyAllWeatherStrategy())
controller.run()
```

---

## ⚙️ 当前阶段（Phase 1）

✅ 已完成:
- [x] 数据层实现（腾讯财经 API）
- [x] 账户状态管理（现金/持仓/冻结）
- [x] 基础撮合引擎（市价单）
- [x] T+1 规则实现

📋 待完成 (Phase 2-4):
- [x] 限价单支持 + 价格优先/时间优先撮合
- [x] 涨跌停模拟 + 排队成交概率模型
- [x] 交易日志持久化（JSON/CSV双格式）
- [x] 基础绩效统计（收益率/胜率/盈亏比）
- [ ] 策略接口标准化（适配全天候/002/003）
- [ ] Web Dashboard (Phase 3)

---

## 🛡️ 风险提示

⚠️ **重要认知**:
- 模拟盘 ≠ 实盘
- 模拟盘可以验证策略逻辑
- 模拟盘不能模拟真实的心理承受力
- "模拟盘赚 100 万，实盘可能亏 10 万"

建议：先用小仓位（≤10% 资金）实盘验证！

---

## 📞 技术支持

遇到问题请查看:
1. `simulation_trading_analysis.md` - 第一性原理分析文档
2. `data/tencent_feed.py` - 数据源详细注释
3. `core/account.py` - 账户逻辑详细注释

---

**版本**: v1.0  
**创建时间**: 2026-03-31  
**作者**: Oracle AI Assistant
