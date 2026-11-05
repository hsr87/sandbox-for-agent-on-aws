data "aws_caller_identity" "me" {}
resource "aws_ecr_repository" "agent" {
  name                 = "${var.name}/agent"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}
resource "aws_s3_bucket" "bench" {
  bucket        = "${var.name}-${data.aws_caller_identity.me.account_id}"
  force_destroy = true
}

# Workload permission shared by all platforms: invoke Bedrock.
# Only the EKS pod role is limited to this. The AgentCore and MicroVM roles also carry the platform
# permissions below (image pull, logs, S3 read on the bench bucket), because the same role is used for them.
# This is a disposable test bed and these roles are not a production reference.
data "aws_iam_policy_document" "sandbox_perm" {
  statement {
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["*"]
  }
}
data "aws_iam_policy_document" "sandbox_logs" {
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams", "logs:DescribeLogGroups"]
    resources = ["*"]
  }
  statement {
    actions   = ["ecr:GetAuthorizationToken", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
    resources = ["*"]
  }
  statement {
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${aws_s3_bucket.bench.arn}/*"]
  }
  statement {
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "cloudwatch:PutMetricData"]
    resources = ["*"]
  }
}

resource "aws_iam_role" "agentcore_exec" {
  name = "${var.name}-agentcore-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.me.account_id } }
    }]
  })
}
resource "aws_iam_role_policy" "agentcore_exec" {
  role   = aws_iam_role.agentcore_exec.id
  policy = data.aws_iam_policy_document.sandbox_perm.json
}
resource "aws_iam_role_policy" "agentcore_exec2" {
  role   = aws_iam_role.agentcore_exec.id
  name   = "platform"
  policy = data.aws_iam_policy_document.sandbox_logs.json
}

resource "aws_iam_role" "microvm_build" {
  name = "${var.name}-microvm-build"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}
resource "aws_iam_role_policy" "microvm_build" {
  role   = aws_iam_role.microvm_build.id
  policy = data.aws_iam_policy_document.sandbox_logs.json
}
resource "aws_iam_role" "microvm_exec" {
  name = "${var.name}-microvm-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}
resource "aws_iam_role_policy" "microvm_exec" {
  role   = aws_iam_role.microvm_exec.id
  policy = data.aws_iam_policy_document.sandbox_perm.json
}
resource "aws_iam_role_policy" "microvm_exec2" {
  role   = aws_iam_role.microvm_exec.id
  name   = "logs"
  policy = data.aws_iam_policy_document.sandbox_logs.json
}

data "aws_iam_policy_document" "pod_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "sandbox_pod" {
  name               = "${var.name}-sandbox-pod"
  assume_role_policy = data.aws_iam_policy_document.pod_trust.json
}
resource "aws_iam_role_policy" "sandbox_pod" {
  role   = aws_iam_role.sandbox_pod.id
  policy = data.aws_iam_policy_document.sandbox_perm.json
}
resource "aws_eks_pod_identity_association" "sandbox" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "sandboxes"
  service_account = "sandbox"
  role_arn        = aws_iam_role.sandbox_pod.arn
}

# Benchmark driver: runs in-region so that no result includes a trans-Pacific round trip.
resource "aws_iam_role" "driver" {
  name               = "${var.name}-driver"
  assume_role_policy = data.aws_iam_policy_document.pod_trust.json
}
resource "aws_iam_role_policy" "driver" {
  role = aws_iam_role.driver.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["bedrock-agentcore:*", "lambda:*Microvm*", "lambda:TagResource", "lambda:ListTags", "lambda:PassNetworkConnector", "lambda-microvms:*", "logs:*", "cloudwatch:GetMetric*", "cloudwatch:ListMetrics", "xray:Get*", "xray:List*", "xray:BatchGet*", "eks:Describe*", "eks:List*", "eks:UpdateNodegroupConfig", "ec2:Describe*", "autoscaling:Describe*"], Resource = "*" },
      { Effect = "Allow", Action = ["s3:*"], Resource = [aws_s3_bucket.bench.arn, "${aws_s3_bucket.bench.arn}/*"] },
      { Effect = "Allow", Action = ["iam:PassRole"], Resource = [aws_iam_role.agentcore_exec.arn, aws_iam_role.microvm_exec.arn, aws_iam_role.microvm_build.arn] },
      { Effect = "Allow", Action = ["iam:CreateServiceLinkedRole"], Resource = "*" },
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:DescribeImages"], Resource = "*" }
    ]
  })
}
resource "aws_eks_pod_identity_association" "driver" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "bench"
  service_account = "driver"
  role_arn        = aws_iam_role.driver.arn
}

output "cluster" { value = aws_eks_cluster.this.name }
output "ecr" { value = aws_ecr_repository.agent.repository_url }
output "bucket" { value = aws_s3_bucket.bench.bucket }
output "agentcore_exec_role" { value = aws_iam_role.agentcore_exec.arn }
output "microvm_build_role" { value = aws_iam_role.microvm_build.arn }
output "microvm_exec_role" { value = aws_iam_role.microvm_exec.arn }
