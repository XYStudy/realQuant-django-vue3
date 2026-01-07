"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

# 设置Django环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# 首先获取Django ASGI应用，这会自动初始化Django应用
django_asgi_app = get_asgi_application()

# 然后导入Channels相关模块（必须在获取Django ASGI应用之后）
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from quant.routing import websocket_urlpatterns

# 创建ASGI应用
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
