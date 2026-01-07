# quant/routing.py
from django.urls import path
from quant.consumers import StockDataConsumer

websocket_urlpatterns = [
    path('ws/stock/<str:stock_code>/', StockDataConsumer.as_asgi()),
]
