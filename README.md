# Whisper API for WatchMe - Vault連携専用

FastAPIを使用したWhisper音声文字起こしAPI（WatchMe統合システム - Vault連携専用）

## ⚠️ 重要な環境情報

**このAPIは macOS システムPython 3.12 で動作します**

- 使用Python: `/usr/local/bin/python3.12` (システムPython)
- 仮想環境: **使用していません**
- ポート: **8001** (WatchMeプロジェクトの標準ポート配置)

### 依存関係のインストール

```bash
# システムPython 3.12環境にインストール
python3.12 -m pip install fastapi uvicorn openai-whisper aiohttp
```

### なぜ仮想環境を使わないのか？

- WatchMeプロジェクトの統合環境での動作が前提
- システム全体でWhisperモデルを共有
- 他のWatchMeコンポーネントとの連携のため

## 機能概要

**このAPIは Vault連携専用に特化されています**

- **Vault APIからWAVファイルを取得**
- **Whisper大規模モデル（large）による高精度文字起こし**
- **結果をVault APIに自動アップロード**

## インストール

必要なパッケージをインストール：

```bash
python3 -m pip install fastapi uvicorn openai-whisper aiohttp
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

## 🔑 API エンドポイント

### POST /fetch-and-transcribe（メインエンドポイント）

**EC2 Vault API (`https://api.hey-watch.me`) からWAVファイルを取得して一括文字起こしを実行**

**リクエスト形式：**
```json
{
  "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
  "date": "2025-07-05"
}
```

**処理フロー：**
1. **WAVファイル取得**: `GET /download?device_id={device_id}&date={date}&slot={time_slot}` を使用
2. **48ファイル処理**: 00-00.wav から 23-30.wav まで30分間隔のスロット
3. **Whisper文字起こし**: 大規模モデルで高精度な文字起こし実行
4. **ローカル保存**: `/Users/kaya.matsumoto/data/data_accounts/{device_id}/{date}/transcriptions/`
5. **EC2アップロード**: 処理済み`.json`ファイルを`https://api.hey-watch.me/upload-transcription`にアップロード

**レスポンス：**
```json
{
  "status": "success",
  "fetched": ["00-00.wav", "00-30.wav"],
  "processed": ["00-00.json", "00-30.json"],
  "uploaded": ["00-00.json", "00-30.json"],
  "errors": [],
  "upload_errors": []
}
```

**使用例：**
```bash
curl -X POST "http://localhost:8001/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0",
    "date": "2025-07-05"
  }'
```

## 出力ファイル形式

**JSONファイル構造：**
```json
{
  "time_block": "00-00",
  "transcription": "Whisperによる文字起こし結果"
}
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

## システム要件

- macOS環境
- Python 3.12
- 十分なメモリ容量（Whisper large モデル用）
- インターネット接続（Vault API連携用）

## 注意事項

- このAPIはVault連携専用に設計されています
- 単体ファイルアップロード機能は提供していません
- ローカルファイル処理機能は提供していません