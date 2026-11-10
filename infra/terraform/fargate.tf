# EKS Fargate as a sixth option: each sandbox pod gets its own Fargate microVM.
# Pods in the sandboxes namespace that carry the label bench/compute=fargate run on Fargate.
# EKS Pod Identity does not run on Fargate, so these pods get Bedrock access through IRSA instead.

data "aws_iam_policy_document" "fargate_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["eks-fargate-pods.amazonaws.com"]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:eks:${var.region}:${data.aws_caller_identity.me.account_id}:fargateprofile/${var.name}/*"]
    }
  }
}
resource "aws_iam_role" "fargate_pod_exec" {
  name               = "${var.name}-fargate-pod-exec"
  assume_role_policy = data.aws_iam_policy_document.fargate_trust.json
}
resource "aws_iam_role_policy_attachment" "fargate_pod_exec" {
  role       = aws_iam_role.fargate_pod_exec.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSFargatePodExecutionRolePolicy"
}

resource "aws_eks_fargate_profile" "sandbox" {
  cluster_name           = aws_eks_cluster.this.name
  fargate_profile_name   = "sandbox"
  pod_execution_role_arn = aws_iam_role.fargate_pod_exec.arn
  subnet_ids             = aws_subnet.private[*].id
  selector {
    namespace = "sandboxes"
    labels    = { "bench/compute" = "fargate" }
  }
}

resource "aws_iam_openid_connect_provider" "eks" {
  url            = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list = ["sts.amazonaws.com"]
}
data "aws_iam_policy_document" "sandbox_fargate_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub"
      values   = ["system:serviceaccount:sandboxes:sandbox-fargate"]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "sandbox_fargate" {
  name               = "${var.name}-sandbox-fargate"
  assume_role_policy = data.aws_iam_policy_document.sandbox_fargate_trust.json
}
resource "aws_iam_role_policy" "sandbox_fargate" {
  role   = aws_iam_role.sandbox_fargate.id
  policy = data.aws_iam_policy_document.sandbox_perm.json
}

output "sandbox_fargate_role" { value = aws_iam_role.sandbox_fargate.arn }
