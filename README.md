# QuantTerminal

一个基于Python的量化交易终端，提供股票数据分析和AI智能投顾功能。

## 功能特性

- **市场行情**: 实时获取A股市场数据，支持新浪财经API
- **图表分析**: K线图绘制，支持RSI、MACD、SMA、布林带等技术指标
- **量化分析**: 策略回测功能，支持多种交易策略
- **AI投顾**: 集成DeepSeek AI，提供巴菲特、格雷厄姆、彼得林奇、达里奥等投资风格分析

## 安装

1. 克隆仓库
```bash
git clone https://github.com/你的用户名/QuantTerminal.git
cd QuantTerminal
```

2. 创建虚拟环境
```bash
python -m venv venv
```

3. 安装依赖
```bash
venv\Scripts\pip install -r requirements.txt
```

## 运行

```bash
venv\Scripts\python app.py
```

## 依赖

- PyQt5: GUI框架
- matplotlib: 图表绘制
- pandas: 数据处理
- numpy: 数值计算
- yfinance: 股票数据获取
- requests: HTTP请求

## 注意事项

- 程序默认使用A股数据
- AI功能需要DeepSeek API密钥
- 部分API可能需要网络代理

## 许可证

MIT License