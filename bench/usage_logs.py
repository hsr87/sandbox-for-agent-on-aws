"""Turns on AgentCore USAGE_LOGS (1 s granularity vCPU-hours and GB-hours per session)."""
import json, sys
import boto3
logs = boto3.client("logs", region_name="us-east-1")
ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
GROUP = "/bench/agentcore-usage"
try:
    logs.create_log_group(logGroupName=GROUP, tags={"project": "sandbox-bench"})
except logs.exceptions.ResourceAlreadyExistsException:
    pass
dest = logs.put_delivery_destination(name="bench-usage", outputFormat="json", deliveryDestinationConfiguration={"destinationResourceArn": f"arn:aws:logs:us-east-1:{ACCOUNT}:log-group:{GROUP}"})["deliveryDestination"]["arn"]
for name, arn in json.loads(sys.argv[1]).items():
    src = f"bench-usage-{name}"
    logs.put_delivery_source(name=src, resourceArn=arn, logType="USAGE_LOGS")
    logs.create_delivery(deliverySourceName=src, deliveryDestinationArn=dest)
    print("delivery on", name)
