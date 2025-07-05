import requests
import json
import sys
import os
from datetime import datetime

def test_batch_transcribe_api(device_id, date=None):
    """
    一括文字起こしAPIをテストする関数
    
    Args:
        device_id: テストするデバイスID
        date: 対象日付（YYYY-MM-DD形式）。指定しない場合は当日
    """
    # APIエンドポイント（WatchMeプロジェクトのポート8001を使用）
    url = "http://localhost:8001/batch-transcribe"
    
    # リクエストデータ
    data = {
        "device_id": device_id
    }
    
    if date:
        data["date"] = date
        target_date = date
    else:
        target_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"デバイスID '{device_id}' の一括文字起こしを開始...")
    print(f"対象日付: {target_date}")
    
    try:
        response = requests.post(url, json=data, headers={"Content-Type": "application/json"})
        
        if response.status_code == 200:
            result = response.json()
            print("\n一括文字起こし完了!")
            print("=" * 50)
            print(f"ステータス: {result['status']}")
            print(f"処理済み: {result['processed']}")
            print(f"スキップ: {result['skipped']}")
            print(f"処理ファイル数: {len(result['processed'])}")
            print(f"スキップファイル数: {len(result['skipped'])}")
            if 'success_rate' in result:
                print(f"成功率: {result['success_rate']}")
            print("=" * 50)
            
            # 処理されたファイルの一覧を表示
            if result['processed']:
                print("\n処理されたファイル:")
                for time_block in result['processed']:
                    print(f"  - {time_block}.wav → {time_block}.json")
            
            if result['skipped']:
                print("\nスキップされたファイル:")
                for time_block in result['skipped']:
                    print(f"  - {time_block}.wav")
        
        elif response.status_code == 404:
            print(f"エラー: 指定されたディレクトリが見つかりません")
            print(response.json()['detail'])
        else:
            print(f"エラー: APIからステータスコード {response.status_code} が返されました")
            print(response.text)
    
    except requests.exceptions.ConnectionError:
        print("エラー: APIサーバーに接続できません。サーバーが実行中か確認してください。")
        print("サーバー起動コマンド: venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --reload")
    except Exception as e:
        print(f"エラー: {str(e)}")

def create_sample_data(device_id):
    """
    テスト用のサンプルデータディレクトリを作成する関数
    """
    today = datetime.now().strftime("%Y-%m-%d")
    base_dir = f"/Users/kaya.matsumoto/data/data_accounts/{device_id}/{today}"
    
    print(f"サンプルデータディレクトリを作成します: {base_dir}")
    
    try:
        os.makedirs(base_dir, exist_ok=True)
        print(f"ディレクトリ作成完了: {base_dir}")
        print("注意: 実際の.wavファイルは手動で配置してください")
        return True
    except Exception as e:
        print(f"エラー: ディレクトリの作成に失敗しました: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python test_batch_api.py <device_id>                    # 当日の一括文字起こしを実行")
        print("  python test_batch_api.py <device_id> <YYYY-MM-DD>       # 指定日の一括文字起こしを実行")
        print("  python test_batch_api.py <device_id> --create-dir       # テスト用ディレクトリを作成")
        print("\nWatchMeプロジェクト用 Whisper API (ポート8001)")
        print("例:")
        print("  python test_batch_api.py device123 2025-06-05")
        sys.exit(1)
    
    device_id = sys.argv[1]
    
    if len(sys.argv) > 2:
        if sys.argv[2] == "--create-dir":
            create_sample_data(device_id)
        else:
            # 日付が指定された場合
            date = sys.argv[2]
            test_batch_transcribe_api(device_id, date)
    else:
        test_batch_transcribe_api(device_id) 