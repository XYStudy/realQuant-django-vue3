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

        # 启动自动分析脚本
        import os
        print(f"DEBUG: os.environ.get('RUN_MAIN')={os.environ.get('RUN_MAIN')}")
        # Daphne 启动时没有 RUN_MAIN，直接启动即可
        try:
            # 暂时关闭自动分析脚本启动，改由外部脚本手动启动以便监控日志
            print("DEBUG: 内部 start_scheduler 已禁用，请手动启动 auto_analyzer.py")
            # from .services.auto_analyzer import start_scheduler
            # start_scheduler()
            # print("DEBUG: 自动分析脚本已启动")
            pass
        except Exception as e:
            print(f"DEBUG: 启动自动分析脚本失败: {e}")
