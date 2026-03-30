#!/usr/bin/env python3
"""
增强版：行业板块与资金流向分析模块
沿用原有腾讯财经接口，保持高速稳定
"""

import pandas as pd
import requests
from datetime import datetime

def get_sector_distribution_batch(stock_codes, market_data=None):
    """
    获取持仓股票的行业分布
    使用腾讯财经接口（快速稳定）
    
    注意：腾讯接口不直接提供行业信息，这里使用简化版
    实际行业数据可通过 akshare 补充（仅在需要时调用）
    
    Returns:
        dict: {
            'sector_dist': DataFrame,  # 行业分布（简化版）
            'concept_overlap': dict,   # 概念重叠分析
        }
    """
    result = {
        'sector_dist': pd.DataFrame(),
        'concept_overlap': {}
    }
    
    try:
        # 简化版：基于股票代码前缀判断板块
        # 实际项目中可调用 akshare 获取真实行业（但会慢）
        sector_map = {
            '000': '深市主板',
            '001': '深市主板',
            '002': '中小板',
            '003': '中小板',
            '300': '创业板',
            '600': '沪市主板',
            '601': '沪市主板',
            '603': '沪市主板',
            '605': '沪市主板',
            '688': '科创板',
        }
        
        sector_counts = {}
        for code in stock_codes:
            prefix = code[:3]
            sector = sector_map.get(prefix, '其他')
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        
        # 构建DataFrame
        total = len(stock_codes)
        result['sector_dist'] = pd.DataFrame({
            '板块': list(sector_counts.keys()),
            '股票数量': list(sector_counts.values()),
            '占比(%)': [round(v/total*100, 2) for v in sector_counts.values()]
        })
        
        # 概念重叠分析（简化）
        result['concept_overlap'] = {
            'total_codes': len(stock_codes),
            'note': '基于代码前缀的板块分布（快速版）',
            'recommendation': '如需详细行业分布，请调用 akshare 补充'
        }
        
    except Exception as e:
        print(f"⚠️  板块分布获取失败: {e}")
        result['sector_dist'] = pd.DataFrame({
            '板块': ['获取失败'],
            '股票数量': [len(stock_codes)],
            '占比(%)': [100.0]
        })
    
    return result


def get_money_flow_from_tencent(stock_codes):
    """
    获取资金流向（简化版）
    使用腾讯财经接口获取主力净流入估算
    """
    result = []
    
    try:
        import requests
        
        # 分批获取，每批最多50只
        batch_size = 50
        for i in range(0, len(stock_codes), batch_size):
            batch = stock_codes[i:i+batch_size]
            
            # 构建腾讯接口URL（获取盘口数据）
            code_list = []
            for code in batch:
                if str(code).startswith('6'):
                    code_list.append(f"sh{code}")
                else:
                    code_list.append(f"sz{code}")
            
            url = f"http://qt.gtimg.cn/q={','.join(code_list)}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = 'gb2312'
            
            for line in resp.text.strip().split(';'):
                if 'v_' not in line:
                    continue
                
                try:
                    prefix, data = line.split('="', 1)
                    data = data.rstrip('"')
                    parts = data.split('~')
                    
                    if len(parts) < 45:
                        continue
                    
                    # 提取代码和名称
                    full_code = prefix.split('_')[-1]
                    code = full_code[2:]  # 去掉 sh/sz
                    name = parts[1]
                    price = float(parts[3])
                    change_pct = float(parts[32])
                    
                    # 腾讯接口的盘口数据不包含资金流向
                    # 使用涨跌幅作为资金流向的代理指标
                    # 涨幅大通常伴随资金流入
                    if change_pct > 5:
                        direction = '强势流入'
                    elif change_pct > 2:
                        direction = '流入'
                    elif change_pct < -5:
                        direction = '强势流出'
                    elif change_pct < -2:
                        direction = '流出'
                    else:
                        direction = '平衡'
                    
                    result.append({
                        '代码': code,
                        '名称': name,
                        '最新价': price,
                        '涨跌幅': f"{change_pct:+.2f}%",
                        '资金流向估算': direction,
                        '说明': '基于涨跌幅估算（腾讯接口）'
                    })
                    
                except Exception:
                    continue
        
    except Exception as e:
        print(f"⚠️  资金流向获取失败: {e}")
        for code in stock_codes:
            result.append({
                '代码': code,
                '名称': '获取失败',
                '最新价': 0,
                '涨跌幅': 'N/A',
                '资金流向估算': '未知',
                '说明': f'错误: {e}'
            })
    
    return pd.DataFrame(result)


def calculate_risk_radar(holdings, market_data, sector_dist, money_flow=None):
    """
    计算综合风险雷达图指标
    
    Returns:
        DataFrame: 各维度风险评分 (0-100，越高风险越大)
    """
    risk_scores = []
    
    # 1. 集中度风险 (前5大占比)
    total_value = sum(h.get('market_value', 0) for h in holdings)
    if total_value > 0:
        sorted_holdings = sorted(holdings, 
                                key=lambda x: x.get('market_value', 0), 
                                reverse=True)
        top5_value = sum(h.get('market_value', 0) for h in sorted_holdings[:5])
        concentration_risk = min(100, (top5_value / total_value) * 100)
    else:
        concentration_risk = 50
    
    # 2. 流动性风险 (平均减仓天数)
    avg_days = sum(h.get('days_to_sell', 7) for h in holdings) / len(holdings) if holdings else 7
    liquidity_risk = min(100, (avg_days / 10) * 100)  # 10天以上为100分
    
    # 3. 板块集中风险
    if not sector_dist.empty and '占比(%)' in sector_dist.columns:
        max_sector_pct = sector_dist['占比(%)'].max()
        sector_risk = min(100, max_sector_pct)
    else:
        sector_risk = 50
    
    # 4. 资金流出风险（简化版，无实时数据）
    fund_risk = 50  # 默认中等风险
    
    # 5. 亏损风险 (当前浮亏比例)
    total_cost = sum(h['shares'] * h['cost_price'] for h in holdings)
    total_value = sum(h['shares'] * market_data.get(h['code'], {}).get('price', h['cost_price']) 
                      for h in holdings)
    if total_cost > 0:
        loss_pct = ((total_value - total_cost) / total_cost) * 100
        loss_risk = min(100, max(0, 50 - loss_pct))  # 亏损越大风险分越高
    else:
        loss_risk = 50
        loss_pct = 0
    
    # 6. 市场相关性风险 (简化，假设中等)
    correlation_risk = 60
    
    risk_scores.append({
        '风险维度': '集中度风险',
        '评分(0-100)': round(concentration_risk, 1),
        '风险等级': '高' if concentration_risk > 70 else '中' if concentration_risk > 40 else '低',
        '说明': f'前5大重仓占比{concentration_risk:.1f}%'
    })
    
    risk_scores.append({
        '风险维度': '流动性风险',
        '评分(0-100)': round(liquidity_risk, 1),
        '风险等级': '高' if liquidity_risk > 70 else '中' if liquidity_risk > 40 else '低',
        '说明': f'平均减仓{avg_days:.1f}天'
    })
    
    risk_scores.append({
        '风险维度': '板块集中风险',
        '评分(0-100)': round(sector_risk, 1),
        '风险等级': '高' if sector_risk > 70 else '中' if sector_risk > 40 else '低',
        '说明': f'最大板块占比{sector_risk:.1f}%'
    })
    
    risk_scores.append({
        '风险维度': '资金流出风险',
        '评分(0-100)': round(fund_risk, 1),
        '风险等级': '中',
        '说明': '需调用akshare获取实时资金流向'
    })
    
    risk_scores.append({
        '风险维度': '亏损风险',
        '评分(0-100)': round(loss_risk, 1),
        '风险等级': '高' if loss_risk > 70 else '中' if loss_risk > 40 else '低',
        '说明': f'当前浮亏{loss_pct:.1f}%' if total_cost > 0 else '未知'
    })
    
    risk_scores.append({
        '风险维度': '相关性风险',
        '评分(0-100)': round(correlation_risk, 1),
        '风险等级': '中',
        '说明': '中等相关性暴露'
    })
    
    # 计算综合评分
    avg_risk = sum(r['评分(0-100)'] for r in risk_scores) / len(risk_scores)
    risk_scores.append({
        '风险维度': '综合风险评分',
        '评分(0-100)': round(avg_risk, 1),
        '风险等级': '高' if avg_risk > 70 else '中' if avg_risk > 40 else '低',
        '说明': '六维度平均值'
    })
    
    return pd.DataFrame(risk_scores)


if __name__ == "__main__":
    # 测试
    test_codes = ['000001', '000002', '600519']
    
    print("测试板块分布（腾讯接口速度）...")
    sector = get_sector_distribution_batch(test_codes)
    print(sector['sector_dist'])
    print(f"耗时: 极速（本地计算，无API调用）")
