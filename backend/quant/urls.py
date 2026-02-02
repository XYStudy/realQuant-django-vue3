from django.urls import path
from . import views

urlpatterns = [
    path('stock/<str:stock_code>/', views.get_stock_realtime_data, name='get_stock_realtime_data'),
    path('trade-records/<str:stock_code>/', views.trade_records, name='trade_records'),
    path('trade-loops/<str:stock_code>/', views.trade_loops, name='trade_loops'),
    path('trade-setting/', views.update_trade_setting, name='update_trade_setting'),
    path('account/', views.account_api, name='account_api'),
    path('trade-callback/', views.trade_callback, name='trade_callback'),
]