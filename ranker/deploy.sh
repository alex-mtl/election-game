#!/bin/sh
# Deploy build/word-ranker-<lang>.zip (./build.sh first). Usage: ./deploy.sh [en ru fr es]
# Packages are >50 MB, so they go through a temporary S3 object (deleted right after).
cd "$(dirname "$0")"
BUCKET=aws-for-claude-registry-565905128720
ROLE=arn:aws:iam::565905128720:role/word-ranker-role
for lang in ${*:-en ru fr es}; do
  fn=word-ranker-$lang key=tmp-deploy/$fn.zip
  ./aws.sh s3 cp --only-show-errors build/$fn.zip s3://$BUCKET/$key || exit 1
  if ./aws.sh lambda get-function --region us-east-1 --function-name $fn >/dev/null 2>&1; then
    ./aws.sh lambda update-function-code --region us-east-1 --function-name $fn --s3-bucket $BUCKET --s3-key $key \
      --query LastUpdateStatus --output text
  else
    ./aws.sh lambda create-function --region us-east-1 --function-name $fn --runtime python3.12 \
      --handler handler.lambda_handler --role $ROLE --code S3Bucket=$BUCKET,S3Key=$key \
      --memory-size 1024 --timeout 30 --tags Project=word-ranker \
      --logging-config LogFormat=JSON,ApplicationLogLevel=WARN,SystemLogLevel=WARN --query State --output text
  fi
  ./aws.sh lambda wait function-updated-v2 --region us-east-1 --function-name $fn
  ./aws.sh s3 rm --only-show-errors s3://$BUCKET/$key
  echo "$fn deployed"
done
