#!/usr/bin/env python3
import sys
print("Python version:", sys.version)
sys.path.insert(0, '..')
try:
    from data.tencent_feed import TencentRealtimeFeed
    print("✅ TencentRealtimeFeed imported")
    from core.account import Account
    print("✅ Account imported")
    from engine.matching import MatchingEngine
    print("✅ MatchingEngine imported")
    from strategies.all_weather_v5 import AllWeatherStrategyV5
    print("✅ AllWeatherStrategyV5 imported")
    from strategies.trading_skill_002_v22 import TradingSkill002V22
    print("✅ TradingSkill002V22 imported")
    from strategies.trading_skill_003_v4 import TradingSkill003V4
    print("✅ TradingSkill003V4 imported")
    print("\n🎉 所有模块导入成功！")
except Exception as e:
    print("\n❌ 导入失败:", e)
    import traceback
    traceback.print_exc()
