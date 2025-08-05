#!/usr/bin/env python3
"""
CSV データを使用したテストスクリプト
audio_files_rows.csv から実際のデータを読み込んでテスト
"""

import requests
import json
import csv
from datetime import datetime

# APIエンドポイントの設定
API_BASE_URL = "http://localhost:8001"
ENDPOINT = "/fetch-and-transcribe"

def test_with_csv_data():
    """CSVファイルから読み込んだデータでテスト"""
    print("\n=== CSVデータを使用したテスト ===")
    
    # CSVファイルを読み込む
    csv_path = "/Users/kaya.matsumoto/Desktop/audio_files_rows.csv"
    
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
                if result['summary']['pending_processed'] == 0:
                    print("（注: 0件の場合は、既に処理済みか、該当ファイルが存在しない可能性があります）")
            else:
                print(f"\n❌ エラー: {response.text}")
            
            # 既存インターフェースでもテスト
            print("\n\n--- 既存インターフェース（file_paths）でテスト ---")
            payload = {
                "file_paths": [row['file_path']],
                "model": "base"
            }
            
            print(f"\nリクエスト: {json.dumps(payload, indent=2)}")
            
            response = requests.post(f"{API_BASE_URL}{ENDPOINT}", json=payload)
            print(f"\nステータスコード: {response.status_code}")
            print(f"レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n✅ 成功: {result['summary']['pending_processed']}件処理")
            else:
                print(f"\n❌ エラー: {response.text}")
                
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
            print(f"レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            return True
        else:
            print("❌ APIに問題があります")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ APIに接続できません。APIが起動していることを確認してください。")
        print("\n以下のコマンドでAPIを起動してください:")
        print("cd /Users/kaya.matsumoto/api_whisper_v1")
        print("python3 main.py")
        return False
    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        return False

if __name__ == "__main__":
    print("CSV データを使用したテストスクリプト")
    print("=====================================")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # APIヘルスチェック
    if check_api_health():
        # CSVデータでテスト
        test_with_csv_data()
    else:
        print("\nテストを中止します。APIを起動してから再度実行してください。")