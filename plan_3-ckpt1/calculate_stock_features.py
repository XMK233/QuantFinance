#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票特征计算主脚本
基于数据库计算所有股票的特征属性
"""

import pandas as pd
from datetime import datetime
from tqdm import tqdm

# 导入算子模块 - 使用重命名后的文件夹
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from stock_operators.base_operator import FeatureCalculator
from stock_operators.cross_ma_operator import CrossMAOperator, ClosePriceOperator
from stock_operators.st_operator import STStockOperator, LimitUpOperator
from stock_operators.volume_break_operator import VolumeBreakOperator, MADivergenceOperator
from stock_operators.breakthrough_operator import BreakthroughPullbackOperator, ListingDateOperator


def main():
    """主函数"""
    print("🎯 === 股票特征计算开始 ===")
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    # 创建特征计算器
    calculator = FeatureCalculator()
    
    # 注册所有算子
    calculator.register_operator(CrossMAOperator())
    calculator.register_operator(ClosePriceOperator())
    calculator.register_operator(STStockOperator())
    calculator.register_operator(LimitUpOperator())
    calculator.register_operator(VolumeBreakOperator())
    calculator.register_operator(MADivergenceOperator())
    calculator.register_operator(BreakthroughPullbackOperator())
    calculator.register_operator(ListingDateOperator())
    
    print("📊 开始计算所有股票特征...")
    
    # 计算所有股票的特征
    features_df = calculator.calculate_all_stocks()
    
    # 保存结果
    output_file = "/mnt/d/forCoding_data/QuantFinance/plan_3-standardization_1/stock_features.csv"
    features_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    print(f"✅ 特征计算完成!")
    print(f"💾 结果已保存到: {output_file}")
    print(f"📈 共计算了 {len(features_df)} 只股票的特征")
    print(f"⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 显示一些统计信息
    if not features_df.empty:
        print("\n📊 特征统计:")
        print("-" * 30)
        
        # 一阳穿四线统计
        for weeks in [2, 4, 8]:
            col = f'cross_ma_{weeks}w'
            if col in features_df.columns:
                count = features_df[col].sum()
                print(f"过去{weeks}周一阳穿四线: {count} 只股票")
        
        # ST股统计
        if 'is_st' in features_df.columns:
            st_count = features_df['is_st'].sum()
            print(f"ST股数量: {st_count} 只")
        
        # 放量突破统计
        if 'volume_break_ge_2' in features_df.columns:
            break_count = features_df['volume_break_ge_2'].sum()
            print(f"放量突破≥2次: {break_count} 只股票")
        
        # 均线发散统计
        if 'ma_divergence' in features_df.columns:
            divergence_count = features_df['ma_divergence'].sum()
            print(f"均线发散走多: {divergence_count} 只股票")


def test_single_stock():
    """测试单只股票的特征计算"""
    print("🧪 测试单只股票特征计算...")
    
    calculator = FeatureCalculator()
    
    # 注册所有算子
    calculator.register_operator(CrossMAOperator())
    calculator.register_operator(ClosePriceOperator())
    calculator.register_operator(STStockOperator())
    calculator.register_operator(LimitUpOperator())
    calculator.register_operator(VolumeBreakOperator())
    calculator.register_operator(MADivergenceOperator())
    calculator.register_operator(BreakthroughPullbackOperator())
    calculator.register_operator(ListingDateOperator())
    
    # 测试一只股票
    test_stock = "sh.600000"  # 浦发银行
    features = calculator.calculate_features(test_stock)
    
    print(f"\n📋 股票 {test_stock} 的特征:")
    print("-" * 40)
    
    for key, value in features.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='股票特征计算')
    parser.add_argument('--test', action='store_true', help='测试模式，只计算单只股票')
    parser.add_argument('--stock', default='sh.600000', help='测试的股票代码')
    
    args = parser.parse_args()
    
    if args.test:
        test_single_stock()
    else:
        main()