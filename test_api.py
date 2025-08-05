#!/usr/bin/env python3
"""
API Whisper v1 - テストスクリプト
新しいdevice_id/local_date/time_blocksインターフェースと
既存のfile_pathsインターフェースの両方をテスト
"""

import requests
import json
import sys
from datetime import datetime

# APIエンドポイントの設定
API_BASE_URL = "http://localhost:8001"
ENDPOINT = "/fetch-and-transcribe"

def test_new_interface():
    """新しいインターフェースのテスト: device_id + local_date + time_blocks"""
    print("\n=== 新しいインターフェースのテスト ===")
    
    # テストケース1: 特定の時間ブロックを指定
    payload = {
        "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
        "local_date": "2025-07-19",
        "time_blocks": ["14-30", "15-00"],
        "model": "base"
    }
    
    print(f"\nテスト1: 特定の時間ブロックを指定")
    print(f"リクエスト: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(f"{API_BASE_URL}{ENDPOINT}", json=payload)
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 成功: {result['summary']['pending_processed']}件処理")
        else:
            print(f"❌ エラー: {response.text}")
    except Exception as e:
        print(f"❌ リクエストエラー: {str(e)}")
    
    # テストケース2: 時間ブロックを指定しない（全時間帯）
    payload = {
        "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0", 
        "local_date": "2025-07-19",
        "model": "base"
    }
    
    print(f"\n\nテスト2: 時間ブロックを指定しない（全時間帯）")
    print(f"リクエスト: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(f"{API_BASE_URL}{ENDPOINT}", json=payload)
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 成功: {result['summary']['pending_processed']}件処理")
        else:
            print(f"❌ エラー: {response.text}")
    except Exception as e:
        print(f"❌ リクエストエラー: {str(e)}")

def test_legacy_interface():
    """既存のインターフェースのテスト: file_paths"""
    print("\n\n=== 既存のインターフェースのテスト（後方互換性） ===")
    
    payload = {
        "file_paths": [
            "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-19/14-30/audio.wav",
            "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-19/15-00/audio.wav"
        ],
        "model": "base"
    }
    
    print(f"リクエスト: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(f"{API_BASE_URL}{ENDPOINT}", json=payload)
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 成功: {result['summary']['pending_processed']}件処理")
        else:
            print(f"❌ エラー: {response.text}")
    except Exception as e:
        print(f"❌ リクエストエラー: {str(e)}")

def test_error_cases():
    """エラーケースのテスト"""
    print("\n\n=== エラーケースのテスト ===")
    
    # テストケース1: パラメータが不足
    payload = {
        "model": "base"
    }
    
    print(f"\nテスト1: パラメータが不足")
    print(f"リクエスト: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(f"{API_BASE_URL}{ENDPOINT}", json=payload)
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 400:
            print(f"✅ 期待通りのエラー")
        else:
            print(f"❌ 予期しないレスポンス")
    except Exception as e:
        print(f"❌ リクエストエラー: {str(e)}")
    
    # テストケース2: サポートされていないモデル
    payload = {
        "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
        "local_date": "2025-07-19", 
        "model": "large"  # サポートされていない
    }
    
    print(f"\n\nテスト2: サポートされていないモデル")
    print(f"リクエスト: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(f"{API_BASE_URL}{ENDPOINT}", json=payload)
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 400:
            print(f"✅ 期待通りのエラー")
        else:
            print(f"❌ 予期しないレスポンス")
    except Exception as e:
        print(f"❌ リクエストエラー: {str(e)}")

def test_health_check():
    """ヘルスチェック"""
    print("\n=== ヘルスチェック ===")
    
    try:
        response = requests.get(f"{API_BASE_URL}/")
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print(f"✅ APIは正常に稼働しています")
        else:
            print(f"❌ APIに問題があります")
    except Exception as e:
        print(f"❌ APIに接続できません: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("API Whisper v1 テストスクリプト")
    print("================================")
    print(f"API URL: {API_BASE_URL}")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ヘルスチェック
    test_health_check()
    
    # 各種テストの実行
    test_new_interface()
    test_legacy_interface()
    test_error_cases()
    
    print("\n\nテスト完了")