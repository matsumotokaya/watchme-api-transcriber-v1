#!/usr/bin/env python3
"""
新しいCSVデータを使用したテストスクリプト
audio_files_rows (1).csv から実際のデータを読み込んでテスト
"""

import requests
import json
import csv
from datetime import datetime

# APIエンドポイントの設定
API_BASE_URL = "http://localhost:8001"
ENDPOINT = "/fetch-and-transcribe"

def test_with_new_csv_data():
    """新しいCSVファイルから読み込んだデータでテスト"""
    print("\n=== 新しいCSVデータを使用したテスト ===")
    
    # CSVファイルを読み込む
    csv_path = "/Users/kaya.matsumoto/Desktop/audio_files_rows (1).csv"
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            row = next(csv_reader)  # 最初の行を取得
            
            print(f"\nCSVから読み込んだデータ:")
            print(f"device_id: {row['device_id']}")
            print(f"local_date: {row['local_date']}")
            print(f"time_block: {row['time_block']}")
            print(f"file_path: {row['file_path']}")
            print(f"transcriptions_status: {row['transcriptions_status']}")
            
            # 新インターフェースでテスト
            print("\n--- 新インターフェース（device_id + local_date + time_block）でテスト ---")
            payload = {
                "device_id": row['device_id'],
                "local_date": row['local_date'],
                "time_blocks": [row['time_block']],
                "model": "base"
            }
            
            print(f"\nリクエスト: {json.dumps(payload, indent=2)}")
            
            response = requests.post(f"{API_BASE_URL}{ENDPOINT}", json=payload)
            print(f"\nステータスコード: {response.status_code}")
            print(f"レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n✅ 成功: {result['summary']['pending_processed']}件処理")
                if result['summary']['pending_processed'] > 0:
                    print("処理されたタイムブロック:", result['processed_time_blocks'])
            else:
                print(f"\n❌ エラー: {response.text}")
            
            # 全時間帯を処理するテスト（time_blocksを指定しない）
            print("\n\n--- 新インターフェース（全時間帯）でテスト ---")
            payload_all = {
                "device_id": row['device_id'],
                "local_date": row['local_date'],
                "model": "base"
            }
            
            print(f"\nリクエスト: {json.dumps(payload_all, indent=2)}")
            
            response = requests.post(f"{API_BASE_URL}{ENDPOINT}", json=payload_all)
            print(f"\nステータスコード: {response.status_code}")
            print(f"レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n✅ 成功: {result['summary']['pending_processed']}件処理")
                if result['summary']['pending_processed'] > 0:
                    print("処理されたタイムブロック:", result['processed_time_blocks'])
                
    except FileNotFoundError:
        print(f"❌ CSVファイルが見つかりません: {csv_path}")
    except Exception as e:
        print(f"❌ エラーが発生しました: {str(e)}")

def check_api_health():
    """APIのヘルスチェック"""
    print("\n=== APIヘルスチェック ===")
    
    try:
        response = requests.get(f"{API_BASE_URL}/")
        print(f"ステータスコード: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ APIは正常に稼働しています")
            return True
        else:
            print("❌ APIに問題があります")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ APIに接続できません。APIが起動していることを確認してください。")
        return False
    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        return False

if __name__ == "__main__":
    print("新しいCSVデータを使用したテストスクリプト")
    print("=========================================")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # APIヘルスチェック
    if check_api_health():
        # 新しいCSVデータでテスト
        test_with_new_csv_data()
    else:
        print("\nテストを中止します。APIを起動してから再度実行してください。")