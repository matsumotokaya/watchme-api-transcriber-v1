# API Whisper v1 - 本番環境デプロイメントガイド

## 概要
このドキュメントは、api_wisper_v1をDockerを使用して本番環境にデプロイする手順を説明します。

## 前提条件
- Docker 20.10以上
- Docker Compose v3.8以上
- EC2インスタンス（推奨: t3.large以上、8GB RAM）
- 10GB以上の空きディスク容量

## デプロイ手順

### 1. プロジェクトのクローン
```bash
git clone [your-repository-url]
cd api_wisper_v1
```

### 2. 環境変数の設定
```bash
cp .env.example .env
```

`.env`ファイルを編集して、以下の値を設定：
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
```

### 3. 本番環境向けのコード修正

**重要**: 現在のコードはmacOS開発環境用のため、以下の修正が必要です。

#### main.pyの修正（44行目）
```python
# 開発環境（macOS）
output_dir = f"/Users/kaya.matsumoto/data/data_accounts/{device_id}/{date}/transcriptions"

# 本番環境（EC2/Docker）に変更
output_dir = f"/app/data/data_accounts/{device_id}/{date}/transcriptions"
```

**注意**: 現在のAPIはSupabaseに直接保存するため、この行は実際には使用されていませんが、念のため修正することを推奨します。

### 4. Dockerイメージのビルドと起動
```bash
# イメージのビルド（初回は時間がかかります）
docker-compose build

# バックグラウンドで起動
docker-compose up -d

# ログの確認
docker-compose logs -f
```

### 5. 動作確認
```bash
# ヘルスチェック
curl http://localhost:8001/docs

# APIテスト
curl -X POST "http://localhost:8001/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "your-device-id",
    "date": "2025-07-13",
    "model": "medium"
  }'
```

## Docker設定の詳細

### Dockerfileの特徴
- Python 3.12を使用（開発環境と同じバージョン）
- Whisper mediumモデルを事前ダウンロード（起動時間短縮）
- 非rootユーザーで実行（セキュリティ向上）
- ヘルスチェック機能付き

### docker-compose.ymlの特徴
- メモリ制限: 8GB
- CPU制限: 2コア
- Whisperモデルキャッシュの永続化
- ログローテーション設定
- 自動再起動設定

## メンテナンス

### ログの確認
```bash
docker-compose logs -f whisper-api
```

### コンテナの再起動
```bash
docker-compose restart
```

### アップデート時の手順
```bash
# コンテナを停止
docker-compose down

# 最新コードを取得
git pull

# 再ビルドして起動
docker-compose build
docker-compose up -d
```

### Whisperモデルキャッシュの管理
```bash
# キャッシュサイズの確認
docker volume inspect api_wisper_v1_whisper_cache

# 不要な場合のキャッシュ削除
docker-compose down -v
```

## トラブルシューティング

### メモリ不足エラー
EC2インスタンスのメモリが不足している場合：
1. より大きなインスタンスタイプに変更
2. docker-compose.ymlのmem_limitを調整
3. スワップファイルを作成

### ポート競合
ポート8001が既に使用されている場合：
```bash
# 使用中のプロセスを確認
sudo lsof -i :8001

# docker-compose.ymlのポートマッピングを変更
ports:
  - "8002:8001"  # 外部ポートを8002に変更
```

## セキュリティ注意事項
1. .envファイルは絶対にGitにコミットしない
2. 本番環境では適切なファイアウォール設定を行う
3. HTTPS化を検討（リバースプロキシ使用）
4. Supabaseのキーは定期的にローテーション

## パフォーマンス最適化
1. Whisper largeモデルは必要時のみ使用
2. 定期的なDockerイメージの最適化
3. ログファイルの定期的なクリーンアップ