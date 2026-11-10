#!/bin/zsh
set -e
aws ecr get-login-password --region ap-northeast-1 | finch login -u AWS --password-stdin ACCOUNT_ID.dkr.ecr.ap-northeast-1.amazonaws.com
cd app
for a in arm64 amd64; do
  finch build -q --platform linux/$a --build-arg BASE=ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sbx-bench/agent:x1c-$a --build-arg REGION=ap-northeast-1 --build-arg MODEL=jp.anthropic.claude-opus-5-5 -f Dockerfile.xregion -t ACCOUNT_ID.dkr.ecr.ap-northeast-1.amazonaws.com/sbx-tk/agent:tkc-$a .
  finch push -q ACCOUNT_ID.dkr.ecr.ap-northeast-1.amazonaws.com/sbx-tk/agent:tkc-$a
done
echo TK_IMAGES_DONE
