# Whisper API for WatchMe - Supabase/S3統合版

WatchMeエコシステム専用のWhisper音声文字起こしAPI。Supabaseのaudio_filesテーブルを参照し、S3から音声を取得して文字起こしを実行します。

## ⚠️ 重要: 開発環境と本番環境の違い

| 項目 | 開発環境（ローカル） | 本番環境（EC2） |
|-----|---------------------|----------------|
| **URL** | `http://localhost:8001` | `https://api.hey-watch.me/vibe-transcriber/` |
| **起動方法** | `python3.12 main.py` | Docker + systemd |
| **デプロイ先** | ローカルマシン | AWS EC2インスタンス |
| **アクセス** | ローカルのみ | インターネット経由 |

## 🔄 2025年7月 音声処理フロー改善アップデート

### 最新の変更内容（2025年7月19日）
- **audio_filesテーブル経由の処理**: Supabaseのaudio_filesテーブルを参照して音声ファイルを取得
- **transcriptions_statusの活用**: 処理済みファイルをcompletedステータスで管理
- **シンプルな判定ロジック**: transcriptions_statusのみで処理対象を判定（pendingのみ処理）
- **S3パス取得**: audio_filesテーブルのfile_pathカラムからS3パスを取得
- **スケジューラー改善**: 管理画面のスケジューラーログを詳細化し、処理対象日付を明確化

### 🔧 管理画面スケジューラー改善詳細
**問題**: スケジューラーログに処理対象日付の詳細情報が不足

**修正内容**:
1. **詳細なログ出力**:
   - 処理対象期間を明確に表示（例：`2025-07-18 00:00:00 〜 2025-07-19 00:00:00`）
   - 検索条件の詳細表示（device_id、recorded_at範囲）
   - 処理対象の日付リストを表示

2. **カラム名の修正**:
   - `whisper_status` → `transcriptions_status`に対応
   - 新しいテーブル構造に合わせて更新

3. **日付フィルタリング改善**:
   - タイムゾーン処理を強化（`+00:00`と`Z`の両方に対応）
   - 明確な範囲チェック（`yesterday <= recorded_at <= now`）

**改善後のログ例**:
```
0:00:00 - 🚀 Whisper自動処理を開始
0:00:00 - 📅 処理対象期間: 2025-07-18 00:00:00 〜 2025-07-19 00:00:00
0:00:00 - ⏰ 現在時刻: 2025-07-19 00:00:00
0:00:00 - 🔍 検索条件: device_id=d067d407..., recorded_at=2025-07-18 00:00〜2025-07-19 00:00
0:00:01 - 📋 audio_filesテーブル確認: 6件の未処理ファイルを検出
0:00:01 - 📆 処理対象の日付: 2025-07-18
```

## 🚀 2025年7月 性能改善アップデート

### 改善内容
- **重複処理の排除**: Supabaseで処理済みデータを事前チェックし、未処理分のみを処理
- **無駄な処理の削減**: Vault APIで音声データの存在を事前確認し、データが存在するスロットのみ処理
- **処理時間の大幅短縮**: 従来最大1時間以上 → 実データのみの処理時間に短縮
- **詳細な処理レポート**: スキップ理由と処理結果を明確に表示

### 📊 処理フロー詳細（最新版）

#### 1. リクエスト受信
```json
{
  "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
  "date": "2025-07-18",
  "model": "base"
}
```

#### 2. 処理の流れ

```
[開始] リクエスト受信
   ↓
[Step 1] audio_filesテーブルから音声ファイル情報を取得
   ├─ 条件: device_id + date + transcriptions_status='pending'
   ├─ 取得データ: file_path, recorded_at など
   └─ 結果: 未処理音声ファイルのリスト
   ↓
[判定] pendingファイルが存在する？
   ├─ NO  → 処理終了（全て処理済みのレスポンス）
   └─ YES → 次のステップへ
   ↓
[Step 2] 音声ダウンロードと文字起こし
   ├─ 対象: pendingステータスのファイルすべて
   ├─ 処理内容:
   │   1. file_pathを使用してS3から音声ファイルをダウンロード
   │   2. Whisperで文字起こし実行
   │   3. 結果をvibe_whisperテーブルに保存（upsert）
   │   4. audio_filesのtranscriptions_statusをcompletedに更新
   └─ エラー時: エラーリストに追加して継続
   ↓
[終了] 処理結果レスポンス返却
```

### 🔧 実装の重要ポイント（最新版）

#### 1. get_audio_files_from_supabase関数
```python
async def get_audio_files_from_supabase(device_id: str, date: str, status_filter: str = 'pending') -> List[Dict]:
    """Supabaseのaudio_filesテーブルから該当日の音声ファイル情報を取得"""
    # audio_filesテーブルから指定条件でレコードを検索
    # recorded_atの日付部分とtranscriptions_statusでフィルタリング
    # 返り値: 音声ファイル情報のリスト
```

#### 2. 処理対象の判定（シンプル化）
```python
# pendingステータスのファイルのみ取得
pending_files = await get_audio_files_from_supabase(device_id, date, 'pending')

# pendingファイルをすべて処理対象とする（既存データがあっても上書き）
files_to_process = pending_files
```

#### 3. ステータス更新
```python
# 処理完了後、audio_filesテーブルのステータスを更新
supabase.table('audio_files') \
    .update({'transcriptions_status': 'completed'}) \
    .eq('device_id', audio_file['device_id']) \
    .eq('recorded_at', audio_file['recorded_at']) \
    .execute()
```

### 📈 パフォーマンス比較

#### 改修前（直接S3スキャン方式）
- 48スロット全てをチェック（データの有無に関わらず）
- vibe_whisperテーブルとS3の両方を確認する複雑なロジック
- 処理判定が不明確（既存データがあってもpendingなら再処理すべきか不明）

#### 改修後（audio_filesテーブル経由）
- audio_filesテーブルのtranscriptions_statusのみで判定（シンプル）
- pendingファイルのみを処理対象とする明確なロジック
- 処理時間: 必要な分のみ（例: 4ファイルなら約10秒）

### 💡 実際の処理例（最新版）

#### ケース1: 初回処理（pendingファイルがある場合）
```
リクエスト: device_id="xxx", date="2025-07-18"
処理結果:
- audio_filesチェック: 6件のファイル（pending: 4件、completed: 2件）
- 処理対象: pendingステータスの4件すべて
- 文字起こし実行: 4件を処理し、transcriptions_statusをcompletedに更新
- 実行時間: 11.3秒
```

#### ケース2: 再実行（全てcompleted済み）
```
リクエスト: 同じdevice_id, date
処理結果:
- audio_filesチェック: 6件のファイル（全てcompleted）
- 処理対象: 0件（pendingファイルなし）
- 処理スキップ: 全てスキップ
- 実行時間: 0.5秒（高速終了）
```

### 🔄 今後の改善ポイント

1. **並列処理の最適化**
   - 現在: Vault APIチェックは並列、文字起こしは逐次
   - 改善案: 文字起こしも並列化（メモリ使用量に注意）

2. **キャッシング**
   - 改善案: 最近チェックしたスロットの存在情報をキャッシュ

3. **バッチ処理API**
   - 改善案: S3オブジェクトのバッチ確認機能の利用

4. **プログレス通知**
   - 改善案: WebSocketやSSEで処理進捗をリアルタイム通知

## 🔑 重要な特徴

### ✨ 単一エンドポイント設計
- **POST /fetch-and-transcribe** のみ提供
- S3からの音声取得 → 文字起こし → Supabaseへの直接保存を一つの処理で完結
- シンプルで信頼性の高いワークフロー

### 🎯 高精度音声認識
- **Whisper Base モデル** (74M パラメータ) をサーバーリソース制約により使用
- 精度とパフォーマンスのバランス最適化
- 医療・心理分析用途に最適化

### 🏗️ WatchMeエコシステム統合
- iOS app → Vault API (S3保存) → Whisper API → Supabase の完全な処理チェーン
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
- **ネットワーク**: AWS S3 (watchme-vaultバケット) への接続

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
python3.12 -m pip install fastapi uvicorn openai-whisper aiohttp boto3 supabase python-dotenv
```

### EC2本番環境
```bash
# システム更新
sudo apt update && sudo apt upgrade -y

# 必要パッケージ
sudo apt install -y python3 python3-pip ffmpeg

# Python依存関係
pip3 install fastapi uvicorn openai-whisper aiohttp boto3 supabase python-dotenv
```

## 🎬 使用方法

### 🖥️ 開発環境（ローカル）での起動
```bash
# Python 3.12を使用
python3.12 main.py

# APIにアクセス
curl http://localhost:8001/
```

### 🌍 本番環境（EC2）での確認
```bash
# 本番環境のAPIステータス確認（インターネット経由）
curl https://api.hey-watch.me/vibe-transcriber/

# 注意: 本番環境はDockerとsystemdで管理されています
# 直接Pythonで起動しないでください！
```

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

#### 処理フロー（性能改善版）
1. **事前チェック（新機能）**: 
   - Supabaseで処理済みデータを確認
   - Vault APIで音声データの存在を確認
2. **効率的な処理**: 
   - 未処理かつデータ存在のスロットのみ処理
   - Whisper baseモデルで文字起こし実行
3. **結果保存**: Supabaseのvibe_whisperテーブルに保存
4. **詳細レポート**: スキップ理由を含む処理結果を返却

#### レスポンス例（最新版）
```json
{
  "status": "success",
  "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
  "date": "2025-07-18",
  "summary": {
    "total_files": 6,
    "already_completed": 2,
    "pending_processed": 4,
    "errors": 0
  },
  "processed_files": [
    "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-18/12-00/audio.wav",
    "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-18/14-00/audio.wav"
  ],
  "processed_time_blocks": ["12-00", "14-00"],
  "error_files": null,
  "execution_time_seconds": 11.3,
  "message": "pendingステータスの4件中4件を正常に処理しました"
}
```

#### 使用例

**本番環境での使用:**
```bash
curl -X POST "https://api.hey-watch.me/vibe-transcriber/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
    "date": "2025-07-05",
    "model": "base"
  }'
```

**開発環境での使用:**
```bash
curl -X POST "http://localhost:8001/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
    "date": "2025-07-05",
    "model": "base"
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
このAPIは本番環境でbaseモデルのみをサポートしています：

#### **Base モデル (本番環境で使用中)**
- **パラメータ数**: 74M (0.74億)
- **精度**: 基本的な精度
- **処理速度**: 高速
- **メモリ使用量**: ~200MB (モデル) + ~500MB (処理)
- **推奨用途**: リソース制約環境、基本的な文字起こし
- **本番制約**: サーバーリソース制約により、本番環境では **baseモデルのみ** 利用可能

### モデル比較表と必要メモリ
| モデル | パラメータ | 精度 | 速度 | 必要メモリ | 推奨EC2 | WatchMe対応 |
|--------|-----------|------|------|-----------|---------|------------|
| tiny | 39M | ⭐⭐ | ⭐⭐⭐⭐⭐ | ~1GB | t4g.small | ✅ 可能 |
| **base** | **74M** | **⭐⭐⭐** | **⭐⭐⭐⭐** | **~2GB** | **t4g.small** | **✅ 現在使用中** |
| small | 244M | ⭐⭐⭐⭐ | ⭐⭐⭐ | ~4GB | t3.medium | ⚠️ 要スケールアップ |
| medium | 769M | ⭐⭐⭐⭐ | ⭐⭐ | ~8GB | t3.large | ⚠️ 要スケールアップ |
| large | 1550M | ⭐⭐⭐⭐⭐ | ⭐ | ~16GB | t3.xlarge | ⚠️ 要スケールアップ |

### モデル選択ガイド
- **本番環境**: `base` モデル固定（サーバーリソース制約）
- **開発環境**: `base` モデル推奨（他のモデルはメモリ不足の可能性）
- **将来のアップグレード**: インスタンスタイプ向上時に検討

## 🌐 本番運用 (EC2)

### ⚠️ 本番デプロイ前の必須修正

環境変数の設定が必要です：

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

### ⚠️ 重要な前提
- **本番環境はEC2インスタンス上で動作します**（ローカルではありません）
- **URLは `https://api.hey-watch.me/vibe-transcriber/` です**（localhost:8001ではありません）
- **Dockerとsystemdで管理されています**（直接Pythonで起動しません）

### 🔧 本番環境へのデプロイ手順

#### 1. 本番環境（EC2）でのデプロイ
```bash
# 1. EC2インスタンスにSSH接続
ssh -i your-key.pem ubuntu@your-ec2-ip

# 2. プロジェクトディレクトリに移動
cd /path/to/api_wisper_v1

# 3. 最新のコードを取得（gitまたはファイル転送）
git pull origin main
# または
scp -i your-key.pem -r local-api_wisper_v1/* ubuntu@your-ec2-ip:/path/to/api_wisper_v1/

# 4. 環境変数を設定
cp .env.example .env
nano .env  # 本番環境の設定を入力

# 5. Dockerイメージをビルド
sudo docker-compose build

# 6. 既存のコンテナを停止
sudo docker-compose down

# 7. 新しいコンテナを起動
sudo docker-compose up -d

# 8. 動作確認
curl https://api.hey-watch.me/vibe-transcriber/
```

#### 2. systemdサービスでの自動起動設定（推奨）
```bash
# サービスを停止
sudo systemctl stop api-wisper

# 最新のコードでサービスを再起動
sudo systemctl start api-wisper

# 状態確認
sudo systemctl status api-wisper

# ログ確認
sudo journalctl -u api-wisper -f
```

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

### 🚨 開発環境での作業について
**開発環境（ローカル）でDockerコンテナを起動しても、それは本番環境にはなりません！**
- ローカルでのDocker起動 → `http://localhost:8001` でアクセス可能（開発用）
- 本番環境 → EC2インスタンス上で動作し、`https://api.hey-watch.me/vibe-transcriber/` でアクセス

### 前提条件
- **本番EC2インスタンス**（Ubuntu 20.04/22.04）へのSSHアクセス権限
- EC2インスタンスタイプ：t4g.small（現在使用中）
- EC2上にDocker/Docker Composeがインストール済み

### デプロイ手順（EC2へのデプロイ）

#### 1. EC2インスタンスへ接続してプロジェクトをアップロード
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
# 本番環境ヘルスチェック
curl https://api.hey-watch.me/vibe-transcriber/

# 本番環境APIテスト
curl -X POST "https://api.hey-watch.me/vibe-transcriber/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "your-device-id",
    "date": "2025-07-13",
    "model": "base"
  }'

# 開発環境（ローカル）での確認
curl http://localhost:8001/docs

# 開発環境APIテスト
curl -X POST "http://localhost:8001/fetch-and-transcribe" \
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