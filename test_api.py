#!/usr/bin/env python3
"""
Whisper API動作確認テスト
file_pathを使ったステータス更新が正しく動作するか確認
"""

import requests
import json

# APIエンドポイント
API_URL = "http://localhost:8001/fetch-and-transcribe"

# テストデータ
test_request = {
    "file_paths": [
        "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-19/14-30/audio.wav"
    ],
    "model": "base"
}

print("=== Whisper API動作確認テスト ===")
print(f"リクエストURL: {API_URL}")
print(f"リクエストデータ: {json.dumps(test_request, indent=2)}")
print()

try:
    # APIリクエストを送信
    response = requests.post(API_URL, json=test_request)
    
    # レスポンスを確認
    print(f"ステータスコード: {response.status_code}")
    print(f"レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
    if response.status_code == 200:
        result = response.json()
        print("\n=== 処理結果サマリー ===")
        print(f"総ファイル数: {result['summary']['total_files']}")
        print(f"処理済み: {result['summary']['pending_processed']}")
        print(f"エラー: {result['summary']['errors']}")
        print(f"実行時間: {result['execution_time_seconds']}秒")
        
        if result['summary']['pending_processed'] > 0:
            print("\n✅ ステータス更新が正常に動作しています。")
        else:
            print("\n⚠️ ファイルが処理されませんでした。S3にファイルが存在するか確認してください。")
    else:
        print("\n❌ APIエラーが発生しました。")
        
except requests.exceptions.ConnectionError:
    print("❌ APIに接続できません。サーバーが起動しているか確認してください。")
except Exception as e:
    print(f"❌ エラーが発生しました: {str(e)}")

print("\n=== テスト完了 ===")