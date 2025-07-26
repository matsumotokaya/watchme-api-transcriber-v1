FROM python:3.12-slim

WORKDIR /app

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Whisperモデルのキャッシュディレクトリを作成
RUN mkdir -p /root/.cache/whisper

# 依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Whisperモデルを事前にダウンロード
RUN python -c "import whisper; whisper.load_model('base')"

# アプリケーションをコピー
COPY main.py .
COPY .env .

# ポートを公開（main.pyは8001で起動）
EXPOSE 8001

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8001/ || exit 1

# アプリケーションを実行
CMD ["python", "main.py"]