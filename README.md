# Whisper API for WatchMe - Supabase統合版

WatchMeエコシステム専用のWhisper音声文字起こしAPI。Vault APIからの音声取得とSupabaseへの直接保存により、音声データの取得から文字起こし、結果保存まで一貫した処理を提供します。

## 🔑 重要な特徴

### ✨ 単一エンドポイント設計
- **POST /fetch-and-transcribe** のみ提供
- Vault APIからの音声取得 → 文字起こし → Supabaseへの直接保存を一つの処理で完結
- シンプルで信頼性の高いワークフロー

### 🎯 高精度音声認識
- **Whisper Base モデル** (74M パラメータ) をサーバーリソース制約により使用
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
- **インスタンス**: t4g.small (2vCPU, 2GB RAM)
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
| **base** | base.pt | **139MB** | 起動時 |
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

**開発環境URL**: `http://localhost:8001`
**本番環境URL**: `https://api.hey-watch.me/vibe-transcriber/`

### 初回起動について
Whisperモデルの読み込み時間：
- **Base**: 10-20秒

「Whisper base モデル読み込み完了」が表示されるまでお待ちください。

## 📡 API仕様

### 本番環境で利用可能なエンドポイント

**ベースURL**: `https://api.hey-watch.me/vibe-transcriber`

- **GET /** - APIステータス確認
- **POST /fetch-and-transcribe** - メイン処理エンドポイント
- **GET /docs** - Swagger UI（開発用）

### POST /fetch-and-transcribe

WatchMeシステムのメイン処理エンドポイント。指定デバイス・日付の音声データを一括処理します。

**本番環境での完全なURL**: `https://api.hey-watch.me/vibe-transcriber/fetch-and-transcribe`

**⚠️ 重要な仕様**:
- **404エラーは正常動作**: 測定されていない時間スロットでは404が返りますが、これはエラーではありません
- **データなし = 正常**: ほとんどの時間スロットではデータが存在しないのが通常の状態です
- **スキップ処理**: 存在しないデータは自動的にスキップされ、存在するデータのみが処理されます

#### リクエスト
```json
{
  "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
  "date": "2025-07-05",
  "model": "base"
}
```

**パラメータ詳細:**
- `device_id`: デバイス識別子 (必須)
- `date`: 処理対象日付 YYYY-MM-DD形式 (必須)
- `model`: Whisperモデル (オプション、デフォルト: "base")
  - **本番環境では "base" モデルのみ利用可能**（サーバーリソース制約）
  - 将来的なアップグレード時に他のモデルも検討可能

#### 処理フロー
1. **モデル選択**: Whisper baseモデルを使用（サーバーリソース制約）
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

### ⚠️ **重要警告：Whisperモデルのサイズとメモリ制限**

> **警告**: **大きいWhisperモデル（small, medium, large）を使用すると、EC2インスタンスのメモリ上限を超えてクラッシュし、本番環境が停止します！**
> 
> **モデル変更時の注意事項：**
> - 現在の本番環境（t4g.small, 2GB RAM）では **baseモデルのみ** が安全に動作します
> - より大きなモデル（small以上）を使用する場合は、**必ずサーバーのスケールアップとセットで実施してください**
> - メモリ不足によるクラッシュは、システム全体の停止を引き起こす可能性があります
> 
> **推奨手順：**
> 1. まず開発環境で新しいモデルのメモリ使用量を測定
> 2. 必要なEC2インスタンスタイプを決定（最低でもt3.medium以上）
> 3. 本番環境のインスタンスをアップグレード
> 4. その後でモデルを変更

### 対応モデル
このAPIは2つのWhisperモデルをサポートしています：

#### **Base モデル (現在使用中)**
- **パラメータ数**: 74M (0.74億)
- **精度**: 基本的な精度
- **処理速度**: 高速
- **メモリ使用量**: ~200MB (モデル) + ~500MB (処理)
- **推奨用途**: リソース制約環境、基本的な文字起こし

### モデル比較表と必要メモリ
| モデル | パラメータ | 精度 | 速度 | 必要メモリ | 推奨EC2 | WatchMe対応 |
|--------|-----------|------|------|-----------|---------|------------|
| tiny | 39M | ⭐⭐ | ⭐⭐⭐⭐⭐ | ~1GB | t4g.small | ✅ 可能 |
| **base** | **74M** | **⭐⭐⭐** | **⭐⭐⭐⭐** | **~2GB** | **t4g.small** | **✅ 現在使用中** |
| small | 244M | ⭐⭐⭐⭐ | ⭐⭐⭐ | ~4GB | t3.medium | ⚠️ 要スケールアップ |
| medium | 769M | ⭐⭐⭐⭐ | ⭐⭐ | ~8GB | t3.large | ⚠️ 要スケールアップ |
| large | 1550M | ⭐⭐⭐⭐⭐ | ⭐ | ~16GB | t3.xlarge | ⚠️ 要スケールアップ |

### モデル選択ガイド
- **現在の設定**: `base` (サーバーリソース制約)
- **将来のアップグレード**: インスタンスタイプ向上時に検討

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

#### ⚠️ **メモリ不足によるクラッシュ警告**
> **重要**: 現在の本番環境（t4g.small）で**baseモデル以外を使用するとメモリ不足でクラッシュします**。
> モデル変更前に必ずインスタンスのアップグレードを実施してください。

| インスタンス | vCPU | RAM | 時間コスト | 月額概算 | 使用可能モデル | 用途 |
|-------------|------|-----|-----------|----------|--------------|------|
| t4g.small | 2 | 2GB | $0.0168 | ~$12 | tiny, **base** | 現在使用中 |
| t3.medium | 2 | 4GB | $0.04 | ~$30 | tiny, base, small | モデルアップグレード時 |
| t3.large | 2 | 8GB | $0.08 | ~$60 | tiny, base, small, medium | 高精度処理用 |
| t3.xlarge | 4 | 16GB | $0.16 | ~$120 | 全モデル対応 | 最高精度処理用 |

### 💰 コスト最適化案
1. **現在はBaseモデル**: リソース制約に最適化
2. **将来的なアップグレード**: インスタンス拡張時に検討
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
python3 -c "import whisper; whisper.load_model('base')"
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

#### Baseモデル (現在使用中)
- **1分音声**: ~2-3秒
- **30分音声**: ~1-1.5分
- **1日分 (48ファイル)**: ~45-60分

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

### 📝 本番環境でのAPI実行方法

**本番環境URL**: `https://api.hey-watch.me/vibe-transcriber/`

このAPIは本番環境で上記のURLでアクセス可能です。Nginxでリバースプロキシ設定されており、外部から直接アクセスできます。

### ⚠️ 本番環境での既知の問題とタイムアウトについて

**重要な懸念点**:
- 48ファイル（1日分）の処理には約2-6時間かかる可能性があります
- 現在の実装では、Nginxのプロキシタイムアウト（デフォルト60秒）により、長時間の処理でタイムアウトエラーが発生します
- **ただし、タイムアウトエラーが表示されても、バックエンドの処理は継続されています**

**現状の動作**:
- クライアント側には504 Gateway Timeoutエラーが返されます
- しかし、APIサーバー側では処理が継続され、Supabaseへの保存は完了します
- 処理結果の確認は、Supabaseのデータベースを直接確認する必要があります

**今後の改善予定**:
- タイムアウト問題の根本的解決
- 処理の高速化
- リアルタイム進捗表示機能

**暫定的な対処法**:
1. 少量のデータでテストする（特定の時間帯のみ）
2. Supabaseで結果を確認する
3. 必要に応じてNginxのタイムアウト設定を延長する（推奨しません）

**実行例:**

```bash
# 本番環境のAPIを直接呼び出す（外部からアクセス可能）
curl -X POST "https://api.hey-watch.me/vibe-transcriber/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
    "date": "2025-07-14",
    "model": "base"
  }'
```

**注意事項**:
- モデルは必ず `"base"` を指定してください（本番環境の制約）
- 大量データ処理時はタイムアウトが発生しますが、処理は継続されます
- 結果の確認はSupabaseデータベースで行ってください

---

### 前提条件
- EC2インスタンス（Ubuntu 20.04/22.04）
- t4g.small（現在使用中）
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

現在はbaseモデルのみを使用：

```bash
# モデルは既にbaseに設定済み
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