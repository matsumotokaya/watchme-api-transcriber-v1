# Whisper API - 音声文字起こしAPI

WatchMeプラットフォーム用の音声文字起こしAPI。OpenAI Whisperを使用して音声ファイルをテキストに変換します。

## 概要

このAPIは、S3に保存された音声ファイルをダウンロードし、OpenAI Whisperモデルを使用してテキストに変換します。変換結果はSupabaseデータベースに保存され、処理ステータスが更新されます。

## APIエンドポイント

### POST /fetch-and-transcribe

音声ファイルを取得して文字起こしを実行します。

#### リクエスト

```json
{
  "file_paths": [
    "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-19/14-30/audio.wav"
  ],
  "model": "base"
}
```

#### パラメータ

- `file_paths` (array): 処理する音声ファイルのパス一覧
- `model` (string, optional): 使用するWhisperモデル（デフォルト: "base"）

#### レスポンス

```json
{
  "status": "success",
  "summary": {
    "total_files": 1,
    "pending_processed": 1,
    "errors": 0
  },
  "processed_files": ["files/.../audio.wav"],
  "processed_time_blocks": ["14-30"],
  "error_files": null,
  "execution_time_seconds": 5.3,
  "message": "1件中1件を正常に処理しました"
}
```

## データベース

### audio_filesテーブル

```sql
CREATE TABLE audio_files (
  device_id text NOT NULL,
  recorded_at timestamp WITH TIME ZONE NOT NULL,
  file_path text NOT NULL,
  transcriptions_status text DEFAULT 'pending',
  file_size_bytes bigint,
  duration_seconds numeric,
  created_at timestamp WITH TIME ZONE DEFAULT now(),
  behavior_features_status text DEFAULT 'pending',
  emotion_features_status text DEFAULT 'pending',
  PRIMARY KEY (device_id, recorded_at)
);
```

### vibe_whisperテーブル

```sql
CREATE TABLE vibe_whisper (
  device_id text NOT NULL,
  date date NOT NULL,
  time_block text NOT NULL,
  transcription text,
  PRIMARY KEY (device_id, date, time_block)
);
```

## 環境変数

```bash
# Supabase設定
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# AWS S3設定
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
S3_BUCKET_NAME=watchme-vault
AWS_REGION=us-east-1
```

## セットアップ

### 依存関係のインストール

```bash
python3 -m pip install -r requirements.txt
```

### ローカル起動

```bash
python3 main.py
# APIは http://localhost:8001 で起動
```

## デプロイ

### 本番環境への自動デプロイ

```bash
# 1. プロジェクトを圧縮（親ディレクトリから実行）
cd /Users/kaya.matsumoto
tar -czf api_whisper_v1_updated.tar.gz api_whisper_v1

# 2. デプロイスクリプトを実行
cd api_whisper_v1
./deploy_to_production.sh
```

### ローカル Docker Compose

```bash
# コンテナ起動
docker-compose up -d

# ログ確認
docker-compose logs -f
```

### システムサービス（本番環境）

```bash
# サービス再起動
sudo systemctl restart api-whisper

# 状態確認
sudo systemctl status api-whisper
```

## 動作テスト

```bash
curl -X POST "http://localhost:8001/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
      "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-19/14-30/audio.wav"
    ],
    "model": "base"
  }'
```

## 注意事項

- 本番環境（t4g.small, 2GB RAM）ではbaseモデルのみ使用可能
- より大きなモデルを使用する場合はインスタンスのアップグレードが必要
- 1分の音声ファイルの処理時間は約2-3秒