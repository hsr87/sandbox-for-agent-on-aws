#!/bin/zsh
# Builds follow-up images with Finch. Run from output/followup.
set -e
ACC=$(aws sts get-caller-identity --query Account --output text)
US=$ACC.dkr.ecr.us-east-1.amazonaws.com; TK=$ACC.dkr.ecr.ap-northeast-1.amazonaws.com
ECR=$US/sbx-bench/agent
aws ecr get-login-password --region us-east-1 | finch login -u AWS --password-stdin $US
cd app
finch build -q --platform linux/arm64 --build-arg BASE=$ECR:noping-arm64 -f Dockerfile.xclaude -t ${ECR}:x1c-arm64 .
finch build -q --platform linux/arm64 --build-arg BASE=$ECR:noping-arm64 -f Dockerfile.xstrands -t ${ECR}:x1s-arm64 .
finch build -q --platform linux/amd64 --build-arg BASE=$ECR:base-amd64 -f Dockerfile.xclaude -t ${ECR}:x1c-amd64 .
finch build -q --platform linux/amd64 --build-arg BASE=$ECR:base-amd64 -f Dockerfile.xstrands -t ${ECR}:x1s-amd64 .
for t in x1c-arm64 x1s-arm64 x1c-amd64 x1s-amd64; do finch push -q ${ECR}:$t; done
for mb in 10 50 100 200; do
  finch build -q --platform linux/arm64 --build-arg BASE=$ECR:x1s-arm64 --build-arg MB=$mb -f Dockerfile.xasset -t ${ECR}:x1a$mb-arm64 .
  finch push -q ${ECR}:x1a$mb-arm64
done
echo IMAGES_US_DONE
