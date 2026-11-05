variable "region" { default = "us-east-1" }
variable "name" { default = "sbx-bench" }
variable "k8s_version" { default = "1.36" }
variable "gvisor_release" { default = "20261102.0" }

# One node group per runtime so that runtimes never share a host during a run.
# size = desired node count; set metal to 1 only for the metal control run.
variable "node_groups" {
  default = {
    system     = { instance = "m7i.large", arch = "x86_64", runtime = "system", size = 2, nested = false }
    x86-runc   = { instance = "m8i.2xlarge", arch = "x86_64", runtime = "runc", size = 1, nested = true }
    x86-gvisor = { instance = "m8i.2xlarge", arch = "x86_64", runtime = "gvisor", size = 1, nested = true }
    x86-kata   = { instance = "m8i.2xlarge", arch = "x86_64", runtime = "kata", size = 1, nested = true }
    arm-runc   = { instance = "m8g.2xlarge", arch = "arm64", runtime = "runc", size = 1, nested = false }
    arm-gvisor = { instance = "m8g.2xlarge", arch = "arm64", runtime = "gvisor", size = 1, nested = false }
    # Graviton3: same CPU generation that AgentCore and MicroVMs reported (CPU part 0xd40).
    g3-runc    = { instance = "m7g.2xlarge", arch = "arm64", runtime = "runc", size = 1, nested = false }
    g3-gvisor  = { instance = "m7g.2xlarge", arch = "arm64", runtime = "gvisor", size = 1, nested = false }
    metal-kata = { instance = "m8i.metal-48xl", arch = "x86_64", runtime = "kata", size = 0, nested = false }
  }
}
