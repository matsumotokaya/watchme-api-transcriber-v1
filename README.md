# Whisper API for WatchMe - 音声処理APIのリファレンス実装

WatchMeエコシステム専用のWhisper音声文字起こしAPI。**このAPIは他の音声処理APIのお手本となるリファレンス実装です。**

## 🎯 重要：このAPIがリファレンス実装である理由

このAPIは、WatchMeエコシステムにおける音声ファイル処理の標準的な実装パターンを示しています：

1. **file_pathベースの処理**: `recorded_at`ではなく`file_path`を主キーとして使用
2. **ステータス管理**: 処理完了後に`audio_files`テーブルのステータスを更新
3. **シンプルな責務分離**: 音声処理に特化し、ファイル管理はVault APIに委譲

## 🔄 最新アップデート (2025-12-19)

### ⚡ 重要な設計改善: file_pathベースの処理

#### 変更内容
1. **ステータス更新の簡素化**
   - **変更前**: `recorded_at`の時間範囲で複雑な検索を実行
   - **変更後**: `file_path`で直接更新（シンプルで確実）
   
2. **責務の明確化**
   - Whisper API: `file_path`を受け取り、処理し、ステータスを更新
   - Vault API: `recorded_at`を管理し、`file_path`を生成
   
3. **エラー削減**
   - `recorded_at`のフォーマット差異による問題を完全に回避

### 🏗️ アーキテクチャのベストプラクティス

```python
# ❌ 悪い例：recorded_atで複雑な時間範囲検索
update_response = supabase.table('audio_files') \
    .update({'transcriptions_status': 'completed'}) \
    .eq('device_id', device_id) \
    .gte('recorded_at', slot_start) \
    .lte('recorded_at', slot_end) \
    .execute()

# ✅ 良い例：file_pathで直接更新
update_response = supabase.table('audio_files') \
    .update({'transcriptions_status': 'completed'}) \
    .eq('file_path', file_path) \
    .execute()
```

## 📋 他の音声処理APIへの実装ガイド

### 1. 基本的な処理フロー

```python
# Step 1: file_pathsを受け取る
request.file_paths = ["files/device_id/date/time/audio.wav", ...]

# Step 2: 各ファイルを処理
for file_path in request.file_paths:
    # S3からダウンロード
    s3_client.download_file(bucket, file_path, temp_file)
    
    # 音声処理を実行（API固有の処理）
    result = process_audio(temp_file)  # 例：感情分析、音響特徴抽出など
    
    # 結果をSupabaseに保存
    supabase.table('your_table').upsert(result).execute()
    
    # ステータスを更新（重要！）
    supabase.table('audio_files') \
        .update({'your_status_field': 'completed'}) \
        .eq('file_path', file_path) \
        .execute()
```

### 2. ステータスフィールドの命名規則

各APIは`audio_files`テーブルの専用ステータスフィールドを更新します：

- `transcriptions_status`: Whisper API（このAPI）
- `emotion_features_status`: 感情分析API
- `behavior_features_status`: 行動分析API
- など、`{feature}_status`の形式で命名

### 3. エラーハンドリング

```python
try:
    # ステータス更新
    update_response = supabase.table('audio_files') \
        .update({'your_status_field': 'completed'}) \
        .eq('file_path', file_path) \
        .execute()
    
    if update_response.data:
        logger.info(f"✅ ステータス更新成功: {file_path}")
    else:
        logger.warning(f"⚠️ 対象レコードが見つかりません: {file_path}")
        
except Exception as e:
    logger.error(f"❌ ステータス更新エラー: {str(e)}")
    # エラーでも処理は継続
```

## 🚀 APIエンドポイント仕様

### POST /fetch-and-transcribe

#### リクエスト
```json
{
  "file_paths": [
    "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-19/14-30/audio.wav"
  ],
  "model": "base"
}
```

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

## 💾 データベース設計

### audio_filesテーブル（共通）
```sql
CREATE TABLE audio_files (
  device_id text NOT NULL,
  recorded_at timestamp WITH TIME ZONE NOT NULL,
  file_path text UNIQUE NOT NULL,  -- 主キーとして使用
  transcriptions_status text DEFAULT 'pending',
  emotion_features_status text DEFAULT 'pending',
  behavior_features_status text DEFAULT 'pending',
  -- 他のステータスフィールド
);
```

### vibe_whisperテーブル（このAPI固有）
```sql
CREATE TABLE vibe_whisper (
  device_id text NOT NULL,
  date date NOT NULL,
  time_block text NOT NULL,
  transcription text,
  PRIMARY KEY (device_id, date, time_block)
);
```

## 🛠️ 開発環境セットアップ

### 1. 環境変数の設定
```bash
# .envファイルを作成
cat > .env << EOF
# Supabase設定
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# AWS S3設定
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
S3_BUCKET_NAME=watchme-vault
AWS_REGION=us-east-1
EOF
```

### 2. 依存関係のインストール
```bash
# macOS開発環境
python3.12 -m pip install fastapi uvicorn openai-whisper aiohttp boto3 supabase python-dotenv

# Ubuntu本番環境
sudo apt update && sudo apt install -y python3 python3-pip ffmpeg
pip3 install fastapi uvicorn openai-whisper aiohttp boto3 supabase python-dotenv
```

### 3. ローカル起動
```bash
python3.12 main.py
# APIは http://localhost:8001 で起動
```

## 🌐 本番環境デプロイ手順

### 1. EC2インスタンスへのアップロード
```bash
# ローカルでプロジェクトを圧縮
tar -czf api_wisper_v1.tar.gz api_wisper_v1

# EC2にアップロード
scp -i ~/watchme-key.pem api_wisper_v1.tar.gz ubuntu@your-ec2-ip:~/

# EC2で解凍
ssh -i ~/watchme-key.pem ubuntu@your-ec2-ip
tar -xzf api_wisper_v1.tar.gz
cd api_wisper_v1
```

### 2. 環境変数の設定（本番）
```bash
# 本番用の.envファイルを作成
cp .env.example .env
nano .env  # 本番環境の認証情報を設定
```

### 3. Dockerビルドとデプロイ
```bash
# 既存のコンテナを停止
sudo docker-compose down

# 新しいイメージをビルド
sudo docker-compose build

# コンテナを起動
sudo docker-compose up -d

# ログ確認
sudo docker-compose logs -f
```

### 4. systemdサービスの再起動
```bash
# サービスを再起動
sudo systemctl restart api-wisper

# 状態確認
sudo systemctl status api-wisper

# リアルタイムログ
sudo journalctl -u api-wisper -f
```

### 5. 動作確認
```bash
# 本番環境のヘルスチェック
curl https://api.hey-watch.me/vibe-transcriber/

# 本番環境でのテスト
curl -X POST "https://api.hey-watch.me/vibe-transcriber/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
      "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-19/14-30/audio.wav"
    ],
    "model": "base"
  }'
```

## ⚠️ 重要な注意事項

### メモリ制限
- 本番環境（t4g.small, 2GB RAM）では**baseモデルのみ**使用可能
- より大きなモデルを使用する場合はEC2インスタンスのアップグレードが必要

### パフォーマンス
- 1分の音声: 約2-3秒で処理
- 並列処理は実装されていない（メモリ節約のため）

### セキュリティ
- 環境変数で認証情報を管理
- S3へのアクセスはIAMロールで制限
- Supabaseはanon keyを使用（RLSで保護）

## 🔍 トラブルシューティング

### ステータスが更新されない場合
1. `file_path`が正確に一致しているか確認
2. `audio_files`テーブルにレコードが存在するか確認
3. ログでエラーメッセージを確認

### メモリ不足エラー
```bash
# スワップメモリを追加
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## 📞 関連ドキュメント

- [Vault API](../api_vault_v1/README.md) - 音声ファイルのアップロード管理
- [感情分析API](../api_emotion_v1/README.md) - 音声から感情を分析
- [行動分析API](../api_behavior_v1/README.md) - 音声から行動パターンを分析

---

**このAPIは、WatchMeエコシステムにおける音声処理APIの標準的な実装パターンを示すリファレンス実装です。新しい音声処理APIを実装する際は、このREADMEとコードを参考にしてください。**