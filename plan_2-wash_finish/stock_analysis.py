import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime, timedelta
from ta import trend, momentum, volatility, volume
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import warnings
warnings.filterwarnings('ignore')

class StockAnalyzer:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.all_stocks = []
        self.features = []
        self.labels = []
        
    def load_stock_data(self, file_path):
        """加载单只股票数据"""
        try:
            df = pd.read_csv(file_path)
            if len(df) < 50:  # 至少需要50周数据
                return None
            
            # 确保日期格式正确
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            # 确保数值列格式正确
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 移除包含NaN的行
            df = df.dropna(subset=['close', 'volume'])
            
            if len(df) < 50:  # 再次检查数据量
                return None
                
            return df
        except Exception as e:
            print(f"加载 {file_path} 时出错: {e}")
            return None
    
    def calculate_technical_indicators(self, df):
        """计算技术指标"""
        # 确保数据为float64类型
        df = df.copy()
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 移除NaN值
        df = df.dropna(subset=['close', 'volume'])
        
        if len(df) < 20:  # 确保有足够的数据
            return df
        
        # 使用ta库计算技术指标（兼容性更好）
        close = df['close']
        high = df['high']
        low = df['low']
        vol = df['volume']
        
        # 移动平均线
        df['MA5'] = trend.sma_indicator(close, window=5)
        df['MA10'] = trend.sma_indicator(close, window=10)
        df['MA20'] = trend.sma_indicator(close, window=20)
        
        # MACD
        macd = trend.MACD(close)
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff()
        
        # RSI
        df['RSI'] = momentum.rsi(close, window=14)
        
        # 布林带
        bb = volatility.BollingerBands(close, window=20, window_dev=2)
        df['BB_Upper'] = bb.bollinger_hband()
        df['BB_Middle'] = bb.bollinger_mavg()
        df['BB_Lower'] = bb.bollinger_lband()
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
        
        # 随机指标KDJ
        stoch = momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)
        df['KDJ_K'] = stoch.stoch()
        df['KDJ_D'] = stoch.stoch_signal()
        df['KDJ_J'] = 3 * df['KDJ_K'] - 2 * df['KDJ_D']
        
        # 成交量指标
        df['Volume_MA5'] = volume.volume_weighted_average_price(high, low, close, vol, window=5)
        df['Volume_MA20'] = volume.volume_weighted_average_price(high, low, close, vol, window=20)
        df['Volume_Ratio'] = vol / df['Volume_MA20']
        
        # 价格动量
        df['Momentum'] = momentum.roc(close, window=10)
        df['ROC'] = momentum.roc(close, window=10)
        
        return df
    
    def calculate_features(self, df):
        """计算特征向量"""
        features = {}
        
        # 价格位置特征
        current_close = df['close'].iloc[-1]
        features['price_vs_MA5'] = current_close / df['MA5'].iloc[-1] - 1
        features['price_vs_MA10'] = current_close / df['MA10'].iloc[-1] - 1
        features['price_vs_MA20'] = current_close / df['MA20'].iloc[-1] - 1
        features['price_vs_BB_middle'] = current_close / df['BB_Middle'].iloc[-1] - 1
        
        # 布林带位置
        features['bollinger_position'] = (current_close - df['BB_Lower'].iloc[-1]) / \
                                        (df['BB_Upper'].iloc[-1] - df['BB_Lower'].iloc[-1])
        
        # 技术指标值
        features['RSI'] = df['RSI'].iloc[-1]
        features['MACD'] = df['MACD'].iloc[-1]
        features['MACD_Hist'] = df['MACD_Hist'].iloc[-1]
        features['KDJ_K'] = df['KDJ_K'].iloc[-1]
        features['KDJ_D'] = df['KDJ_D'].iloc[-1]
        features['KDJ_J'] = df['KDJ_J'].iloc[-1]
        
        # 成交量特征
        features['volume_ratio'] = df['Volume_Ratio'].iloc[-1]
        features['volume_trend'] = df['Volume_MA5'].iloc[-1] / df['Volume_MA20'].iloc[-1] - 1
        
        # 动量特征
        features['momentum'] = df['Momentum'].iloc[-1]
        features['ROC'] = df['ROC'].iloc[-1]
        
        # 波动性特征
        features['bollinger_width'] = df['BB_Width'].iloc[-1]
        
        # 价格区间特征（最近20周）
        recent_high = df['high'][-20:].max()
        recent_low = df['low'][-20:].min()
        features['price_in_range'] = (current_close - recent_low) / (recent_high - recent_low)
        
        return features
    
    def calculate_future_return(self, df, weeks=4):
        """计算未来收益"""
        if len(df) < weeks + 1:
            return None
        
        current_close = df['close'].iloc[-1]
        future_close = df['close'].iloc[-weeks-1]
        
        return (future_close / current_close) - 1
    
    def analyze_stock(self, file_path):
        """分析单只股票"""
        df = self.load_stock_data(file_path)
        if df is None:
            return None
        
        # 计算技术指标
        df = self.calculate_technical_indicators(df)
        
        # 计算特征
        features = self.calculate_features(df)
        
        # 计算未来4周收益
        future_return = self.calculate_future_return(df, weeks=4)
        
        if future_return is None:
            return None
        
        # 股票代码
        stock_code = os.path.basename(file_path).split('.')[0]
        
        return {
            'stock_code': stock_code,
            'features': features,
            'future_return': future_return,
            'current_price': df['close'].iloc[-1],
            'volume': df['volume'].iloc[-1],
            'last_date': df['date'].iloc[-1]
        }
    
    def train_model(self):
        """训练机器学习模型"""
        if not self.features:
            return None
        
        # 准备特征矩阵
        X = []
        y = []
        
        for stock_data in self.all_stocks:
            features = list(stock_data['features'].values())
            X.append(features)
            
            # 二分类：未来4周收益超过10%为正面
            y.append(1 if stock_data['future_return'] > 0.10 else 0)
        
        X = np.array(X)
        y = np.array(y)
        
        # 数据标准化
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # 训练随机森林模型
        X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
        
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        
        # 评估模型
        train_score = model.score(X_train, y_train)
        test_score = model.score(X_test, y_test)
        
        print(f"模型训练完成 - 训练集准确率: {train_score:.3f}, 测试集准确率: {test_score:.3f}")
        
        return model, scaler
    
    def find_best_stocks(self, top_n=20):
        """找到最佳股票"""
        # 收集所有股票数据
        csv_files = glob.glob(os.path.join(self.data_dir, "*.csv"))
        
        print(f"开始分析 {len(csv_files)} 只股票...")
        
        for i, file_path in enumerate(csv_files):
            if i % 100 == 0:
                print(f"已处理 {i}/{len(csv_files)} 只股票")
            
            stock_data = self.analyze_stock(file_path)
            if stock_data:
                self.all_stocks.append(stock_data)
                self.features.append(stock_data['features'])
        
        print(f"成功分析 {len(self.all_stocks)} 只股票")
        
        # 训练机器学习模型
        model, scaler = self.train_model()
        
        # 预测所有股票
        X_all = []
        for features in self.features:
            X_all.append(list(features.values()))
        
        X_all_scaled = scaler.transform(X_all)
        predictions = model.predict_proba(X_all_scaled)[:, 1]
        
        # 综合评分
        results = []
        for i, stock_data in enumerate(self.all_stocks):
            score = predictions[i]
            
            # 技术分析加分项
            features = stock_data['features']
            tech_score = 0
            
            # RSI在30-70之间加分
            if 30 <= features['RSI'] <= 70:
                tech_score += 1
            
            # MACD金叉或即将金叉
            if features['MACD'] > features['MACD'] * 0.9:  # 接近金叉
                tech_score += 1
            
            # 价格在布林带中下部
            if features['bollinger_position'] < 0.7:
                tech_score += 1
            
            # 成交量放大
            if features['volume_ratio'] > 1.2:
                tech_score += 1
            
            final_score = score * 0.7 + tech_score * 0.3
            
            results.append({
                'stock_code': stock_data['stock_code'],
                'score': final_score,
                'ml_probability': score,
                'tech_score': tech_score,
                'future_return': stock_data['future_return'],
                'current_price': stock_data['current_price'],
                'volume': stock_data['volume'],
                'last_date': stock_data['last_date'],
                'features': features
            })
        
        # 按评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        return results[:top_n]
    
    def generate_report(self, best_stocks):
        """生成分析报告"""
        report = ""
        report += "=" * 80 + "\n"
        report += "股票洗盘完成分析报告\n"
        report += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"分析股票数量: {len(self.all_stocks)}\n"
        report += "=" * 80 + "\n\n"
        
        for i, stock in enumerate(best_stocks, 1):
            report += f"第{i}名: {stock['stock_code']}\n"
            report += f"综合评分: {stock['score']:.3f} "
            report += f"(机器学习概率: {stock['ml_probability']:.3f}, "
            report += f"技术评分: {stock['tech_score']}/4)\n"
            report += f"当前价格: {stock['current_price']:.2f} "
            report += f"成交量: {stock['volume']:.0f}\n"
            report += f"预测未来4周收益: {stock['future_return']*100:.1f}%\n"
            report += f"最后交易日期: {stock['last_date']}\n"
            
            # 关键技术指标
            features = stock['features']
            report += "关键技术指标:\n"
            report += f"  RSI: {features['RSI']:.1f} "
            report += f"MACD: {features['MACD']:.3f} "
            report += f"KDJ_K: {features['KDJ_K']:.1f}\n"
            report += f"  价格相对MA20: {features['price_vs_MA20']*100:+.1f}% "
            report += f"布林带位置: {features['bollinger_position']:.2f}\n"
            report += f"  成交量比率: {features['volume_ratio']:.2f} "
            report += f"动量: {features['momentum']:.2f}\n"
            
            # 买入理由
            report += "买入理由:\n"
            if features['RSI'] < 40:
                report += "  • RSI处于超卖区域，有反弹机会\n"
            if features['price_vs_MA20'] < -0.05:
                report += "  • 价格低于20周均线，处于相对低位\n"
            if features['bollinger_position'] < 0.3:
                report += "  • 价格在布林带下部，有向上回归趋势\n"
            if features['volume_ratio'] > 1.5:
                report += "  • 成交量明显放大，资金关注度提升\n"
            if features['MACD'] > 0:
                report += "  • MACD显示多头动能\n"
            
            report += "-" * 60 + "\n\n"
        
        return report

def main():
    # 数据目录
    data_dir = "/mnt/d/forCoding_data/QuantFinance/plan_1-select_stock_by_week/originalData/"
    output_dir = "/mnt/d/forCoding_code/QuantFinance/plan_2-wash_finish/"
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 初始化分析器
    analyzer = StockAnalyzer(data_dir)
    
    # 寻找最佳股票
    print("开始寻找洗盘完成的最佳股票...")
    best_stocks = analyzer.find_best_stocks(top_n=20)
    
    # 生成报告
    report = analyzer.generate_report(best_stocks)
    
    # 保存报告
    report_file = os.path.join(output_dir, "stock_analysis_report.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"分析完成！报告已保存至: {report_file}")
    print("\n" + "="*60)
    print("推荐关注的前5只股票:")
    for i, stock in enumerate(best_stocks[:5], 1):
        print(f"{i}. {stock['stock_code']} - 评分: {stock['score']:.3f}")
    print("="*60)

if __name__ == "__main__":
    main()