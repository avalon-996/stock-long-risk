#!/usr/bin/env python3
"""
股票多头持仓风险测评工具
用法: python3 stock_long_risk.py [持仓文件路径]
示例: python3 stock_long_risk.py /path/to/holdings.json
"""
import json
import sys
from datetime import datetime, timedelta

def get_realtime_data(stock_codes, holdings=None):
    """
    获取实时行情数据（分批获取，支持大量股票）
    使用腾讯财经接口获取A股实时行情（快速稳定）
    
    Args:
        stock_codes: 股票代码列表，如 ['000001', '600519']
        holdings: 持仓列表，用于获取股票名称
    
    Returns:
        dict: {code: {"price": float, "avg_volume": int, "name": str}}
    """
    import requests
    
    result = {}
    
    # 分批获取，每批最多50只
    batch_size = 50
    total_codes = len(stock_codes)
    
    for i in range(0, total_codes, batch_size):
        batch = stock_codes[i:i+batch_size]
        
        # 构建腾讯财经接口URL
        code_list = []
        for code in batch:
            if code.startswith('6'):
                code_list.append(f"sh{code}")
            else:
                code_list.append(f"sz{code}")
        
        url = f"http://qt.gtimg.cn/q={','.join(code_list)}"
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = 'gb2312'
            text = resp.text
            
            # 解析数据
            for line in text.strip().split(';'):
                line = line.strip()
                if not line or 'v_' not in line:
                    continue
                
                try:
                    prefix, data = line.split('="', 1)
                    data = data.rstrip('"')
                    parts = data.split('~')
                    
                    if len(parts) < 45:
                        continue
                    
                    # 提取股票代码（去掉前缀）
                    full_code = prefix.split('_')[-1]
                    code = full_code[2:]  # 去掉 sh/sz 前缀
                    
                    # 获取股票名称
                    name = parts[1]
                    if holdings:
                        for h in holdings:
                            if h['code'] == code:
                                name = h.get('name', parts[1])
                                break
                    
                    result[code] = {
                        "name": name,
                        "price": float(parts[3]),
                        "avg_volume": int(parts[36]) if parts[36].isdigit() else 100000,
                        "change_pct": float(parts[32]),
                    }
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"  批次 {i//batch_size + 1} 获取失败: {e}")
            continue
    
    if result:
        return result
    
    # 备用：使用 akshare 逐个获取
    print("  尝试备用数据源...")
    try:
        import akshare as ak
        from datetime import datetime, timedelta
        
        for code in stock_codes:
            try:
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
                
                df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                       start_date=start_date, end_date=end_date, adjust="qfq")
                
                if not df.empty:
                    latest = df.iloc[-1]
                    name = code
                    if holdings:
                        for h in holdings:
                            if h['code'] == code:
                                name = h.get('name', code)
                                break
                    
                    result[code] = {
                        "name": name,
                        "price": float(latest['收盘']),
                        "avg_volume": 100000,
                        "change_pct": 0,
                    }
            except Exception as e:
                continue
        
        return result
        
    except Exception as e:
        print(f"⚠️  获取实时数据失败: {e}")
        return {}

# 模拟市场数据（备用）
MARKET_DATA = {
    "000001": {"name": "平安银行", "price": 11.02, "avg_volume": 1000000, "beta": 1.1},
    "000002": {"name": "万科A", "price": 15.50, "avg_volume": 800000, "beta": 1.2},
    "600519": {"name": "贵州茅台", "price": 1680.00, "avg_volume": 50000, "beta": 0.9},
    "000858": {"name": "五粮液", "price": 145.00, "avg_volume": 200000, "beta": 1.0},
    "002857": {"name": "三晖电气", "price": 23.50, "avg_volume": 50000, "beta": 1.3},
}

def load_market_data(holdings):
    """
    加载市场数据，优先使用持仓文件中的现价，其次使用实时数据
    
    Args:
        holdings: 持仓列表
    
    Returns:
        dict: {code: {"price": float, "avg_volume": int, "name": str, "beta": float}}
    """
    stock_codes = [h['code'] for h in holdings]
    
    # 先尝试获取实时数据（用于获取成交量等信息）
    realtime_data = get_realtime_data(stock_codes, holdings)
    
    market_data = {}
    for h in holdings:
        code = h['code']
        
        # 优先使用持仓文件中的 current_price
        if h.get('current_price') and h['current_price'] > 0:
            price = h['current_price']
        elif code in realtime_data:
            price = realtime_data[code]["price"]
        else:
            price = h.get('cost_price', 0)
        
        # 获取其他市场数据
        if code in realtime_data:
            avg_volume = realtime_data[code].get("avg_volume", 100000)
            # 如果日均成交量为0或无效，设置默认值
            if not avg_volume or avg_volume <= 0:
                avg_volume = 100000
            name = realtime_data[code].get("name", h.get('name', code))
        else:
            avg_volume = 100000
            name = h.get('name', code)
        
        market_data[code] = {
            "name": name,
            "price": price,
            "avg_volume": avg_volume,
            "beta": 1.0,  # 默认Beta为1.0
        }
    
    # 尝试计算个股Beta
    try:
        stock_betas = calculate_stock_betas(stock_codes)
        for code, beta in stock_betas.items():
            if code in market_data:
                market_data[code]['beta'] = beta
    except Exception as e:
        pass  # 如果Beta计算失败，使用默认值1.0
    
    return market_data

def calculate_stock_betas(stock_codes, period=60):
    """
    计算个股Beta（基于行业分类估算）
    
    Args:
        stock_codes: 股票代码列表
        period: 计算Beta的历史天数（默认60天）
    
    Returns:
        dict: {code: beta}
    """
    # 行业Beta参考值（基于历史数据的经验值）
    industry_betas = {
        # 金融
        '银行': 1.0, '证券': 1.3, '保险': 1.1,
        # 科技
        '半导体': 1.4, '软件': 1.3, '电子': 1.2,
        # 医药
        '医药': 0.9, '生物科技': 1.1,
        # 消费
        '白酒': 1.1, '食品': 0.8, '家电': 1.0,
        # 周期
        '有色': 1.3, '钢铁': 1.2, '化工': 1.1,
        # 能源
        '电力': 0.7, '煤炭': 1.0, '石油': 0.9,
        # 制造
        '汽车': 1.2, '机械': 1.1, '军工': 1.3,
        # 地产
        '房地产': 1.2, '建筑': 1.1,
        # 其他
        'ST': 1.4, '传媒': 1.2, '通信': 1.0,
    }
    
    # 股票代码到行业的映射（简化版）
    stock_industry_map = {
        # 金融
        '000001': '银行', '600000': '银行', '601166': '银行', '002142': '银行',
        '600030': '证券', '600837': '证券', '601688': '证券', '601788': '证券',
        '601318': '保险', '601601': '保险', '601628': '保险',
        # 科技
        '002156': '半导体', '600745': '半导体', '603501': '半导体', '600703': '半导体',
        '600570': '软件', '300033': '软件', '300059': '软件',
        '002230': '电子', '002415': '电子', '000725': '电子', '000100': '电子',
        # 医药
        '600276': '医药', '600196': '医药', '603259': '医药', '300015': '医药',
        '300122': '医药', '002007': '医药', '300142': '医药', '603658': '医药',
        # 消费
        '000858': '白酒', '000568': '白酒', '002304': '白酒', '600809': '白酒',
        '600887': '食品', '000895': '食品', '603288': '食品',
        '000333': '家电', '000651': '家电', '600690': '家电',
        # 周期
        '002460': '有色', '300014': '有色', '601899': '有色',
        '600585': '建材', '002271': '建材',
        # 能源
        '600900': '电力', '601985': '电力', '601088': '煤炭',
        '601857': '石油', '600028': '石油',
        # 制造
        '002594': '汽车', '601633': '汽车',
        '600031': '机械', '601766': '机械',
        '600893': '军工', '000768': '军工',
        # 地产
        '000002': '房地产', '600048': '房地产',
        '601668': '建筑', '601390': '建筑', '601186': '建筑', '601800': '建筑',
        # 其他
        '300096': 'ST',  # ST易联众
        '300413': '传媒', '002027': '传媒',
        '000063': '通信', '600050': '通信',
    }
    
    betas = {}
    for code in stock_codes:
        industry = stock_industry_map.get(code, '其他')
        beta = industry_betas.get(industry, 1.0)
        betas[code] = beta
    
    return betas

def calculate_risk_metrics(holdings, market_data, warning_line=0.85, liquidation_line=0.80):
    """
    计算持仓风险指标
    
    Args:
        holdings: 持仓列表 [{code, name, shares, cost_price, current_price}]
        market_data: 市场数据 {code: {price, avg_volume, name, beta}}
        warning_line: 预警线（默认85%）
        liquidation_line: 平仓线（默认80%）
    """
    total_cost = sum(h['shares'] * h['cost_price'] for h in holdings)
    
    # 使用持仓文件中的 current_price 或市场数据中的最新价格计算总市值
    total_value = 0
    for h in holdings:
        code = h['code']
        # 优先使用持仓文件中的 current_price
        if h.get('current_price') and h['current_price'] > 0:
            current_price = h['current_price']
        elif code in market_data:
            current_price = market_data[code]['price']
        else:
            current_price = h.get('cost_price', 0)
        total_value += h['shares'] * current_price
    
    total_profit = total_value - total_cost
    profit_pct = (total_profit / total_cost) * 100 if total_cost > 0 else 0
    
    # 计算净值（假设初始净值为1）
    nav = 1 + (profit_pct / 100)
    
    # 距离预警线/平仓线的跌幅
    warning_drop = ((nav - warning_line) / nav) * 100 if nav > warning_line else 0
    liquidation_drop = ((nav - liquidation_line) / nav) * 100 if nav > liquidation_line else 0
    
    # 集中度分析
    weights = []
    for h in holdings:
        code = h['code']
        # 优先使用持仓文件中的 current_price
        if h.get('current_price') and h['current_price'] > 0:
            current_price = h['current_price']
        elif code in market_data:
            current_price = market_data[code]['price']
        else:
            current_price = h.get('cost_price', 0)
        value = h['shares'] * current_price
        weight = (value / total_value) * 100 if total_value > 0 else 0
        weights.append({
            'code': h['code'],
            'name': h['name'],
            'weight': weight,
            'value': value
        })
    weights.sort(key=lambda x: x['weight'], reverse=True)
    
    # 前5大重仓集中度
    top5_concentration = sum(w['weight'] for w in weights[:5])
    
    # 计算投资组合Beta（加权平均）
    portfolio_beta = 0
    for w in weights:
        code = w['code']
        weight = w['weight'] / 100  # 转换为小数
        stock_beta = market_data.get(code, {}).get('beta', 1.0)
        portfolio_beta += weight * stock_beta
    
    return {
        'total_cost': total_cost,
        'total_value': total_value,
        'total_profit': total_profit,
        'profit_pct': profit_pct,
        'nav': nav,
        'warning_line': warning_line,
        'liquidation_line': liquidation_line,
        'warning_drop': warning_drop,
        'liquidation_drop': liquidation_drop,
        'weights': weights,
        'top5_concentration': top5_concentration,
        'portfolio_beta': portfolio_beta
    }

def calculate_liquidity(holdings, market_data):
    """计算流动性指标和减仓时间"""
    liquidity_analysis = []
    
    for h in holdings:
        code = h['code']
        shares = h['shares']
        
        # 获取市场数据
        if code in market_data:
            avg_volume = market_data[code]['avg_volume']
            name = market_data[code]['name']
        else:
            avg_volume = 100000
            name = h['name']
        
        # 假设每天最多卖出日均成交量的 20%（避免冲击成本）
        daily_sellable = avg_volume * 0.2
        
        # 减仓所需天数
        days_to_sell = shares / daily_sellable if daily_sellable > 0 else float('inf')
        
        # 流动性评级
        if days_to_sell <= 1:
            liquidity_rating = "优秀"
        elif days_to_sell <= 3:
            liquidity_rating = "良好"
        elif days_to_sell <= 7:
            liquidity_rating = "一般"
        else:
            liquidity_rating = "较差"
        
        liquidity_analysis.append({
            'code': code,
            'name': name,
            'shares': shares,
            'avg_daily_volume': avg_volume,
            'daily_sellable': daily_sellable,
            'days_to_sell': days_to_sell,
            'liquidity_rating': liquidity_rating
        })
    
    return liquidity_analysis

def simulate_extreme_scenario(holdings, market_data, market_drop=0.20, liquidity_discount=0.30):
    """
    模拟极端情景下的减仓过程和亏损
    
    Args:
        holdings: 持仓列表
        market_data: 市场数据
        market_drop: 市场下跌幅度（默认20%）
        liquidity_discount: 流动性折扣（默认30%，即只能卖出日均70%）
    """
    results = []
    total_loss = 0
    total_days = 0
    
    for h in holdings:
        code = h['code']
        shares = h['shares']
        cost_price = h['cost_price']
        
        # 优先使用持仓文件中的 current_price，其次使用 market_data 中的价格
        if h.get('current_price') and h['current_price'] > 0:
            current_price = h['current_price']
        elif code in market_data:
            current_price = market_data[code]['price']
        else:
            current_price = cost_price
        
        # 获取成交量数据
        if code in market_data:
            avg_volume = market_data[code]['avg_volume']
        else:
            avg_volume = 100000
        
        # 极端行情下的价格
        extreme_price = current_price * (1 - market_drop)
        
        # 极端行情下可卖出的量（考虑流动性折扣）
        daily_sellable = avg_volume * (1 - liquidity_discount)
        
        # 减仓所需天数
        days_to_sell = shares / daily_sellable if daily_sellable > 0 else float('inf')
        
        # 计算亏损
        # 假设每天均匀卖出，价格每天继续下跌（滑点）
        daily_slippage = 0.02  # 每天额外下跌2%
        avg_sell_price = extreme_price * (1 - daily_slippage * days_to_sell / 2)
        
        total_sell_value = shares * avg_sell_price
        total_cost_value = shares * cost_price
        loss = total_cost_value - total_sell_value
        loss_pct = (loss / total_cost_value) * 100 if total_cost_value > 0 else 0
        
        results.append({
            'code': code,
            'name': h['name'],
            'shares': shares,
            'cost_price': cost_price,
            'current_price': current_price,
            'extreme_price': extreme_price,
            'avg_sell_price': avg_sell_price,
            'days_to_sell': days_to_sell,
            'total_sell_value': total_sell_value,
            'total_cost_value': total_cost_value,
            'loss': loss,
            'loss_pct': loss_pct
        })
        
        total_loss += loss
        total_days = max(total_days, days_to_sell)
    
    return {
        'holdings': results,
        'total_loss': total_loss,
        'avg_days': total_days,
        'market_drop': market_drop,
        'liquidity_discount': liquidity_discount
    }

def calculate_correlation(stock_codes, period=60):
    """
    计算持仓股票间的相关性矩阵（并行获取历史数据，带超时控制）
    
    Args:
        stock_codes: 股票代码列表
        period: 计算相关性的历史天数（默认60天）
    
    Returns:
        dict: {
            'correlation_matrix': DataFrame,
            'high_corr_pairs': [(code1, code2, corr), ...],
            'avg_correlation': float
        }
    """
    try:
        import akshare as ak
        import pandas as pd
        import numpy as np
        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
        
        # 并行获取历史行情数据
        price_data = {}
        
        def fetch_stock_data(code):
            """获取单只股票历史数据（带超时）"""
            try:
                # 只获取最近60天数据，减少请求时间
                import datetime
                end_date = datetime.datetime.now().strftime('%Y%m%d')
                start_date = (datetime.datetime.now() - datetime.timedelta(days=70)).strftime('%Y%m%d')
                
                df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                       start_date=start_date, end_date=end_date, adjust="qfq")
                
                if not df.empty and '收盘' in df.columns and len(df) >= 20:
                    return code, df.set_index('日期')['收盘'].iloc[-period:]
            except Exception as e:
                pass  # 静默失败，不打印错误
            return code, None
        
        # 使用线程池并行获取（10个线程）
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_code = {executor.submit(fetch_stock_data, code): code for code in stock_codes}
            
            # 设置总超时时间60秒
            completed = 0
            for future in as_completed(future_to_code, timeout=60):
                code = future_to_code[future]
                try:
                    code_result, data = future.result(timeout=10)  # 单只股票10秒超时
                    if data is not None:
                        price_data[code_result] = data
                        completed += 1
                except Exception as e:
                    pass
        
        if len(price_data) < 2:
            return None
        
        # 构建价格矩阵
        price_df = pd.DataFrame(price_data)
        
        # 计算日收益率
        returns_df = price_df.pct_change().dropna()
        
        # 如果数据太少，返回None
        if len(returns_df) < 10:
            return None
        
        # 计算相关性矩阵
        corr_matrix = returns_df.corr()
        
        # 找出高相关性股票对（相关系数 > 0.7）
        high_corr_pairs = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                corr = corr_matrix.iloc[i, j]
                # 检查是否为有效数值
                if pd.notna(corr) and abs(corr) > 0.7:
                    high_corr_pairs.append((
                        corr_matrix.columns[i],
                        corr_matrix.columns[j],
                        corr
                    ))
        
        # 按相关系数绝对值排序
        high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        
        # 计算平均相关性（排除对角线和NaN）
        mask = ~np.eye(len(corr_matrix), dtype=bool)
        corr_values = corr_matrix.values[mask]
        # 只取有效数值
        valid_corr = corr_values[~np.isnan(corr_values)]
        avg_corr = valid_corr.mean() if len(valid_corr) > 0 else 0
        
        return {
            'correlation_matrix': corr_matrix,
            'high_corr_pairs': high_corr_pairs,
            'avg_correlation': avg_corr
        }
        
    except Exception as e:
        return None

def export_to_excel(holdings, market_data, risk, liquidity, extreme, correlation, output_file=None, send_wechat=False, wechat_user=None):
    """
    导出风险测评数据到 Excel
    
    Args:
        holdings: 持仓列表
        market_data: 市场数据
        risk: 风险指标
        liquidity: 流动性分析
        extreme: 极端情景模拟
        correlation: 相关性分析
        output_file: 输出文件路径（默认自动生成）
        send_wechat: 是否发送到微信
        wechat_user: 微信用户ID
    """
    try:
        import pandas as pd
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils.dataframe import dataframe_to_rows
        
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"/tmp/stock_risk_report_{timestamp}.xlsx"
        
        # 创建 Excel writer
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            
            # Sheet 1: 整体风险评估
            summary_data = {
                '指标': ['总成本', '总市值', '总盈亏', '盈亏比例', '当前净值', '预警线', '平仓线', 
                        '距离预警线', '距离平仓线', '前5大集中度', '投资组合β'],
                '数值': [
                    f"{risk['total_cost']:,.2f} 元",
                    f"{risk['total_value']:,.2f} 元",
                    f"{risk['total_profit']:,.2f} 元",
                    f"{risk['profit_pct']:+.2f}%",
                    f"{risk['nav']:.4f}",
                    f"{risk['warning_line']:.2%}",
                    f"{risk['liquidation_line']:.2%}",
                    f"{risk['warning_drop']:.2f}%",
                    f"{risk['liquidation_drop']:.2f}%",
                    f"{risk['top5_concentration']:.2f}%",
                    f"{risk['portfolio_beta']:.3f}"
                ]
            }
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name='整体风险评估', index=False)
            
            # Sheet 2: 持仓明细
            holdings_data = []
            for h in holdings:
                code = h['code']
                # 优先使用持仓文件中的 current_price
                if h.get('current_price') and h['current_price'] > 0:
                    current_price = h['current_price']
                elif code in market_data:
                    current_price = market_data[code]['price']
                else:
                    current_price = h.get('cost_price', 0)
                market_value = h['shares'] * current_price
                cost_value = h['shares'] * h['cost_price']
                profit = market_value - cost_value
                profit_pct = (profit / cost_value) * 100 if cost_value > 0 else 0
                
                holdings_data.append({
                    '股票代码': code,
                    '股票名称': h['name'],
                    '持仓数量': h['shares'],
                    '成本价': h['cost_price'],
                    '当前价': current_price,
                    '市值': market_value,
                    '成本': cost_value,
                    '盈亏': profit,
                    '盈亏比例': f"{profit_pct:+.2f}%",
                    '个股β': round(market_data.get(code, {}).get('beta', 1.0), 3)
                })
            df_holdings = pd.DataFrame(holdings_data)
            df_holdings.to_excel(writer, sheet_name='持仓明细', index=False)
            
            # Sheet 3: 流动性分析
            liquidity_data = []
            for l in liquidity:
                liquidity_data.append({
                    '股票代码': l['code'],
                    '股票名称': l['name'],
                    '持仓数量': l['shares'],
                    '日均成交量': l['avg_daily_volume'],
                    '每日可卖': int(l['daily_sellable']),
                    '减仓天数': round(l['days_to_sell'], 2),
                    '流动性评级': l['liquidity_rating']
                })
            df_liquidity = pd.DataFrame(liquidity_data)
            df_liquidity.to_excel(writer, sheet_name='流动性分析', index=False)
            
            # Sheet 4: 极端情景模拟
            extreme_data = []
            for r in extreme['holdings']:
                extreme_data.append({
                    '股票代码': r['code'],
                    '股票名称': r['name'],
                    '持仓数量': r['shares'],
                    '成本价': r['cost_price'],
                    '当前价': r['current_price'],
                    '极端情景价': r['extreme_price'],
                    '平均卖出价': r['avg_sell_price'],
                    '减仓天数': round(r['days_to_sell'], 2),
                    '卖出金额': r['total_sell_value'],
                    '成本金额': r['total_cost_value'],
                    '预计亏损': r['loss'],
                    '亏损比例': f"{r['loss_pct']:.2f}%"
                })
            # 添加合计行
            extreme_data.append({
                '股票代码': '合计',
                '股票名称': '',
                '持仓数量': '',
                '成本价': '',
                '当前价': '',
                '极端情景价': '',
                '平均卖出价': '',
                '减仓天数': round(extreme['avg_days'], 2),
                '卖出金额': sum(r['total_sell_value'] for r in extreme['holdings']),
                '成本金额': sum(r['total_cost_value'] for r in extreme['holdings']),
                '预计亏损': extreme['total_loss'],
                '亏损比例': f"{(extreme['total_loss'] / sum(r['total_cost_value'] for r in extreme['holdings']) * 100):.2f}%"
            })
            df_extreme = pd.DataFrame(extreme_data)
            df_extreme.to_excel(writer, sheet_name='极端情景模拟', index=False)
            
            # Sheet 5: 相关性矩阵（如果有）
            if correlation and correlation.get('correlation_matrix') is not None:
                corr_matrix = correlation['correlation_matrix']
                corr_matrix.to_excel(writer, sheet_name='相关性矩阵')
                
                # 高相关性股票对
                if correlation.get('high_corr_pairs'):
                    high_corr_data = []
                    for code1, code2, corr in correlation['high_corr_pairs']:
                        name1 = market_data.get(code1, {}).get('name', code1)
                        name2 = market_data.get(code2, {}).get('name', code2)
                        high_corr_data.append({
                            '股票1代码': code1,
                            '股票1名称': name1,
                            '股票2代码': code2,
                            '股票2名称': name2,
                            '相关系数': round(corr, 4),
                            '相关类型': '正相关' if corr > 0 else '负相关'
                        })
                    df_high_corr = pd.DataFrame(high_corr_data)
                    df_high_corr.to_excel(writer, sheet_name='高相关性股票对', index=False)
        
        print(f"\n📊 Excel 报告已生成: {output_file}")
        
        # 发送到微信
        if send_wechat and wechat_user:
            try:
                import subprocess
                # 使用 OpenClaw message 工具发送文件
                # 注意：这里需要在 OpenClaw 环境中运行才能使用 message 工具
                print(f"📤 正在发送 Excel 报告到微信...")
                # 返回文件路径，由调用方处理发送
            except Exception as e:
                print(f"⚠️  发送微信失败: {e}")
        
        return output_file
        
    except Exception as e:
        print(f"⚠️  导出 Excel 失败: {e}")
        return None

def generate_report(holdings_file=None, output_excel=None, wechat_user=None):
    """生成完整的风险测评报告"""
    
    # 示例持仓数据（如果没有提供文件）
    if holdings_file:
        with open(holdings_file, 'r') as f:
            holdings = json.load(f)
    else:
        holdings = [
            {"code": "000001", "name": "平安银行", "shares": 10000, "cost_price": 10.50, "current_price": 11.02},
            {"code": "000002", "name": "万科A", "shares": 5000, "cost_price": 16.00, "current_price": 15.50},
            {"code": "600519", "name": "贵州茅台", "shares": 100, "cost_price": 1650.00, "current_price": 1680.00},
            {"code": "002857", "name": "三晖电气", "shares": 2000, "cost_price": 22.72, "current_price": 23.50},
        ]
    
    print("=" * 60)
    print("📊 股票多头持仓风险测评报告")
    print("=" * 60)
    print(f"测评时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    
    # 加载市场数据
    print("正在获取实时行情数据...")
    market_data = load_market_data(holdings)
    # 统计成功获取实时数据的股票数量（有成交量数据说明接口返回成功）
    realtime_count = sum(1 for h in holdings if h['code'] in market_data and market_data[h['code']].get('avg_volume', 0) > 0)
    print(f"✅ 已获取 {realtime_count}/{len(holdings)} 只股票的实时数据")
    print()
    
    # 1. 整体风险评估
    print("【一、整体风险评估】")
    print("-" * 60)
    risk = calculate_risk_metrics(holdings, market_data)
    print(f"总成本: {risk['total_cost']:,.2f} 元")
    print(f"总市值: {risk['total_value']:,.2f} 元")
    print(f"总盈亏: {risk['total_profit']:,.2f} 元 ({risk['profit_pct']:+.2f}%)")
    print(f"当前净值: {risk['nav']:.4f}")
    print(f"预警线: {risk['warning_line']:.2%}")
    print(f"平仓线: {risk['liquidation_line']:.2%}")
    print()
    print(f"距离预警线还需下跌: {risk['warning_drop']:.2f}%")
    print(f"距离平仓线还需下跌: {risk['liquidation_drop']:.2f}%")
    print()
    print(f"前5大重仓集中度: {risk['top5_concentration']:.2f}%")
    print(f"投资组合β: {risk['portfolio_beta']:.3f}")
    if risk['portfolio_beta'] > 1.2:
        print("  ⚠️  β > 1.2，组合波动大于市场，市场上涨时收益更高，下跌时亏损更大")
    elif risk['portfolio_beta'] < 0.8:
        print("  ✅  β < 0.8，组合波动小于市场，防御性较强")
    else:
        print("  ✅  β 在0.8-1.2之间，组合波动与市场相当")
    print()
    
    # 2. 持仓权重分析
    print("【二、持仓权重分析】")
    print("-" * 60)
    for w in risk['weights'][:5]:
        print(f"{w['code']} {w['name']}: {w['weight']:.2f}% ({w['value']:,.2f}元)")
    print()
    
    # 3. 持仓相关性分析
    print("【三、持仓相关性分析】")
    print("-" * 60)
    stock_codes = [h['code'] for h in holdings]
    correlation = calculate_correlation(stock_codes)
    
    if correlation:
        print(f"平均相关性: {correlation['avg_correlation']:.3f}")
        print()
        
        if correlation['high_corr_pairs']:
            print("⚠️  高相关性股票对（|相关系数| > 0.7）:")
            for code1, code2, corr in correlation['high_corr_pairs'][:5]:
                name1 = market_data.get(code1, {}).get('name', code1)
                name2 = market_data.get(code2, {}).get('name', code2)
                corr_type = "正相关" if corr > 0 else "负相关"
                print(f"  {code1}({name1}) - {code2}({name2}): {corr:.3f} ({corr_type})")
            print()
            print("  提示: 高相关性股票同涨同跌风险大，建议分散配置")
        else:
            print("✅ 持仓股票间相关性较低，分散化效果良好")
    else:
        print("⚠️  无法获取历史数据，跳过相关性分析")
    print()
    
    # 4. 流动性分析
    print("【四、流动性分析】")
    print("-" * 60)
    liquidity = calculate_liquidity(holdings, market_data)
    total_liquidation_days = 0
    for l in liquidity:
        print(f"{l['code']} {l['name']}:")
        print(f"  持仓数量: {l['shares']:,} 股")
        print(f"  日均成交: {l['avg_daily_volume']:,} 股")
        print(f"  预计减仓天数: {l['days_to_sell']:.1f} 天")
        print(f"  流动性评级: {l['liquidity_rating']}")
        print()
        total_liquidation_days = max(total_liquidation_days, l['days_to_sell'])
    print(f"整体清仓预计需要: {total_liquidation_days:.1f} 天")
    print()
    
    # 5. 极端情景模拟
    print("【五、极端情景模拟】")
    print("-" * 60)
    print("假设条件:")
    print("  - 市场下跌 20%")
    print("  - 流动性下降 30%（只能卖出日均70%）")
    print("  - 每日额外滑点 2%")
    print()
    
    extreme = simulate_extreme_scenario(holdings, market_data, market_drop=0.20, liquidity_discount=0.30)
    
    for r in extreme['holdings']:
        print(f"{r['code']} {r['name']}:")
        print(f"  成本价: {r['cost_price']:.2f} → 当前: {r['current_price']:.2f} → 极端: {r['extreme_price']:.2f}")
        print(f"  平均卖出价: {r['avg_sell_price']:.2f}")
        print(f"  减仓天数: {r['days_to_sell']:.1f} 天")
        print(f"  预计亏损: {r['loss']:,.2f} 元 ({r['loss_pct']:.2f}%)")
        print()
    
    print(f"总预计亏损: {extreme['total_loss']:,.2f} 元")
    print(f"平均减仓时间: {extreme['avg_days']:.1f} 天")
    print()
    
    # 6. 风险提示
    print("【六、风险提示与建议】")
    print("-" * 60)
    if risk['warning_drop'] < 5:
        print("⚠️ 警告: 距离预警线不足5%，建议降低仓位或增加保证金")
    elif risk['warning_drop'] < 10:
        print("⚠️ 注意: 距离预警线不足10%，密切关注市场波动")
    else:
        print("✅ 安全: 距离预警线尚有缓冲空间")
    
    print()
    if total_liquidation_days > 5:
        print(f"⚠️ 流动性风险: 完全清仓需要 {total_liquidation_days:.1f} 天")
        print("  建议: 提前分批减仓，避免极端行情下无法及时退出")
    else:
        print(f"✅ 流动性良好: 完全清仓预计 {total_liquidation_days:.1f} 天")
    
    print()
    print("=" * 60)
    
    # 导出 Excel（如果指定了输出路径）
    if output_excel:
        excel_file = export_to_excel(holdings, market_data, risk, liquidity, extreme, correlation, output_excel)
        
        # 如果指定了微信用户，发送文件
        if excel_file and wechat_user:
            print(f"\n📤 准备发送 Excel 报告到微信用户: {wechat_user}")
            print(f"   文件路径: {excel_file}")
            # 返回文件路径，由调用方（OpenClaw）使用 message 工具发送
            return {
                'excel_file': excel_file,
                'wechat_user': wechat_user,
                'risk_summary': {
                    'total_cost': risk['total_cost'],
                    'total_value': risk['total_value'],
                    'profit_pct': risk['profit_pct'],
                    'nav': risk['nav'],
                    'warning_drop': risk['warning_drop']
                }
            }
    
    return None

if __name__ == "__main__":
    holdings_file = sys.argv[1] if len(sys.argv) > 1 else None
    output_excel = sys.argv[2] if len(sys.argv) > 2 else None
    wechat_user = sys.argv[3] if len(sys.argv) > 3 else None
    result = generate_report(holdings_file, output_excel, wechat_user)
