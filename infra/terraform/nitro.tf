# Nitro Sandboxes as a seventh option: each pod runs in its own Nitro hypervisor VM.
# Uses a separate EKS Auto Mode cluster, because Auto Mode ships the sandbox runtime and
# the main cluster already runs its own Karpenter. Same VPC and subnets as the main cluster,
# and the sandbox NodePool is pinned to the same zone and instance type as the x86 node groups.

data "aws_iam_policy_document" "nitro_cluster_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "nitro_cluster" {
  name               = "${var.name}-nitro-cluster"
  assume_role_policy = data.aws_iam_policy_document.nitro_cluster_trust.json
}
resource "aws_iam_role_policy_attachment" "nitro_cluster" {
  for_each = toset([
    "AmazonEKSClusterPolicy",
    "AmazonEKSComputePolicy",
    "AmazonEKSBlockStoragePolicyV2",
    "AmazonEKSLoadBalancingPolicy",
    "AmazonEKSNetworkingPolicy",
  ])
  role       = aws_iam_role.nitro_cluster.name
  policy_arn = "arn:aws:iam::aws:policy/${each.value}"
}

resource "aws_iam_role" "nitro_node" {
  name               = "${var.name}-nitro-node"
  assume_role_policy = data.aws_iam_policy_document.node_trust.json
}
resource "aws_iam_role_policy_attachment" "nitro_node" {
  for_each   = toset(["AmazonEKSWorkerNodeMinimalPolicy", "AmazonEC2ContainerRegistryPullOnly"])
  role       = aws_iam_role.nitro_node.name
  policy_arn = "arn:aws:iam::aws:policy/${each.value}"
}

resource "aws_eks_cluster" "nitro" {
  name                          = "${var.name}-nitro"
  version                       = var.k8s_version
  role_arn                      = aws_iam_role.nitro_cluster.arn
  bootstrap_self_managed_addons = false
  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true
  }
  compute_config {
    enabled       = true
    node_pools    = ["general-purpose", "system"]
    node_role_arn = aws_iam_role.nitro_node.arn
  }
  kubernetes_network_config {
    elastic_load_balancing { enabled = true }
  }
  storage_config {
    block_storage { enabled = true }
  }
  vpc_config {
    subnet_ids              = aws_subnet.private[*].id
    endpoint_public_access  = true
    endpoint_private_access = true
  }
  depends_on = [aws_iam_role_policy_attachment.nitro_cluster, aws_iam_role_policy_attachment.nitro_node]
}

# The same sandbox and driver roles as the main cluster.
resource "aws_eks_pod_identity_association" "nitro_sandbox" {
  cluster_name    = aws_eks_cluster.nitro.name
  namespace       = "sandboxes"
  service_account = "sandbox"
  role_arn        = aws_iam_role.sandbox_pod.arn
}
resource "aws_eks_pod_identity_association" "nitro_driver" {
  cluster_name    = aws_eks_cluster.nitro.name
  namespace       = "bench"
  service_account = "driver"
  role_arn        = aws_iam_role.driver.arn
}

output "nitro_cluster" { value = aws_eks_cluster.nitro.name }
