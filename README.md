# Whisper API for WatchMe - Vault統合専用版

WatchMeエコシステム専用のWhisper音声文字起こしAPI。Vault APIとの完全統合により、音声データの取得から文字起こし、結果保存まで一貫した処理を提供します。

## 🔑 重要な特徴

### ✨ 単一エンドポイント設計
- **POST /fetch-and-transcribe** のみ提供
- Vault APIからの音声取得 → 文字起こし → Vault APIへの保存を一つの処理で完結
- シンプルで信頼性の高いワークフロー

### 🎯 高精度音声認識
- **Whisper Medium モデル** (769M パラメータ) を標準使用
- **Whisper Large モデル** (1.55B パラメータ) をオプション選択可能
- 精度とパフォーマンスのバランス最適化
- 医療・心理分析用途に最適化

### 🏗️ WatchMeエコシステム統合
- iOS app → Vault API → Whisper API → Vault API の完全な処理チェーン
- デバイスベースの識別システム (device_id)
- 30分間隔の時間スロット処理 (48スロット/日)

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
3. **文字起こし**: 選択されたWhisperモデルで文字起こし実行
4. **ローカル保存**: 処理結果をJSONファイルとして一時保存
5. **Vault保存**: 全てのJSONファイルをVault APIにアップロード
6. **検証**: アップロード後の整合性確認

#### レスポンス例
```json
{
  "status": "success",
  "fetched": ["02-00.wav", "02-30.wav", "11-00.wav", "13-30.wav"],
  "processed": ["02-00.json", "02-30.json", "11-00.json", "13-30.json"],
  "uploaded": ["02-00.json", "02-30.json", "11-00.json", "13-30.json"],
  "errors": [],
  "upload_errors": [],
  "local_file_count": 4,
  "verification_note": "アップロード検証を実行済み - ログを確認してください"
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

### JSONファイル構造
```json
{
  "time_block": "02-00",
  "transcription": "おはようございます。今日は良い天気ですね。"
}
```

### ファイル保存場所
- **開発環境**: `/Users/kaya.matsumoto/data/data_accounts/{device_id}/{date}/transcriptions/`
- **本番環境**: `/home/ubuntu/data/data_accounts/{device_id}/{date}/transcriptions/`

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
- **iOS App** → **Vault API** → **Whisper API** → **分析システム**

### 技術仕様
- **FastAPI**: 3.10+
- **Whisper**: OpenAI公式実装
- **Python**: 3.12 (システム推奨)

---

**注意**: このAPIはVault連携専用です。単体ファイル処理や独立利用は想定していません。