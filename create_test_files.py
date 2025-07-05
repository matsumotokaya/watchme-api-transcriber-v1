import os
import numpy as np
import wave
from datetime import datetime
import sys

def create_dummy_wav(filepath, duration=1.0, sample_rate=16000):
    """
    ダミーの音声ファイル（短いビープ音）を作成
    
    Args:
        filepath: 出力ファイルパス
        duration: 音声の長さ（秒）
        sample_rate: サンプリングレート
    """
    # 短いビープ音を生成（440Hz）
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    frequency = 440.0  # A音
    wave_data = np.sin(frequency * 2 * np.pi * t)
    
    # 音量を調整（16bit整数に変換）
    wave_data = (wave_data * 0.3 * 32767).astype(np.int16)
    
    # WAVファイルとして保存
    with wave.open(filepath, 'w') as wav_file:
        wav_file.setnchannels(1)  # モノラル
        wav_file.setsampwidth(2)  # 16bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(wave_data.tobytes())

def create_test_files(device_id, num_files=5):
    """
    テスト用の音声ファイルを作成
    
    Args:
        device_id: ユーザーID
        num_files: 作成するファイル数
    """
    today = datetime.now().strftime("%Y-%m-%d")
    base_dir = f"/Users/kaya.matsumoto/data/data_accounts/{device_id}/{today}"
    
    # ディレクトリを作成
    os.makedirs(base_dir, exist_ok=True)
    
    print(f"テスト用音声ファイルを作成します...")
    print(f"ディレクトリ: {base_dir}")
    print(f"作成ファイル数: {num_files}")
    print("-" * 40)
    
    # 時間形式のファイル名を生成（00-00, 00-30, 01-00, 01-30, ...）
    for i in range(num_files):
        hour = i // 2
        minute = 30 if i % 2 == 1 else 0
        filename = f"{hour:02d}-{minute:02d}.wav"
        filepath = os.path.join(base_dir, filename)
        
        try:
            create_dummy_wav(filepath, duration=2.0)  # 2秒の音声
            print(f"✅ 作成完了: {filename}")
        except Exception as e:
            print(f"❌ 作成失敗: {filename} - {str(e)}")
    
    print("-" * 40)
    print(f"テスト用ファイル作成完了")
    print(f"次のコマンドでAPIをテストできます:")
    print(f"python3 test_batch_api.py {device_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python3 create_test_files.py <device_id> [ファイル数]")
        print("例:")
        print("  python3 create_test_files.py test_user 5")
        sys.exit(1)
    
    device_id = sys.argv[1]
    num_files = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    try:
        create_test_files(device_id, num_files)
    except ImportError:
        print("エラー: numpyが必要です。以下のコマンドでインストールしてください:")
        print("python3 -m pip install numpy")
    except Exception as e:
        print(f"エラー: {str(e)}") 