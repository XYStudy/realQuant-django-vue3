# -*- coding: utf-8 -*-
import os
from pathlib import Path
from collections import OrderedDict

def get_market_advice(count):
    """根据新高数量返回投资建议"""
    if count > 100:
        return "[极度狂热] 重仓出击 | 仓位: 80%-100%"
    elif count >= 70:
        return "[强势进攻] 聚焦核心龙头，抛弃跟风股 | 仓位: 60%-80%"
    elif count >= 50:
        return "[混沌期] 谨慎操作 | 仓位: 30%-50%"
    else:
        return "[冰点期] 管住手/防守 | 仓位: 0%-20%"

def get_today_advice_msg():
    """
    获取今日操作建议消息（用于发送微信）
    返回: (消息字符串, 今日新高数量) 或 (None, 0)
    """
    dir_path = Path(r'\\vmware-host\Shared Folders\通达信新高日志')
    
    if not dir_path.exists():
        return None, 0
    
    # 获取所有txt文件
    files = sorted(dir_path.glob('实时新高*.txt'))
    
    if not files:
        return None, 0
    
    results = []
    for file in files:
        filename = file.name
        date_str = filename.replace('实时新高', '').replace('.txt', '')
        
        try:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                with open(file, 'r', encoding='gbk', errors='ignore') as f:
                    lines = f.readlines()
            data_lines = [line for line in lines if line.strip()]
            
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            results.append((formatted_date, len(data_lines)))
        except Exception as e:
            print(f"[analyze_new_high] Error reading {filename}: {e}", flush=True)
            continue
    
    if not results:
        return None, 0
    
    # 构建今日操作建议消息
    today_date, today_count = results[-1]
    advice = get_market_advice(today_count)
    
    msg = f"今日 ({today_date}) 操作建议:\n"
    msg += f"新高数量: {today_count} 条\n"
    msg += f"市场状态: {advice}"
    
    return msg, today_count

def print_full_report():
    """打印完整的每日统计报告（用于独立运行脚本）"""
    dir_path = Path(r'\\vmware-host\Shared Folders\通达信新高日志')
    
    if not dir_path.exists():
        print(f"目录不存在: {dir_path}")
        return
    
    files = sorted(dir_path.glob('实时新高*.txt'))
    
    print("=" * 60)
    print("每日创新高股票数量统计")
    print("=" * 60)
    
    results = []
    for file in files:
        filename = file.name
        date_str = filename.replace('实时新高', '').replace('.txt', '')
        
        with open(file, 'r', encoding='gbk') as f:
            lines = f.readlines()
            data_lines = [line for line in lines if line.strip()]
        
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        results.append((formatted_date, len(data_lines)))
        advice = get_market_advice(len(data_lines))
        print(f"{formatted_date}: {len(data_lines):3d} 条 | {advice}")
    
    print("=" * 60)
    print(f"总计: {len(results)} 个交易日")
    print(f"累计新高数据: {sum(r[1] for r in results)} 条")
    
    if results:
        today_count = results[-1][1]
        print("\n" + "=" * 60)
        print(f">>> 今日 ({results[-1][0]}) 操作建议:")
        print("=" * 60)
        advice = get_market_advice(today_count)
        print(f"  新高数量: {today_count} 条")
        print(f"  市场状态: {advice}")
        print("=" * 60)

if __name__ == "__main__":
    print_full_report()
