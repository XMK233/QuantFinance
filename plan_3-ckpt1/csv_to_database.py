#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
将已下载的CSV股票数据导入到SQLite数据库
支持增量导入，只导入数据库中缺失的数据
"""

import pandas as pd
import os
import glob
from tqdm import tqdm
from stock_database import StockDatabase
from datetime import datetime

def import_csv_to_database(csv_dir, db_path=None):
    """
    将CSV文件数据导入数据库，支持增量导入
    
    Args:
        csv_dir: CSV文件所在目录
        db_path: 数据库路径（默认使用数据目录的数据库）
    """
    
    # 初始化数据库
    db = StockDatabase(db_path)
    
    # 查找所有CSV文件
    csv_pattern = os.path.join(csv_dir, "*.csv")
    csv_files = glob.glob(csv_pattern)
    
    print(f"📁 找到 {len(csv_files)} 个CSV文件在目录: {csv_dir}")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    total_rows = 0
    
    with tqdm(total=len(csv_files), desc="导入CSV数据", unit="文件") as pbar:
        for csv_file in csv_files:
            try:
                # 从文件名提取股票代码
                filename = os.path.basename(csv_file)
                stock_code = filename.replace('.csv', '')
                
                # 清理股票代码（移除sh. sz.前缀）
                if stock_code.startswith('sh.') or stock_code.startswith('sz.'):
                    stock_code = stock_code[3:]
                
                # 读取CSV文件
                df = pd.read_csv(csv_file)
                
                if len(df) == 0:
                    pbar.write(f"⚠️  {filename}: 文件为空")
                    skip_count += 1
                    pbar.update(1)
                    continue
                
                # 确保有必要的列
                if 'date' not in df.columns or 'code' not in df.columns:
                    pbar.write(f"⚠️  {filename}: 缺少必要列(date/code)")
                    skip_count += 1
                    pbar.update(1)
                    continue
                
                # 添加股票代码列（如果不存在）
                if 'code' not in df.columns:
                    df['code'] = stock_code
                
                # 转换日期格式
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                
                # 获取数据库中该股票的最新日期
                latest_date = db.get_max_date(stock_code, 'daily')
                
                if latest_date:
                    # 只导入比数据库更新的数据
                    latest_date_dt = datetime.strptime(latest_date, '%Y-%m-%d')
                    df['date_dt'] = pd.to_datetime(df['date'])
                    df_to_import = df[df['date_dt'] > latest_date_dt].copy()
                    df_to_import.drop('date_dt', axis=1, inplace=True)
                    
                    if len(df_to_import) == 0:
                        pbar.write(f"✅  {filename}: 数据已是最新（最新日期: {latest_date}）")
                        skip_count += 1
                        pbar.update(1)
                        continue
                else:
                    # 数据库中没有该股票数据，导入全部
                    df_to_import = df
                
                # 导入数据到数据库
                db.insert_price_data(df_to_import, 'daily')
                
                success_count += 1
                total_rows += len(df_to_import)
                
                pbar.set_postfix({
                    '成功': success_count,
                    '跳过': skip_count, 
                    '错误': error_count,
                    '行数': total_rows
                })
                
            except Exception as e:
                error_count += 1
                pbar.write(f"❌  {filename}: 导入失败 - {str(e)}")
            
            pbar.update(1)
    
    print(f"\n📊 导入完成:")
    print(f"   ✅ 成功: {success_count} 个文件")
    print(f"   ⏭️  跳过: {skip_count} 个文件（数据已是最新）")
    print(f"   ❌ 错误: {error_count} 个文件")
    print(f"   📈 总行数: {total_rows} 行数据")
    print(f"   💾 数据库: {db.db_path}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='CSV股票数据导入数据库工具')
    parser.add_argument('--csv-dir', required=True, help='CSV文件所在目录')
    parser.add_argument('--db', default=None, help='数据库文件路径（可选）')
    
    args = parser.parse_args()
    
    print("🐂 CSV数据导入工具")
    print("💾 将已下载的CSV股票数据导入SQLite数据库")
    print("🔄 支持增量导入，避免重复数据")
    print()
    
    if not os.path.exists(args.csv_dir):
        print(f"❌ 目录不存在: {args.csv_dir}")
        return
    
    import_csv_to_database(args.csv_dir, args.db)

if __name__ == "__main__":
    main()