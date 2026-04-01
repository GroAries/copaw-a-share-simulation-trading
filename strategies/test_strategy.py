from typing import Dict, Optional


class TestStrategy:
    def __init__(self, name: str = "测试策略"):
        self.name = name
        self.has_bought = False
        
    def on_tick(self, quotes: Dict[str, object]) -> Optional[Dict]:
        """
        处理新的行情数据
        """
        if self.has_bought:
            return None
            
        for stock_code, data in quotes.items():
            try:
                print(f"[DEBUG] 处理股票: {stock_code}")
                print(f"[DEBUG] 当前价格: {data['price']}")
                
                # 简单买入信号：价格大于10元就买
                if data['price'] > 10.0 and not self.has_bought:
                    self.has_bought = True
                    entry_price = data['price']
                    stop_loss = entry_price * 0.98  # 止损：亏损2%
                    take_profit = entry_price * 1.05  # 止盈：盈利5%
                    print(f"[DEBUG] 触发买入信号: {stock_code} @ {entry_price:.2f} (止损: {stop_loss:.2f}, 止盈: {take_profit:.2f})")
                    return {
                        'stock_code': stock_code,
                        'side': 'BUY',
                        'qty': 100,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit
                    }
                
            except Exception as e:
                print(f"[警告] 策略 {self.name} 出错：{str(e)}")
                import traceback
                traceback.print_exc()
                
        return None
