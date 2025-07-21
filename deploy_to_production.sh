#!/bin/bash

# 本番環境へのデプロイスクリプト
# 使用方法: ./deploy_to_production.sh

echo "🚀 Whisper API 本番環境デプロイを開始します..."

# EC2の接続情報
EC2_HOST="3.24.16.82"
EC2_USER="ubuntu"
KEY_PATH="~/watchme-key.pem"

# 色付き出力のための設定
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}📦 Step 1: プロジェクトをEC2にアップロード${NC}"
scp -i $KEY_PATH ../api_whisper_v1_updated.tar.gz $EC2_USER@$EC2_HOST:~/

echo -e "${YELLOW}🔧 Step 2: EC2上でデプロイを実行${NC}"
ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << 'ENDSSH'
    echo "EC2上での作業を開始..."
    
    # バックアップを作成
    echo "📋 既存のAPIをバックアップ..."
    if [ -d "api_whisper_v1" ]; then
        sudo cp -r api_whisper_v1 api_whisper_v1_backup_$(date +%Y%m%d_%H%M%S)
    fi
    
    # 新しいコードを展開
    echo "📂 新しいコードを展開..."
    tar -xzf api_whisper_v1_updated.tar.gz
    
    # ディレクトリに移動
    cd api_whisper_v1
    
    # 環境変数ファイルが存在しない場合は作成を促す
    if [ ! -f ".env" ]; then
        echo "⚠️  .envファイルが見つかりません。"
        echo "以下の内容で.envファイルを作成してください："
        echo "----------------------------------------"
        echo "SUPABASE_URL=your_supabase_url"
        echo "SUPABASE_KEY=your_supabase_key"
        echo "AWS_ACCESS_KEY_ID=your_access_key_id"
        echo "AWS_SECRET_ACCESS_KEY=your_secret_access_key"
        echo "S3_BUCKET_NAME=watchme-vault"
        echo "AWS_REGION=us-east-1"
        echo "----------------------------------------"
        exit 1
    fi
    
    # Dockerコンテナを再構築
    echo "🐳 Dockerコンテナを再構築..."
    sudo docker-compose down
    sudo docker-compose build
    sudo docker-compose up -d
    
    # systemdサービスを再起動
    echo "⚙️  systemdサービスを再起動..."
    sudo systemctl restart api-whisper
    
    # 状態確認
    echo "✅ デプロイ完了！サービス状態を確認..."
    sudo systemctl status api-whisper --no-pager
    
    # アップロードファイルを削除
    rm -f ~/api_whisper_v1_updated.tar.gz
    
    echo "🎉 デプロイが正常に完了しました！"
ENDSSH

echo -e "${GREEN}✨ 本番環境へのデプロイが完了しました！${NC}"
echo ""
echo "動作確認用コマンド:"
echo -e "${YELLOW}curl https://api.hey-watch.me/vibe-transcriber/${NC}"
echo ""
echo "テスト用コマンド:"
cat << 'EOF'
curl -X POST "https://api.hey-watch.me/vibe-transcriber/fetch-and-transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": [
      "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-19/14-30/audio.wav"
    ],
    "model": "base"
  }'
EOF