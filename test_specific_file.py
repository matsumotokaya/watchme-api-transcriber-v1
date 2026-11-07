#!/usr/bin/env python3
"""
特定のファイルでハルシネーション対策をテストするスクリプト
"""

import requests
import json

# APIのベースURL
BASE_URL = "http://localhost:8001"

def test_specific_file():
    """指定されたファイルをテスト"""
    
    # テスト対象のファイル
    file_path = "files/9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93/2025-08-29/07-00/audio.wav"
    
    print(f"\n{'='*60}")
    print(f"テストファイル: {file_path}")
    print(f"{'='*60}")
    
    # リクエストペイロード
    payload = {
        "file_paths": [file_path],
        "model": "base"
    }
    
    print(f"\nAPIにリクエスト送信中...")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    try:
        # APIリクエスト
        response = requests.post(
            f"{BASE_URL}/fetch-and-transcribe",
            json=payload,
            timeout=60  # タイムアウトを60秒に設定
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 処理成功")
            print(f"レスポンス: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
            # 結果の解析
            if result.get('summary', {}).get('pending_processed', 0) > 0:
                print(f"\n📝 処理結果:")
                print(f"  - 処理されたファイル数: {result['summary']['pending_processed']}")
                print(f"  - 処理時間: {result.get('execution_time_seconds', 'N/A')}秒")
                
                # データベースから結果を確認（実際にはAPIログで確認）
                print(f"\n💡 APIログを確認して、transcriptionフィールドの内容を確認してください")
                print(f"   期待される結果: 「発話なし」または実際の発話内容")
                print(f"   問題のあるパターン: 「スタッフ」などの繰り返し")
            else:
                print(f"\n⚠️ ファイルは処理されませんでした（既に処理済みの可能性があります）")
        else:
            print(f"\n❌ APIエラー: {response.status_code}")
            print(f"詳細: {response.text}")
            
    except requests.exceptions.Timeout:
        print(f"\n⏱️ リクエストがタイムアウトしました（60秒）")
        print(f"APIログを確認して処理状況を確認してください")
    except Exception as e:
        print(f"\n❌ エラー発生: {str(e)}")

if __name__ == "__main__":
    # ヘルスチェック
    try:
        health = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ API起動確認済み: {health.json()['name']}")
    except Exception as e:
        print(f"❌ APIが起動していません。先に起動してください: python3 main.py")
        exit(1)
    
    # テスト実行
    test_specific_file()