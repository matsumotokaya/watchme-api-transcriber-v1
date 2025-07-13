# Whisper API for WatchMe - Supabase統合版

WatchMeエコシステム専用のWhisper音声文字起こしAPI。Vault APIからの音声取得とSupabaseへの直接保存により、音声データの取得から文字起こし、結果保存まで一貫した処理を提供します。

## 🔑 重要な特徴

### ✨ 単一エンドポイント設計
- **POST /fetch-and-transcribe** のみ提供
- Vault APIからの音声取得 → 文字起こし → Supabaseへの直接保存を一つの処理で完結
- シンプルで信頼性の高いワークフロー

### 🎯 高精度音声認識
- **Whisper Medium モデル** (769M パラメータ) を標準使用
- **Whisper Large モデル** (1.55B パラメータ) をオプション選択可能
- 精度とパフォーマンスのバランス最適化
- 医療・心理分析用途に最適化

### 🏗️ WatchMeエコシステム統合
- iOS app → Vault API → Whisper API → Supabase の完全な処理チェーン
- デバイスベースの識別システム (device_id)
- 30分間隔の時間スロット処理 (48スロット/日)
- Supabaseへの直接保存でリアルタイムデータアクセス

## 📋 システム要件

### 開発環境 (macOS)
- **Python**: 3.12 (システムPython)
- **メモリ**: 8GB以上推奨
- **ストレージ**: 5GB以上 (Whisperモデル用)

### 本番環境 (EC2)
- **OS**: Ubuntu 20.04/22.04
- **インスタンス**: t3.large以上推奨 (2vCPU, 8GB RAM)
- **メモリ**: 最低4GB、推奨8GB以上
- **ストレージ**: 10GB以上
- **ネットワーク**: Vault API (api.hey-watch.me) への接続

## 💾 容量要件詳細

### APIコード本体
- **サイズ**: 約350KB
- **内容**: Pythonコード、README、設定ファイル
- **注意**: 仮想環境（venv）は**使用しません**

### Whisperモデルキャッシュ
モデルは `~/.cache/whisper/` に自動保存されます：

| モデル | ファイル名 | サイズ | 初回ダウンロード |
|--------|-----------|--------|-----------------|
| **medium** | medium.pt | **1.4GB** | 起動時 |
| **large** | large-v3.pt | **2.9GB** | 初回使用時 |
| **合計** | - | **4.3GB** | - |

### ディスク容量管理
```bash
# APIディレクトリサイズ確認
du -sh /path/to/api_wisper_v1
# → 約350KB（コードのみ）

# Whisperキャッシュ確認
du -sh ~/.cache/whisper/
# → 約4.3GB（2モデル）

# 不要モデル削除（必要に応じて）
rm ~/.cache/whisper/base.pt    # 使用しない場合
rm ~/.cache/whisper/small.pt   # 使用しない場合
```

## 🚀 インストール

### macOS開発環境
```bash
# システムPython環境にインストール
python3.12 -m pip install fastapi uvicorn openai-whisper aiohttp
```

### EC2本番環境
```bash
# システム更新
sudo apt update && sudo apt upgrade -y

# 必要パッケージ
sudo apt install -y python3 python3-pip ffmpeg

# Python依存関係
pip3 install fastapi uvicorn openai-whisper aiohttp
```

## 🎬 使用方法

### サーバー起動
```bash
# 開発環境
python3.12 main.py

# 本番環境
python3 main.py
```

**サーバーURL**: `http://localhost:8001`

### 初回起動について
Whisperモデルの読み込み時間：
- **Medium**: 30秒-1分
- **Large**: 1-3分（初回リクエスト時の動的ロード）

「Whisper medium モデル読み込み完了（標準）」が表示されるまでお待ちください。

## 📡 API仕様

### POST /fetch-and-transcribe

WatchMeシステムのメイン処理エンドポイント。指定デバイス・日付の音声データを一括処理します。

**⚠️ 重要な仕様**:
- **404エラーは正常動作**: 測定されていない時間スロットでは404が返りますが、これはエラーではありません
- **データなし = 正常**: ほとんどの時間スロットではデータが存在しないのが通常の状態です
- **スキップ処理**: 存在しないデータは自動的にスキップされ、存在するデータのみが処理されます

#### リクエスト
```json
{
  "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
  "date": "2025-07-05",
  "model": "medium"
}
```

**パラメータ詳細:**
- `device_id`: デバイス識別子 (必須)
- `date`: 処理対象日付 YYYY-MM-DD形式 (必須)
- `model`: Whisperモデル (オプション、デフォルト: "medium")
  - `"medium"`: 標準モデル (769M、バランス重視)
  - `"large"`: 高精度モデル (1.55B、精度最優先)

#### 処理フロー
1. **モデル選択**: 指定されたWhisperモデル（medium/large）を動的ロード
2. **音声取得**: Vault APIから48個の時間スロット(00-00.wav～23-30.wav)を取得
   - **重要**: 404エラーは正常な動作です（測定されていない時間スロット）
   - 存在するデータのみを処理し、存在しないデータは自動的にスキップされます
3. **文字起こし**: 選択されたWhisperモデルで文字起こし実行
4. **Supabase保存**: 処理結果をSupabaseのvibe_whisperテーブルに直接保存
5. **結果報告**: 処理結果の詳細を返却

#### レスポンス例
```json
{
  "status": "success",
  "fetched": ["18-00.wav", "18-30.wav"],
  "processed": ["18-00", "18-30"],
  "saved_to_supabase": ["18-00", "18-30"],
  "skipped": ["00-00.wav", "00-30.wav", "01-00.wav", "..."],
  "errors": [],
  "summary": {
    "total_time_blocks": 48,
    "audio_fetched": 2,
    "supabase_saved": 2,
    "skipped_existing": 46,
    "errors": 0
  }
}
```

#### 使用例

**標準モデル (medium) の使用:**
```bash
curl -X POST "http://localhost:8001/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
    "date": "2025-07-05"
  }'
```

**高精度モデル (large) の使用:**
```bash
curl -X POST "http://localhost:8001/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
    "date": "2025-07-05",
    "model": "large"
  }'
```

## 📄 出力形式

### Supabaseテーブル構造 (vibe_whisper)
```sql
CREATE TABLE vibe_whisper (
  device_id     text not null,
  date          date not null,
  time_block    text not null check (time_block ~ '^[0-2][0-9]-[0-5][0-9]$'),
  transcription text,
  primary key (device_id, date, time_block)
);
```

### データ保存例
```json
{
  "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
  "date": "2025-07-06",
  "time_block": "18-00",
  "transcription": "おはようございます。今日は良い天気ですね。"
}
```

## ⚙️ Whisperモデル詳細

### 対応モデル
このAPIは2つのWhisperモデルをサポートしています：

#### **Medium モデル (標準)**
- **パラメータ数**: 769M (7.69億)
- **精度**: 高精度
- **処理速度**: 中速
- **メモリ使用量**: ~1.5GB (モデル) + ~1GB (処理)
- **推奨用途**: 標準的な文字起こし、コスト重視

#### **Large モデル (高精度)**
- **パラメータ数**: 1,550M (15.5億)
- **精度**: 最高レベル
- **処理速度**: 低速 (高精度優先)
- **メモリ使用量**: ~3GB (モデル) + ~1-2GB (処理)
- **推奨用途**: 最高精度が必要な医療・研究用途

### モデル比較表
| モデル | パラメータ | 精度 | 速度 | メモリ | コスト | WatchMe対応 |
|--------|-----------|------|------|-------|------|------------|
| tiny | 39M | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ❌ |
| base | 74M | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ |
| small | 244M | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ❌ |
| **medium** | **769M** | **⭐⭐⭐⭐⭐** | **⭐⭐** | **⭐⭐** | **⭐⭐** | **✅ 標準** |
| **large** | **1550M** | **⭐⭐⭐⭐⭐** | **⭐** | **⭐** | **⭐** | **✅ オプション** |

### モデル選択ガイド
- **通常用途**: `medium` (標準、バランス重視)
- **高精度要求**: `large` (医療・研究、精度最優先)
- **リソース制約**: `medium` (メモリ・コスト節約)
- **処理速度重視**: `medium` (約2倍高速)

## 🌐 本番運用 (EC2)

### ⚠️ 本番デプロイ前の必須修正

現在のコードはmacOS開発環境用のため、EC2では以下の修正が必要です：

```python
# main.py の44行目を修正
# 修正前（macOS用）
output_dir = f"/Users/kaya.matsumoto/data/data_accounts/{device_id}/{date}/transcriptions"

# 修正後（EC2用）
output_dir = f"/home/ubuntu/data/data_accounts/{device_id}/{date}/transcriptions"
```

### EC2インスタンス推奨

| インスタンス | vCPU | RAM | 時間コスト | 月額概算 | 推奨モデル | 用途 |
|-------------|------|-----|-----------|----------|-----------|------|
| t3.medium | 2 | 4GB | $0.04 | ~$30 | medium | 軽量テスト |
| t3.large | 2 | 8GB | $0.08 | ~$60 | medium | 開発・小規模 |
| c5.xlarge | 4 | 8GB | $0.17 | ~$125 | medium/large | 標準本番 |
| c5.2xlarge | 8 | 16GB | $0.34 | ~$250 | large | 高精度本番 |

### 💰 コスト最適化案
1. **標準はMediumモデル**: Largeより50%高速、メモリ使用量半減
2. **必要時のみLarge**: 重要データのみ高精度モデル使用
3. **Spot Instance**: 最大90%削減
4. **スケジュール起動**: 夜間停止で30-50%削減

## 🔧 開発者向け情報

### API設計思想
- **単一責任**: 1つのエンドポイントで完結
- **統合優先**: Vaultとの密結合設計
- **エラー透明性**: 詳細なログと状況報告

### デバッグ情報
- **Swagger UI**: `http://localhost:8001/docs`
- **ログ出力**: 処理状況を詳細表示
- **検証機能**: アップロード後の整合性確認

### セキュリティ
- **SSL無効化**: 内部通信用 (aiohttp.TCPConnector(ssl=False))
- **CORS有効**: 開発環境用

## 🔍 トラブルシューティング

### よくある問題

#### 1. メモリ不足
```bash
# エラー例
OutOfMemoryError: CUDA out of memory

# 対処法
- インスタンスサイズ拡大
- 他プロセス停止
- swapファイル作成
```

#### 2. モデル読み込み失敗
```bash
# 対処法
pip3 install --upgrade openai-whisper
python3 -c "import whisper; whisper.load_model('large')"
```

#### 3. 依存関係エラー
```bash
# Ubuntu環境
sudo apt install -y ffmpeg
pip3 install torch torchvision torchaudio
```

#### 4. ポート競合
```bash
# ポート確認
sudo lsof -i :8001

# プロセス終了
sudo kill -9 <PID>
```

## 📊 パフォーマンス

### 処理時間目安

#### Mediumモデル (標準)
- **1分音声**: ~5-8秒
- **30分音声**: ~2.5-4分
- **1日分 (48ファイル)**: ~2-3時間

#### Largeモデル (高精度)
- **1分音声**: ~10-15秒
- **30分音声**: ~5-8分
- **1日分 (48ファイル)**: ~4-6時間

### 最適化のヒント
- **並列処理**: 複数ファイル同時処理 (メモリ許可範囲)
- **キャッシュ**: モデルの永続化
- **バッチサイズ**: メモリ使用量に応じて調整

## 📞 サポート

### システム統合
このAPIはWatchMeエコシステムの一部です：
- **iOS App** → **Vault API** → **Whisper API** → **Supabase** → **分析システム**

### 技術仕様
- **FastAPI**: 0.109.2
- **Whisper**: OpenAI公式実装 (20231117)
- **Python**: 3.12 (システム推奨)
- **Supabase**: 2.13.0

---

**注意**: このAPIはVault連携とSupabase統合専用です。単体ファイル処理や独立利用は想定していません。

## 🚀 本番環境デプロイ手順（EC2 + Docker + systemd）

### 前提条件
- EC2インスタンス（Ubuntu 20.04/22.04）
- t3.large以上推奨（メモリ不足の場合はbaseモデルを使用）
- Docker/Docker Composeインストール済み

### デプロイ手順

#### 1. プロジェクトのアップロード
```bash
# ローカルでプロジェクトを圧縮
tar -czf api_wisper_v1.tar.gz api_wisper_v1

# EC2にアップロード
scp -i ~/your-key.pem api_wisper_v1.tar.gz ubuntu@your-ec2-ip:~/

# EC2で解凍
ssh -i ~/your-key.pem ubuntu@your-ec2-ip
tar -xzf api_wisper_v1.tar.gz
cd api_wisper_v1
```

#### 2. 環境変数の設定
```bash
# .envファイルを作成
cp .env.example .env

# .envファイルを編集
nano .env
# 以下を設定:
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your-supabase-anon-key
```

#### 3. メモリ不足対策（必要な場合）

EC2インスタンスのメモリが少ない場合（2GB以下）、スワップメモリを追加：

```bash
# 2GBのスワップファイルを作成
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 永続化
echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
```

#### 4. Whisperモデルの変更（メモリ制限時）

デフォルトはmediumモデルですが、メモリが限られている場合はbaseモデルに変更：

```bash
# main.pyを編集
sed -i 's/"medium"/"base"/g' main.py
```

#### 5. Dockerイメージのビルドと起動
```bash
# Dockerイメージをビルド
sudo docker-compose build

# コンテナを起動
sudo docker-compose up -d

# ログ確認
sudo docker-compose logs -f
```

### systemdサービスとして登録（常時起動）

#### 1. systemdサービスファイルの作成
```bash
sudo tee /etc/systemd/system/api-wisper.service << 'EOF'
[Unit]
Description=API Wisper v1 - Whisper Speech Recognition Service
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=10
WorkingDirectory=/home/ubuntu/api_wisper_v1
ExecStartPre=/usr/bin/docker-compose down
ExecStart=/usr/bin/docker-compose up
ExecStop=/usr/bin/docker-compose down
StandardOutput=journal
StandardError=journal
SyslogIdentifier=api-wisper

[Install]
WantedBy=multi-user.target
EOF
```

#### 2. サービスの有効化と起動
```bash
# 既存のDockerコンテナを停止
cd ~/api_wisper_v1
sudo docker-compose down

# systemdをリロード
sudo systemctl daemon-reload

# サービスを有効化（自動起動ON）
sudo systemctl enable api-wisper.service

# サービスを起動
sudo systemctl start api-wisper.service

# 状態確認
sudo systemctl status api-wisper.service
```

### サービス管理コマンド

```bash
# サービスの状態確認
sudo systemctl status api-wisper

# サービスの停止
sudo systemctl stop api-wisper

# サービスの開始
sudo systemctl start api-wisper

# サービスの再起動
sudo systemctl restart api-wisper

# リアルタイムログ表示
sudo journalctl -u api-wisper -f

# 過去のログ表示
sudo journalctl -u api-wisper --since "1 hour ago"
```

### Docker操作（手動管理時）

```bash
# コンテナの状態確認
sudo docker ps

# コンテナの停止
cd ~/api_wisper_v1
sudo docker-compose down

# コンテナの起動
sudo docker-compose up -d

# ログの確認
sudo docker-compose logs -f

# コンテナ内に入る
sudo docker exec -it api_wisper_v1 bash
```

### トラブルシューティング

#### メモリ不足エラー
```bash
# エラー: "Killed" または OOMエラー
# 解決策:
1. スワップメモリを追加（上記参照）
2. より小さいWhisperモデルを使用（base/small）
3. docker-compose.ymlのmem_limitを調整
```

#### ポート競合
```bash
# エラー: "bind: address already in use"
# 解決策:
sudo lsof -i :8001
sudo kill -9 <PID>
```

#### Whisperモデルのキャッシュクリア
```bash
# Dockerボリュームを削除してキャッシュをクリア
sudo docker volume rm api_wisper_v1_whisper_cache
```

### API動作確認

```bash
# ヘルスチェック
curl http://your-ec2-ip:8001/docs

# APIテスト
curl -X POST "http://your-ec2-ip:8001/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "your-device-id",
    "date": "2025-07-13",
    "model": "base"
  }'
```

### セキュリティグループ設定

EC2のセキュリティグループで以下のポートを開放：
- インバウンドルール: ポート8001 (TCP) - APIアクセス用

### 本番環境での推奨事項

1. **HTTPS化**: リバースプロキシ（Nginx）を使用してSSL証明書を設定
2. **認証**: APIキー認証やOAuth2の実装
3. **モニタリング**: CloudWatchやPrometheusでの監視
4. **バックアップ**: 定期的な設定ファイルのバックアップ
5. **ログ管理**: ログファイルのローテーションと保存

---