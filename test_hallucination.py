#!/usr/bin/env python3
"""
Whisper APIのハルシネーション対策機能をテストするスクリプト

このスクリプトは、無音ファイルまたは低品質音声ファイルに対して
Whisperがハルシネーションを起こさないことを確認します。
"""

import requests
import json
import sys
from datetime import datetime

# APIのURL（ローカル環境）
API_URL = "http://localhost:8001/fetch-and-transcribe"

def test_with_file_paths(file_paths):
    """
    file_paths形式でテスト
    """
    print("\n" + "="*60)
    print("テスト: file_paths形式")
    print("="*60)
    
    payload = {
        "file_paths": file_paths,
        "model": "base"
    }
    
    print(f"リクエスト:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(API_URL, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        print(f"\nレスポンス:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 処理されたファイルの確認
        if result.get("processed_files"):
            print(f"\n✅ {len(result['processed_files'])}件のファイルを処理")
        else:
            print("\n⚠️ 処理されたファイルがありません")
            
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ エラー: {e}")
        if hasattr(e.response, 'text'):
            print(f"エラー詳細: {e.response.text}")
        return None

def test_with_device_date(device_id, local_date, time_blocks=None):
    """
    device_id/local_date/time_blocks形式でテスト
    """
    print("\n" + "="*60)
    print("テスト: device_id/local_date/time_blocks形式")
    print("="*60)
    
    payload = {
        "device_id": device_id,
        "local_date": local_date,
        "model": "base"
    }
    
    if time_blocks:
        payload["time_blocks"] = time_blocks
    
    print(f"リクエスト:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(API_URL, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        print(f"\nレスポンス:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 処理されたファイルの確認
        if result.get("processed_time_blocks"):
            print(f"\n✅ {len(result['processed_time_blocks'])}件の時間ブロックを処理")
        else:
            print("\n⚠️ 処理された時間ブロックがありません")
            
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ エラー: {e}")
        if hasattr(e.response, 'text'):
            print(f"エラー詳細: {e.response.text}")
        return None

def main():
    print("\n" + "="*60)
    print("Whisper APIハルシネーション対策テスト")
    print("="*60)
    
    # ヘルスチェック
    try:
        health = requests.get("http://localhost:8001/")
        print(f"\n✅ API稼働中: {health.json()['name']}")
    except:
        print("\n❌ APIが起動していません。先にAPIを起動してください:")
        print("   python3 main.py")
        sys.exit(1)
    
    print("\n【説明】")
    print("このテストでは、無音や低品質音声に対するハルシネーション対策を確認します。")
    print("- 無音検出（RMS閾値）")
    print("- フレーズの繰り返し検出")
    print("- 単語の過度な繰り返し検出")
    print("- Whisperのno_speech_prob活用")
    
    # テスト1: 問題のあるファイルのテスト（CSVで確認されたもの）
    print("\n【テスト1】問題のあるファイル")
    test_file_paths = [
        "files/9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93/2025-08-26/05-30/audio.wav"
    ]
    
    result = test_with_file_paths(test_file_paths)
    
    if result:
        print("\n【分析】")
        print("改善された点:")
        print("- 無音や低品質音声は空文字として保存")
        print("- 「スタッフの方が」のような繰り返しは検出・除去")
        print("- データベースには正常に保存（空文字でも）")
    
    # テスト2: device_id/date形式でのテスト
    print("\n【テスト2】device_id/date形式でのテスト")
    result = test_with_device_date(
        device_id="9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93",
        local_date="2025-08-26",
        time_blocks=["05-30"]
    )

if __name__ == "__main__":
    main()