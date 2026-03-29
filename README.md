# Stock Long Risk - 股票多头持仓风险测评

[![Version](https://img.shields.io/badge/version-0.4.0-blue.svg)](https://github.com/avalon-996/stock-long-risk)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

分析股票多头产品持仓风险，计算极端情况下减仓所需时间和预期亏损。

## 功能特点

- 📈 **实时行情接入** - 使用腾讯财经接口获取 A 股实时行情数据（快速稳定）
- 📊 **整体风险评估** - 净值、盈亏、预警线/平仓线距离
- 📈 **持仓集中度分析** - 前5大重仓占比
- 🔗 **持仓相关性分析** - 计算股票间相关系数，识别同涨同跌风险
- 💧 **流动性分析** - 各持仓减仓所需天数
- ⚡ **极端情景模拟** - 市场下跌20%情景下的减仓过程
- 💰 **预期亏损计算** - 从触发平仓线到清仓的全程损益
- 📑 **Excel 报告导出** - 导出多维度风险分析数据到 Excel

## 快速开始

```bash
# 安装依赖
pip install akshare pandas openpyxl

# 运行测试
python3 scripts/stock_long_risk.py examples/holdings_10.json

# 导出 Excel 报告
python3 scripts/stock_long_risk.py holdings.json /tmp/report.xlsx
```

## 持仓文件格式

```json
[
  {
    "code": "600958",
    "name": "东方证券",
    "shares": 10240,
    "cost_price": 16.027
  }
]
```

## 详细文档

详见 [SKILL.md](SKILL.md)

## 📧 联系方式

如有问题或建议，欢迎联系：**495019787@qq.com**

## 许可证

MIT License

## 更新日志

### v0.4.0 (2026-03-29)
- 📧 添加联系方式

### v0.3.0 (2026-03-28)
- 📑 新增 Excel 报告导出功能
- 📊 支持多维度风险分析数据导出
