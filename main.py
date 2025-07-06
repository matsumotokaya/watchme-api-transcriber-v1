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
from supabase import create_client, Client
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

app = FastAPI(title="Whisper API for WatchMe", description="WatchMe統合システム用Whisper音声文字起こしAPI - Supabase連携専用")

# Supabaseクライアントの初期化
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URLおよびSUPABASE_KEYが設定されていません")

supabase: Client = create_client(supabase_url, supabase_key)
print(f"Supabase接続設定完了: {supabase_url}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Whisperモデルをグローバルで管理
print("Whisperモデルを読み込み中...")
models = {}
# 標準モデル（medium）を初期ロード
models["medium"] = whisper.load_model("medium")
print("Whisper mediumモデル読み込み完了（標準）")

# リクエストボディのモデル
class FetchAndTranscribeRequest(BaseModel):
    device_id: str
    date: str
    model: str = "medium"  # デフォルトはmedium、large指定可能

# モデル取得関数
def get_whisper_model(model_name: str = "medium"):
    """
    指定されたWhisperモデルを取得、未ロードの場合は動的ロード
    """
    if model_name not in ["medium", "large"]:
        raise HTTPException(status_code=400, detail=f"サポートされていないモデル: {model_name}. 対応モデル: medium, large")
    
    if model_name not in models:
        print(f"Whisper {model_name}モデルを読み込み中...")
        models[model_name] = whisper.load_model(model_name)
        print(f"Whisper {model_name}モデル読み込み完了")
    
    return models[model_name]


@app.post("/fetch-and-transcribe")
async def fetch_and_transcribe(request: FetchAndTranscribeRequest):
    """
    指定されたデバイス・日付の.wavファイルをAPIから取得し、一括文字起こしを行う
    """
    device_id = request.device_id
    date = request.date
    model_name = request.model
    
    # 指定されたWhisperモデルを取得
    whisper_model = get_whisper_model(model_name)
    
    print(f"Supabaseへの直接保存モードで実行中")
    
    # 一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"\n=== 一括取得・文字起こし開始 ===")
        print(f"デバイスID: {device_id}")
        print(f"対象日付: {date}")
        print(f"Whisperモデル: {model_name}")
        print(f"保存先: Supabase transcriptions テーブル")
        print(f"=" * 50)
        
        fetched = []
        processed = []
        skipped = []
        errors = []
        saved_to_supabase = []
        
        # 時間ブロックのリスト（00-00から23-30まで）
        # 重要: ほとんどの時間スロットではデータが存在しないのが正常
        time_blocks = [f"{hour:02d}-{minute:02d}" for hour in range(24) for minute in [0, 30]]
        
        # SSL検証をスキップするコネクターを作成（音声ファイル取得用）
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            for time_block in time_blocks:
                try:
                    print(f"📝 処理開始: {time_block}")
                    
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
                            result = whisper_model.transcribe(temp_file)
                            transcription = result["text"]
                            
                            # Supabaseに直接保存
                            try:
                                supabase_data = {
                                    "device_id": device_id,
                                    "date": date,
                                    "time_block": time_block,
                                    "transcription": transcription
                                }
                                
                                supabase_result = supabase.table('vibe_whisper').insert(supabase_data).execute()
                                
                                if supabase_result.data:
                                    print(f"💾 Supabase保存完了: {time_block}")
                                    print(f"📄 文字起こし結果: {len(transcription)} 文字")
                                    saved_to_supabase.append(f"{time_block}")
                                    processed.append(f"{time_block}")
                                    print(f"✅ 完了: {time_block} ({len(transcription)} 文字)")
                                else:
                                    print(f"❌ Supabase保存失敗: {time_block}")
                                    errors.append(f"{time_block}")
                                    
                            except Exception as supabase_error:
                                print(f"❌ Supabase保存エラー: {time_block} - {str(supabase_error)}")
                                errors.append(f"{time_block}")
                            
                        else:
                            if response.status == 404:
                                # 404は正常な動作: 測定されていない時間スロットでは音声データが存在しない
                                print(f"⏭️ データなし: {time_block}.wav (測定されていません)")
                                skipped.append(f"{time_block}.wav")
                            else:
                                print(f"❌ 取得失敗: {time_block}.wav (ステータス: {response.status})")
                                errors.append(f"{time_block}.wav")
                
                except Exception as e:
                    print(f"❌ エラー: {time_block} - {str(e)}")
                    errors.append(f"{time_block}.wav")
        
        print(f"\n=== 一括取得・文字起こし・Supabase保存完了 ===")
        print(f"📥 音声取得成功: {len(fetched)} ファイル")
        print(f"📝 処理対象: {len(processed)} ファイル")
        print(f"💾 Supabase保存成功: {len(saved_to_supabase)} ファイル")
        print(f"⏭️ スキップ: {len([s for s in skipped if not s.endswith('.wav')])} ファイル (既存データ)")
        print(f"📭 データなし: {len([s for s in skipped if s.endswith('.wav')])} ファイル (測定なし)")
        print(f"❌ エラー: {len(errors)} ファイル")
        print(f"=" * 50)
        
        return {
            "status": "success",
            "fetched": fetched,
            "processed": processed,
            "saved_to_supabase": saved_to_supabase,
            "skipped": skipped,
            "errors": errors,
            "summary": {
                "total_time_blocks": len(time_blocks),
                "audio_fetched": len(fetched),
                "supabase_saved": len(saved_to_supabase),
                "skipped_existing": len(skipped),
                "errors": len(errors)
            }
        }


if __name__ == "__main__":
    # WatchMeプロジェクトのポート配置に合わせてポート8001を使用
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True) 