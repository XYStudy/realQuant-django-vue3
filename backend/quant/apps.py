from django.apps import AppConfig


class QuantConfig(AppConfig):
    name = 'quant'

    def ready(self):
        # 启动时重置所有交易执行状态，防止因意外崩溃导致的锁定
        try:
            from .models import TradeSetting
            TradeSetting.objects.all().update(is_executing=False)
            print("DEBUG: 已重置所有股票的交易执行状态")
        except Exception as e:
            print(f"DEBUG: 重置交易状态失败 (可能数据库尚未就绪): {e}")
