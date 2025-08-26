from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, model_validator
import tempfile
import os
import whisper
import uvicorn
import json
from datetime import datetime
import aiohttp
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
import time
from typing import List, Dict, Set, Optional
import boto3
from botocore.exceptions import ClientError
import numpy as np
import soundfile as sf
import re
from collections import Counter

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
    # 新しいインターフェース
    device_id: Optional[str] = None  # デバイスID
    local_date: Optional[str] = None  # 日付（YYYY-MM-DD形式）
    time_blocks: Optional[List[str]] = None  # 特定の時間ブロック（指定しない場合は全時間帯）
    
    # 既存のインターフェース（後方互換性）
    file_paths: Optional[List[str]] = None  # 直接file_pathを指定
    
    # 共通パラメータ
    model: str = "base"  # baseモデルのみサポート
    
    @model_validator(mode='after')
    def validate_request(self):
        # どちらかのインターフェースが必要
        if self.device_id and self.local_date:
            # 新インターフェース
            return self
        elif self.file_paths:
            # 既存インターフェース
            return self
        else:
            raise ValueError("device_id + local_date または file_paths のどちらかを指定してください")


@app.post("/fetch-and-transcribe")
async def fetch_and_transcribe(request: FetchAndTranscribeRequest):
    """WatchMeシステムのメイン処理エンドポイント（device_id/local_date/time_blocks対応版）"""
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
    
    # リクエストの処理
    if request.device_id and request.local_date:
        # 新しいインターフェース: device_id + local_date + time_blocks
        logger.info(f"新インターフェース使用: device_id={request.device_id}, local_date={request.local_date}, time_blocks={request.time_blocks}")
        
        # audio_filesテーブルから該当するファイルを検索
        query = supabase.table('audio_files') \
            .select('file_path, device_id, recorded_at, local_date, time_block, transcriptions_status') \
            .eq('device_id', request.device_id) \
            .eq('local_date', request.local_date) \
            .eq('transcriptions_status', 'pending')
        
        # time_blocksが指定されている場合はフィルタを追加
        if request.time_blocks:
            query = query.in_('time_block', request.time_blocks)
        
        # クエリ実行
        try:
            response = query.execute()
            audio_files = response.data
            logger.info(f"audio_filesテーブルから{len(audio_files)}件のファイルを取得")
        except Exception as e:
            logger.error(f"audio_filesテーブルのクエリエラー: {str(e)}")
            raise HTTPException(status_code=500, detail=f"データベースクエリエラー: {str(e)}")
        
        # file_pathsリストを構築
        file_paths = [file['file_path'] for file in audio_files]
        
        if not file_paths:
            execution_time = time.time() - start_time
            return {
                "status": "success",
                "summary": {
                    "total_files": 0,
                    "already_completed": 0,
                    "pending_processed": 0,
                    "errors": 0
                },
                "device_id": request.device_id,
                "local_date": request.local_date,
                "time_blocks_requested": request.time_blocks,
                "processed_time_blocks": [],
                "execution_time_seconds": round(execution_time, 1),
                "message": "処理対象のファイルがありません（全て処理済みまたは該当なし）"
            }
    
    elif request.file_paths:
        # 既存のインターフェース: file_pathsを直接指定
        logger.info(f"既存インターフェース使用: file_paths={len(request.file_paths)}件")
        file_paths = request.file_paths
        audio_files = None  # 後方互換性のため
    
    else:
        # ここに来ることはない（model_validatorで検証済み）
        raise HTTPException(
            status_code=400,
            detail="device_id + local_dateまたはfile_pathsのどちらかを指定してください"
        )
    
    if not file_paths:
        # file_pathsが空の場合は、処理対象なしとして正常終了
        execution_time = time.time() - start_time
        
        return {
            "status": "success",
            "summary": {
                "total_files": 0,
                "already_completed": 0,
                "pending_processed": 0,
                "errors": 0
            },
            "processed_files": [],
            "execution_time_seconds": round(execution_time, 1),
            "message": "処理対象のファイルがありません"
        }
    
    logger.info(f"処理対象: {len(file_paths)}件のファイル")
    
    # 処理対象ファイルの情報を構築
    files_to_process = []
    device_ids = set()
    dates = set()
    
    # 新インターフェースの場合
    if audio_files:
        for audio_file in audio_files:
            files_to_process.append({
                'file_path': audio_file['file_path'],
                'device_id': audio_file['device_id'],
                'local_date': audio_file['local_date'],
                'time_block': audio_file['time_block']
            })
            device_ids.add(audio_file['device_id'])
            dates.add(audio_file['local_date'])
    
    # 既存インターフェースの場合（file_pathから情報を抽出）
    else:
        for file_path in file_paths:
            # file_pathから情報を抽出
            # 例: files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-19/14-30/audio.wav
            parts = file_path.split('/')
            if len(parts) >= 5:
                device_id = parts[1]  # d067d407-cf73-4174-a9c1-d91fb60d64d0
                date_part = parts[2]  # 2025-07-19
                time_part = parts[3]  # 14-30
                
                device_ids.add(device_id)
                dates.add(date_part)
                
                files_to_process.append({
                    'file_path': file_path,
                    'device_id': device_id,
                    'local_date': date_part,
                    'time_block': time_part
                })
    
    # 実際の音声ダウンロードと文字起こし処理
    # 処理結果を記録
    successfully_transcribed = []
    error_files = []
    
    for audio_file in files_to_process:
        try:
            file_path = audio_file['file_path']
            # 新インターフェースの場合は既に情報があるので、抽出不要
            time_block = audio_file['time_block']
            local_date = audio_file['local_date']
            device_id = audio_file['device_id']
            
            # 一時ファイルに音声データをダウンロード
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_file_path = tmp_file.name
                
                try:
                    # S3からファイルをダウンロード（file_pathをそのまま使用）
                    s3_client.download_file(s3_bucket_name, file_path, tmp_file_path)
                    
                    # 音声ファイルを読み込んで分析
                    try:
                        audio_data, sample_rate = sf.read(tmp_file_path)
                        
                        # 音声のRMS（Root Mean Square）を計算して無音判定
                        rms = np.sqrt(np.mean(audio_data**2))
                        
                        # 無音の閾値（実験的に調整が必要）
                        silence_threshold = 0.0005  # より厳しい閾値に変更
                        
                        if rms < silence_threshold:
                            logger.info(f"🔇 無音検出: RMS={rms:.6f} < {silence_threshold}")
                            transcription = ""  # 無音の場合は空文字
                        else:
                            # Whisperで文字起こし
                            result = whisper_model.transcribe(tmp_file_path, language="ja")
                            transcription = result["text"].strip()
                            
                            # ハルシネーション検出（同じフレーズの繰り返し）
                            if transcription:
                                # 句読点で分割してセグメントを抽出
                                segments = re.split(r'[、。，．,.]', transcription)
                                segments = [s.strip() for s in segments if s.strip()]
                                
                                if segments:
                                    # セグメントの繰り返しを検出
                                    segment_counts = Counter(segments)
                                    most_common_segment, count = segment_counts.most_common(1)[0]
                                    
                                    # 同じセグメントが10回以上繰り返される場合はハルシネーション
                                    if count >= 10:
                                        logger.warning(f"⚠️ ハルシネーション検出: '{most_common_segment}'が{count}回繰り返し")
                                        transcription = ""  # ハルシネーションの場合は空文字
                                    # 同じセグメントが全体の70%以上を占める場合もハルシネーション
                                    elif len(segments) >= 5 and count >= len(segments) * 0.7:
                                        logger.warning(f"⚠️ ハルシネーション検出: '{most_common_segment}'が全体の{count/len(segments)*100:.1f}%")
                                        transcription = ""  # ハルシネーションの場合は空文字
                                
                                # 短いフレーズパターンの検出（日本語対応）
                                if transcription:  # まだ空でない場合
                                    # 日本語のフレーズパターンを抽出
                                    pattern = r'([\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]+[がのはをにでと]*)'
                                    phrases = re.findall(pattern, transcription)
                                    if phrases:
                                        phrase_counts = Counter(phrases)
                                        for phrase, count in phrase_counts.items():
                                            if len(phrase) >= 2 and count >= 10:
                                                logger.warning(f"⚠️ フレーズの過度な繰り返し検出: '{phrase}'が{count}回")
                                                transcription = ""  # 繰り返しの場合は空文字
                                                break
                            
                            # ログレベルの確認（no_speech_probが高い場合）
                            if 'no_speech_prob' in result and result['no_speech_prob'] > 0.9:
                                logger.info(f"📊 高い無音確率: no_speech_prob={result['no_speech_prob']:.2f}")
                                if not transcription or len(transcription) < 5:
                                    transcription = ""  # 無音確率が高く短いテキストは無視
                    
                    except Exception as audio_error:
                        logger.error(f"音声分析エラー: {str(audio_error)}")
                        # 音声分析に失敗した場合は通常のWhisper処理にフォールバック
                        result = whisper_model.transcribe(tmp_file_path, language="ja")
                        transcription = result["text"].strip()
                    
                    # vibe_whisperテーブルに保存（空の文字起こし結果も保存）
                    data = {
                        "device_id": device_id,
                        "date": local_date,  # リクエストから受け取った日付をそのまま使用
                        "time_block": time_block,
                        "transcription": transcription if transcription else ""
                    }
                    
                    # upsert（既存データは更新、新規データは挿入）
                    response = supabase.table('vibe_whisper').upsert(data).execute()
                    
                    # ■■■ START: 詳細なデバッグログを追加 ■■■
                    # Supabaseからの応答を詳細にログ出力
                    logger.info(f"Supabase upsert response data: {response.data}")
                    logger.info(f"Supabase upsert response count: {response.count}")
                    
                    # 応答にエラーが含まれていないか、データが空でないかを確認
                    if not response.data:
                        logger.error("❌ Supabase returned an empty response or an error.")
                        logger.error(f"   - Full response object: {response}")
                        # エラーとして扱い、処理を中断
                        raise Exception("Supabase upsert failed with empty response.")
                    # ■■■ END: 詳細なデバッグログを追加 ■■■
                    
                    # audio_filesテーブルのtranscriptions_statusをcompletedに更新
                    # file_pathで直接更新する（シンプルで正確）
                    try:
                        update_response = supabase.table('audio_files') \
                            .update({'transcriptions_status': 'completed'}) \
                            .eq('file_path', file_path) \
                            .execute()
                        
                        # 更新が成功したかチェック
                        if update_response.data:
                            logger.info(f"✅ audio_filesテーブルのステータス更新成功: {len(update_response.data)}件更新")
                            logger.info(f"   file_path: {file_path}")
                        else:
                            logger.warning(f"⚠️ audio_filesテーブルのステータス更新: 対象レコードが見つかりません")
                            logger.warning(f"   file_path: {file_path}")
                            
                    except Exception as update_error:
                        logger.error(f"❌ audio_filesテーブルのステータス更新エラー: {str(update_error)}")
                        logger.error(f"   file_path: {file_path}")
                    
                    successfully_transcribed.append({
                        'file_path': file_path,
                        'time_block': time_block
                    })
                    logger.info(f"✅ {file_path}: 文字起こし完了・Supabase保存済み")
                
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
    
    # レスポンスの構築（インターフェースによって異なる）
    if request.device_id and request.local_date:
        # 新インターフェースのレスポンス
        return {
            "status": "success",
            "summary": {
                "total_files": len(file_paths),
                "pending_processed": len(successfully_transcribed),
                "errors": len(error_files)
            },
            "device_id": request.device_id,
            "local_date": request.local_date,
            "time_blocks_requested": request.time_blocks,
            "processed_time_blocks": [f['time_block'] for f in successfully_transcribed],
            "error_time_blocks": [f['time_block'] for f in error_files] if error_files else None,
            "execution_time_seconds": round(execution_time, 1),
            "message": f"{len(file_paths)}件中{len(successfully_transcribed)}件を正常に処理しました"
        }
    else:
        # 既存インターフェースのレスポンス（後方互換性）
        return {
            "status": "success",
            "summary": {
                "total_files": len(file_paths),
                "pending_processed": len(successfully_transcribed),
                "errors": len(error_files)
            },
            "processed_files": [f['file_path'] for f in successfully_transcribed],
            "processed_time_blocks": [f['time_block'] for f in successfully_transcribed],
            "error_files": [f['file_path'] for f in error_files] if error_files else None,
            "execution_time_seconds": round(execution_time, 1),
            "message": f"{len(file_paths)}件中{len(successfully_transcribed)}件を正常に処理しました"
        }

@app.get("/")
def read_root():
    return {
        "name": "Whisper API for WatchMe",
        "version": "2.0.0",
        "description": "音声文字起こしAPI - Supabase統合版（local_date/time_block対応）",
        "endpoints": {
            "main": "/fetch-and-transcribe",
            "docs": "/docs"
        },
        "parameters": {
            "device_id": "デバイスID（必須）",
            "local_date": "日付 YYYY-MM-DD形式（必須）",
            "time_blocks": "時間ブロックのリスト（オプション、省略時は全時間帯）",
            "model": "Whisperモデル（デフォルト: base）"
        },
        "features": [
            "local_date/time_blockベースの効率的な処理",
            "Supabaseインデックスを活用した高速検索",
            "S3とSupabaseの統合",
            "バッチ処理サポート"
        ]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)