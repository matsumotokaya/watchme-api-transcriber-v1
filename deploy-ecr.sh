#!/bin/bash

# --- 依存関係の安全確認 ---
echo "==> 依存サービス(watchme-infrastructure.service)の稼働状況を確認中..."

# スクリプト内の変数を利用してSSH接続
KEY_PATH="~/watchme-key.pem"
EC2_USER="ubuntu"
EC2_HOST="3.24.16.82"

ssh -i ${KEY_PATH} ${EC2_USER}@${EC2_HOST} "systemctl is-active --quiet watchme-infrastructure.service"
if [ $? -ne 0 ]; then
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  echo "[エラー] 依存する 'watchme-infrastructure.service' が稼働していません！"
  echo "先に watchme-server-configs のセットアップを実行してください。"
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  exit 1
fi
echo "==> 依存サービスの確認OK。デプロイを続行します。"
echo ""
# --- 安全確認ここまで ---


# ECRベースのデプロイスクリプト
# 使用方法: ./deploy-ecr.sh [TAG]

echo "🚀 Whisper API ECRデプロイを開始します..."

# 設定
TAG="${1:-latest}"
EC2_HOST="3.24.16.82"
EC2_USER="ubuntu"
KEY_PATH="~/watchme-key.pem"
ECR_URI="754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-transcriber"

# 色付き出力
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}📦 Step 1: DockerイメージをビルドしてECRにプッシュ${NC}"
./build-and-push-ecr.sh ${TAG}

echo -e "${YELLOW}🔧 Step 2: Systemdサービスファイルをアップロード${NC}"
scp -i ${KEY_PATH} systemd/api-transcriber.service ${EC2_USER}@${EC2_HOST}:~/

echo -e "${YELLOW}⚙️  Step 3: EC2上でサービスを更新${NC}"
ssh -i ${KEY_PATH} ${EC2_USER}@${EC2_HOST} << ENDSSH
    echo "EC2上での作業を開始..."
    
    # 既存のDockerコンテナを停止
    echo "🐳 既存のDockerコンテナを停止..."
    sudo docker stop api_whisper_v1 || true
    sudo docker rm api_whisper_v1 || true
    
    # docker-composeも停止
    if [ -d "api_whisper_v1" ]; then
        cd api_whisper_v1
        sudo docker-compose down || true
        cd ~
    fi
    
    # Systemdサービスファイルをインストール
    echo "📋 Systemdサービスファイルをインストール..."
    sudo cp ~/api-transcriber.service /etc/systemd/system/
    sudo systemctl daemon-reload
    
    # 環境変数ファイルの確認
    if [ ! -f "/home/ubuntu/api_whisper_v1/.env" ]; then
        echo "⚠️  .envファイルが見つかりません！"
        echo "/home/ubuntu/api_whisper_v1/.env に環境変数ファイルを作成してください"
        exit 1
    fi
    
    # サービスを起動
    echo "🚀 Systemdサービスを起動..."
    sudo systemctl enable api-transcriber
    sudo systemctl start api-transcriber
    
    # 状態確認
    echo "✅ デプロイ完了！サービス状態を確認..."
    sleep 5
    sudo systemctl status api-transcriber --no-pager
    
    # ヘルスチェック
    echo "🏥 ヘルスチェック..."
    sleep 10
    curl -f http://localhost:8001/ && echo -e "\n✅ ヘルスチェック成功！" || echo -e "\n❌ ヘルスチェック失敗"
    
    # クリーンアップ
    rm -f ~/api-transcriber.service
    
    echo "🎉 ECRベースのデプロイが完了しました！"
ENDSSH

echo -e "${GREEN}✨ デプロイが完了しました！${NC}"
echo ""
echo "動作確認用コマンド:"
echo -e "${YELLOW}curl https://api.hey-watch.me/vibe-transcriber/${NC}"
echo ""
echo "ログ確認:"
echo -e "${YELLOW}ssh -i ${KEY_PATH} ${EC2_USER}@${EC2_HOST} 'sudo journalctl -u api-transcriber -f'${NC}"