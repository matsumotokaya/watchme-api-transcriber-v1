#!/usr/bin/env python3
"""
Supabaseデータベース接続テストプログラム
audio_filesテーブルから指定されたdevice_idと日付のデータを確認する
"""

import os
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timezone
import json

# 環境変数を読み込み
load_dotenv()

# Supabaseクライアントの初期化
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if not supabase_url or not supabase_key:
    print("エラー: SUPABASE_URLおよびSUPABASE_KEYが設定されていません")
    exit(1)

print(f"Supabase URL: {supabase_url}")

supabase = create_client(supabase_url, supabase_key)

# テスト用パラメータ
device_id = "d067d407-cf73-4174-a9c1-d91fb60d64d0"
test_date = "2025-07-19"

print(f"\n=== audio_filesテーブル確認 ===")
print(f"device_id: {device_id}")
print(f"対象日付: {test_date}")

# 1. まず全体の件数を確認
try:
    all_records = supabase.table('audio_files') \
        .select('*') \
        .eq('device_id', device_id) \
        .execute()
    
    print(f"\n該当device_idの全レコード数: {len(all_records.data)}件")
    
    # 日付ごとにグループ化
    date_groups = {}
    for record in all_records.data:
        recorded_at = record['recorded_at']
        date_part = recorded_at.split('T')[0]
        if date_part not in date_groups:
            date_groups[date_part] = []
        date_groups[date_part].append(record)
    
    print("\n日付別レコード数:")
    for date, records in sorted(date_groups.items()):
        print(f"  {date}: {len(records)}件")
        
except Exception as e:
    print(f"エラー: {str(e)}")
    exit(1)

# 2. 現在のクエリ方法でのテスト（問題がある方法）
print(f"\n--- 現在の実装（問題あり）でのクエリテスト ---")
try:
    query1 = supabase.table('audio_files') \
        .select('*') \
        .eq('device_id', device_id) \
        .gte('recorded_at', f"{test_date}T00:00:00") \
        .lt('recorded_at', f"{test_date}T23:59:59") \
        .execute()
    
    print(f"取得件数: {len(query1.data)}件")
    if query1.data:
        print("取得したレコード例:")
        for i, record in enumerate(query1.data[:3]):
            print(f"  {i+1}. recorded_at: {record['recorded_at']}, status: {record['transcriptions_status']}")
            
except Exception as e:
    print(f"エラー: {str(e)}")

# 3. 修正案1: タイムゾーン付きでクエリ
print(f"\n--- 修正案1: タイムゾーン付きクエリ ---")
try:
    query2 = supabase.table('audio_files') \
        .select('*') \
        .eq('device_id', device_id) \
        .gte('recorded_at', f"{test_date}T00:00:00+00:00") \
        .lt('recorded_at', f"{test_date}T23:59:59+00:00") \
        .execute()
    
    print(f"取得件数: {len(query2.data)}件")
    if query2.data:
        print("取得したレコード例:")
        for i, record in enumerate(query2.data[:3]):
            print(f"  {i+1}. recorded_at: {record['recorded_at']}, status: {record['transcriptions_status']}")
            
except Exception as e:
    print(f"エラー: {str(e)}")

# 4. 修正案2: 翌日の00:00:00を使用
print(f"\n--- 修正案2: 翌日の境界を使用 ---")
try:
    from datetime import datetime, timedelta
    
    # 対象日付の開始と終了を計算
    start_date = datetime.strptime(test_date, "%Y-%m-%d")
    end_date = start_date + timedelta(days=1)
    
    query3 = supabase.table('audio_files') \
        .select('*') \
        .eq('device_id', device_id) \
        .gte('recorded_at', f"{start_date.strftime('%Y-%m-%d')}T00:00:00") \
        .lt('recorded_at', f"{end_date.strftime('%Y-%m-%d')}T00:00:00") \
        .execute()
    
    print(f"取得件数: {len(query3.data)}件")
    if query3.data:
        print("取得したレコード例:")
        for i, record in enumerate(query3.data[:3]):
            print(f"  {i+1}. recorded_at: {record['recorded_at']}, status: {record['transcriptions_status']}")
            
except Exception as e:
    print(f"エラー: {str(e)}")

# 5. 修正案3: likeクエリを使用
print(f"\n--- 修正案3: likeクエリ使用 ---")
try:
    query4 = supabase.table('audio_files') \
        .select('*') \
        .eq('device_id', device_id) \
        .like('recorded_at', f"{test_date}%") \
        .execute()
    
    print(f"取得件数: {len(query4.data)}件")
    if query4.data:
        print("取得したレコード例:")
        for i, record in enumerate(query4.data[:3]):
            print(f"  {i+1}. recorded_at: {record['recorded_at']}, status: {record['transcriptions_status']}")
            
except Exception as e:
    print(f"エラー: {str(e)}")

# 6. pendingステータスの確認
print(f"\n--- pendingステータスのレコード確認 ---")
try:
    # likeクエリでpendingのものを取得
    pending_query = supabase.table('audio_files') \
        .select('*') \
        .eq('device_id', device_id) \
        .like('recorded_at', f"{test_date}%") \
        .eq('transcriptions_status', 'pending') \
        .execute()
    
    print(f"pending件数: {len(pending_query.data)}件")
    
    if pending_query.data:
        print("\npendingレコードの詳細:")
        for record in pending_query.data:
            print(f"  - recorded_at: {record['recorded_at']}")
            print(f"    file_path: {record['file_path']}")
            print(f"    status: {record['transcriptions_status']}")
            print()
            
except Exception as e:
    print(f"エラー: {str(e)}")

print("\n=== テスト完了 ===")