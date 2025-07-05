import requests
import sys
import os

def test_whisper_api(file_path):
    """
    Whisper APIをテストする関数
    
    Args:
        file_path: アップロードする音声ファイルのパス
    """
    if not os.path.exists(file_path):
        print(f"エラー: ファイル '{file_path}' が見つかりません")
        return
    
    # サポートされているファイル拡張子のチェック
    allowed_extensions = [".m4a", ".mp3", ".wav"]
    file_extension = os.path.splitext(file_path)[1].lower()
    
    if file_extension not in allowed_extensions:
        print(f"エラー: サポートされていないファイル形式です。対応形式: {', '.join(allowed_extensions)}")
        return
    
    print(f"ファイル '{file_path}' をアップロード中...")
    
    # APIエンドポイント
    url = "http://localhost:8000/analyze/whisper"
    
    # ファイルをアップロード
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, f"audio/{file_extension[1:]}")}
        
        try:
            response = requests.post(url, files=files)
            
            if response.status_code == 200:
                result = response.json()
                print("\n文字起こし結果:")
                print("=" * 50)
                print(result["transcription"])
                print("=" * 50)
            else:
                print(f"エラー: APIからステータスコード {response.status_code} が返されました")
                print(response.text)
        
        except requests.exceptions.ConnectionError:
            print("エラー: APIサーバーに接続できません。サーバーが実行中か確認してください。")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使用方法: python test_api.py <音声ファイルパス>")
        sys.exit(1)
    
    test_whisper_api(sys.argv[1]) 