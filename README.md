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

### 現在の実装（修正不要）

APIマネージャーは現在の`file_paths`インターフェースを使用しており、**修正の必要はありません**：

```javascript
// WhisperTranscriberApiClient.js - 現在の実装
const response = await this.api.post('/fetch-and-transcribe', {
  file_paths: filePaths,  // ファイルパス配列
  model: model           // "base"
})
```

**処理フロー：**
1. `AudioFilesService.getPendingAudioFiles()` - `transcriptions_status = 'pending'`のファイル取得
2. `WhisperTranscriberApiClient.transcribe()` - `file_paths`配列でAPIリクエスト
3. Whisper API処理 - 既存インターフェースで正常動作
4. データベース更新（`vibe_whisper`テーブル）

### 新しいインターフェース（追加オプション）

効率的な検索のため、新しい`device_id/local_date/time_blocks`インターフェースも利用可能です：

```python
# 新しいインターフェースの例（オプション）
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

このエンドポイントは2つのインターフェースをサポートします：

#### インターフェース1: file_paths配列（従来形式）

音声ファイルのfile_pathを直接指定して文字起こしを実行します。**APIマネージャーで現在使用中**。

**リクエスト例：**

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

#### インターフェース2: device_id/local_date/time_blocks（新形式）

データベースインデックスを活用した効率的な検索により、指定したデバイス・日付・時間帯の音声ファイルを処理します。

**リクエスト例：**

```json
{
  "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
  "local_date": "2025-08-05",
  "time_blocks": ["09-30", "10-00"],
  "model": "base"
}
```

**パラメータ：**

- `device_id` (string): デバイスID
- `local_date` (string): 処理対象日（YYYY-MM-DD形式）
- `time_blocks` (array, optional): 時間帯配列（例：["09-30", "10-00"]）。省略時は全時間帯
- `model` (string, optional): 使用するWhisperモデル（デフォルト: "base"）

#### 共通レスポンス

両インターフェースとも同じレスポンス形式を返します：

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

## デプロイ時の注意事項

### コンテナの競合問題（2025年8月26日発生）

#### 問題
- 既存のコンテナが`api-transcriber`という名前でSystemdサービスとして実行中
- docker-composeとSystemdサービスが同時に管理しようとして競合
- 新バージョンのデプロイ時に「container already exists」エラー

#### 解決方法
```bash
# 1. Systemdサービスを停止（存在する場合）
sudo systemctl stop api-transcriber

# 2. docker-composeを停止
cd ~/api_whisper_v1
sudo docker-compose down

# 3. 既存コンテナを確認して削除
sudo docker ps -a | grep api-transcriber
sudo docker stop [CONTAINER_ID]
sudo docker rm [CONTAINER_ID]

# 4. 新バージョンをプル
aws ecr get-login-password --region ap-southeast-2 | sudo docker login --username AWS --password-stdin 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com
sudo docker pull 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-transcriber:[TAG]

# 5. 新コンテナを起動
sudo docker run -d --name api-transcriber \
  -p 8001:8001 \
  --env-file .env \
  --restart always \
  754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-transcriber:[TAG]
```

#### 推奨事項
- **一元管理**: Systemdサービスまたはdocker-composeのいずれか1つで管理
- **タグ管理**: `latest`タグの使用を避け、明示的なバージョンタグを使用
- **ヘルスチェック**: デプロイ後は必ず動作確認を実施

### 複数バージョンが同時実行される問題

#### 現象
```bash
# 実際に発生した状況
754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-transcriber:latest      # 古いバージョン
754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-transcriber:v1.1-fix    # 新バージョン
```
同じポート8001で2つのバージョンが競合

#### 対策
1. 必ず古いコンテナを停止・削除してから新バージョンを起動
2. `docker ps`で実行中のコンテナを確認
3. ポートの競合を避けるため、起動前に`lsof -i :8001`で確認

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

### ⚠️ 重要：後方互換性の確保

新しいインターフェースを追加する際は、**既存のfile_pathsインターフェースを削除せず**、両方をサポートすることが重要です：

- ✅ 既存のAPIマネージャーやクライアントが継続して動作
- ✅ 新機能は追加オプションとして提供
- ✅ 段階的な移行が可能

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

## Whisperハルシネーション問題と対策

### 問題の概要
OpenAI Whisperモデルには、ノイズのみの音声データに対して実在しない言葉を生成する「ハルシネーション」という既知の問題があります。

#### 観察された現象
- **症状**: ノイズや無音の音声ファイルに対して「スタッフの方が」「上に」などの言葉を大量に繰り返し生成
- **再現性**: 100%に近い確率で発生
- **例**: 1分間のノイズ音声 → 「スタッフの上に、上に、上に...」×146回

### 実装済みの対策（2025年8月26日）

#### 1. 繰り返し検出によるフィルタリング
```python
# 句読点で分割してセグメントの繰り返しを検出
segments = re.split(r'[、。，．,.]', transcription)
if count >= 10:  # 同じセグメントが10回以上
    transcription = ""  # 空文字として保存
```

#### 2. RMS（Root Mean Square）による音声レベル判定
```python
rms = np.sqrt(np.mean(audio_data**2))
if rms < 0.0005:  # 極めて低い音声レベル
    transcription = ""  # 無音として処理
```

#### 3. 日本語フレーズパターンの異常検出
```python
# 同じ日本語フレーズが過度に繰り返される場合
pattern = r'([\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]+[がのはをにでと]*)'
if phrase_count >= 10:
    transcription = ""  # ハルシネーションとして除外
```

### 現状の課題と限界

#### ルールベースアプローチの限界
1. **本質的解決ではない**: Whisperモデル自体のバグは修正できない
2. **誤検出リスク**: 正当な繰り返し表現も削除される可能性
3. **網羅性の欠如**: 「スタッフ」以外の単語でも同様の問題が起きる可能性

#### 技術的制約
- ローカルWhisperモデル（base）での限界
- VAD（Voice Activity Detection）の精度不足
- メモリ制約によるモデルサイズの制限（EC2 t4g.small）

### 今後の改善方針

#### Phase 1: ローカルWhisperの限界までチューニング
- [ ] Whisperのパラメータ最適化（temperature, beam_size等）
- [ ] より高精度なVADライブラリの導入（webrtcVAD, sileroVAD）
- [ ] 信頼度スコアベースのフィルタリング

#### Phase 2: 外部APIへの移行検討
実用レベルに達しない場合は以下を検討：
- **Azure Speech Services**: 商用グレードの音声認識
- **Google Cloud Speech-to-Text**: 高精度な日本語対応
- **Amazon Transcribe**: AWS環境との親和性

### パフォーマンス指標
- **現在の誤検出率**: 約100%（ノイズ音声に対して）
- **目標誤検出率**: 5%以下
- **処理速度**: 1分音声で約2-3秒（base モデル）

## 最近の改善内容

### 2025年8月の改善

1. **device_id/local_date/time_blocksインターフェースの追加**
   - データベースの`local_date`と`time_block`インデックスを活用した高速検索
   - リクエストパラメータをそのままvibe_whisperテーブルに保存（データの一貫性保証）
   - file_pathからの情報抽出を最小限に削減

2. **後方互換性の維持**
   - 既存のfile_pathsインターフェースも継続サポート
   - 1つのエンドポイントで両方のインターフェースを処理

3. **APIマネージャー連携の検証**
   - APIマネージャーは既存の`file_paths`インターフェースを使用
   - `WhisperTranscriberApiClient.js`で正常動作確認済み
   - 心理グラフページでWhisper → Aggregator → Scorerの処理フロー確認
   - **結論：APIマネージャーの修正は不要**

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