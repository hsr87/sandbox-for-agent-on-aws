FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm
RUN pip install --no-cache-dir -q boto3 kubernetes requests
WORKDIR /work
ENV PYTHONUNBUFFERED=1 AWS_REGION=us-east-1 PYTHONPATH=/work/bench
CMD ["sleep", "infinity"]
