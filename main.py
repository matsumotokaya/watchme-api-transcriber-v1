from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import tempfile
import os
import whisper
import uvicorn
from typing import Dict, List
import shutil
import json
from datetime import datetime
import glob
import aiohttp
import asyncio
from pathlib import Path

app = FastAPI(title="Whisper API for WatchMe", description="WatchMe統合システム用Whisper音声文字起こしAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静的ファイルを提供するためのマウント
app.mount("/static", StaticFiles(directory="static"), name="static")

# Whisperモデルをグローバルで一度だけ読み込む
print("Whisperモデルを読み込み中...")
model = whisper.load_model("large")
print("Whisperモデル読み込み完了")

# リクエストボディのモデル
class BatchTranscribeRequest(BaseModel):
    device_id: str
    date: str = None  # オプション: YYYY-MM-DD形式。指定しない場合は当日

class FetchAndTranscribeRequest(BaseModel):
    device_id: str
    date: str

# 既存システムとの互換性のための /transcribe エンドポイント
@app.post("/transcribe", response_model=Dict[str, str])
async def transcribe_audio(file: UploadFile = File(...)):
    """
    WatchMeシステム互換の単体ファイル文字起こしエンドポイント
    """
    # ファイル形式のチェック
    allowed_extensions = [".m4a", ".mp3", ".wav"]
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"サポートされていないファイル形式です。対応形式: {', '.join(allowed_extensions)}"
        )
    
    # 一時ファイルを作成して音声を保存
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
            
        # Whisperでの文字起こし処理
        result = model.transcribe(temp_path)
        transcription = result["text"]
        
        # 一時ファイルの削除
        os.unlink(temp_path)
        
        # WatchMeシステム互換の形式で返却
        return {"transcript": transcription}
    
    except Exception as e:
        # エラーが発生した場合も一時ファイルを削除
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(status_code=500, detail=f"処理中にエラーが発生しました: {str(e)}")
    
    finally:
        # ファイルを閉じる
        file.file.close()

# 従来の /analyze/whisper エンドポイントも維持
@app.post("/analyze/whisper", response_model=Dict[str, str])
async def analyze_audio(file: UploadFile = File(...)):
    """
    従来のAnalyze形式エンドポイント
    """
    # ファイル形式のチェック
    allowed_extensions = [".m4a", ".mp3", ".wav"]
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"サポートされていないファイル形式です。対応形式: {', '.join(allowed_extensions)}"
        )
    
    # 一時ファイルを作成して音声を保存
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
            
        # Whisperでの文字起こし処理
        result = model.transcribe(temp_path)
        transcription = result["text"]
        
        # 一時ファイルの削除
        os.unlink(temp_path)
        
        return {"transcription": transcription}
    
    except Exception as e:
        # エラーが発生した場合も一時ファイルを削除
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(status_code=500, detail=f"処理中にエラーが発生しました: {str(e)}")
    
    finally:
        # ファイルを閉じる
        file.file.close()

@app.post("/batch-transcribe")
async def batch_transcribe(request: BatchTranscribeRequest):
    """
    指定されたユーザーの指定日（または当日）フォルダ内の全.wavファイルを一括文字起こし
    """
    device_id = request.device_id
    
    # 日付の設定（指定されていない場合は当日）
    if request.date:
        target_date = request.date
    else:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    # 入力ディレクトリのパス
    input_dir = f"/Users/kaya.matsumoto/data/data_accounts/{device_id}/{target_date}/raw"
    
    # 出力ディレクトリのパス
    output_dir = f"/Users/kaya.matsumoto/data/data_accounts/{device_id}/{target_date}/transcriptions"
    
    # 入力ディレクトリが存在するかチェック
    if not os.path.exists(input_dir):
        raise HTTPException(
            status_code=404, 
            detail=f"ディレクトリが見つかりません: {input_dir}"
        )
    
    # 出力ディレクトリを作成（存在しない場合）
    os.makedirs(output_dir, exist_ok=True)
    
    # .wavファイルを取得してソート
    wav_files = glob.glob(os.path.join(input_dir, "*.wav"))
    wav_files.sort()  # ファイル名の昇順でソート
    
    total_files = len(wav_files)
    print(f"\n=== 一括文字起こし開始 ===")
    print(f"デバイスID: {device_id}")
    print(f"対象日付: {target_date}")
    print(f"対象ディレクトリ: {input_dir}")
    print(f"出力ディレクトリ: {output_dir}")
    print(f"処理対象ファイル数: {total_files}")
    print(f"=" * 50)
    
    if total_files == 0:
        print("⚠️  処理対象の.wavファイルが見つかりませんでした")
        return {
            "status": "success",
            "processed": [],
            "skipped": [],
            "total_files": 0,
            "message": "処理対象ファイルが見つかりませんでした"
        }
    
    processed = []
    skipped = []
    
    for index, wav_file in enumerate(wav_files, 1):
        try:
            # ファイル名から時間ブロックを抽出（例: 00-00.wav → 00-00）
            filename = os.path.basename(wav_file)
            time_block = os.path.splitext(filename)[0]
            
            print(f"📝 [{index:2d}/{total_files:2d}] 処理中: {filename} → {time_block}.json")
            
            # 出力ファイルパス
            output_file = os.path.join(output_dir, f"{time_block}.json")
            
            # Whisperで文字起こし
            result = model.transcribe(wav_file)
            transcription = result["text"]
            
            # JSONデータを作成
            transcription_data = {
                "time_block": time_block,
                "transcription": transcription
            }
            
            # JSONファイルに保存
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(transcription_data, f, ensure_ascii=False, indent=2)
            
            processed.append(time_block)
            print(f"✅ [{index:2d}/{total_files:2d}] 完了: {time_block} ({len(transcription)} 文字)")
            
        except Exception as e:
            print(f"❌ [{index:2d}/{total_files:2d}] エラー: {filename} - {str(e)}")
            skipped.append(time_block)
    
    print(f"\n=== 一括文字起こし完了 ===")
    print(f"✅ 処理済み: {len(processed)} ファイル")
    print(f"❌ スキップ: {len(skipped)} ファイル")
    print(f"📊 成功率: {len(processed)}/{total_files} ({len(processed)/total_files*100:.1f}%)")
    print(f"=" * 50)
    
    return {
        "status": "success",
        "processed": processed,
        "skipped": skipped,
        "total_files": total_files,
        "success_rate": f"{len(processed)}/{total_files} ({len(processed)/total_files*100:.1f}%)"
    }

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

@app.get("/verify-ec2-upload/{device_id}/{date}/{time_block}")
async def verify_ec2_upload(device_id: str, date: str, time_block: str):
    """
    EC2側でファイルが正しく保存されているかを確認
    """
    # EC2上での期待保存場所
    expected_path = f"/home/ubuntu/data/data_accounts/{device_id}/{date}/transcriptions/{time_block}.json"
    
    try:
        # EC2の/downloadエンドポイントを使ってファイル存在確認
        verify_url = f"https://api.hey-watch.me/download?device_id={device_id}&date={date}&slot={time_block}&type=json"
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(verify_url) as response:
                if response.status == 200:
                    content = await response.text()
                    return {
                        "status": "found",
                        "device_id": device_id,
                        "date": date,
                        "time_block": time_block,
                        "expected_path": expected_path,
                        "file_exists": True,
                        "content_size": len(content),
                        "content_preview": content[:200] + "..." if len(content) > 200 else content
                    }
                else:
                    return {
                        "status": "not_found",
                        "device_id": device_id,
                        "date": date,
                        "time_block": time_block,
                        "expected_path": expected_path,
                        "file_exists": False,
                        "http_status": response.status,
                        "error_message": await response.text()
                    }
    except Exception as e:
        return {
            "status": "error",
            "device_id": device_id,
            "date": date,
            "time_block": time_block,
            "expected_path": expected_path,
            "error": str(e)
        }

@app.get("/check-local-files/{device_id}/{date}")
async def check_local_files(device_id: str, date: str):
    """
    指定されたデバイス・日付のローカルJSONファイル状況を確認
    """
    output_dir = f"/Users/kaya.matsumoto/data/data_accounts/{device_id}/{date}/transcriptions"
    
    if not os.path.exists(output_dir):
        return {
            "status": "directory_not_found",
            "directory": output_dir,
            "files": []
        }
    
    local_json_files = glob.glob(os.path.join(output_dir, "*.json"))
    file_info = []
    
    for json_file in sorted(local_json_files):
        filename = os.path.basename(json_file)
        file_size = os.path.getsize(json_file)
        file_mtime = datetime.fromtimestamp(os.path.getmtime(json_file)).strftime("%Y-%m-%d %H:%M:%S")
        
        # JSONファイルの内容を簡易チェック
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
                is_valid = "time_block" in content and "transcription" in content
                transcription_length = len(content.get("transcription", ""))
        except Exception as e:
            is_valid = False
            transcription_length = 0
            
        file_info.append({
            "filename": filename,
            "size_bytes": file_size,
            "modified_time": file_mtime,
            "is_valid_json": is_valid,
            "transcription_length": transcription_length
        })
    
    return {
        "status": "success",
        "directory": output_dir,
        "total_files": len(file_info),
        "files": file_info
    }

@app.get("/")
async def redirect_to_index():
    # ルートURLにアクセスした場合、静的ファイルのindex.htmlにリダイレクト
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")

@app.get("/batch-verify-ec2/{device_id}/{date}")
async def batch_verify_ec2(device_id: str, date: str):
    """
    指定されたデバイス・日付の全ファイルのEC2保存状況を一括確認
    """
    results = []
    not_found_files = []
    found_files = []
    error_files = []
    
    # 48個の時間ブロックを確認
    time_blocks = [f"{hour:02d}-{minute:02d}" for hour in range(24) for minute in [0, 30]]
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        for time_block in time_blocks:
            try:
                verify_url = f"https://api.hey-watch.me/download?device_id={device_id}&date={date}&slot={time_block}&type=json"
                
                async with session.get(verify_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        found_files.append(time_block)
                        results.append({
                            "time_block": time_block,
                            "status": "found",
                            "file_size": len(content),
                            "content_preview": content[:100] + "..." if len(content) > 100 else content
                        })
                    else:
                        not_found_files.append(time_block)
                        results.append({
                            "time_block": time_block,
                            "status": "not_found",
                            "http_status": response.status,
                            "error": await response.text()
                        })
                        
            except Exception as e:
                error_files.append(time_block)
                results.append({
                    "time_block": time_block,
                    "status": "error",
                    "error": str(e)
                })
    
    return {
        "device_id": device_id,
        "date": date,
        "total_blocks": len(time_blocks),
        "found_count": len(found_files),
        "not_found_count": len(not_found_files),
        "error_count": len(error_files),
        "found_files": found_files,
        "not_found_files": not_found_files,
        "error_files": error_files,
        "detailed_results": results
    }

if __name__ == "__main__":
    # WatchMeプロジェクトのポート配置に合わせてポート8001を使用
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True) 