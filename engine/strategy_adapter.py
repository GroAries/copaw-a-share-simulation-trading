from typing import Dict, Any


class StrategyData:
    """
    第一性原理：统一数据访问接口
    策略应能通过属性或字典键访问数据，无需关心底层实现
    """
    def __init__(self, data: Dict[str, Any]):
        self._data = data
        
    def __getattr__(self, name: str) -> Any:
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"'{name}' not found in strategy data")
        
    def __getitem__(self, key: str) -> Any:
        return self._data[key]
        
    def __contains__(self, key: str) -> bool:
        return key in self._data
        
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


def adapt_quote_for_strategy(quote: Any) -> StrategyData:
    """
    将原始行情对象转换为策略期望的格式
    
    第一性原理：策略只应关心市场数据，不应关心数据来源格式
    系统层负责数据转换，确保策略接收统一格式
    """
    # 标准化价格字段
    if hasattr(quote, 'current_price'):
        price = quote.current_price
    elif 'current_price' in quote:
        price = quote['current_price']
    else:
        price = 0.0

    # 标准化涨跌幅字段（处理字符串和浮点数格式）
    change_pct = 0.0
    if hasattr(quote, 'change_pct'):
        change_str = quote.change_pct
    elif 'change_pct' in quote:
        change_str = quote['change_pct']
    else:
        change_str = '0.0%'

    if isinstance(change_str, str) and '%' in change_str:
        change_pct = float(change_str.strip('%')) / 100
    elif isinstance(change_str, (float, int)):
        change_pct = change_str

    # 第一性原理：返回StrategyData对象，支持属性和字典两种访问方式
    return StrategyData({
        'price': price,
        'current_price': price,  # 兼容旧字段名
        'open': quote.open_price if hasattr(quote, 'open_price') else quote.get('open_price', 0.0),
        'high': quote.high_price if hasattr(quote, 'high_price') else quote.get('high_price', 0.0),
        'low': quote.low_price if hasattr(quote, 'low_price') else quote.get('low_price', 0.0),
        'volume': quote.volume if hasattr(quote, 'volume') else quote.get('volume', 0),
        'amount': quote.amount if hasattr(quote, 'amount') else quote.get('amount', 0.0),
        'change_pct': change_pct,
        'timestamp': quote.trade_time if hasattr(quote, 'trade_time') else quote.get('trade_time', '')
    })


def validate_strategy_data(data: Any) -> bool:
    """
    验证适配后的数据是否符合策略要求
    
    第一性原理：确保策略接收的数据满足基本有效性
    """
    return (
        isinstance(data.get('price', 0), (int, float)) and
        data.get('price', 0) > 0.01 and
        isinstance(data.get('volume', 0), (int, float))
    )
