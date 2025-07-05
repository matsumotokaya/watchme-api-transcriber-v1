# Whisper API for WatchMe

FastAPIを使用したWhisper音声文字起こしAPI（WatchMe統合システム用）

## ⚠️ 重要な環境情報

**このAPIは macOS システムPython 3.12 で動作します**

- 使用Python: `/usr/local/bin/python3.12` (システムPython)
- 仮想環境: **使用していません**
- ポート: **8001** (WatchMeプロジェクトの標準ポート配置)

### 依存関係のインストール

```bash
# システムPython 3.12環境にインストール
python3.12 -m pip install fastapi uvicorn python-multipart openai-whisper aiohttp
```

### なぜ仮想環境を使わないのか？

- WatchMeプロジェクトの統合環境での動作が前提
- システム全体でWhisperモデルを共有
- 他のWatchMeコンポーネントとの連携のため

## 機能

- 音声ファイル（.m4a, .mp3, .wav）をアップロードして、テキストに変換
- 指定デバイスの指定日フォルダ内の全.wavファイルを一括文字起こし
- リモートAPIから音声ファイルを取得して一括文字起こし
- Whisperの大規模モデル（large）を使用して高精度な文字起こし
- WatchMeシステム統合対応のREST APIインターフェース

## インストール

必要なパッケージをインストール：

```bash
python3 -m pip install fastapi uvicorn python-multipart openai-whisper
```

## 使用方法

サーバーを起動：

```bash
python3.12 main.py
```

または

```bash
python main.py  # システムpythonがpython3.12を指している場合
```

サーバーは `http://localhost:8001` で実行されます。

## API エンドポイント

### 🔑 コアAPI: Vault APIからのファイル取得

#### GET /download (最重要エンドポイント)
**EC2 Vault APIから個別WAVファイルを取得する主要エンドポイント**

**使用例:**
```bash
# 特定時間スロットのWAVファイルを取得
curl "https://api.hey-watch.me/download?device_id=user123&date=2025-06-25&slot=20-30"

# JSONファイルを取得
curl "https://api.hey-watch.me/download?device_id=user123&date=2025-06-25&slot=20-30&type=json"
```

**パラメータ:**
- `device_id`: デバイスID (例: user123)
- `date`: 日付 (YYYY-MM-DD形式, 例: 2025-06-25)  
- `slot`: 時間スロット (HH-MM形式, 例: 20-30)
- `type`: ファイル種別 (省略時はwav, jsonも指定可能)

**ユースケース:**
- **他のAPIサービスからの連携**: OpenSMILE APIなど外部サービスが音声ファイルを取得
- **時間スロット指定の個別取得**: 特定の30分間の音声データのみ必要な場合
- **リアルタイム処理**: 最新スロットの音声を即座に処理したい場合

#### GET /download-file (ファイルパス直接指定)
**EC2サーバー上のファイルパスを直接指定してダウンロード**

**使用例:**
```bash
# ファイルパス直接指定でダウンロード
curl "https://api.hey-watch.me/download-file?path=/home/ubuntu/data/data_accounts/user123/2025-06-25/raw/20-30.wav"
```

**パラメータ:**
- `path`: EC2サーバー上の完全ファイルパス

**ユースケース:**
- **開発・デバッグ**: サーバー上のファイル構造を把握している場合の直接アクセス
- **バックアップ・メンテナンス**: 管理者がファイルシステムを直接操作する場合
- **カスタムパス**: 標準の時間スロット以外のファイルにアクセスする場合

### 📝 文字起こし関連エンドポイント

#### POST /transcribe (WatchMe互換)
WatchMeシステム互換の単体ファイル文字起こしエンドポイント

**レスポンス**：
```json
{
  "transcript": "Whisperによる文字起こし結果"
}
```

#### POST /analyze/whisper (従来互換)
従来のAnalyze形式エンドポイント

**レスポンス**：
```json
{
  "transcription": "Whisperによる文字起こし結果"
}
```

#### POST /batch-transcribe (ローカルファイル処理)
指定されたデバイスの指定日フォルダ内の全.wavファイルを一括文字起こしします。

**リクエスト形式**：
```json
{
  "device_id": "user123",
  "date": "2025-01-06"  // オプション: 指定しない場合は当日
}
```

**処理対象ディレクトリ**：
```
/Users/kaya.matsumoto/data/data_accounts/{device_id}/{date}/
```

**出力先ディレクトリ**：
```
/Users/kaya.matsumoto/data/data_accounts/{device_id}/{date}/transcriptions/
```

**出力ファイル形式**：
```json
{
  "time_block": "00-00",
  "transcription": "（0:00）おはよう…"
}
```

**レスポンス**：
```json
{
  "status": "success",
  "processed": ["00-00", "00-30", "01-00"],
  "skipped": ["01-30"]
}
```

#### POST /fetch-and-transcribe (Vault API連携)
**EC2 Vault API (`https://api.hey-watch.me`) からWAVファイルを取得して一括文字起こしを実行**

**リクエスト形式**：
```json
{
  "device_id": "user123",
  "date": "2025-01-06"
}
```

**処理内容**：
1. **WAVファイル取得**: `GET /download?device_id={device_id}&date={date}&slot={time_slot}` を使用
2. **48ファイル処理**: 00-00.wav から 23-30.wav まで30分間隔のスロット
3. **ローカル保存**: `/Users/kaya.matsumoto/data/data_accounts/{device_id}/{date}/transcriptions/`
4. **EC2アップロード**: 処理済み`.json`ファイルを`https://api.hey-watch.me/upload-transcription`にアップロード

**レスポンス**：
```json
{
  "status": "success",
  "fetched": ["00-00.wav", "00-30.wav"],
  "processed": ["00-00.json", "00-30.json"],
  "uploaded": ["00-00.json", "00-30.json"],
  "skipped": ["01-00.json"],
  "errors": ["01-30.wav"],
  "upload_errors": []
}
```

## テスト

### 単体ファイル文字起こしのテスト

```bash
python3.12 test_api.py <音声ファイルパス>
```

### 一括文字起こしのテスト

```bash
# テスト用ディレクトリを作成
python3.12 test_batch_api.py user123 --create-dir

# 一括文字起こしを実行
python3.12 test_batch_api.py user123
```

## Swagger UI ドキュメント

API ドキュメントは以下のURLでアクセスできます：
http://localhost:8001/docs

## トラブルシューティング

### ModuleNotFoundError: No module named 'aiohttp'

このエラーが発生した場合は、システムPython環境にaiohttpをインストールしてください：

```bash
python3.12 -m pip install aiohttp
```

### Whisperモデルの読み込みに時間がかかる

初回起動時やモデル変更時は、Whisperの大規模モデル（large）の読み込みに1-2分程度かかる場合があります。「Whisperモデル読み込み完了」が表示されるまでお待ちください。

### ポート8001が使用中

WatchMeプロジェクトの他のコンポーネントとのポート競合を避けるため、ポート8001を使用しています。他のサービスでポート8001が使用されている場合は、そのサービスを停止してください。