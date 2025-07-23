#!/bin/bash

# ECRの設定
AWS_REGION="ap-southeast-2"
AWS_ACCOUNT_ID="754724220380"
ECR_REPO="watchme-api-transcriber"
IMAGE_TAG="${1:-latest}"

# ECRにログイン
echo "ECRにログインしています..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Dockerイメージをビルド
echo "Dockerイメージをビルドしています..."
docker build -t ${ECR_REPO}:${IMAGE_TAG} .

# イメージにタグを付ける
echo "イメージにタグを付けています..."
docker tag ${ECR_REPO}:${IMAGE_TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}

# ECRにプッシュ
echo "ECRにプッシュしています..."
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}

echo "完了しました！"
echo "イメージURI: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"