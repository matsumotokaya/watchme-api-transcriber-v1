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
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
# ⚠️ 警告: baseモデル以外を使用すると、EC2（t4g.small）のメモリ上限を超えてクラッシュします！
# モデル変更時は必ずEC2インスタンスのスケールアップとセットで実施してください
# - small以上: t3.medium（4GB RAM）以上が必要
# - medium以上: t3.large（8GB RAM）以上が必要
# - large: t3.xlarge（16GB RAM）以上が必要
models["base"] = whisper.load_model("base")
print("Whisper baseモデル読み込み完了（サーバーリソース制約により固定）")

# リクエストボディのモデル
class FetchAndTranscribeRequest(BaseModel):
    device_id: str
    date: str
    model: str = "base"  # baseモデルのみサポート

@app.post("/fetch-and-transcribe")
async def fetch_and_transcribe(request: FetchAndTranscribeRequest):
    """WatchMeシステムのメイン処理エンドポイント"""
    
    # サポートされているモデルの確認
    if request.model not in ["base"]:
        raise HTTPException(
            status_code=400,
            detail=f"サポートされていないモデル: {request.model}. 対応モデル: base. "
                   f"⚠️ 警告: 他のモデルを使用するとメモリ不足でEC2がクラッシュします！"
                   f"モデル変更にはEC2インスタンスのスケールアップが必要です。"
        )
    
    # Whisperモデルを選択
    whisper_model = models.get(request.model)
    if not whisper_model:
        raise HTTPException(
            status_code=500,
            detail=f"モデル {request.model} が読み込まれていません"
        )
    
    # 時間スロットを生成（00-00から23-30まで）
    time_blocks = []
    for hour in range(24):
        for minute in ["00", "30"]:
            time_blocks.append(f"{hour:02d}-{minute}")
    
    # 処理結果を記録
    fetched_files = []
    processed_files = []
    saved_to_supabase = []
    skipped_files = []
    errors = []
    
    # SSLを無効化してaiohttp接続を設定
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        for time_block in time_blocks:
            try:
                # Vault APIから音声ファイルを取得
                url = f"https://api.hey-watch.me/download?device_id={request.device_id}&date={request.date}&slot={time_block}"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        # 音声データを一時ファイルに保存
                        audio_data = await response.read()
                        
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                            tmp_file.write(audio_data)
                            tmp_file_path = tmp_file.name
                        
                        try:
                            # Whisperで文字起こし
                            result = whisper_model.transcribe(tmp_file_path, language="ja")
                            transcription = result["text"].strip()
                            
                            if transcription:
                                # Supabaseに保存
                                data = {
                                    "device_id": request.device_id,
                                    "date": request.date,
                                    "time_block": time_block,
                                    "transcription": transcription
                                }
                                
                                # upsert（既存データは更新、新規データは挿入）
                                response = supabase.table('vibe_whisper').upsert(data).execute()
                                
                                fetched_files.append(f"{time_block}.wav")
                                processed_files.append(time_block)
                                saved_to_supabase.append(time_block)
                                logger.info(f"✅ {time_block}: 文字起こし完了・Supabase保存済み")
                            else:
                                logger.info(f"⏭️ {time_block}: 無音または文字起こし結果なし")
                                skipped_files.append(f"{time_block}.wav")
                        
                        finally:
                            # 一時ファイルを削除
                            if os.path.exists(tmp_file_path):
                                os.unlink(tmp_file_path)
                    
                    elif response.status == 404:
                        # ファイルが存在しない（測定されていない時間）
                        logger.info(f"⏭️ {time_block}: データなし（404）")
                        skipped_files.append(f"{time_block}.wav")
                    else:
                        error_msg = f"{time_block}: HTTPエラー {response.status}"
                        logger.error(f"❌ {error_msg}")
                        errors.append(error_msg)
            
            except Exception as e:
                error_msg = f"{time_block}: エラー - {str(e)}"
                logger.error(f"❌ {error_msg}")
                errors.append(error_msg)
    
    # 処理結果を返す
    return {
        "status": "success",
        "fetched": fetched_files,
        "processed": processed_files,
        "saved_to_supabase": saved_to_supabase,
        "skipped": skipped_files,
        "errors": errors,
        "summary": {
            "total_time_blocks": len(time_blocks),
            "audio_fetched": len(fetched_files),
            "supabase_saved": len(saved_to_supabase),
            "skipped_existing": len(skipped_files),
            "errors": len(errors)
        }
    }

@app.get("/")
def read_root():
    return {
        "name": "Whisper API for WatchMe",
        "version": "1.0.0",
        "description": "音声文字起こしAPI - Supabase統合版",
        "endpoints": {
            "main": "/fetch-and-transcribe",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)