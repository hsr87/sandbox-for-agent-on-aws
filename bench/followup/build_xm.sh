#!/bin/zsh
# Images for the comparison reruns: same code, x86 and arm64, plus SDK versions with distinct CLI bytes. Run from output/followup.
set -ex
ACC=$(aws sts get-caller-identity --query Account --output text)
US=$ACC.dkr.ecr.us-east-1.amazonaws.com; ECR=$US/sbx-bench/agent
aws ecr get-login-password --region us-east-1 | finch login -u AWS --password-stdin $US
cd app
finch build --progress=plain --platform linux/arm64 --build-arg BASE=$ECR:noping-arm64 -f Dockerfile.xclaude -t $ECR:x1f-arm64 .
finch push -q $ECR:x1f-arm64
finch build --progress=plain --platform linux/amd64 --build-arg BASE=$ECR:base-amd64 -f Dockerfile.xclaude -t $ECR:x1f-amd64 .
finch push -q $ECR:x1f-amd64
finch image rm $ECR:x1f-amd64 >/dev/null
b() { # tag version pre
  finch build --progress=plain --platform linux/arm64 --build-arg BASE=$ECR:x1f-arm64 --build-arg VER=$2 --build-arg PRE=$3 -f Dockerfile.xver -t $ECR:xm-$1-arm64 .
  finch push -q $ECR:xm-$1-arm64
  finch image rm $ECR:xm-$1-arm64 >/dev/null
}
b none176 0.2.176 ""
b map178 0.2.178 map
b pre173 0.2.173 exec
b w175 0.2.175 ""
b w174 0.2.174 ""
b none171 0.2.171 ""
b map168 0.2.168 map
echo XM_IMAGES_DONE
