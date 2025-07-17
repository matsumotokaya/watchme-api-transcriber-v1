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
import time
from typing import List, Dict, Set

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

async def check_existing_data_in_supabase(device_id: str, date: str) -> Set[str]:
    """Supabaseで既に処理済みのtime_blockを確認"""
    try:
        response = supabase.table('vibe_whisper').select('time_block').eq('device_id', device_id).eq('date', date).execute()
        existing_time_blocks = {item['time_block'] for item in response.data}
        logger.info(f"Supabaseチェック完了: {len(existing_time_blocks)}件の処理済みデータを発見")
        return existing_time_blocks
    except Exception as e:
        logger.error(f"Supabaseチェックエラー: {str(e)}")
        return set()

async def check_audio_exists_in_vault(session: aiohttp.ClientSession, device_id: str, date: str, time_blocks: List[str]) -> Dict[str, bool]:
    """Vault APIで音声データの存在を確認（GETリクエストでステータスコードのみ確認）"""
    audio_exists = {}
    
    # 並列でチェックするためのタスクを作成
    async def check_single_slot(time_block: str) -> tuple:
        url = f"https://api.hey-watch.me/download?device_id={device_id}&date={date}&slot={time_block}"
        try:
            # GETリクエストでステータスコードのみ確認（データは読まない）
            async with session.get(url) as response:
                exists = response.status == 200
                # データを読み込んで破棄（接続を正常に閉じるため）
                if exists:
                    await response.read()
                return time_block, exists
        except Exception as e:
            logger.error(f"Vault API確認エラー ({time_block}): {str(e)}")
            return time_block, False
    
    # 並列実行
    tasks = [check_single_slot(tb) for tb in time_blocks]
    results = await asyncio.gather(*tasks)
    
    for time_block, exists in results:
        audio_exists[time_block] = exists
    
    existing_count = sum(1 for exists in audio_exists.values() if exists)
    logger.info(f"Vault APIチェック完了: {existing_count}/{len(time_blocks)}件の音声データが存在")
    
    return audio_exists

@app.post("/fetch-and-transcribe")
async def fetch_and_transcribe(request: FetchAndTranscribeRequest):
    """WatchMeシステムのメイン処理エンドポイント（性能改善版）"""
    start_time = time.time()
    
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
    all_time_blocks = []
    for hour in range(24):
        for minute in ["00", "30"]:
            all_time_blocks.append(f"{hour:02d}-{minute}")
    
    # Step 1: Supabaseで処理済みデータをチェック
    existing_in_db = await check_existing_data_in_supabase(request.device_id, request.date)
    
    # 未処理のスロットを特定
    unprocessed_blocks = [tb for tb in all_time_blocks if tb not in existing_in_db]
    
    if not unprocessed_blocks:
        execution_time = time.time() - start_time
        return {
            "status": "success",
            "device_id": request.device_id,
            "date": request.date,
            "summary": {
                "total_slots": len(all_time_blocks),
                "skipped_as_processed_in_db": len(existing_in_db),
                "skipped_as_no_audio_in_vault": 0,
                "successfully_transcribed": 0,
                "errors": 0
            },
            "processed_blocks": [],
            "execution_time_seconds": round(execution_time, 1),
            "message": "全てのスロットが既に処理済みです"
        }
    
    # Step 2: Vault APIで音声データの存在を確認
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        audio_exists = await check_audio_exists_in_vault(session, request.device_id, request.date, unprocessed_blocks)
    
    # 音声データが存在するスロットのみを処理対象とする
    blocks_to_process = [tb for tb in unprocessed_blocks if audio_exists.get(tb, False)]
    blocks_no_audio = [tb for tb in unprocessed_blocks if not audio_exists.get(tb, False)]
    
    if not blocks_to_process:
        execution_time = time.time() - start_time
        return {
            "status": "success",
            "device_id": request.device_id,
            "date": request.date,
            "summary": {
                "total_slots": len(all_time_blocks),
                "skipped_as_processed_in_db": len(existing_in_db),
                "skipped_as_no_audio_in_vault": len(blocks_no_audio),
                "successfully_transcribed": 0,
                "errors": 0
            },
            "processed_blocks": [],
            "execution_time_seconds": round(execution_time, 1),
            "message": "処理対象となる新規音声データがありません"
        }
    
    # Step 3: 実際の音声ダウンロードと文字起こし処理
    # 処理結果を記録
    successfully_transcribed = []
    error_blocks = []
    
    # SSLを無効化してaiohttp接続を設定
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        for time_block in blocks_to_process:
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
                            
                            # Supabaseに保存（空の文字起こし結果も保存）
                            data = {
                                "device_id": request.device_id,
                                "date": request.date,
                                "time_block": time_block,
                                "transcription": transcription if transcription else ""
                            }
                            
                            # upsert（既存データは更新、新規データは挿入）
                            response = supabase.table('vibe_whisper').upsert(data).execute()
                            
                            successfully_transcribed.append(time_block)
                            logger.info(f"✅ {time_block}: 文字起こし完了・Supabase保存済み")
                        
                        finally:
                            # 一時ファイルを削除
                            if os.path.exists(tmp_file_path):
                                os.unlink(tmp_file_path)
                    
                    else:
                        # 想定外のエラー（音声存在チェックは通ったが取得失敗）
                        error_msg = f"{time_block}: HTTPエラー {response.status}"
                        logger.error(f"❌ {error_msg}")
                        error_blocks.append(time_block)
            
            except Exception as e:
                logger.error(f"❌ {time_block}: エラー - {str(e)}")
                error_blocks.append(time_block)
    
    # 処理結果を返す
    execution_time = time.time() - start_time
    
    return {
        "status": "success",
        "device_id": request.device_id,
        "date": request.date,
        "summary": {
            "total_slots": len(all_time_blocks),
            "skipped_as_processed_in_db": len(existing_in_db),
            "skipped_as_no_audio_in_vault": len(blocks_no_audio),
            "successfully_transcribed": len(successfully_transcribed),
            "errors": len(error_blocks)
        },
        "processed_blocks": successfully_transcribed,
        "error_blocks": error_blocks if error_blocks else None,
        "execution_time_seconds": round(execution_time, 1)
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