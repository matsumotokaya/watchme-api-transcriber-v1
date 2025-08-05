# Whisper API - 音声文字起こしAPI

WatchMeプラットフォーム用の音声文字起こしAPI。OpenAI Whisperを使用して音声ファイルをテキストに変換します。

**⚠️ 重要**: このAPIは行動グラフ、感情グラフなど他のAPIのリファレンス実装となっています。

## 概要

このAPIは、S3に保存された音声ファイルをダウンロードし、OpenAI Whisperモデルを使用してテキストに変換します。変換結果はSupabaseデータベースに保存され、処理ステータスが更新されます。

### 主な特徴

- **効率的なデータベース検索**: `local_date`と`time_block`インデックスを活用
- **データの一貫性保証**: リクエストパラメータを直接データベースに保存
- **後方互換性**: 既存の`file_paths`インターフェースもサポート

## 本番環境エンドポイント

- **Gateway経由**: `https://api.hey-watch.me/vibe-transcriber/`
- **内部ポート**: `8001`

## 🔄 APIマネージャーからの呼び出し方

APIマネージャーからこのAPIを呼び出す際は、新しいインターフェースを使用してください：

```python
# APIマネージャーからの呼び出し例
requests.post(
    "https://api.hey-watch.me/vibe-transcriber/fetch-and-transcribe",
    json={
        "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
        "local_date": "2025-08-05",
        "time_blocks": ["09-30", "10-00"],  # 省略可
        "model": "base"
    }
)
```

## APIエンドポイント

### POST /fetch-and-transcribe

音声ファイルのfile_pathを直接指定して文字起こしを実行します。

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
  created_at timestamp WITH TIME ZONE DEFAULT now(),
  behavior_features_status text DEFAULT 'pending',
  emotion_features_status text DEFAULT 'pending',
  local_date date,
  time_block varchar(5),
  PRIMARY KEY (device_id, recorded_at)
);

-- インデックス
CREATE INDEX idx_audio_files_device_date ON audio_files(device_id, local_date);
CREATE INDEX idx_audio_files_device_date_block ON audio_files(device_id, local_date, time_block);
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

## Git 運用ルール（ブランチベース開発フロー）

このプロジェクトでは、**ブランチベースの開発フロー**を採用しています。  
main ブランチで直接開発せず、以下のルールに従って作業を進めてください。

---

### 🔹 運用ルール概要

1. `main` ブランチは常に安定した状態を保ちます（リリース可能な状態）。
2. 開発作業はすべて **`feature/xxx` ブランチ** で行ってください。
3. 作業が完了したら、GitHub上で Pull Request（PR）を作成し、差分を確認した上で `main` にマージしてください。
4. **1人開発の場合でも、必ずPRを経由して `main` にマージしてください**（レビューは不要、自分で確認＆マージOK）。

---

### 🔧 ブランチ運用の手順

#### 1. `main` を最新化して作業ブランチを作成
```bash
git checkout main
git pull origin main
git checkout -b feature/機能名
```

#### 2. 作業内容をコミット
```bash
git add .
git commit -m "変更内容の説明"
```

#### 3. リモートにプッシュしてPR作成
```bash
git push origin feature/機能名
# GitHub上でPull Requestを作成
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

**注意**: APIサーバーはフォアグラウンドで実行されます。テストを実行する場合は、別のターミナルウィンドウを開いてテストスクリプトを実行してください。

バックグラウンドで起動する場合:
```bash
nohup python3 main.py > api.log 2>&1 &
# ログを確認: tail -f api.log
# プロセスを停止: pkill -f "python3 main.py"
```

## デプロイ

### 推奨デプロイフロー（ECRベース）

ECR（Elastic Container Registry）を使用したデプロイ方法が推奨です：

#### ステップ1: DockerイメージをビルドしてECRにプッシュ

```bash
# スクリプトを実行（TAGは省略可能、デフォルトは "latest"）
# 例: ./build-and-push-ecr.sh v1.2
./build-and-push-ecr.sh [TAG]
```

このスクリプトは、内部で `docker build` を実行し、AWS ECRにログイン後、イメージをプッシュします。

#### ステップ2: 新しいイメージをEC2にデプロイ

```bash
# スクリプトを実行（TAGはステップ1で指定したものと同じものを指定）
# 例: ./deploy-ecr.sh v1.2
./deploy-ecr.sh [TAG]
```

このスクリプトは、内部で以下の処理を自動的に行います：
1. `systemd/api-transcriber.service` ファイルをEC2にアップロード
2. SSHでEC2に接続
3. 古いDockerコンテナを停止・削除
4. ECRから新しいバージョンのイメージをプル
5. Systemdサービスをリロードし、新しいコンテナでサービスを起動
6. サービスの稼働状態とヘルスチェックを実行

#### サーバーでのサービス管理 (Systemd)

本番EC2サーバー上では、`api-transcriber.service` という名前でサービスが管理されています（注：`api-wisper.service`ではありません）。

```bash
# サービスの状態確認
sudo systemctl status api-transcriber

# サービスの起動 / 停止 / 再起動
sudo systemctl start api-transcriber
sudo systemctl stop api-transcriber
sudo systemctl restart api-transcriber

# ログの確認（リアルタイム）
sudo journalctl -u api-transcriber -f

# サービスの自動起動設定
sudo systemctl enable api-transcriber   # 有効化
sudo systemctl disable api-transcriber  # 無効化
```

#### ECRリポジトリ情報

- リポジトリ: `754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-transcriber`
- リージョン: `ap-southeast-2`

### ローカル開発環境での起動

ローカルでの開発やテストには `docker-compose` を使用します。

```bash
# .env ファイルを準備した後、コンテナをビルドして起動
docker-compose up --build -d

# ログの確認
docker-compose logs -f

# 停止
docker-compose down
```

## 動作テスト

### テストスクリプトの実行

```bash
# APIを起動した後、テストスクリプトを実行
python3 test_api.py

# CSVデータを使用したテスト
python3 test_with_csv.py        # audio_files_rows.csvを使用
python3 test_with_csv_new.py    # audio_files_rows (1).csvを使用
```

### ローカル環境でのテスト

```bash
# ヘルスチェック
curl http://localhost:8001/

# 文字起こしAPIテスト
curl -X POST "http://localhost:8001/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
      "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-19/14-30/audio.wav"
    ],
    "model": "base"
  }'
```

### 本番環境でのテスト

```bash
# ヘルスチェック
curl https://api.hey-watch.me/vibe-transcriber/

# 文字起こしAPIテスト（Gateway経由）
curl -X POST "https://api.hey-watch.me/vibe-transcriber/fetch-and-transcribe" \
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
- 1分の音声ファイルの処理時間は約2-3秒（大きなファイルの場合は処理時間が長くなる可能性があります）

## トラブルシューティング

### 処理がタイムアウトに見える場合

APIリクエストがタイムアウトしても、バックグラウンドで処理は継続されています。以下の点を確認してください：

1. **Dockerログの確認**
   ```bash
   docker logs api_whisper_v1 --tail 100
   ```

2. **Whisperモデルの初回ダウンロード**
   - コンテナ初回起動時、Whisperモデル（約139MB）のダウンロードが発生します
   - Dockerfileに事前ダウンロードの設定を追加済みですが、イメージの再ビルドが必要です

3. **デバッグログの活用**
   - Supabaseへの書き込み結果を詳細にログ出力するようになっています
   - `Supabase upsert response data`でデータベースへの書き込み成功を確認できます

### 2025年8月の改善

1. **device_id/local_date/time_blocksインターフェースの追加**
   - データベースの`local_date`と`time_block`インデックスを活用した高速検索
   - リクエストパラメータをそのままvibe_whisperテーブルに保存（データの一貫性保証）
   - file_pathからの情報抽出を最小限に削減

2. **後方互換性の維持**
   - 既存のfile_pathsインターフェースも継続サポート
   - 1つのエンドポイントで両方のインターフェースを処理

3. **テストでの検証済み**
   - 新インターフェース: 2025-08-05の09-30, 10-30のデータで正常動作確認
   - 既存インターフェース: 後方互換性を維持

### よくある問題と解決策

1. **「サイレントフェイラー」に見える現象**
   - 症状：APIログでは成功と表示されるが、データベースにデータがない
   - 原因：多くの場合、処理中または別のデータを確認している
   - 解決：処理完了まで待ち、正しいタイムブロックのデータを確認

2. **処理時間の長さ**
   - 原因：音声ファイルのサイズ、Whisperモデルの処理負荷
   - 対策：タイムアウト値を延長するか、非同期処理として扱う

3. **日付の確認**
   - vibe_whisperテーブルの日付は正しく保存されます
   - タイムゾーンはUTCで統一されています

## 🎯 他のAPIへの適用ガイド

この実装パターンは、行動グラフAPI、感情グラフAPIなど、同様の構造を持つ他のAPIにも適用できます。

### 修正のポイント

1. **リクエストモデルの変更**
   ```python
   # 新しいインターフェースを追加
   device_id: Optional[str] = None
   local_date: Optional[str] = None
   time_blocks: Optional[List[str]] = None
   
   # 既存のインターフェースを保持
   file_paths: Optional[List[str]] = None
   ```

2. **データベース検索の変更**
   ```python
   # audio_filesテーブルから検索
   query = supabase.table('audio_files') \
       .select('file_path, device_id, local_date, time_block') \
       .eq('device_id', request.device_id) \
       .eq('local_date', request.local_date) \
       .eq('ステータスカラム名', 'pending')
   ```

3. **データ保存の一貫性**
   ```python
   # リクエストパラメータを直接使用
   data = {
       "device_id": device_id,
       "date": local_date,  # リクエストから受け取った値を使用
       "time_block": time_block,
       "結果カラム": result
   }
   ```

4. **インデックスの活用**
   - `idx_audio_files_device_date`
   - `idx_audio_files_device_date_block`

### 各APIでの変更箇所

| API | ステータスカラム | 結果テーブル | 結果カラム |
|-----|--------------|------------|----------|
| Whisper API | transcriptions_status | vibe_whisper | transcription |
| 行動グラフAPI | behavior_features_status | vibe_behavior | behavior_data |
| 感情グラフAPI | emotion_features_status | vibe_emotion | emotion_data |

## 最近の改善内容

### 2025年8月の改善

1. **device_id/local_date/time_blocksインターフェースの追加**
   - データベースの`local_date`と`time_block`インデックスを活用した高速検索
   - リクエストパラメータをそのままvibe_whisperテーブルに保存（データの一貫性保証）
   - file_pathからの情報抽出を最小限に削減

2. **後方互換性の維持**
   - 既存のfile_pathsインターフェースも継続サポート
   - 1つのエンドポイントで両方のインターフェースを処理

### 2025年7月の改善

1. **デバッグログの追加**
   - Supabaseへの書き込み応答を詳細にログ出力
   - 空のレスポンスの場合はエラーとして扱うように改善
   ```python
   logger.info(f"Supabase upsert response data: {response.data}")
   logger.info(f"Supabase upsert response count: {response.count}")
   ```

2. **Dockerfileの最適化**
   - Whisperモデルをビルド時に事前ダウンロード
   - コンテナ再起動時のモデル再ダウンロードを防止
   ```dockerfile
   RUN python -c "import whisper; whisper.load_model('base')"
   ```

3. **エラーハンドリングの強化**
   - Supabaseからの空レスポンスを検出
   - 処理失敗時の詳細なエラー情報を記録

4. **ドキュメントの充実**
   - 本番環境のエンドポイント情報を追加
   - systemdサービス名の正確な記載
   - トラブルシューティングセクションの追加