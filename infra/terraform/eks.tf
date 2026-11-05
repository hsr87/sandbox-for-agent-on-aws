data "aws_iam_policy_document" "eks_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}
data "aws_iam_policy_document" "node_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "cluster" {
  name               = "${var.name}-cluster"
  assume_role_policy = data.aws_iam_policy_document.eks_trust.json
}
resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}
resource "aws_iam_role" "node" {
  name               = "${var.name}-node"
  assume_role_policy = data.aws_iam_policy_document.node_trust.json
}
resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "AmazonEKSWorkerNodePolicy",
    "AmazonEC2ContainerRegistryPullOnly",
    "AmazonEKS_CNI_Policy",
    "AmazonSSMManagedInstanceCore",
  ])
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/${each.value}"
}

resource "aws_eks_cluster" "this" {
  name     = var.name
  version  = var.k8s_version
  role_arn = aws_iam_role.cluster.arn
  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true
  }
  vpc_config {
    subnet_ids              = aws_subnet.private[*].id
    endpoint_public_access  = true
    endpoint_private_access = true
  }
  depends_on = [aws_iam_role_policy_attachment.cluster]
}

resource "aws_eks_addon" "core" {
  for_each   = toset(["vpc-cni", "kube-proxy", "coredns", "eks-pod-identity-agent"])
  cluster_name = aws_eks_cluster.this.name
  addon_name   = each.value
  depends_on   = [aws_eks_node_group.ng]
}

locals {
  # Installs gVisor on gvisor nodes only. Kata is installed later by kata-deploy.
  # The containerd stanza goes through NodeConfig because the AL2023 EKS containerd
  # config has no config.d import.
  gvisor_userdata = <<-MIME
    MIME-Version: 1.0
    Content-Type: multipart/mixed; boundary="BOUNDARY"

    --BOUNDARY
    Content-Type: application/node.eks.aws

    apiVersion: node.eks.aws/v1alpha1
    kind: NodeConfig
    spec:
      containerd:
        config: |
          [plugins."io.containerd.cri.v1.runtime".containerd.runtimes.runsc]
          runtime_type = "io.containerd.runsc.v1"

    --BOUNDARY
    Content-Type: text/x-shellscript; charset="us-ascii"

    #!/bin/bash
    set -eux
    ARCH=$(uname -m)
    URL=https://storage.googleapis.com/gvisor/releases/release/${var.gvisor_release}/$ARCH
    cd /tmp
    command -v zstd >/dev/null || dnf install -y -q zstd
    curl -fsSLO $URL/gvisor.tar.zstd
    curl -fsSLO $URL/gvisor.tar.zstd.sha512
    sha512sum -c gvisor.tar.zstd.sha512
    tar --zstd -xf gvisor.tar.zstd -C /usr/local/bin
    chmod 0755 /usr/local/bin/runsc /usr/local/bin/containerd-shim-runsc-v1
    /usr/local/bin/runsc --version
    --BOUNDARY--
  MIME
}

resource "aws_launch_template" "ng" {
  for_each = var.node_groups
  name     = "${var.name}-${each.key}"
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 100
      volume_type = "gp3"
      iops        = 6000
      throughput  = 400
    }
  }
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  dynamic "cpu_options" {
    for_each = each.value.nested ? [1] : []
    content { nested_virtualization = "enabled" }
  }
  user_data = each.value.runtime == "gvisor" ? base64encode(local.gvisor_userdata) : null
  tag_specifications {
    resource_type = "instance"
    tags          = { project = "sandbox-bench", Name = "${var.name}-${each.key}" }
  }
}

resource "aws_eks_node_group" "ng" {
  for_each        = var.node_groups
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = each.key
  node_role_arn   = aws_iam_role.node.arn
  # Single AZ: the driver and the sandboxes are always one network hop apart.
  subnet_ids     = [aws_subnet.private[0].id]
  ami_type       = each.value.arch == "arm64" ? "AL2023_ARM_64_STANDARD" : "AL2023_x86_64_STANDARD"
  instance_types = [each.value.instance]
  capacity_type  = "ON_DEMAND"
  labels         = { "bench/runtime" = each.value.runtime, "bench/group" = each.key }
  launch_template {
    id      = aws_launch_template.ng[each.key].id
    version = aws_launch_template.ng[each.key].latest_version
  }
  scaling_config {
    desired_size = each.value.size
    min_size     = 0
    max_size     = 6
  }
  lifecycle { ignore_changes = [scaling_config[0].desired_size] }
  depends_on = [aws_iam_role_policy_attachment.node]
}
