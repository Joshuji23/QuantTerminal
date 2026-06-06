# -*- coding: utf-8 -*-
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QLineEdit,
    QPushButton, QComboBox, QTextEdit, QLabel, QHeaderView
)
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

print("1. Import OK")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        print("2. MainWindow init")
        self.setWindowTitle("Fincept Terminal")
        self.resize(1200, 800)
        self.current_theme = "dark"
        self.setup_ui()
    
    def setup_ui(self):
        print("3. setup_ui")
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        self.market_widget = MarketWidget(self)
        self.chart_widget = ChartWidget(self)
        
        self.tabs.addTab(self.market_widget, "市场行情")
        self.tabs.addTab(self.chart_widget, "图表分析")
        
        self.apply_theme("dark")
    
    def apply_theme(self, theme):
        print("4. apply_theme:", theme)
        palette = QPalette()
        if theme == "dark":
            palette.setColor(QPalette.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(40, 40, 40))
            palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(50, 50, 50))
            palette.setColor(QPalette.ButtonText, Qt.white)
        else:
            palette.setColor(QPalette.Window, QColor(255, 255, 255))
            palette.setColor(QPalette.WindowText, Qt.black)
            palette.setColor(QPalette.Base, QColor(240, 240, 240))
            palette.setColor(QPalette.AlternateBase, QColor(255, 255, 255))
            palette.setColor(QPalette.Text, Qt.black)
            palette.setColor(QPalette.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ButtonText, Qt.black)
        QApplication.instance().setPalette(palette)

class MarketWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        print("5. MarketWidget init")
        self.parent = parent
        self.setup_ui()
    
    def setup_ui(self):
        print("6. MarketWidget setup_ui")
        layout = QVBoxLayout()
        self.market_table = QTableWidget()
        self.market_table.setColumnCount(6)
        self.market_table.setHorizontalHeaderLabels(["代码", "名称", "最新价", "涨跌额", "涨跌幅", "成交量"])
        self.market_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.market_table)
        self.setLayout(layout)
        self.load_mock_data()
    
    def load_mock_data(self):
        print("7. Loading mock data")
        symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
        names = ["Apple", "Google", "Microsoft", "Amazon", "Tesla"]
        prices = [178.50, 141.20, 378.90, 178.25, 248.80]
        changes = [2.30, -1.50, 1.80, 0.95, -3.20]
        
        self.market_table.setRowCount(5)
        for i in range(5):
            self.market_table.setItem(i, 0, QTableWidgetItem(symbols[i]))
            self.market_table.setItem(i, 1, QTableWidgetItem(names[i]))
            self.market_table.setItem(i, 2, QTableWidgetItem(f"{prices[i]:.2f}"))
            change_item = QTableWidgetItem(f"{changes[i]:.2f}")
            self.market_table.setItem(i, 3, change_item)
    
    def apply_theme(self, theme):
        pass

class ChartWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        print("8. ChartWidget init")
        self.parent = parent
        self.current_symbol = "AAPL"
        self.setup_ui()
    
    def setup_ui(self):
        print("9. ChartWidget setup_ui")
        layout = QVBoxLayout()
        
        self.figure = Figure(figsize=(8, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        self.draw_chart()
    
    def draw_chart(self):
        print("10. Drawing chart")
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
        prices = 100 + np.cumsum(np.random.randn(30))
        
        ax.plot(dates, prices)
        ax.set_title(f'{self.current_symbol} Price Chart')
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def apply_theme(self, theme):
        pass

def main():
    print("Starting application...")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    print("Creating main window...")
    window = MainWindow()
    window.show()
    
    print("Starting event loop...")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
