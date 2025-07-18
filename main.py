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
import boto3
from botocore.exceptions import ClientError

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

# AWS S3クライアントの初期化
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
s3_bucket_name = os.getenv('S3_BUCKET_NAME', 'watchme-vault')
aws_region = os.getenv('AWS_REGION', 'us-east-1')

if not aws_access_key_id or not aws_secret_access_key:
    raise ValueError("AWS_ACCESS_KEY_IDおよびAWS_SECRET_ACCESS_KEYが設定されていません")

s3_client = boto3.client(
    's3',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region
)
print(f"AWS S3接続設定完了: バケット={s3_bucket_name}, リージョン={aws_region}")

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
    file_paths: List[str] = None  # オプション: 処理対象のfile_pathリスト

async def get_audio_files_from_supabase(device_id: str, date: str, status_filter: str = 'pending') -> List[Dict]:
    """Supabaseのaudio_filesテーブルから該当日の音声ファイル情報を取得"""
    try:
        # recorded_atの日付部分でフィルタリング
        query = supabase.table('audio_files') \
            .select('*') \
            .eq('device_id', device_id) \
            .gte('recorded_at', f"{date}T00:00:00") \
            .lt('recorded_at', f"{date}T23:59:59")
        
        # ステータスフィルタが指定されている場合は適用
        if status_filter:
            query = query.eq('transcriptions_status', status_filter)
            
        response = query.execute()
        
        if status_filter:
            logger.info(f"audio_filesテーブルから{len(response.data)}件の{status_filter}ステータスの音声ファイルを発見")
        else:
            logger.info(f"audio_filesテーブルから{len(response.data)}件の音声ファイルを発見")
        return response.data
    except Exception as e:
        logger.error(f"audio_filesテーブルの取得エラー: {str(e)}")
        return []

def extract_time_block_from_path(file_path: str) -> str:
    """file_pathからtime_blockを抽出"""
    # 例: files/device_id/2025-07-18/21-00/audio.wav → 21-00
    parts = file_path.split('/')
    if len(parts) >= 4:
        return parts[-2]  # time_block部分を取得
    return None

@app.post("/fetch-and-transcribe")
async def fetch_and_transcribe(request: FetchAndTranscribeRequest):
    """WatchMeシステムのメイン処理エンドポイント（audio_filesテーブル経由版）"""
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
    
    # audio_filesテーブルから未処理（pending）の音声ファイルを取得
    pending_files = await get_audio_files_from_supabase(request.device_id, request.date, 'pending')
    
    # 全ての音声ファイルを取得（統計情報用）
    all_files = await get_audio_files_from_supabase(request.device_id, request.date, None)
    
    # completedステータスのファイル数を計算
    completed_count = len([f for f in all_files if f['transcriptions_status'] == 'completed'])
    
    if not pending_files:
        execution_time = time.time() - start_time
        return {
            "status": "success",
            "device_id": request.device_id,
            "date": request.date,
            "summary": {
                "total_files": len(all_files),
                "already_completed": completed_count,
                "pending_processed": 0,
                "errors": 0
            },
            "processed_files": [],
            "execution_time_seconds": round(execution_time, 1),
            "message": f"処理対象となる音声ファイルがありません（全{len(all_files)}件中{completed_count}件が処理済み）"
        }
    
    # pendingステータスのファイルをすべて処理対象とする
    files_to_process = pending_files
    
    # 実際の音声ダウンロードと文字起こし処理
    # 処理結果を記録
    successfully_transcribed = []
    error_files = []
    
    for audio_file in files_to_process:
        try:
            file_path = audio_file['file_path']
            time_block = extract_time_block_from_path(file_path)
            
            if not time_block:
                logger.error(f"time_blockの抽出に失敗: {file_path}")
                error_files.append(audio_file)
                continue
            
            # 一時ファイルに音声データをダウンロード
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_file_path = tmp_file.name
                
                try:
                    # S3からファイルをダウンロード（file_pathをそのまま使用）
                    s3_client.download_file(s3_bucket_name, file_path, tmp_file_path)
                    
                    # Whisperで文字起こし
                    result = whisper_model.transcribe(tmp_file_path, language="ja")
                    transcription = result["text"].strip()
                    
                    # vibe_whisperテーブルに保存（空の文字起こし結果も保存）
                    data = {
                        "device_id": request.device_id,
                        "date": request.date,
                        "time_block": time_block,
                        "transcription": transcription if transcription else ""
                    }
                    
                    # upsert（既存データは更新、新規データは挿入）
                    response = supabase.table('vibe_whisper').upsert(data).execute()
                    
                    # audio_filesテーブルのtranscriptions_statusをcompletedに更新
                    update_response = supabase.table('audio_files') \
                        .update({'transcriptions_status': 'completed'}) \
                        .eq('device_id', audio_file['device_id']) \
                        .eq('recorded_at', audio_file['recorded_at']) \
                        .execute()
                    
                    successfully_transcribed.append({
                        'file_path': file_path,
                        'time_block': time_block,
                        'recorded_at': audio_file['recorded_at']
                    })
                    logger.info(f"✅ {file_path}: 文字起こし完了・Supabase保存済み・ステータス更新済み")
                
                finally:
                    # 一時ファイルを削除
                    if os.path.exists(tmp_file_path):
                        os.unlink(tmp_file_path)
        
        except ClientError as e:
            error_msg = f"{audio_file['file_path']}: S3エラー - {str(e)}"
            logger.error(f"❌ {error_msg}")
            error_files.append(audio_file)
        
        except Exception as e:
            logger.error(f"❌ {audio_file['file_path']}: エラー - {str(e)}")
            error_files.append(audio_file)
    
    # 処理結果を返す
    execution_time = time.time() - start_time
    
    return {
        "status": "success",
        "device_id": request.device_id,
        "date": request.date,
        "summary": {
            "total_files": len(all_files),
            "already_completed": completed_count,
            "pending_processed": len(successfully_transcribed),
            "errors": len(error_files)
        },
        "processed_files": [f['file_path'] for f in successfully_transcribed],
        "processed_time_blocks": [f['time_block'] for f in successfully_transcribed],
        "error_files": [f['file_path'] for f in error_files] if error_files else None,
        "execution_time_seconds": round(execution_time, 1),
        "message": f"pendingステータスの{len(pending_files)}件中{len(successfully_transcribed)}件を正常に処理しました"
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