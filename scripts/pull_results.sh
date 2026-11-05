#!/bin/zsh
# Copies raw results from S3 into results/raw and removes the account id before they reach git.
set -e
cd "$(dirname "$0")/.."
ACC=$(aws sts get-caller-identity --query Account --output text)
T=$(mktemp -d)
aws s3 sync --quiet s3://sbx-bench-$ACC/results/ "$T"/
mkdir -p results/raw
for f in "$T"/*.jsonl; do
  sed "s/$ACC/000000000000/g" "$f" > "results/raw/$(basename "$f")"
done
rm -rf "$T"
wc -l results/raw/*.jsonl | tail -1
