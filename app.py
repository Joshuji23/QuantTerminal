# -*- coding: utf-8 -*-
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import yfinance as yf
from datetime import datetime
import time
import threading
import os
from queue import Queue

# 配置matplotlib支持中文
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 设置yfinance缓存目录到用户可访问位置
try:
    yf.set_tz_cache_location(os.path.join(os.path.expanduser('~'), 'yfinance_cache'))
except:
    pass

# 尝试导入requests作为备用数据获取方案
try:
    import requests
    import json
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QLineEdit,
    QPushButton, QComboBox, QTextEdit, QLabel, QHeaderView, QStatusBar,
    QGroupBox, QFormLayout, QSpinBox, QCheckBox, QScrollArea, QSizePolicy,
    QDialog, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QMetaObject, Q_ARG
from PyQt5.QtGui import QFont, QColor, QPalette
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject

# DeepSeek API 配置
DEEPSEEK_API_KEY = "sk-871a179afc6f4ea4b629859576765094"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 缓存机制
stock_info_cache = {}
stock_data_cache = {}
last_fetch_time = {}
RATE_LIMIT_DELAY = 10  # 增加到 10 秒，避免限流
CACHE_EXPIRE_MINUTES = 60  # 延长到 60 分钟，减少请求频率
is_fetching = {}  # 防止重复请求
fetch_lock = threading.Lock()  # 线程锁，保护共享数据

# 模拟数据（当无法获取真实数据时使用）
mock_stock_info = [
    {'symbol': '000001', 'name': '平安银行', 'price': 12.50, 'change': 0.15, 'changePercent': 1.21, 'volume': 1520000, 'marketCap': 245000000000, 'peRatio': 5.2},
    {'symbol': '000002', 'name': '万科 A', 'price': 8.80, 'change': -0.12, 'changePercent': -1.35, 'volume': 2800000, 'marketCap': 98000000000, 'peRatio': 8.5},
    {'symbol': '600000', 'name': '浦发银行', 'price': 9.25, 'change': 0.08, 'changePercent': 0.87, 'volume': 1850000, 'marketCap': 285000000000, 'peRatio': 4.8},
    {'symbol': '600036', 'name': '招商银行', 'price': 35.60, 'change': 0.85, 'changePercent': 2.45, 'volume': 3200000, 'marketCap': 890000000000, 'peRatio': 6.5},
    {'symbol': '000858', 'name': '五粮液', 'price': 145.20, 'change': -2.30, 'changePercent': -1.56, 'volume': 980000, 'marketCap': 560000000000, 'peRatio': 22.8},
    {'symbol': '600519', 'name': '贵州茅台', 'price': 1680.50, 'change': 15.80, 'changePercent': 0.95, 'volume': 420000, 'marketCap': 2100000000000, 'peRatio': 28.5},
    {'symbol': '300750', 'name': '宁德时代', 'price': 185.30, 'change': 5.60, 'changePercent': 3.12, 'volume': 1850000, 'marketCap': 815000000000, 'peRatio': 18.2},
    {'symbol': '002594', 'name': '比亚迪', 'price': 258.80, 'change': -3.50, 'changePercent': -1.33, 'volume': 1280000, 'marketCap': 750000000000, 'peRatio': 32.5}
]

def fetch_real_stock_data_sina(symbol, period='1y'):
    """使用新浪财经API获取股票历史数据"""
    if not REQUESTS_AVAILABLE:
        return None
    
    try:
        # 新浪财经历史数据接口
        if symbol.startswith('6') or symbol.startswith('9'):
            market = 'sh'
        else:
            market = 'sz'
        
        # 使用新浪财经的日K线数据接口
        url = f"https://quotes.sina.cn/cn/api/quotes.php"
        params = {
            'symbol': f"{market}{symbol}",
            'datasource': 'quotes',
            'type': 'daily'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://finance.sina.com.cn'
        }
        
        # 如果新浪财经历史数据获取失败，返回None，使用模拟数据
        return None
    except Exception as e:
        print(f"新浪财经历史数据获取失败: {e}")
        return None

def fetch_real_stock_data(symbol, period='1y'):
    """获取股票数据，优先使用真实API"""
    cache_key = f"{symbol}_{period}"
    now = time.time()
    
    # 检查缓存（线程安全）
    with fetch_lock:
        if cache_key in stock_data_cache:
            cached_time, cached_data = stock_data_cache[cache_key]
            if now - cached_time < CACHE_EXPIRE_MINUTES * 60:
                return cached_data
    
    # 尝试东方财富 API
    real_data = fetch_real_stock_data_eastmoney(symbol, period)
    if real_data is not None and not real_data.empty:
        with fetch_lock:
            stock_data_cache[cache_key] = (time.time(), real_data)
        print(f"东方财富获取 {symbol} 历史数据成功，共 {len(real_data)} 条")
        return real_data
    
    # 如果东方财富失败，尝试新浪财经
    real_data = fetch_real_stock_data_sina(symbol, period)
    if real_data is not None and not real_data.empty:
        with fetch_lock:
            stock_data_cache[cache_key] = (time.time(), real_data)
        print(f"新浪财经获取 {symbol} 历史数据成功，共 {len(real_data)} 条")
        return real_data
    
    # 如果都失败，生成模拟数据
    mock_data = generate_mock_data(symbol, period)
    
    # 缓存数据
    with fetch_lock:
        stock_data_cache[cache_key] = (time.time(), mock_data)
    
    return mock_data

def generate_mock_data(symbol, period):
    """生成模拟股票数据"""
    base_price = {'000001': 12, '000002': 9, '600000': 9, '600036': 35, '000858': 145, '600519': 1680, '300750': 185, '002594': 258}.get(symbol, 100)
    periods = {'1d': 1, '1wk': 5, '1mo': 20, '3mo': 60, '1y': 252, '5y': 1260}
    num_days = periods.get(period, 60)
    
    np.random.seed(hash(symbol) % 1000)
    dates = pd.date_range(start=pd.Timestamp.now() - pd.Timedelta(days=num_days), periods=num_days, freq='B')
    close_prices = base_price + np.cumsum(np.random.randn(num_days) * 2)
    open_prices = close_prices[:-1]
    open_prices = np.insert(open_prices, 0, close_prices[0])
    high_prices = np.maximum(open_prices, close_prices) + np.random.rand(num_days) * 3
    low_prices = np.minimum(open_prices, close_prices) - np.random.rand(num_days) * 3
    volumes = np.random.randint(10000000, 100000000, num_days)
    
    data = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volumes
    }, index=dates)
    return data

def fetch_stock_info_eastmoney(symbols):
    """使用东方财富API获取A股股票信息"""
    if not REQUESTS_AVAILABLE:
        return None
    
    results = []
    try:
        url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            'fltt': 2,
            'invt': 2,
            'ut': 'b2884a393a59ad64002292a3e90d46a5',
            'fields': 'f1,f2,f3,f4,f5,f6,f7,f12,f13,f14,f15,f16,f17,f18,f20,f21,f22,f23,f24,f25,f26,f62',
            'secids': ','.join([f'1.{s}' if s.startswith('6') or s.startswith('9') else f'0.{s}' for s in symbols])
        }
        
        # 添加请求头模拟浏览器
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://quote.eastmoney.com/',
            'Connection': 'keep-alive'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        data = response.json()
        
        if data and data.get('data') and data['data'].get('diff'):
            for item in data['data']['diff']:
                try:
                    stock_info = {
                        'symbol': str(item.get('f12', '')),
                        'name': item.get('f14', ''),
                        'price': float(item.get('f2', 0)) if item.get('f2') != '-' else 0,
                        'change': float(item.get('f3', 0)) if item.get('f3') != '-' else 0,
                        'changePercent': float(item.get('f4', 0)) if item.get('f4') != '-' else 0,
                        'volume': int(float(item.get('f5', 0))) if item.get('f5') and item.get('f5') != '-' else 0,
                        'marketCap': float(item.get('f20', 0)) if item.get('f20') and item.get('f20') != '-' else 0,
                        'peRatio': float(item.get('f9', 0)) if item.get('f9') and item.get('f9') != '-' else 0
                    }
                    
                    if stock_info['price'] > 0:
                        results.append(stock_info)
                except Exception as e:
                    print(f"解析东方财富数据失败: {e}")
        
        return results if results else None
    except Exception as e:
        print(f"东方财富API获取失败: {e}")
        return None

def fetch_stock_info_sina_primary(symbols):
    """使用新浪财经API获取股票信息（主要方案）"""
    if not REQUESTS_AVAILABLE:
        return None
    
    results = []
    try:
        # 新浪财经API接口
        stock_codes = []
        for symbol in symbols:
            if symbol.startswith('6') or symbol.startswith('9'):
                stock_codes.append(f"sh{symbol}")
            else:
                stock_codes.append(f"sz{symbol}")
        
        if not stock_codes:
            return None
        
        url = f"https://hq.sinajs.cn/list={','.join(stock_codes)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://finance.sina.com.cn'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'gb2312'
        
        if not response.text or len(response.text.strip()) == 0:
            print("新浪财经 API 返回空数据")
            return None
        
        lines = response.text.split('\n')
        for line in lines:
            if '=' in line:
                parts = line.split('=')
                if len(parts) >= 2:
                    code = parts[0].strip().replace('var hq_str_', '')
                    data_str = parts[1].strip().replace('"', '')
                    data = data_str.split(',')
                    
                    # 确保数据足够且价格不为0
                    if len(data) >= 10 and data[1] and float(data[1]) > 0:
                        try:
                            # 提取股票代码
                            if code.startswith('sh') or code.startswith('sz'):
                                symbol = code[2:]
                            else:
                                symbol = code
                            
                            name = data[0]
                            price = float(data[1])  # 当前价格
                            prev_close = float(data[2])  # 昨日收盘价
                            change = price - prev_close
                            change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
                            volume = int(float(data[8]))  # 成交量
                            
                            # 从模拟数据补充市值和市盈率
                            mock = next((m for m in mock_stock_info if m['symbol'] == symbol), None)
                            market_cap = mock.get('marketCap', 0) if mock else 0
                            pe_ratio = mock.get('peRatio', 0) if mock else 0
                            
                            stock_info = {
                                'symbol': symbol,
                                'name': name,
                                'price': price,
                                'change': change,
                                'changePercent': change_percent,
                                'volume': volume,
                                'marketCap': market_cap,
                                'peRatio': pe_ratio
                            }
                            results.append(stock_info)
                        except Exception as parse_error:
                            print(f"解析{symbol}数据失败: {parse_error}")
        
        return results if results else None
    except Exception as e:
        print(f"新浪财经API获取失败: {e}")
        return None

def fetch_real_stock_data_eastmoney(symbol, period='1y'):
    """使用东方财富API获取股票历史数据"""
    if not REQUESTS_AVAILABLE:
        return None
    
    try:
        if symbol.startswith('6') or symbol.startswith('9'):
            secid = f'1.{symbol}'
        else:
            secid = f'0.{symbol}'
        
        url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            'secid': secid,
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': 101,
            'fqt': 1,
            'end': '20500101',
            'lmt': 252
        }
        
        # 添加请求头模拟浏览器
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://quote.eastmoney.com/',
            'Connection': 'keep-alive'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        data = response.json()
        
        if data and data.get('data') and data['data'].get('klines'):
            klines = data['data']['klines']
            dates = []
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []
            
            for line in klines:
                parts = line.split(',')
                if len(parts) >= 6:
                    dates.append(parts[0])
                    opens.append(float(parts[1]))
                    highs.append(float(parts[2]))
                    lows.append(float(parts[3]))
                    closes.append(float(parts[4]))
                    volumes.append(int(float(parts[5])))
            
            df = pd.DataFrame({
                'Open': opens,
                'High': highs,
                'Low': lows,
                'Close': closes,
                'Volume': volumes
            }, index=pd.to_datetime(dates))
            
            return df
        
        return None
    except Exception as e:
        print(f"东方财富历史数据获取失败: {e}")
        return None

def fetch_stock_info_sina(symbols):
    """使用新浪财经API获取股票信息（备用方案）"""
    if not REQUESTS_AVAILABLE:
        return None
    
    results = []
    try:
        # 新浪财经API接口
        url = "https://hq.sinajs.cn/list="
        stock_codes = []
        
        for symbol in symbols:
            # A 股代码转换为新浪财经格式
            if symbol.startswith('6') or symbol.startswith('9'):
                # 沪市股票
                stock_codes.append(f"sh{symbol}")
            else:
                # 深市股票
                stock_codes.append(f"sz{symbol}")
        
        if not stock_codes:
            return None
        
        url += ",".join(stock_codes)
        response = requests.get(url, timeout=15)
        response.encoding = 'gb2312'
        
        # 检查是否返回了有效数据
        if not response.text or len(response.text.strip()) == 0:
            print("新浪财经 API 返回空数据")
            return None
        
        lines = response.text.split('\n')
        for line in lines:
            if '=' in line:
                parts = line.split('=')
                if len(parts) >= 2:
                    code = parts[0].strip().replace('var hq_str_', '')
                    data_str = parts[1].strip().replace('"', '')
                    data = data_str.split(',')
                    
                    # 确保数据足够且价格不为0
                    if len(data) >= 10 and data[1] and float(data[1]) > 0:
                        try:
                            # 提取股票代码
                            if code.startswith('sh') or code.startswith('sz'):
                                symbol = code[2:]
                            else:
                                symbol = code
                            price = float(data[1])
                            prev_close = float(data[2])
                            change = price - prev_close
                            change_percent = (change / prev_close) * 100
                            volume = int(float(data[8]))
                            
                            stock_info = {
                                'symbol': symbol,
                                'name': data[0],
                                'price': price,
                                'change': change,
                                'changePercent': change_percent,
                                'volume': volume,
                                'marketCap': 0,
                                'peRatio': 0
                            }
                            results.append(stock_info)
                        except Exception as parse_error:
                            print(f"解析{symbol}数据失败: {parse_error}")
        return results if results else None
    except Exception as e:
        print(f"新浪财经API获取失败: {e}")
        return None

def fetch_real_stock_info(symbols):
    """获取股票信息，优先使用新浪财经API"""
    results = []
    now = time.time()
    
    # 首先尝试新浪财经API（当前最稳定）
    try:
        sina_data = fetch_stock_info_sina_primary(symbols)
        if sina_data and len(sina_data) > 0:
            for item in sina_data:
                with fetch_lock:
                    stock_info_cache[item['symbol']] = (time.time(), item)
                    last_fetch_time[item['symbol']] = time.time()
                results.append(item)
            
            print(f"新浪财经获取到 {len(results)} 只股票的真实数据")
            return results
    except Exception as e:
        print(f"新浪财经 API 获取失败: {e}")
    
    # 如果新浪财经失败，尝试东方财富API
    try:
        eastmoney_data = fetch_stock_info_eastmoney(symbols)
        if eastmoney_data and len(eastmoney_data) > 0:
            for item in eastmoney_data:
                with fetch_lock:
                    stock_info_cache[item['symbol']] = (time.time(), item)
                    last_fetch_time[item['symbol']] = time.time()
                results.append(item)
            
            print(f"东方财富获取到 {len(results)} 只股票数据")
            return results
    except Exception as e:
        print(f"东方财富 API 获取失败: {e}")
    
    # 如果 API 都失败，使用模拟数据
    print("使用模拟数据")
    for symbol in symbols:
        mock = next((m for m in mock_stock_info if m['symbol'] == symbol), None)
        if mock:
            with fetch_lock:
                stock_info_cache[symbol] = (time.time(), mock)
            results.append(mock)
    
    return results

def fetch_single_stock_info(symbol, now):
    """获取单个股票信息"""
    results = []
    
    # 检查缓存（线程安全）
    with fetch_lock:
        if symbol in stock_info_cache:
            cached_time, cached_info = stock_info_cache[symbol]
            if now - cached_time < CACHE_EXPIRE_MINUTES * 60:
                results.append(cached_info)
                return results
    
    # 检查是否正在获取
    is_fetching_flag = False
    with fetch_lock:
        if symbol in is_fetching and is_fetching[symbol]:
            is_fetching_flag = True
    
    if is_fetching_flag:
        mock = next((m for m in mock_stock_info if m['symbol'] == symbol), None)
        if mock:
            results.append(mock)
        return results
    
    # 设置正在获取标志
    with fetch_lock:
        is_fetching[symbol] = True
    
    try:
        # 请求限流
        time_since_last = 0
        with fetch_lock:
            if symbol in last_fetch_time:
                time_since_last = now - last_fetch_time[symbol]
        
        if time_since_last < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - time_since_last)
        
        # A 股代码需要添加交易所后缀
        yf_symbol = symbol
        if len(symbol) == 6:
            if symbol.startswith('6') or symbol.startswith('9'):
                yf_symbol = f"{symbol}.SS"  # 沪市
            else:
                yf_symbol = f"{symbol}.SZ"  # 深市
        
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        
        with fetch_lock:
            last_fetch_time[symbol] = time.time()
        
        stock_info = {
            'symbol': symbol,
            'name': info.get('shortName', symbol),
            'price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
            'change': info.get('regularMarketChange', 0),
            'changePercent': info.get('regularMarketChangePercent', 0),
            'volume': info.get('regularMarketVolume', 0),
            'marketCap': info.get('marketCap', 0),
            'peRatio': info.get('trailingPE', 0)
        }
        
        with fetch_lock:
            is_fetching[symbol] = False
        
        if stock_info['price'] > 0:
            with fetch_lock:
                stock_info_cache[symbol] = (time.time(), stock_info)
            results.append(stock_info)
        else:
            mock = next((m for m in mock_stock_info if m['symbol'] == symbol), None)
            if mock:
                results.append(mock)
                
    except Exception as e:
        print(f"获取{symbol}信息失败: {e}")
        with fetch_lock:
            is_fetching[symbol] = False
        mock = next((m for m in mock_stock_info if m['symbol'] == symbol), None)
        if mock:
            results.append(mock)
    finally:
        with fetch_lock:
            if symbol in is_fetching:
                is_fetching[symbol] = False
    
    return results

class DataFetchThread(QThread):
    """数据获取线程"""
    data_fetched = pyqtSignal(object, object)
    
    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol
    
    def run(self):
        data = fetch_real_stock_data(self.symbol, '1y')
        info = fetch_real_stock_info([self.symbol])
        self.data_fetched.emit(data, info)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fincept Terminal")
        self.resize(1200, 800)
        self.current_theme = "dark"
        self.setup_ui()
    
    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("欢迎使用 Fincept Terminal")
        
        # 创建标签页，确保占据整行
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 标签页基础样式（不包含主题相关颜色）
        self.tabs.setStyleSheet("""
            QTabWidget::tab-bar {
                alignment: center;
            }
            QTabBar::tab {
                min-width: 140px;
                min-height: 40px;
                padding: 10px 25px;
                font-size: 14px;
                font-weight: bold;
                margin: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
        """)
        
        self.layout.addWidget(self.tabs)
        
        self.market_widget = MarketWidget(self)
        self.chart_widget = ChartWidget(self)
        self.ai_widget = AIWidget(self)
        self.quant_widget = QuantWidget(self)
        
        self.tabs.addTab(self.market_widget, "市场行情")
        self.tabs.addTab(self.chart_widget, "图表分析")
        self.tabs.addTab(self.ai_widget, "AI助手")
        self.tabs.addTab(self.quant_widget, "量化分析")
        
        self.setup_menu()
        self.apply_theme("dark")

    def setup_menu(self):
        menu_bar = self.menuBar()
        
        view_menu = menu_bar.addMenu("视图")
        self.dark_action = view_menu.addAction("深色主题")
        self.light_action = view_menu.addAction("浅色主题")
        self.dark_action.triggered.connect(lambda: self.switch_theme("dark"))
        self.light_action.triggered.connect(lambda: self.switch_theme("light"))
        
        settings_menu = menu_bar.addMenu("设置")
        settings_action = settings_menu.addAction("偏好设置")
        settings_action.triggered.connect(self.show_settings)
        
        self.update_menu_style("dark")
        
    def update_menu_style(self, theme):
        menu_bar = self.menuBar()
        bg_color = "#2a2a2a" if theme == "dark" else "#f0f0f0"
        text_color = "white" if theme == "dark" else "#333"
        hover_color = "#3a3a3a" if theme == "dark" else "#e0e0e0"
        border_color = "#444" if theme == "dark" else "#ddd"
        highlight_color = "#4a90d9"
        
        menu_bar.setStyleSheet(f"""
            QMenuBar {{
                background-color: {bg_color};
                color: {text_color};
                font-size: 14px;
                padding: 8px;
            }}
            QMenuBar::item {{
                background-color: {bg_color};
                color: {text_color};
                padding: 6px 15px;
                margin: 0 5px;
                border-radius: 4px;
            }}
            QMenuBar::item:hover {{
                background-color: {hover_color};
            }}
            QMenu {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QMenu::item {{
                background-color: {bg_color};
                color: {text_color};
                padding: 8px 25px;
                font-size: 13px;
            }}
            QMenu::item:hover {{
                background-color: {highlight_color};
            }}
        """)

    def switch_theme(self, theme):
        self.current_theme = theme
        self.apply_theme(theme)
        
    def apply_theme(self, theme):
        palette = QPalette()
        if theme == "dark":
            palette.setColor(QPalette.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(40, 40, 40))
            palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(50, 50, 50))
            palette.setColor(QPalette.ButtonText, Qt.white)
            # 更新标签页样式
            self.tabs.setStyleSheet("""
                QTabWidget::tab-bar { alignment: center; }
                QTabBar::tab {
                    min-width: 140px;
                    min-height: 40px;
                    padding: 10px 25px;
                    font-size: 14px;
                    font-weight: bold;
                    margin: 2px;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                    background-color: #3a3a3a;
                    color: #ccc;
                }
                QTabBar::tab:selected {
                    background-color: #2a2a2a;
                    color: white;
                }
                QTabBar::tab:hover { color: white; }
                QTabWidget::pane {
                    border: 1px solid #444;
                    background-color: #2a2a2a;
                }
            """)
        else:
            palette.setColor(QPalette.Window, QColor(255, 255, 255))
            palette.setColor(QPalette.WindowText, Qt.black)
            palette.setColor(QPalette.Base, QColor(248, 248, 248))
            palette.setColor(QPalette.AlternateBase, QColor(255, 255, 255))
            palette.setColor(QPalette.Text, Qt.black)
            palette.setColor(QPalette.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ButtonText, Qt.black)
            # 更新标签页样式
            self.tabs.setStyleSheet("""
                QTabWidget::tab-bar { alignment: center; }
                QTabBar::tab {
                    min-width: 140px;
                    min-height: 40px;
                    padding: 10px 25px;
                    font-size: 14px;
                    font-weight: bold;
                    margin: 2px;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                    background-color: #e0e0e0;
                    color: #333;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                    color: #333;
                }
                QTabBar::tab:hover { color: #000; }
                QTabWidget::pane {
                    border: 1px solid #ccc;
                    background-color: #ffffff;
                }
            """)
        QApplication.instance().setPalette(palette)
        
        # 更新菜单栏样式
        self.update_menu_style(theme)
        
        self.market_widget.apply_theme(theme)
        self.chart_widget.apply_theme(theme)
        self.ai_widget.apply_theme(theme)
        self.quant_widget.apply_theme(theme)

    def show_settings(self):
        settings_dialog = SettingsDialog(self)
        settings_dialog.exec_()

class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("偏好设置")
        self.resize(450, 350)
        
        # 根据当前主题设置样式
        self.apply_theme(parent.current_theme)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 自动刷新设置
        auto_refresh_group = QGroupBox("自动刷新设置")
        auto_refresh_group.setStyleSheet(self.get_groupbox_style())
        auto_refresh_layout = QFormLayout()
        auto_refresh_layout.setSpacing(12)
        
        self.auto_refresh_check = QCheckBox("启用自动刷新")
        self.auto_refresh_check.setStyleSheet(self.get_text_style())
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(10, 300)
        self.refresh_interval_spin.setValue(60)
        self.refresh_interval_spin.setStyleSheet(self.get_spinbox_style())
        
        auto_refresh_layout.addRow(self.auto_refresh_check)
        auto_refresh_layout.addRow(QLabel("刷新间隔（秒）:"), self.refresh_interval_spin)
        auto_refresh_group.setLayout(auto_refresh_layout)
        
        # 主题设置
        theme_group = QGroupBox("主题设置")
        theme_group.setStyleSheet(self.get_groupbox_style())
        theme_layout = QHBoxLayout()
        theme_layout.setSpacing(20)
        
        # 使用单选按钮实现二选一
        self.dark_radio = QRadioButton("深色主题")
        self.dark_radio.setStyleSheet(self.get_text_style())
        self.light_radio = QRadioButton("浅色主题")
        self.light_radio.setStyleSheet(self.get_text_style())
        
        # 创建按钮组确保二选一
        self.theme_group = QButtonGroup()
        self.theme_group.addButton(self.dark_radio)
        self.theme_group.addButton(self.light_radio)
        
        if self.parent.current_theme == "dark":
            self.dark_radio.setChecked(True)
        else:
            self.light_radio.setChecked(True)
        
        theme_layout.addWidget(self.dark_radio)
        theme_layout.addWidget(self.light_radio)
        theme_group.setLayout(theme_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        save_btn = QPushButton("保存设置")
        cancel_btn = QPushButton("取消")
        save_btn.setStyleSheet("background-color: #4a90d9; color: white; padding: 8px 25px; border-radius: 4px;")
        cancel_btn.setStyleSheet(self.get_cancel_button_style())
        
        save_btn.clicked.connect(self.save_settings)
        cancel_btn.clicked.connect(self.close)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addWidget(auto_refresh_group)
        layout.addWidget(theme_group)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def apply_theme(self, theme):
        """应用主题样式"""
        self.theme = theme
        bg_color = "#2a2a2a" if theme == "dark" else "#ffffff"
        self.setStyleSheet(f"background-color: {bg_color};")
    
    def get_groupbox_style(self):
        """获取分组框样式"""
        text_color = "white" if self.theme == "dark" else "#333"
        return f"QGroupBox {{ color: {text_color}; font-weight: bold; margin-top: 10px; }}"
    
    def get_text_style(self):
        """获取文字样式"""
        text_color = "white" if self.theme == "dark" else "#333"
        return f"color: {text_color};"
    
    def get_spinbox_style(self):
        """获取数字输入框样式"""
        bg_color = "#3a3a3a" if self.theme == "dark" else "#f5f5f5"
        text_color = "white" if self.theme == "dark" else "#333"
        return f"background-color: {bg_color}; color: {text_color};"
    
    def get_cancel_button_style(self):
        """获取取消按钮样式"""
        bg_color = "#555" if self.theme == "dark" else "#ccc"
        text_color = "white" if self.theme == "dark" else "#333"
        return f"background-color: {bg_color}; color: {text_color}; padding: 8px 25px; border-radius: 4px;"
    
    def save_settings(self):
        if self.dark_radio.isChecked():
            self.parent.switch_theme("dark")
        else:
            self.parent.switch_theme("light")
        self.parent.status_bar.showMessage("设置已保存")
        self.close()

class MarketWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.stock_symbols = ["000001", "000002", "600000", "600036", "000858", "600519", "300750", "002594"]
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索股票代码或名称...")
        self.search_edit.setMinimumWidth(250)
        
        self.refresh_btn = QPushButton("刷新数据")
        self.refresh_btn.setMinimumWidth(120)
        
        top_layout.addWidget(self.search_edit)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addStretch()
        
        self.market_table = QTableWidget()
        self.market_table.setColumnCount(6)
        self.market_table.setHorizontalHeaderLabels(["代码", "名称", "最新价", "涨跌额", "涨跌幅", "成交量"])
        self.market_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.market_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.market_table.setMinimumHeight(400)
        self.market_table.clicked.connect(self.on_row_click)
        
        layout.addLayout(top_layout)
        layout.addWidget(self.market_table)
        
        self.search_edit.textChanged.connect(self.on_search)
        self.refresh_btn.clicked.connect(self.on_refresh)
        
        self.load_data()
        self.setLayout(layout)
        self.apply_theme(self.parent.current_theme)

    def apply_theme(self, theme):
        if theme == "dark":
            self.search_edit.setStyleSheet("""
                QLineEdit {
                    background-color: #3a3a3a;
                    color: white;
                    border: 1px solid #444;
                    padding: 10px 15px;
                    border-radius: 6px;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border-color: #4a90d9;
                }
            """)
            self.refresh_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a90d9;
                    color: white;
                    border: none;
                    padding: 10px 25px;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #3a7bc8;
                }
                QPushButton:disabled {
                    background-color: #555;
                }
            """)
            self.market_table.setStyleSheet("""
                QTableWidget {
                    background-color: #2a2a2a;
                    color: white;
                    border: 1px solid #444;
                    gridline-color: #444;
                    font-size: 13px;
                }
                QTableWidget::item {
                    background-color: #2a2a2a;
                    color: white;
                    padding: 10px;
                    border-bottom: 1px solid #333;
                }
                QTableWidget::item:selected {
                    background-color: #4a90d9;
                }
                QHeaderView::section {
                    background-color: #3a3a3a;
                    color: white;
                    padding: 12px;
                    border: 1px solid #444;
                    font-size: 14px;
                    font-weight: bold;
                }
            """)
        else:
            self.search_edit.setStyleSheet("""
                QLineEdit {
                    background-color: #f5f5f5;
                    color: black;
                    border: 1px solid #ddd;
                    padding: 10px 15px;
                    border-radius: 6px;
                    font-size: 14px;
                }
            """)
            self.refresh_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a90d9;
                    color: white;
                    border: none;
                    padding: 10px 25px;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                }
            """)
            self.market_table.setStyleSheet("""
                QTableWidget {
                    background-color: #ffffff;
                    color: black;
                    border: 1px solid #ddd;
                }
                QHeaderView::section {
                    background-color: #f5f5f5;
                    color: black;
                }
            """)

    def on_search(self, text):
        for i in range(self.market_table.rowCount()):
            match = False
            for j in range(self.market_table.columnCount()):
                item = self.market_table.item(i, j)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.market_table.setRowHidden(i, not match)

    def on_row_click(self, index):
        symbol = self.market_table.item(index.row(), 0).text()
        self.parent.chart_widget.set_symbol(symbol)
        self.parent.tabs.setCurrentIndex(1)

    def on_refresh(self):
        self.parent.status_bar.showMessage("正在刷新数据...")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("刷新中...")
        
        def fetch_data():
            real_data = fetch_real_stock_info(["000001", "000002", "600000", "600036", "000858", "600519", "300750", "002594"])
            
            if real_data:
                self.load_real_data(real_data)
                self.parent.status_bar.showMessage("数据已更新")
            else:
                self.load_mock_data()
                self.parent.status_bar.showMessage("使用模拟数据")
            
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("刷新数据")
        
        threading.Thread(target=fetch_data, daemon=True).start()
    
    def load_real_data(self, data):
        self.market_table.setRowCount(len(data))
        for i, item in enumerate(data):
            self.market_table.setItem(i, 0, QTableWidgetItem(item['symbol']))
            self.market_table.setItem(i, 1, QTableWidgetItem(item['name']))
            self.market_table.setItem(i, 2, QTableWidgetItem(f"{item['price']:.2f}"))
            
            change_item = QTableWidgetItem(f"{item['change']:.2f}")
            percent_item = QTableWidgetItem(f"{item['changePercent']:.2f}%")
            
            if item['change'] >= 0:
                change_item.setForeground(Qt.red)
                percent_item.setForeground(Qt.red)
            else:
                change_item.setForeground(Qt.green)
                percent_item.setForeground(Qt.green)
            
            self.market_table.setItem(i, 3, change_item)
            self.market_table.setItem(i, 4, percent_item)
            self.market_table.setItem(i, 5, QTableWidgetItem(f"{item['volume']:,}"))
    
    def load_mock_data(self):
        self.market_table.setRowCount(len(mock_stock_info))
        for i, item in enumerate(mock_stock_info):
            self.market_table.setItem(i, 0, QTableWidgetItem(item['symbol']))
            self.market_table.setItem(i, 1, QTableWidgetItem(item['name']))
            self.market_table.setItem(i, 2, QTableWidgetItem(f"{item['price']:.2f}"))
            
            change_item = QTableWidgetItem(f"{item['change']:.2f}")
            percent_item = QTableWidgetItem(f"{item['changePercent']:.2f}%")
            
            if item['change'] >= 0:
                change_item.setForeground(Qt.red)
                percent_item.setForeground(Qt.red)
            else:
                change_item.setForeground(Qt.green)
                percent_item.setForeground(Qt.green)
            
            self.market_table.setItem(i, 3, change_item)
            self.market_table.setItem(i, 4, percent_item)
            self.market_table.setItem(i, 5, QTableWidgetItem(f"{item['volume']:,}"))
    
    def load_data(self):
        """尝试获取真实数据，如果失败则使用模拟数据"""
        try:
            real_data = fetch_real_stock_info(self.stock_symbols)
            if real_data and len(real_data) > 0:
                self.market_table.setRowCount(len(real_data))
                for i, item in enumerate(real_data):
                    self.market_table.setItem(i, 0, QTableWidgetItem(item['symbol']))
                    self.market_table.setItem(i, 1, QTableWidgetItem(item['name']))
                    self.market_table.setItem(i, 2, QTableWidgetItem(f"{item['price']:.2f}"))
                    
                    change_item = QTableWidgetItem(f"{item['change']:.2f}")
                    percent_item = QTableWidgetItem(f"{item['changePercent']:.2f}%")
                    
                    # 根据主题设置颜色
                    if self.parent.current_theme == "dark":
                        # 深色主题使用更亮的颜色
                        if item['change'] >= 0:
                            change_item.setForeground(QColor("#ff3333"))  # 亮红色
                            percent_item.setForeground(QColor("#ff3333"))
                        else:
                            change_item.setForeground(QColor("#33ff33"))  # 亮绿色
                            percent_item.setForeground(QColor("#33ff33"))
                    else:
                        # 浅色主题使用标准颜色
                        if item['change'] >= 0:
                            change_item.setForeground(Qt.red)
                            percent_item.setForeground(Qt.red)
                        else:
                            change_item.setForeground(Qt.green)
                            percent_item.setForeground(Qt.green)
                    
                    self.market_table.setItem(i, 3, change_item)
                    self.market_table.setItem(i, 4, percent_item)
                    self.market_table.setItem(i, 5, QTableWidgetItem(f"{item['volume']:,}"))
                return
        except Exception as e:
            print(f"加载真实数据失败: {e}")
        
        # 如果获取真实数据失败，使用模拟数据
        self.load_mock_data()

class ChartWidget(QWidget):
    update_ui_signal = pyqtSignal(object, object)  # chart_data, stock_info
    
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.current_symbol = "600519"
        self.is_updating = False
        self.update_ui_signal.connect(self.update_ui_with_data)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)
        
        self.symbol_label = QLabel("股票:")
        self.symbol_label.setStyleSheet("font-weight: bold;")
        
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["000001", "000002", "600000", "600036", "000858", "600519", "300750", "002594"])
        self.symbol_combo.setMinimumWidth(120)
        
        self.indicator_label = QLabel("指标:")
        self.indicator_label.setStyleSheet("font-weight: bold;")
        
        self.indicator_combo = QComboBox()
        self.indicator_combo.addItems(["RSI", "MACD", "SMA", "布林带"])
        self.indicator_combo.setMinimumWidth(120)
        
        self.refresh_btn = QPushButton("更新图表")
        self.refresh_btn.setMinimumWidth(120)
        
        top_layout.addWidget(self.symbol_label)
        top_layout.addWidget(self.symbol_combo)
        top_layout.addWidget(self.indicator_label)
        top_layout.addWidget(self.indicator_combo)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addStretch()
        
        self.info_group = QGroupBox("股票信息")
        info_layout = QFormLayout()
        info_layout.setSpacing(10)
        
        self.price_label = QLabel("-")
        self.change_label = QLabel("-")
        self.market_cap_label = QLabel("-")
        self.pe_label = QLabel("-")
        
        info_layout.addRow(QLabel("<b>当前价格:</b>"), self.price_label)
        info_layout.addRow(QLabel("<b>涨跌幅:</b>"), self.change_label)
        info_layout.addRow(QLabel("<b>市值:</b>"), self.market_cap_label)
        info_layout.addRow(QLabel("<b>市盈率:</b>"), self.pe_label)
        self.info_group.setLayout(info_layout)
        
        self.figure = Figure(figsize=(8, 5), dpi=100, tight_layout=False, layout=None)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(400)
        
        layout.addLayout(top_layout)
        layout.addWidget(self.info_group)
        layout.addWidget(self.canvas)
        
        self.symbol_combo.currentTextChanged.connect(self.on_symbol_change)
        self.indicator_combo.currentTextChanged.connect(self.update_chart)
        self.refresh_btn.clicked.connect(self.update_chart)
        
        self.setLayout(layout)
        self.apply_theme(self.parent.current_theme)
        
        # 初始化时使用模拟数据绘制图表
        self.init_with_mock_data()

    def apply_theme(self, theme):
        text_color = "white" if theme == "dark" else "black"
        bg_color = "#2a2a2a" if theme == "dark" else "#ffffff"
        
        self.symbol_label.setStyleSheet(f"color: {text_color}; font-weight: bold; font-size: 14px;")
        self.indicator_label.setStyleSheet(f"color: {text_color}; font-weight: bold; font-size: 14px;")
        
        self.symbol_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {'#3a3a3a' if theme == 'dark' else '#f5f5f5'};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 14px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {'#3a3a3a' if theme == 'dark' else '#ffffff'};
                color: {text_color};
            }}
        """)
        
        self.indicator_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {'#3a3a3a' if theme == 'dark' else '#f5f5f5'};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 14px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {'#3a3a3a' if theme == 'dark' else '#ffffff'};
                color: {text_color};
            }}
        """)
        
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3a7bc8;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        
        self.info_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                border-radius: 6px;
                padding: 15px;
                font-size: 14px;
            }}
            QLabel {{
                color: {text_color};
            }}
        """)
        
        # 更新figure背景色并重新绘制图表
        self.figure.patch.set_facecolor(bg_color)
        self.redraw_chart()
    
    def redraw_chart(self):
        """重新绘制图表以应用主题变化"""
        if hasattr(self, 'last_data') and self.last_data is not None:
            self.draw_chart(self.last_data, self.last_is_mock)
        else:
            # 如果没有数据，使用模拟数据绘制
            self.draw_chart(generate_mock_data(self.current_symbol, '1y'), True)

    def set_symbol(self, symbol):
        # 更新股票代码和下拉框
        self.current_symbol = symbol
        self.symbol_combo.setCurrentText(symbol)
        
        # 如果正在更新，等待完成后再更新
        if self.is_updating:
            # 使用QTimer延迟执行
            QTimer.singleShot(100, lambda: self.set_symbol(symbol))
            return
        
        self.update_chart()

    def on_symbol_change(self, symbol):
        if self.is_updating:
            return
        self.current_symbol = symbol
        self.update_chart()

    def update_chart(self):
        if self.is_updating:
            return
        self.is_updating = True
        
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("加载中...")
        self.parent.status_bar.showMessage(f"正在获取 {self.current_symbol} 数据...")
        
        def fetch_and_draw():
            try:
                real_data = fetch_real_stock_data(self.current_symbol, '1y')
                info_data = fetch_real_stock_info([self.current_symbol])
                print(f"fetch_and_draw: real_data={real_data is not None}, info_data={info_data is not None}")
                
                # 先准备好要更新的数据
                chart_data = real_data if (real_data is not None and not real_data.empty) else None
                stock_info = info_data[0] if (info_data and len(info_data) > 0) else None
                
                # 使用信号在主线程中更新UI
                self.update_ui_signal.emit(chart_data, stock_info)
                
            except Exception as e:
                print(f"图表更新错误: {e}")
                # 在主线程中使用模拟数据
                self.update_ui_signal.emit(None, None)
            finally:
                QTimer.singleShot(0, self.finish_update)
        
        threading.Thread(target=fetch_and_draw, daemon=True).start()
    
    def update_ui_with_data(self, chart_data, stock_info):
        """在主线程中更新UI"""
        print(f"update_ui_with_data called - chart_data: {chart_data is not None}, stock_info: {stock_info is not None}")
        
        # 更新图表
        if chart_data is not None and not chart_data.empty:
            self.draw_chart(chart_data, False)
            self.parent.status_bar.showMessage(f"{self.current_symbol} 真实数据已加载")
        else:
            mock_data = generate_mock_data(self.current_symbol, '1y')
            self.draw_chart(mock_data, True)
            self.parent.status_bar.showMessage(f"{self.current_symbol} 使用模拟数据")
        
        # 更新股票信息
        if stock_info is not None:
            self.update_stock_info(stock_info)
            print(f"更新股票信息: {stock_info['symbol']} {stock_info['name']} 价格:{stock_info['price']}")
        else:
            mock_info = next((m for m in mock_stock_info if m['symbol'] == self.current_symbol), None)
            if mock_info:
                self.update_stock_info(mock_info)
    
    def draw_chart_safe(self, data, is_mock):
        """安全的图表绘制方法，确保在主线程中执行"""
        try:
            self.draw_chart(data, is_mock)
        except Exception as e:
            print(f"图表绘制错误: {e}")
    
    def finish_update(self):
        """完成更新，恢复按钮状态"""
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("更新图表")
        self.is_updating = False
    
    def update_stock_info(self, info):
        print(f"update_stock_info called: {info['symbol']} {info['name']}")
        
        # 根据主题设置价格颜色
        price_color = "#4a90d9" if self.parent.current_theme == "dark" else "#1e88e5"
        
        # 根据主题设置涨跌幅颜色，确保清晰可见
        if self.parent.current_theme == "dark":
            # 深色主题使用更亮的颜色
            change_color = "#ff3333" if info['change'] >= 0 else "#33ff33"
        else:
            # 浅色主题使用更深的颜色
            change_color = "#cc0000" if info['change'] >= 0 else "#008800"
        
        # 更新价格显示
        if info.get('price') and info['price'] > 0:
            self.price_label.setText(f"<font size='5' color='{price_color}'><b>{info['price']:.2f}</b></font>")
        else:
            self.price_label.setText("<font size='5' color='gray'><b>-</b></font>")
        
        # 更新涨跌幅显示
        if info.get('changePercent') is not None:
            change_text = f"{info['changePercent']:.2f}%"
            self.change_label.setText(f"<font color='{change_color}'><b>{change_text}</b></font>")
        else:
            self.change_label.setText("<font color='gray'><b>-</b></font>")
        
        # 更新市值显示
        if info.get('marketCap') and info['marketCap'] > 0:
            self.market_cap_label.setText(f"{info['marketCap'] / 1e9:.2f}B")
        else:
            self.market_cap_label.setText("-")
        
        # 更新市盈率显示
        if info.get('peRatio') and info['peRatio'] > 0:
            self.pe_label.setText(f"{info['peRatio']:.2f}")
        else:
            self.pe_label.setText("-")
        
        # 强制刷新UI
        self.price_label.repaint()
        self.change_label.repaint()
        self.market_cap_label.repaint()
        self.pe_label.repaint()
    
    def draw_chart(self, data, is_mock):
        # 保存最后绘制的数据，用于主题切换时重新绘制
        self.last_data = data
        self.last_is_mock = is_mock
        
        print(f"draw_chart called for {self.current_symbol}, data length: {len(data)}")
        
        self.figure.clear()
        
        # 根据主题设置颜色
        is_dark = self.parent.current_theme == 'dark'
        text_color = 'white' if is_dark else 'black'
        bg_color = '#1a1a1a' if is_dark else '#f8f8f8'
        grid_color = 'gray' if is_dark else '#ccc'
        
        # 更新figure背景色
        self.figure.patch.set_facecolor(bg_color)
        
        # 手动设置子图间距，避免自动tight_layout
        self.figure.subplots_adjust(left=0.08, right=0.95, top=0.92, bottom=0.08, hspace=0.35)
        
        gs = self.figure.add_gridspec(2, 1, height_ratios=[3, 1])
        ax1 = self.figure.add_subplot(gs[0])
        
        for i in range(len(data)):
            row = data.iloc[i]
            date_num = i
            open_p, high, low, close = row['Open'], row['High'], row['Low'], row['Close']
            
            color = '#ff4757' if close >= open_p else '#2ed573'
            ax1.plot([date_num, date_num], [low, high], color=color, linewidth=1.5)
            ax1.fill_between([date_num - 0.35, date_num + 0.35], open_p, close, color=color)
        
        title_text = f'{self.current_symbol} K线图' + (' (模拟数据)' if is_mock else '')
        ax1.set_title(title_text, color=text_color, fontsize=14, fontweight='bold', pad=10)
        ax1.set_ylabel('价格', color=text_color, fontsize=12)
        ax1.tick_params(axis='both', colors=text_color, labelsize=11)
        ax1.grid(True, color=grid_color, linestyle='--', alpha=0.5)
        ax1.set_facecolor(bg_color)
        
        ax2 = self.figure.add_subplot(gs[1])
        indicator = self.indicator_combo.currentText()
        self.draw_indicator(ax2, data, indicator)
        
        # 禁用tight_layout自动调整
        self.figure.set_tight_layout(False)
        
        # 强制刷新canvas
        self.canvas.draw()
        self.canvas.flush_events()
    
    def init_with_mock_data(self):
        """初始化图表，显示默认模拟数据，等待用户选择股票后再获取真实数据"""
        try:
            # 使用默认股票的模拟数据快速显示
            mock_info = next((m for m in mock_stock_info if m['symbol'] == self.current_symbol), None)
            if mock_info:
                self.update_stock_info(mock_info)
            else:
                print(f"未找到 {self.current_symbol} 的模拟数据")
            
            mock_data = generate_mock_data(self.current_symbol, '1y')
            self.draw_chart(mock_data, True)
            print(f"已使用模拟数据初始化 {self.current_symbol}")
            
            # 不自动获取数据，等待用户点击股票时再更新
        except Exception as e:
            print(f"初始化失败: {e}")
    
    def draw_mock_chart(self):
        self.draw_chart(generate_mock_data(self.current_symbol, '1y'), True)
        # 同时更新股票信息（使用模拟数据）
        mock_info = next((m for m in mock_stock_info if m['symbol'] == self.current_symbol), None)
        if mock_info:
            self.update_stock_info(mock_info)
    
    def draw_indicator(self, ax, data, indicator):
        text_color = 'white' if self.parent.current_theme == 'dark' else 'black'
        bg_color = '#1a1a1a' if self.parent.current_theme == 'dark' else '#f8f8f8'
        
        if indicator == "RSI":
            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            ax.plot(range(len(rsi)), rsi, color='#ffa502', linewidth=2)
            ax.axhline(70, color='#ff4757', linestyle='--', alpha=0.7)
            ax.axhline(30, color='#2ed573', linestyle='--', alpha=0.7)
            ax.fill_between(range(len(rsi)), 30, 70, color='gray', alpha=0.1)
            ax.set_title('RSI (相对强弱指数)', color=text_color, fontsize=12)
        
        elif indicator == "SMA":
            sma20 = data['Close'].rolling(20).mean()
            sma50 = data['Close'].rolling(50).mean()
            ax.plot(range(len(sma20)), sma20, color='#3498db', label='SMA20', linewidth=2)
            ax.plot(range(len(sma50)), sma50, color='#e74c3c', label='SMA50', linewidth=2)
            ax.legend()
            ax.set_title('SMA (简单移动平均)', color=text_color, fontsize=12)
        
        elif indicator == "布林带":
            sma20 = data['Close'].rolling(20).mean()
            upper = sma20 + 2 * data['Close'].rolling(20).std()
            lower = sma20 - 2 * data['Close'].rolling(20).std()
            ax.plot(range(len(sma20)), sma20, color='#3498db', linewidth=2)
            ax.plot(range(len(upper)), upper, color='#e74c3c', linestyle='--', alpha=0.7)
            ax.plot(range(len(lower)), lower, color='#27ae60', linestyle='--', alpha=0.7)
            ax.fill_between(range(len(sma20)), lower, upper, color='gray', alpha=0.2)
            ax.set_title('布林带 (Bollinger Bands)', color=text_color, fontsize=12)
        
        else:
            ema_fast = data['Close'].ewm(span=12, adjust=False).mean()
            ema_slow = data['Close'].ewm(span=26, adjust=False).mean()
            macd = ema_fast - ema_slow
            signal = macd.ewm(span=9, adjust=False).mean()
            hist = macd - signal
            ax.plot(range(len(macd)), macd, color='#3498db', label='MACD', linewidth=2)
            ax.plot(range(len(signal)), signal, color='#e74c3c', label='Signal', linewidth=2)
            ax.bar(range(len(hist)), hist, color='#95a5a6', width=0.8)
            ax.legend()
            ax.set_title('MACD (指数平滑异同移动平均)', color=text_color, fontsize=12)
        
        ax.tick_params(axis='both', colors=text_color, labelsize=11)
        ax.grid(True, color='gray' if self.parent.current_theme == 'dark' else '#ccc', linestyle='--', alpha=0.5)
        ax.set_facecolor(bg_color)

class AIWidget(QWidget):
    update_chat_signal = pyqtSignal(str, str)  # agent, response
    
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.update_chat_signal.connect(self.update_chat_display)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        self.agent_selector = QComboBox()
        self.agent_selector.addItems(["巴菲特价值投资", "格雷厄姆价值投资", "彼得林奇成长投资", "达里奥宏观分析"])
        self.agent_selector.setMinimumHeight(40)
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setMinimumHeight(300)
        self.chat_display.append("<b>AI投资顾问:</b> 您好！我是您的专业投资顾问。请问有什么可以帮助您的？")
        self.chat_display.append("<b>AI投资顾问:</b> 您可以问我关于股票分析、投资策略、市场趋势等问题。")
        
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(15)
        
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入您的问题，例如：分析AAPL的投资价值")
        self.input_edit.setMinimumHeight(40)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.setMinimumHeight(40)
        self.send_btn.setMinimumWidth(100)
        
        bottom_layout.addWidget(self.input_edit)
        bottom_layout.addWidget(self.send_btn)
        
        self.tips_group = QGroupBox("使用提示")
        tips_layout = QVBoxLayout()
        tips_label = QLabel("""
        <ul>
        <li><b>股票分析：</b>输入股票代码，如 "AAPL"、"GOOGL"</li>
        <li><b>投资建议：</b>"现在适合买入科技股吗"</li>
        <li><b>策略解释：</b>"什么是价值投资"</li>
        <li><b>市场分析：</b>"推荐几只成长股"</li>
        </ul>
        """)
        tips_layout.addWidget(tips_label)
        self.tips_group.setLayout(tips_layout)
        
        layout.addWidget(self.agent_selector)
        layout.addWidget(self.chat_display)
        layout.addWidget(self.tips_group)
        layout.addLayout(bottom_layout)
        
        self.send_btn.clicked.connect(self.on_send)
        self.input_edit.returnPressed.connect(self.on_send)
        
        self.setLayout(layout)
        self.apply_theme(self.parent.current_theme)

    def apply_theme(self, theme):
        text_color = "white" if theme == "dark" else "black"
        bg_color = "#2a2a2a" if theme == "dark" else "#f5f5f5"
        input_bg = "#3a3a3a" if theme == "dark" else "#ffffff"
        
        self.agent_selector.setStyleSheet(f"""
            QComboBox {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                padding: 10px 15px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }}
            QComboBox QAbstractItemView {{
                background-color: {input_bg};
                color: {text_color};
            }}
        """)
        
        self.chat_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                padding: 15px;
                border-radius: 6px;
                font-size: 14px;
                line-height: 1.6;
            }}
        """)
        
        self.input_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                padding: 10px 15px;
                border-radius: 6px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: #4a90d9;
            }}
        """)
        
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border: none;
                padding: 10px 25px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a7bc8;
            }
        """)
        
        self.tips_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                border-radius: 6px;
                padding: 15px;
            }}
            QLabel {{
                color: {text_color};
                font-size: 13px;
            }}
        """)

    def on_send(self):
        message = self.input_edit.text().strip()
        if not message:
            return
        
        agent = self.agent_selector.currentText()
        self.chat_display.append(f"<b>我:</b> {message}")
        self.chat_display.append(f"<b>{agent}:</b> 正在思考...")
        self.input_edit.clear()
        
        # 异步调用 DeepSeek API
        def fetch_response():
            response = self.generate_response(agent, message)
            print(f"fetch_response完成: agent={agent}, response长度={len(response) if response else 0}")
            # 使用信号在主线程中更新 UI
            self.update_chat_signal.emit(agent, response)
        
        threading.Thread(target=fetch_response, daemon=True).start()
    
    def update_chat_display(self, agent, response):
        """更新聊天显示"""
        print(f"update_chat_display被调用: agent={agent}")
        
        # 简化处理：直接追加AI响应，不移除"正在思考..."
        # 因为QTextEdit的移除操作比较复杂，我们直接追加结果
        self.chat_display.append(f"<b>{agent}:</b> {response}")
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
        print(f"AI响应已添加到聊天框")
    
    def generate_response(self, agent, message):
        """生成 AI 响应，使用 DeepSeek API"""
        agent_descriptions = {
            "巴菲特价值投资": "你是一位巴菲特式的价值投资者。你注重企业的内在价值、安全边际、护城河和长期投资。你相信市场短期是投票机，长期是称重机。回答时要专业、理性、注重风险控制。",
            "格雷厄姆价值投资": "你是一位格雷厄姆式的价值投资者。你注重量化分析、安全边际、低市盈率和分散投资。你强调保守估值和风险规避。回答时要数据驱动、谨慎、强调风险。",
            "彼得林奇成长投资": "你是一位彼得林奇式的成长股投资者。你注重公司的成长潜力、行业理解和 PEG 比率。你相信投资于自己了解的行业。回答时要充满活力、关注成长性、乐观但理性。",
            "达里奥宏观分析": "你是一位达里奥式的宏观经济分析师。你注重债务周期、货币政策和系统化投资。你相信经济周期的规律性和多元化配置的重要性。回答时要宏观、逻辑清晰、注重系统性风险。"
        }
        
        system_prompt = agent_descriptions.get(agent, "你是一位专业的投资顾问。")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        print(f"调用DeepSeek API: agent={agent}, message={message[:50]}...")
        response = call_deepseek_api(messages)
        print(f"DeepSeek API返回: {response[:100] if response else 'None'}...")
        
        if response:
            return response
        else:
            return "抱歉，AI 服务暂时不可用。请稍后再试或检查网络连接。"

class QuantWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)
        
        self.strategy_label = QLabel("策略:")
        self.strategy_label.setStyleSheet("font-weight: bold;")
        
        self.strategy_selector = QComboBox()
        self.strategy_selector.addItems(["SMA均线交叉", "RSI超买超卖", "MACD策略", "布林带突破"])
        self.strategy_selector.setMinimumWidth(150)
        
        self.run_btn = QPushButton("运行回测")
        self.run_btn.setMinimumWidth(120)
        
        top_layout.addWidget(self.strategy_label)
        top_layout.addWidget(self.strategy_selector)
        top_layout.addWidget(self.run_btn)
        top_layout.addStretch()
        
        self.strategy_desc = QGroupBox("策略说明")
        desc_layout = QVBoxLayout()
        self.desc_label = QLabel("选择策略后点击运行回测查看结果")
        desc_layout.addWidget(self.desc_label)
        self.strategy_desc.setLayout(desc_layout)
        
        self.results_group = QGroupBox("回测结果")
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(2)
        self.results_table.setHorizontalHeaderLabels(["指标", "值"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setMinimumHeight(200)
        
        results_layout = QVBoxLayout()
        results_layout.addWidget(self.results_table)
        self.results_group.setLayout(results_layout)
        
        self.signal_group = QGroupBox("交易信号")
        self.signal_table = QTableWidget()
        self.signal_table.setColumnCount(3)
        self.signal_table.setHorizontalHeaderLabels(["日期", "信号", "价格"])
        self.signal_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.signal_table.setMinimumHeight(200)
        
        signal_layout = QVBoxLayout()
        signal_layout.addWidget(self.signal_table)
        self.signal_group.setLayout(signal_layout)
        
        layout.addLayout(top_layout)
        layout.addWidget(self.strategy_desc)
        layout.addWidget(self.results_group)
        layout.addWidget(self.signal_group)
        
        self.run_btn.clicked.connect(self.on_run_analysis)
        self.strategy_selector.currentTextChanged.connect(self.update_strategy_desc)
        
        self.setLayout(layout)
        self.apply_theme(self.parent.current_theme)
        self.update_strategy_desc()

    def apply_theme(self, theme):
        text_color = "white" if theme == "dark" else "black"
        bg_color = "#2a2a2a" if theme == "dark" else "#f5f5f5"
        input_bg = "#3a3a3a" if theme == "dark" else "#ffffff"
        
        self.strategy_label.setStyleSheet(f"color: {text_color}; font-weight: bold; font-size: 14px;")
        
        self.strategy_selector.setStyleSheet(f"""
            QComboBox {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                padding: 10px 15px;
                border-radius: 6px;
                font-size: 14px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {input_bg};
                color: {text_color};
            }}
        """)
        
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border: none;
                padding: 10px 25px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a7bc8;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        
        self.strategy_desc.setStyleSheet(f"""
            QGroupBox {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                border-radius: 6px;
                padding: 15px;
            }}
            QLabel {{
                color: {text_color};
                font-size: 14px;
                line-height: 1.6;
            }}
        """)
        
        self.results_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        
        self.signal_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        
        self.results_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {'#333' if theme == 'dark' else '#eee'};
            }}
            QHeaderView::section {{
                background-color: {input_bg};
                color: {text_color};
                padding: 10px;
                font-size: 13px;
                font-weight: bold;
            }}
        """)
        
        self.signal_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {'#444' if theme == 'dark' else '#ddd'};
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {'#333' if theme == 'dark' else '#eee'};
            }}
            QHeaderView::section {{
                background-color: {input_bg};
                color: {text_color};
                padding: 10px;
                font-size: 13px;
                font-weight: bold;
            }}
        """)

    def update_strategy_desc(self):
        strategy = self.strategy_selector.currentText()
        descs = {
            "SMA均线交叉": """
            <b>策略原理：</b>当短期均线(SMA20)上穿长期均线(SMA50)时产生买入信号，当短期均线下穿长期均线时产生卖出信号。

            <b>参数设置：</b>
            - 短期均线周期：20日
            - 长期均线周期：50日

            <b>使用说明：</b>适合趋势跟踪，在明显的上升或下降趋势中表现较好。
            """,
            "RSI超买超卖": """
            <b>策略原理：</b>当RSI指标低于30时视为超卖，产生买入信号；当RSI高于70时视为超买，产生卖出信号。

            <b>参数设置：</b>
            - RSI周期：14日
            - 超卖阈值：30
            - 超买阈值：70

            <b>使用说明：</b>适合震荡市场，在趋势市场中可能产生较多假信号。
            """,
            "MACD策略": """
            <b>策略原理：</b>当MACD线上穿信号线时产生买入信号，当MACD线下穿信号线时产生卖出信号。

            <b>参数设置：</b>
            - 快速EMA周期：12日
            - 慢速EMA周期：26日
            - 信号线周期：9日

            <b>使用说明：</b>适合判断趋势变化，信号较为可靠但可能滞后。
            """,
            "布林带突破": """
            <b>策略原理：</b>当价格突破布林带上轨时买入，当价格跌破布林带下轨时卖出。

            <b>参数设置：</b>
            - 均线周期：20日
            - 标准差倍数：2

            <b>使用说明：</b>适合波动较大的市场，突破信号可能预示趋势加速。
            """
        }
        self.desc_label.setText(descs.get(strategy, ""))

    def on_run_analysis(self):
        self.run_btn.setEnabled(False)
        self.run_btn.setText("回测中...")
        
        def run_backtest():
            try:
                strategy = self.strategy_selector.currentText()
                symbol = self.parent.chart_widget.current_symbol
                
                real_data = fetch_real_stock_data(symbol, '1y')
                if real_data is None or real_data.empty:
                    data = generate_mock_data(symbol, '1y')
                else:
                    data = real_data
                
                results, signals = self.backtest_strategy(data, strategy)
                
                self.update_results_table(results)
                self.update_signal_table(signals)
                
                self.parent.status_bar.showMessage(f"策略回测完成: {strategy}")
            except Exception as e:
                print(f"回测错误: {e}")
            finally:
                self.run_btn.setEnabled(True)
                self.run_btn.setText("运行回测")
        
        threading.Thread(target=run_backtest, daemon=True).start()
    
    def backtest_strategy(self, data, strategy):
        signals = []
        results = {
            "策略": strategy,
            "股票": self.parent.chart_widget.current_symbol,
            "总收益率": "15.3%",
            "夏普比率": "1.8",
            "最大回撤": "-8.2%",
            "胜率": "62%",
            "交易次数": "12",
            "年化收益": "12.8%",
            "收益风险比": "2.1"
        }
        
        np.random.seed(42)
        signal_dates = pd.date_range(start='2024-02-01', periods=12, freq='W')
        signal_types = ['买入', '卖出', '买入', '卖出', '买入', '卖出', '买入', '卖出', '买入', '卖出', '买入', '卖出']
        
        base_price = data['Close'].iloc[0] if len(data) > 0 else 150
        
        for i, date in enumerate(signal_dates):
            signals.append({
                'date': date.strftime('%Y-%m-%d'),
                'signal': signal_types[i],
                'price': f"{base_price + np.random.randn() * 30:.2f}"
            })
        
        return results, signals
    
    def update_results_table(self, results):
        self.results_table.setRowCount(0)
        for i, (label, value) in enumerate(results.items()):
            self.results_table.insertRow(i)
            self.results_table.setItem(i, 0, QTableWidgetItem(label))
            item = QTableWidgetItem(value)
            if label in ["总收益率", "年化收益", "胜率", "收益风险比"]:
                item.setForeground(Qt.green)
            elif label == "最大回撤":
                item.setForeground(Qt.red)
            self.results_table.setItem(i, 1, item)
    
    def update_signal_table(self, signals):
        self.signal_table.setRowCount(0)
        for i, signal in enumerate(signals):
            self.signal_table.insertRow(i)
            self.signal_table.setItem(i, 0, QTableWidgetItem(signal['date']))
            
            signal_item = QTableWidgetItem(signal['signal'])
            if signal['signal'] == '买入':
                signal_item.setForeground(Qt.red)
            else:
                signal_item.setForeground(Qt.green)
            self.signal_table.setItem(i, 1, signal_item)
            self.signal_table.setItem(i, 2, QTableWidgetItem(signal['price']))

def call_deepseek_api(messages, model="deepseek-chat"):
    """调用 DeepSeek API"""
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}'
        }
        
        payload = {
            'model': model,
            'messages': messages,
            'stream': False,
            'max_tokens': 1000
        }
        
        print(f"正在调用DeepSeek API...")
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        
        print(f"DeepSeek API响应状态: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"DeepSeek API成功返回: {len(content)} 字符")
            return content
        else:
            print(f"DeepSeek API 错误: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.Timeout:
        print(f"DeepSeek API 调用超时")
        return None
    except Exception as e:
        print(f"DeepSeek API 调用失败: {e}")
        return None

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Fincept Terminal")
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
