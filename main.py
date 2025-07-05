from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile
import os
import whisper
import uvicorn
import json
from datetime import datetime
import glob
import aiohttp
import asyncio

app = FastAPI(title="Whisper API for WatchMe", description="WatchMe統合システム用Whisper音声文字起こしAPI - Vault連携専用")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Whisperモデルをグローバルで一度だけ読み込む
print("Whisperモデルを読み込み中...")
model = whisper.load_model("large")
print("Whisperモデル読み込み完了")

# リクエストボディのモデル
class FetchAndTranscribeRequest(BaseModel):
    device_id: str
    date: str


@app.post("/fetch-and-transcribe")
async def fetch_and_transcribe(request: FetchAndTranscribeRequest):
    """
    指定されたデバイス・日付の.wavファイルをAPIから取得し、一括文字起こしを行う
    """
    device_id = request.device_id
    date = request.date
    
    # Mac環境のローカル出力ディレクトリのパス
    output_dir = f"/Users/kaya.matsumoto/data/data_accounts/{device_id}/{date}/transcriptions"
    
    # 出力ディレクトリを作成（存在しない場合）
    os.makedirs(output_dir, exist_ok=True)
    
    # 一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"\n=== 一括取得・文字起こし開始 ===")
        print(f"デバイスID: {device_id}")
        print(f"対象日付: {date}")
        print(f"出力ディレクトリ: {output_dir}")
        print(f"=" * 50)
        
        fetched = []
        processed = []
        skipped = []
        errors = []
        
        # 時間ブロックのリスト（00-00から23-30まで）
        time_blocks = [f"{hour:02d}-{minute:02d}" for hour in range(24) for minute in [0, 30]]
        
        # SSL検証をスキップするコネクターを作成（音声ファイル取得用）
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            for time_block in time_blocks:
                try:
                    # 出力ファイルパス
                    output_file = os.path.join(output_dir, f"{time_block}.json")
                    
                    # 既存ファイル確認（スキップせずに処理継続）
                    if os.path.exists(output_file):
                        print(f"📄 既存ファイル検出: {time_block}.json (音声取得をスキップ、アップロード対象に追加)")
                        processed.append(f"{time_block}.json")
                    else:
                        print(f"📝 新規ファイル作成: {time_block}.json")
                        
                        # 音声ファイルのURL（/downloadエンドポイントを使用）
                        url = f"https://api.hey-watch.me/download?device_id={device_id}&date={date}&slot={time_block}"
                        
                        # 音声ファイルの取得
                        async with session.get(url) as response:
                            if response.status == 200:
                                # 一時ファイルに保存
                                temp_file = os.path.join(temp_dir, f"{time_block}.wav")
                                with open(temp_file, 'wb') as f:
                                    f.write(await response.read())
                                
                                print(f"📥 取得: {time_block}.wav")
                                fetched.append(f"{time_block}.wav")
                                
                                # Whisperで文字起こし
                                result = model.transcribe(temp_file)
                                transcription = result["text"]
                                
                                # JSONデータを作成
                                transcription_data = {
                                    "time_block": time_block,
                                    "transcription": transcription
                                }
                                
                                # JSONファイルに保存
                                with open(output_file, 'w', encoding='utf-8') as f:
                                    json.dump(transcription_data, f, ensure_ascii=False, indent=2)
                                
                                print(f"💾 JSONファイル生成完了: {output_file}")
                                print(f"📄 ファイルサイズ: {os.path.getsize(output_file)} bytes")
                                
                                processed.append(f"{time_block}.json")
                                print(f"✅ 完了: {time_block}.json ({len(transcription)} 文字)")
                                
                            else:
                                print(f"❌ 取得失敗: {time_block}.wav (ステータス: {response.status})")
                                errors.append(f"{time_block}.wav")
                
                except Exception as e:
                    print(f"❌ エラー: {time_block} - {str(e)}")
                    errors.append(f"{time_block}.wav")
        
        # ローカルに存在する全てのJSONファイルをEC2にアップロード
        uploaded = []
        upload_errors = []
        
        # ローカルJSONファイルを確認
        local_json_files = glob.glob(os.path.join(output_dir, "*.json"))
        
        print(f"\n=== アップロード前状況確認 ===")
        print(f"📝 アップロード対象: {len(processed)} ファイル (新規 + 既存)")
        print(f"❌ 音声取得エラー: {len(errors)} ファイル") 
        print(f"📁 ローカル存在: {len(local_json_files)} ファイル")
        print(f"=" * 50)
        
        if local_json_files:
            print(f"\n=== EC2へのアップロード開始 ===")
            print(f"アップロード対象: {len(local_json_files)} ファイル")
            print(f"=" * 50)
            
            # SSL検証をスキップするコネクターを作成（EC2アップロード用）
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                for json_path in local_json_files:
                    try:
                        json_filename = os.path.basename(json_path)
                        time_block = json_filename.replace('.json', '')
                        
                        # JSONファイルをEC2にアップロード
                        print(f"🚀 アップロード開始: {json_filename}")
                        print(f"📁 ローカルファイルパス: {json_path}")
                        print(f"📏 ファイルサイズ: {os.path.getsize(json_path)} bytes")
                        
                        with open(json_path, 'rb') as f:
                            data = aiohttp.FormData()
                            # ファイル本体
                            data.add_field(
                                "file", 
                                f, 
                                filename=f"{time_block}.json",
                                content_type="application/json"
                            )
                            # 保存先情報を指定
                            data.add_field("device_id", device_id)
                            data.add_field("date", date)
                            data.add_field("time_block", time_block)
                            
                            print(f"📤 POST送信先: https://api.hey-watch.me/upload-transcription")
                            print(f"📋 ファイル名: {time_block}.json")
                            print(f"📱 デバイスID: {device_id}")
                            print(f"📅 対象日付: {date}")
                            print(f"🕒 時間ブロック: {time_block}")
                            
                            async with session.post("https://api.hey-watch.me/upload-transcription", data=data) as upload_response:
                                response_text = await upload_response.text()
                                print(f"📡 レスポンスステータス: {upload_response.status}")
                                print(f"📄 レスポンス本文: {response_text}")
                                print(f"🏷️ レスポンスヘッダー: {dict(upload_response.headers)}")
                                
                                if upload_response.status == 200:
                                    uploaded.append(json_filename)
                                    print(f"✅ アップロード成功: {json_filename}")
                                    
                                    # アップロード直後の検証
                                    print(f"🔍 アップロード後検証開始: {json_filename}")
                                    await asyncio.sleep(1)  # サーバー処理待ち
                                    
                                    verify_url = f"https://api.hey-watch.me/download?device_id={device_id}&date={date}&slot={time_block}&type=json"
                                    try:
                                        async with session.get(verify_url) as verify_response:
                                            if verify_response.status == 200:
                                                verify_content = await verify_response.text()
                                                print(f"✅ 検証成功: {json_filename} - EC2で確認済み")
                                                print(f"   - ファイルサイズ: {len(verify_content)} bytes")
                                            else:
                                                print(f"⚠️ 検証失敗: {json_filename} - EC2で見つからない")
                                                print(f"   - 検証ステータス: {verify_response.status}")
                                    except Exception as verify_error:
                                        print(f"❌ 検証エラー: {json_filename} - {str(verify_error)}")
                                    
                                else:
                                    upload_errors.append(json_filename)
                                    print(f"❌ アップロード失敗: {json_filename}")
                                    print(f"   - ステータスコード: {upload_response.status}")
                                    print(f"   - エラー詳細: {response_text}")
                    
                    except Exception as e:
                        upload_errors.append(json_filename)
                        print(f"❌ アップロード例外エラー: {json_filename}")
                        print(f"   - エラータイプ: {type(e).__name__}")
                        print(f"   - エラー詳細: {str(e)}")
                        print(f"   - ファイル存在確認: {os.path.exists(json_path)}")
                        if os.path.exists(json_path):
                            print(f"   - ファイルサイズ: {os.path.getsize(json_path)} bytes")
            
            print(f"\n=== EC2アップロード完了 ===")
            print(f"🚀 アップロード成功: {len(uploaded)} ファイル")
            print(f"❌ アップロード失敗: {len(upload_errors)} ファイル")
            print(f"=" * 50)
        
        # ローカルに残っている未送信JSONファイルを確認
        print(f"\n=== ローカルファイル状況確認 ===")
        print(f"📁 ローカルディレクトリ: {output_dir}")
        print(f"📄 ローカルJSONファイル数: {len(local_json_files)}")
        
        if local_json_files:
            for json_file in sorted(local_json_files):
                filename = os.path.basename(json_file)
                file_size = os.path.getsize(json_file)
                upload_status = "✅ アップロード済み" if filename in uploaded else "❌ 未アップロード"
                print(f"   - {filename}: {file_size} bytes ({upload_status})")
        
        print(f"=" * 50)
        
        print(f"\n=== 一括取得・文字起こし・アップロード完了 ===")
        print(f"📥 音声取得成功: {len(fetched)} ファイル")
        print(f"📝 アップロード対象: {len(processed)} ファイル (新規 + 既存)")
        print(f"🚀 アップロード成功: {len(uploaded)} ファイル")
        print(f"❌ 音声取得エラー: {len(errors)} ファイル")
        print(f"❌ アップロードエラー: {len(upload_errors)} ファイル")
        print(f"📄 ローカル残存JSONファイル: {len(local_json_files)} ファイル")
        print(f"=" * 50)
        
        return {
            "status": "success",
            "fetched": fetched,
            "processed": processed,
            "uploaded": uploaded,
            "errors": errors,
            "upload_errors": upload_errors,
            "local_files": [os.path.basename(f) for f in local_json_files],
            "local_file_count": len(local_json_files),
            "verification_note": "アップロード検証を実行済み - ログを確認してください"
        }


if __name__ == "__main__":
    # WatchMeプロジェクトのポート配置に合わせてポート8001を使用
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True) 