"""Runs in the driver. Copies complete files to S3 once a minute, so results survive the pod and the laptop."""
import glob, os, sys, time
import boto3, json
b = json.load(open("/work/deployment.json"))["bucket"]
s3 = boto3.client("s3", region_name="us-east-1")
while True:
    for f in glob.glob("/work/results/*.jsonl"):
        s3.upload_file(f, b, "results/" + os.path.basename(f))
    time.sleep(60)
