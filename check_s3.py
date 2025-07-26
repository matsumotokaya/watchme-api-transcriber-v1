
import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数からAWS認証情報と設定を取得
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
s3_bucket_name = os.getenv('S3_BUCKET_NAME', 'watchme-vault')
aws_region = os.getenv('AWS_REGION', 'us-east-1')

# 確認対象のファイルパス
test_file_path = "files/d067d407-cf73-4174-a9c1-d91fb60d64d0/2025-07-26/20-00/audio.wav"

# 引数チェック
if not all([aws_access_key_id, aws_secret_access_key, s3_bucket_name, aws_region]):
    print("❌ Error: AWS credentials or bucket name are not set in the .env file.")
    exit(1)

# S3クライアントを初期化
s3_client = boto3.client(
    's3',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region
)

print("--- S3 File Check ---")
print(f"Bucket: {s3_bucket_name}")
print(f"File:   {test_file_path}")
print("-----------------------")

try:
    # head_objectメソッドでファイルのメタデータを取得
    response = s3_client.head_object(Bucket=s3_bucket_name, Key=test_file_path)
    
    print("✅ Success! File exists on S3.")
    print(f"   - Size: {response['ContentLength']} bytes")
    print(f"   - Last Modified: {response['LastModified']}")
    print(f"   - Content-Type: {response.get('ContentType', 'N/A')}")

except ClientError as e:
    # エラーコードをチェック
    if e.response['Error']['Code'] == '404':
        print("❌ Error: File not found on S3.")
    else:
        print(f"❌ An unexpected ClientError occurred: {e}")
except Exception as e:
    print(f"❌ An unexpected error occurred: {e}")
