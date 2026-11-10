# Agent sandboxes on AWS, measured

[한국어](README.ko.md)

The same Claude Agent SDK application, run on five sandbox options on AWS and measured from a driver in the same region. Measured in `us-east-1`, 2026-11-03 to 05, with several rounds and follow-up tests, and part repeated in `ap-northeast-1`. EKS Fargate and Nitro Sandboxes were added on 2026-11-10 with the same experiments. Measured numbers are generated from `results/raw/`. Measured values are the default; anything taken from documentation is marked (doc), and anything not tested is marked n/t.

## Results vary

These results come mostly from one region (us-east-1), with part repeated in ap-northeast-1, over three days plus one more day for Fargate and Nitro, one account and one application. They can change with region, quotas, account limits, available capacity, instance type, image, application and time of day. Treat them as a starting point and repeat them with your own agent before you decide.

## Key findings

| Finding | Evidence |
|---|---|
| No option wins everywhere. The order changes with what you measure. | Small agent task, same period and shuffled, whole request: gVisor 9.9 s, V1 10.4 s, Kata 14.3 s, MicroVM 17.4 s, V2 33.3 s. 100 at once on echo: V2 2.28 s, gVisor 5.18 s, V1 8.18 s, Kata 11.55 s. |
| V1's start depends on arrival rate and packaging. | Same-period low rate p50 0.49 s, p90 0.70 s. 5 per second 7.37 s, 1.5 GB image 17.61 s, direct code 2.80 s, VPC mode 7.36 s. |
| V2 starts in 1.8 to 3.5 s across the conditions tested, on echo, in the range AWS published. | Low rate 1.92 s, 5 per second 1.79 s, 100 at once 2.28 s, new 1.5 GB runtime 1.79 s, VPC mode 1.83 s, VPC mode at 100 at once 3.49 s. |
| On V2 and MicroVM a new session is slow the first time it reads a large file. The Claude Agent SDK, with its large CLI, waits long for its first message; the Strands Agents SDK, with a small install, does not. | V2 first message on new runtimes: p50 15.6 s, p90 40.5 s, 45% over 20 s, 20 of 20 succeeded. 331 MB CLI on a new V2 sandbox: first read 38.0 s, second 0.04 s. First read of a 200 MB file p50: V2 16.6 s, MicroVM 24.3 s, V1 0.01 s. Until the first model event on V2: Claude Agent SDK 25.4 s, Strands 2.3 s. |
| Mapping the large file before the snapshot, or fetching it from S3 at session start, removes the wait. Periodic warm-up calls reduce it partly and only for the runtime they call. | Same period, V2 first message p50: mapped 2.2 s, S3 3.1 s, warm-up every 5 minutes 6.1 s, 4 every 10 minutes 7.1 s, nothing 34.2 s. MicroVM: mapped 1.7 s, S3 2.0 s, nothing 26.3 s. First read on the warmed runtime 7.4 s, on another runtime with the same image 56.5 s, on a runtime of its own 52.9 s. |
| EKS improves a lot when tuned. | Warm pods that ran the task before ready: first message gVisor 0.4 s, Kata 0.5 s; whole request 6.8 s and 7.3 s. These pods cost nodes while they wait. |
| On a build task gVisor and V1 are fastest and V2 is slowest. | Shuffled in one period, whole request: gVisor 19.0 s, V1 20.0 s, gVisor Graviton3 22.1 s, MicroVM 25.1 s, Kata 29.5 s, V2 47.5 s. After the first message alone, V2 26.2 s against V1 15.6 s. |
| EKS can scale nodes from zero with Karpenter, but default consolidation ends running sessions. | First gVisor sandbox on an empty cluster 31.2 s, 50 all ready in 46.0 s. In a 101 minute trace: 24 of 424 sessions ended by default consolidation, 0 of 389 with do-not-disrupt, at about 30% more node hours. |
| Tokyo showed the same pattern. | ap-northeast-1 low-rate start: V1 0.51 s, gVisor 0.95 s, V2 1.83 s, Kata 3.89 s. Agent first message p50: V2 11.0 s (p90 34.8 s), the others 0.6 to 1.2 s. |
| Nitro Sandboxes give each pod its own VM at almost no syscall cost, and start close to Kata. They slow down under steady arrivals. | Start 4.46 s (Kata 3.87 s, gVisor 1.09 s in the same period), warm pool claim 0.08 s. getppid 82 ns, open+close 1.0 µs, close to runc. Build 24.3 s, between gVisor 19.0 s and Kata 27.4 s. 5 per second 25.5 s. |
| EKS Fargate needs no nodes, but every sandbox takes about a minute to start. | Start p50 57.7 s at 0.25 vCPU and 58.2 s at 2 vCPU, about the same at 100 at once and at 5 per second. After start the agent ran in 8.0 s, gVisor 7.7 s in the same period. |
| Cost depends on scale and session shape. | Interactive scenario with explicit stop: V2 $833, gVisor $1,011, V1 $1,067, MicroVM from $3,430. Without a stop V2 $1,653, V1 $2,199. Steady scenario: gVisor $3,069, V2 $8,588. |

## Which option for which situation

| Situation | First choice | Measured reason | Avoid or check |
|---|---|---|---|
| Sparse interactive sessions, small team | AgentCore V1 | Whole request 10.4 s, first message 2.2 s, deploy about 3 s, metrics with no setup. Scenario $1,067 a month, V2 $833, gVisor $1,011 to $869 | Start time depends on the arrival rate: 0.49 s at low rate, 7.37 s at 5 new sessions per second |
| V1, but steady arrivals and a small package | AgentCore V1, direct code | 3.28 s at low rate, 2.80 s at 5 per second, 3.31 s for 100 at once, deploy about 30 s | Package limits apply (250 MB zipped, 750 MB unzipped, doc). Not tested in VPC mode |
| Large bursts or large images with no spare nodes held, when the app does not need a large first read | AgentCore V2 | 2.28 s for 100 at once, 1.79 s for a new 1.5 GB runtime. With nodes ready, gVisor is faster at small scale (1.02 s at 5 per second, V2 1.79 s) and slower at 100 (5.18 s). MicroVM ties V2 up to its quota (1.78 s) | Agents that load a large binary: first message p50 15.6 s, p90 40.5 s on new runtimes. Deploy about 200 s. Not in Seoul (doc) |
| Agents on V2 that must start fast from the first run | V2, large file mapped before the snapshot or fetched from S3 at session start | First message p50: mapped 2.2 s, fetched from S3 3.1 s, nothing 34.2 s. Runs over 20 s out of 16: 0, 0 and 11 | Periodic warm-up calls help less (6.1 s at 5 minutes) and only for the runtime they call. Running the CLI before the snapshot was not consistent. Mapping and fetching did not raise billed memory |
| Must run inside your VPC | EKS if you run it, otherwise AgentCore V2 for start time | EKS is always in the VPC: gVisor 1.07 s start, 9.9 s whole request. AgentCore VPC mode: start V2 1.83 s, V1 7.33 s. 100 at once V2 3.49 s, V1 11.16 s | VPC mode did not change the agent's whole request against public mode: V1 9.8 s and 10.2 s, V2 32.1 s and 33.0 s. First deploy V1 268 s, V2 518 s |
| Sessions that sit idle until reclaimed | AgentCore V2 | Idle until the default 15 minute reclaim billed 0.26 GB-h on V2 and 0.73 on V1, $0.0049 and $0.0078 | Both versions end an idle session at 15 minutes by default, so state does not survive longer unless you change the timeout. Measured on this image. An AWS blog example shows V2 memory depends on the app |
| Steady high concurrency with a platform team | gVisor + Agent Sandbox | Steady scenario $3,069 a month ($2,503 on Graviton3), V2 $8,588. 5.18 s for 100 at once on prepared nodes | Staff cost is not included. A new node adds about 41 s. Metrics, reclamation and policy are yours. The default is not hardened |
| Lowest agent readiness, willing to pay for idle capacity | EKS Warm Pool that runs the task before ready | First message gVisor 0.4 s, Kata 0.5 s. Whole request 6.8 s and 7.3 s | Warm pods cost nodes (30 pods move the interactive break-even from 43 to 71 sessions). The warm-up itself calls the model. 10 runs each |
| A guest kernel on your own cluster | Kata + QEMU + Agent Sandbox | Guest kernel per pod, 3.89 s start, 11.55 s for 100 at once on 8 nodes. Metal lowers the build task from 28.3 s to 24.4 s | 375 MB per idle sandbox against 58 MB, and half as many per node. Needs nested virtualization or metal. Only virtio-fs tested |
| Build-heavy agents, mostly on CPU | gVisor or V1, decide on cost and operations | Build task, shuffled in one period: gVisor 19.0 s, V1 20.0 s, gVisor Graviton3 22.1 s, MicroVM 25.1 s, Kata 29.5 s, V2 47.5 s. gVisor and V1 overlap | Monthly scenario: gVisor $2,040, Kata $2,383, V1 $2,804, V2 $3,726, MicroVM $3,857. gVisor's rootfs is memory-backed here and managed CPU generations vary, so this mixes more than isolation |
| Sessions that pause and continue with memory intact, or your own harness | Lambda MicroVMs | Resume 0.27 s by API, 8.4 s by traffic, memory and disk kept in every run. Whole request 17.4 s, p90 39.6 s | Baseline billed while running, costing more than the stopped and autoscaled options in our scenarios at the tested size. Suspending pays off only when each idle period passes about 5 minutes at 2 GB. Default 5 per second RunMicrovm quota. Routing is yours |
| EKS that scales nodes from zero | gVisor + Karpenter, do-not-disrupt on session pods | First sandbox on an empty cluster 31.2 s, 50 sandboxes all ready in 46.0 s. In a 101 minute trace, default consolidation ended 24 of 424 sessions and do-not-disrupt ended 0 of 389 | do-not-disrupt used about 30% more node hours per session hour. Kata on a new Karpenter node took about 141 to 151 s, mostly kata-deploy, so keep Kata nodes warm |
| Keep work files when an AgentCore session stops and restarts | AgentCore session storage (preview) | Stopped and restarted with the same session ID 10 times: /tmp was empty every time and the file in session storage was kept every time (10 of 10). Reading the 331 MB CLI from it took 0.2 s. With the CLI there, first message after a restart 1.9 s | Preview, tested on V2 only. The first copy into it is extra (from S3, about 2 s for 331 MB) |
| A VM per pod on EKS, without nested virtualization or metal | Nitro Sandboxes (EKS Auto Mode) | Own guest kernel per pod. Start 4.46 s, warm pool claim 0.08 s. Syscalls close to runc (open+close 1.0 µs, Kata 104 µs). Build 24.3 s, Kata 27.4 s in the same period | The VM gets the pod's requests and its memory is reserved in full, so set requests to what the agent needs (3 sandboxes of 2 vCPU, 8 GB per m8i.2xlarge). 5 new sessions per second queued to 25.5 s. Sequential write 50 MB/s. Kubernetes 1.36 or later, US regions on EKS (doc), Auto Mode fee unless you build the AMI |
| Pause and resume with work files kept, on EKS | Nitro Sandboxes + agent-sandbox Suspended with an EBS volume | Suspend 2.0 s, resume 16.4 s, the file on the volume kept 5 of 5 times. While suspended the sandbox holds no node capacity; the volume is still billed | Memory is not kept (0 of 5); resume is a new VM. A single-attach volume pins the sandbox to one zone. MicroVM resume kept memory |
| A few sessions at a time, no nodes to manage, start time not critical | EKS Fargate | No node groups. Agent time after start 8.0 s, gVisor 7.7 s. Coding scenario $843 a month at the smallest size, $2,124 at 2 vCPU, 8 GB | Every sandbox starts in about 58 s and that minute is billed. No warm pool, no gVisor or Kata, no DaemonSets, no Pod Identity (IRSA instead). An older CPU here: pure Python 2.1x Nitro |
| Already running EKS | gVisor + Agent Sandbox | Interactive scenario adds $686 a month on an existing cluster, $833 on V2 | Assumes ideal scale-down. Sized for peak the node count doubles |
| Seoul region required | AgentCore V1 or EKS | V2 and MicroVMs are not in Seoul (doc, 2026-11-03) | Nothing here was measured in Seoul |

## Results

Values are p50 unless marked. Where confidence intervals overlap, we do not call it a difference. First message runs from the `query()` call, after the SDK import, to the first object the SDK yields, which comes before the first model stream event. It leaves out sandbox start and the SDK import. Whole request is sandbox start plus the agent call: SDK import, task, the harness's pytest and network.

### Cold start, from request to echo reply

Same period, shuffled, one round on new managed runtimes after 10 agent runs on each:

|  | gVisor x86 | gVisor Graviton3 | Kata | AgentCore V1 | AgentCore V2 | Lambda MicroVMs |
|---|---|---|---|---|---|---|
| p50 | 1.07 s | 1.32 s | 4.06 s | 0.49 s | 1.92 s | 1.82 s |
| p90 | 1.11 s | 1.38 s | 4.11 s | 0.70 s | 2.23 s | 2.01 s |
| Share under 3 s | 100% | 100% | 0% | 97% | 100% | 100% |
| Arrival interval per option | 20 s | 21 s | 20 s | 20 s | 19 s | 17 s |

Other conditions and earlier rounds:

|  | gVisor | Kata + QEMU | AgentCore V1 | AgentCore V2 | Lambda MicroVMs |
|---|---|---|---|---|---|
| p50 | 0.93 s | 3.89 s | 0.56 s | 1.78 s | 1.78 s |
| p90 | 1.02 s | 4.00 s | 7.38 s | 2.25 s | 1.99 s |
| 1.5 GB image | 0.95 s | 3.91 s | 0.89 s | 1.93 s | 1.87 s |
| 10 s start-up work | 10.91 s | 13.92 s | 0.63 s | 1.93 s | 1.98 s |
| n / failures | 90 / 0 | 90 / 0 | 30 / 0 | 30 / 0 | 90 / 0 |

V1 and V2 use the image with the documented /ping, except the 1.5 GB and start-up rows, which use the earlier /ping. Warm pools: gVisor 66 ms, Kata 66 ms, paying for the pods kept ready. Baselines: runc 0.85 s, Kata on metal 3.48 s. Warm calls from the driver take about 1 ms on EKS, 3.9 ms on MicroVM, 91 ms on V1 and 115 ms on V2, so differences within 0.1 s should not be ranked.

### Packaging and network mode on AgentCore

|  | Low rate | p90 | 1 per second | 5 per second | 100 at once | New runtime | Deploy |
|---|---|---|---|---|---|---|---|
| V1 container 276 MB | 0.56 s | 7.38 s | 7.36 s | 7.37 s | 8.16 s | 9.4 s | 3 s |
| V1 container 1.5 GB | 0.89 s | 1.85 s | 17.57 s | 17.61 s | 18.45 s | 21.6 s | 3 s |
| V1 direct code | 3.28 s | 3.80 s | 2.81 s | 2.80 s | 3.31 s | 3.3 s | 30 s |
| V1 container 49 MB, no SDK | 0.42 s | 0.77 s | 0.40 s | 3.28 s | 4.23 s | 3.3 s | 3 s |
| V1 VPC mode | 7.33 s | 9.35 s | 7.33 s | 7.36 s | 11.16 s | n/t | 268 s |
| V2 container 276 MB | 1.78 s | 2.25 s | 1.84 s | 1.79 s | 2.28 s | 2.1 s | 200 s |
| V2 direct code | 2.05 s | 2.32 s | 1.83 s | 1.79 s | 2.37 s | 2.1 s | 241 s |
| V2 VPC mode | 1.83 s | 2.30 s | 1.77 s | 1.77 s | 3.49 s | n/t | 518 s |

The docs conflict on the direct code limit (1.6 and 25 sessions per second). New runtime values are the p50 of the first call on 3 separate runtimes. The 1.5 GB row, the new runtime cells of the 276 MB rows and the 276 MB V2 sustained and burst values use the earlier /ping. Failures left out of these p50s: V2 VPC 1 of 30 at low rate (throttled, not retried in this test), V2 2 of 600 at 5 per second (a 504 and an internal error), V1 1 of 1,200 at 10 per second.

The same agent task in VPC and public mode, shuffled in one period, 12 runs each:

|  | First message | Whole request | 95% CI of p50 |
|---|---|---|---|
| V1 VPC mode | 2.1 s | 9.8 s | 9.4 to 10.3 s |
| V1 public | 2.1 s | 10.2 s | 9.7 to 11.0 s |
| V2 VPC mode | 15.6 s | 32.1 s | 18.6 to 55.1 s |
| V2 public | 16.8 s | 33.0 s | 20.5 to 51.6 s |

The intervals overlap within each version, so VPC mode did not change agent time. V2 is slower than V1 here because of the first read described below.

### Bursts and sustained arrivals

|  | gVisor | Kata + QEMU | AgentCore V1 | AgentCore V2 | Lambda MicroVMs |
|---|---|---|---|---|---|
| Burst of 10 | 1.33 s | 4.07 s | 0.96 s | 1.89 s | 1.99 s |
| Burst of 50 | 2.85 s | 5.83 s | 8.01 s | 2.35 s | removed |
| Burst of 100 | 5.18 s | 11.55 s | 8.18 s | 2.28 s | removed |
| Sustained 1/s | 0.94 s | 3.92 s | 7.34 s | 1.84 s | 1.75 s |
| Sustained 5/s | 1.02 s | 4.90 s | 7.39 s | 1.79 s | 1.78 s |

Bursts are the median of 3 rounds from a dedicated 8 vCPU driver, with 4 gVisor nodes and 8 Kata nodes holding the image, so node scale-up is not included. A new node adds about 41 s for gVisor and 192 s for Kata. MicroVM above its default RunMicrovm quota of 5 per second was removed because the quota, not the platform, set the value; the quota is adjustable and was not raised. V1 is the 276 MB container with the earlier /ping. Warm pools with prepared pools: gVisor 1.93 s for 50, Kata 0.96 s for 40, one round. EKS completion is polled, which can add up to 0.5 s at 100. gVisor's p50 grows with size (1.33 s at 10, 5.18 s at 100). One request of a burst of 50 failed in the final rounds on V1 with the documented /ping (a 504), a runtime not shown in this table.

### One real task through the Claude Agent SDK

|  | First message | p90 | Over 20 s | Whole request | p90 | 95% CI of p50 | Succeeded |
|---|---|---|---|---|---|---|---|
| gVisor x86 | 1.9 s | 3.6 s | 0% | 9.9 s | 11.7 s | 9.7 to 10.8 s | 20/20 |
| gVisor Graviton3 | 2.2 s | 2.5 s | 0% | 11.5 s | 12.5 s | 11.3 to 11.7 s | 20/20 |
| Kata nested | 2.5 s | 3.3 s | 0% | 14.3 s | 16.0 s | 14.1 to 14.7 s | 20/20 |
| AgentCore V1 | 2.2 s | 3.3 s | 0% | 10.4 s | 12.0 s | 9.7 to 11.2 s | 20/20 |
| AgentCore V2, new runtimes | 15.6 s | 40.5 s | 45% | 33.3 s | 70.3 s | 19.8 to 58.6 s | 20/20 |
| MicroVMs, new images | 3.1 s | 13.3 s | 10% | 17.4 s | 39.6 s | 16.4 to 21.7 s | 20/20 |

This table is one same-period shuffled test: two new managed runtimes per option, 10 runs each, so each option gets the same arrival pattern. It is the small coding task and the time includes the harness's final pytest. Model time p50 ranged from 6.4 to 8.8 s across rounds, about 1 s higher on some V2 and MicroVM rounds, and no run failed. EKS is x86, with Graviton3 as a CPU control. EKS nodes keep a warm page cache and managed sandboxes do not, which is part of the difference.

#### Another agent SDK: Strands Agents

Same task on every option, 20 runs each on managed (2 runtimes) and 10 on EKS, shuffled in one period. Ready is SDK import plus the time to the first model stream event, since the two SDKs report different first objects.

|  | Claude Agent SDK, ready | p90 | Strands, ready | p90 | Claude, whole request | Strands, whole request |
|---|---|---|---|---|---|---|
| gVisor | 3.6 s | 5.6 s | 1.5 s | 1.6 s | 9.5 s | 8.6 s |
| Kata | 4.6 s | 6.6 s | 2.0 s | 4.6 s | 13.8 s | 12.9 s |
| AgentCore V1 | 4.0 s | 5.7 s | 1.6 s | 1.8 s | 9.6 s | 8.4 s |
| AgentCore V2 | 25.4 s | 47.6 s | 2.3 s | 15.2 s | 38.3 s | 12.8 s |
| Lambda MicroVMs | 7.3 s | 29.4 s | 1.7 s | 12.9 s | 18.0 s | 12.6 s |

All 160 runs succeeded. The Strands app is ours, with 3 tools, and its install is far smaller than the Claude Agent SDK's bundled CLI. On V2 and MicroVM the gap is the first read; elsewhere the two differ by about 2 s.

#### First read by file size

| File | V1 | V2 | V2 p90 | MicroVM | MicroVM p90 |
|---|---|---|---|---|---|
| 10 MB | 0.00 s | 0.0 s | 2.4 s | 0.0 s | 2.2 s |
| 50 MB | 0.00 s | 1.0 s | 11.7 s | 1.6 s | 10.2 s |
| 100 MB | 0.01 s | 3.1 s | 21.5 s | 4.7 s | 21.7 s |
| 200 MB | 0.01 s | 16.6 s | 42.6 s | 24.3 s | 39.7 s |

8 new sessions per cell, one file of random bytes in the image, read once in a Strands app. The second read was under 0.1 s everywhere. Small files are fast; the wait grows with size and varies a lot between sessions.

V1 direct code had no such delay (first message 2.0 s, whole request 15.0 s). V2 direct code did (28.5 s, 50.5 s). Dropping the page cache on EKS nodes shows the same effect at smaller scale: gVisor 2.8 s first message, Kata 3.2 s. Whole request then becomes gVisor 12.4 s and Kata 16.2 s. So EKS's advantage here partly reflects a local disk and a warm page cache.

#### Mitigations (first message, whole request)

All arms ran in one period: 2 runtimes per arm, 8 probes each, 16 minutes apart, so each probe lands on a session that the arm itself has not touched for a while. Billed usage comes from USAGE_LOGS over the 2.4 hours.

| Mitigation | V2 first message | Over 20 s | Whole request | MicroVM first message | Over 20 s | Whole request |
|---|---|---|---|---|---|---|
| None | 34.2 s (p90 45.2) | 11/16 | 52.0 s | 26.3 s (p90 43.2) | 10/16 | 41.5 s |
| Map the CLI file before the snapshot | 2.2 s (p90 6.0) | 0/16 | 16.7 s | 1.7 s (p90 4.7) | 0/16 | 12.8 s |
| Fetch the CLI from S3 at session start | 3.1 s (p90 4.8) | 0/16 | 19.6 s | 2.0 s (p90 3.7) | 0/16 | 18.4 s |
| Warm-up call every 5 minutes | 6.1 s (p90 12.1) | 1/16 | 30.3 s | n/t |  |  |
| 4 warm-up calls every 10 minutes | 7.1 s (p90 15.2) | 0/16 | 25.5 s | n/t |  |  |
| Run the CLI before the snapshot | 46.9 s (p90 60.6) | 14/15 | 67.7 s | n/t |  |  |

Mapping and S3 did not raise billed memory: per probe session mapping used 14 MB-h and S3 14 MB-h against 26 MB-h with none, because the sessions end sooner. Warm-up calls added about $0.0043 an hour per runtime at 5 minutes and $0.0083 with 4 every 10 minutes. Running the CLI before the snapshot was slower than none here, and one of its 16 runs timed out in SDK start-up; earlier rounds gave mixed results, so we do not recommend it. The CLI version differs by arm, so its size ranges from 292 to 337 MB.

Warming only helps the runtime it calls. One 331 MB file, read once per probe, 8 probes 16 minutes apart per runtime:

| Runtime | First read | p90 | 95% CI of p50 | Over 20 s |
|---|---|---|---|---|
| Warmed every 5 minutes | 7.4 s | 9.9 s | 4.1 to 9.5 s | 0/16 |
| Same image as a warmed runtime | 56.5 s | 71.0 s | 45.1 to 63.0 s | 16/16 |
| Same bytes in a different image layer | 52.9 s | 80.1 s | 37.8 to 71.3 s | 16/16 |
| Its own image, not warmed | 52.9 s | 77.2 s | 36.4 to 63.7 s | 14/16 |
| Untouched until the last slot | 86.8 s | 89.4 s | 86.2 to 89.4 s | 4/4 |

Two runtimes per row, except the untouched row with 4 runtimes probed once. The runtimes next to a warmed one gained nothing over a runtime of its own.

#### Session storage

| Where the CLI comes from (V2) | Fetch | First message | p90 | Whole request |
|---|---|---|---|---|
| In the image |  | 21.1 s | 33.5 s | 37.8 s |
| S3 to /tmp at session start | 1.6 s | 2.8 s | 4.3 s | 19.5 s |
| S3 to session storage at session start | 1.9 s | 2.2 s | 3.6 s | 22.8 s |
| Already in session storage, after a restart |  | 1.9 s | 4.5 s | 14.6 s |

8 runs per row. In a separate test the session was stopped and restarted with the same id 10 times: /tmp was empty each time (10 of 10) and the 331 MB file in session storage was there each time (10 of 10), read back in 0.21 s, and 0.19 s after dropping the page cache. Session storage is in preview.

#### Agents at the same time (whole request)

|  | 5 at once | 20 at once | 20 at once, p90 | First message at 20 |
|---|---|---|---|---|
| gVisor, 4 nodes | 10.1 s | 11.3 s | 12.0 s | 1.9 s |
| Kata, 8 nodes | 14.3 s | 15.1 s | 16.0 s | 2.6 s |
| AgentCore V1 | 13.8 s | 10.8 s | 18.1 s | 2.0 s |
| AgentCore V2 | 13.7 s | 14.6 s | 16.8 s | 2.4 s |
| Lambda MicroVMs | 11.8 s | 12.0 s | 13.5 s | 2.5 s |

Shuffled in one period, 4 batches per size, 500 runs, no failure and every pytest passed. Going from 5 to 20 at once did not slow any option by more than about 1.5 s. Managed runtimes had already run agents, so these are not new-runtime values.

#### Build task (whole request, 16 runs)

|  | Whole request | p90 | 95% CI of p50 | After the first message | 95% CI |
|---|---|---|---|---|---|
| gVisor x86 | 19.0 s | 23.4 s | 18.1 to 19.7 s | 14.8 s | 14.3 to 15.6 s |
| AgentCore V1 | 20.0 s | 21.9 s | 19.2 to 20.5 s | 15.6 s | 14.9 to 16.7 s |
| gVisor Graviton3 | 22.1 s | 23.8 s | 21.8 to 22.7 s | 17.1 s | 17.0 to 17.8 s |
| Lambda MicroVMs | 25.1 s | 75.2 s | 24.4 to 31.2 s | 17.5 s | 16.9 to 22.8 s |
| Kata nested | 29.5 s | 36.2 s | 28.4 to 30.6 s | 21.2 s | 20.1 to 22.1 s |
| AgentCore V2 | 47.5 s | 84.2 s | 36.3 to 61.8 s | 26.2 s | 24.9 to 27.3 s |

Shuffled in one period on runtimes that had not run the task before. After the first message is the agent's time minus its first message, so the first read of the CLI is out of it. Model time p50 was 13.8 to 14.6 s on every option. gVisor and V1 overlap. V2 stays slowest even after the first message. MicroVM sees 8 vCPU with a 2 vCPU billed baseline, gVisor's root filesystem is memory-backed here, and managed CPU generations vary by session, so this is not isolation cost alone. Kata on metal was measured separately and was faster than nested Kata.

### Workloads and syscalls

Compare within one CPU. x86 runs on m8i.2xlarge. Managed values are Graviton3 sessions only. Times in seconds, lower is better.

|  | runc x86 | gVisor x86 | Kata nested | Kata metal | runc G3 | gVisor G3 | V1 G3 | V2 G3 | MicroVM G3 |
|---|---|---|---|---|---|---|---|---|---|
| Compile stdlib | 0.81 | 0.97 | 1.70 | 1.24 | 1.08 | 1.47 | 1.07 | 1.07 | 0.97 |
| pytest, 70 tests | 0.38 | 0.43 | 0.80 | 0.57 | 0.48 | 0.65 | 0.46 | 0.46 | 0.42 |
| 2,000 small files | 0.08 | 0.07 | 0.88 | 0.55 | 0.15 | 0.14 | 0.11 | 0.11 | 0.09 |
| Touch 1 GB | 0.37 | 0.60 | 0.37 | 0.35 | 0.29 | 0.63 | 0.28 | 0.29 | 0.28 |
| Pure Python | 0.13 | 0.13 | 0.13 | 0.13 | 0.20 | 0.34 | 0.21 | 0.20 | 0.20 |
| getppid (ns) | 106.6 | 2,846.4 | 60.8 | 60.3 | 214.1 | 3,426.7 | 116.3 | 115.3 | 115.2 |
| open+close (µs) | 1.5 | 4.1 | 104.0 | 65.6 | 2.4 | 9.3 | 2.0 | 2.0 | 1.2 |
| fork+exec (µs) | 346.2 | 1,793.3 | 2,684.8 | 1,594.3 | 450.8 | 1,616.7 | 334.6 | 343.0 | 316.7 |

gVisor's fast disk numbers are not comparable: its root filesystem is a memory-backed overlay here (3,642 MB/s write with fsync). arm64 gVisor was also slower on pure Python (1.7x runc on Graviton3), which x86 did not show.

### Reclamation and lifecycle

|  | Observed |
|---|---|
| V2 with 60 s idle timeout | Alive at 60 s (3/3), gone at 70 s (0/3 alive) |
| V1 with 60 s idle timeout | Alive at 60 s (3/3), 1/3 alive at 70 s, gone at 90 s (0/3 alive) |
| AgentCore explicit stop, same session id | New instance, memory and disk gone, 5/5 on V1 and V2 |
| MicroVM idle policy 60 s, then suspended 120 s | SUSPENDED after 67 s, TERMINATED after 121 s |
| MicroVM resume | API 0.27 s, traffic 8.4 s. Memory and disk kept in every run, up to 2 GB held |
| EKS sandbox delete to pod gone | gVisor 2.3 s, Kata 2.0 s |
| EKS new node to first sandbox, then node removal | gVisor 41 s and 173 s. Kata 192 s including 132 s kata-deploy, and 183 s. Managed node group; Karpenter below |

Deploy times for comparison: EKS cluster and nodes about 19 minutes by one Terraform apply, not counting runtime install; MicroVM image about 160 s; AgentCore in the packaging table.

### EKS nodes from zero with Karpenter

| gVisor sandboxes at once | Pod p50 | All ready | Node Ready |
|---|---|---|---|
| 1 | 31.2 s | 31.2 s | 26.3 s |
| 20 | 33.4 s | 44.4 s | 25.3 s |
| 50 | 36.4 s | 46.0 s | 25.3 s |

Karpenter 1.15 with an m8i NodePool, from no nodes, 5 runs per size. A new node is Ready in about 26 s and the rest is image pull and pod start. Kata on a new Karpenter node took 141 to 151 s until a pod could run, of which kata-deploy took 109 to 120 s, so Kata nodes are better kept warm.

|  | Sessions | Ended by consolidation | Start p50 | Start max | Node hours | Node hours per session hour |
|---|---|---|---|---|---|---|
| Default consolidation | 424 | 24 | 1.03 s | 30.6 s | 4.0 | 0.056 |
| do-not-disrupt | 389 | 0 | 1.03 s | 34.1 s | 4.8 | 0.073 |

The same 101 minute trace of sessions that arrive, live a few minutes and end, run twice. In the default run Karpenter emptied nodes it judged underutilized twice, and those two disruptions account for every lost session. Marking session pods do-not-disrupt kept all of them, at the cost of slower scale-down. Most starts land on an existing node in about 1 s; the maximum is a new node.

### Tokyo (ap-northeast-1)

|  | gVisor | Kata + QEMU | AgentCore V1 | AgentCore V2 |
|---|---|---|---|---|
| Low rate | 0.95 s | 3.89 s | 0.51 s | 1.83 s |
| 5 per second | 1.41 s | 4.43 s | 7.38 s | 1.65 s |
| 100 at once, 3 rounds | 3.7 to 7.9 s | 10.8 to 11.5 s | 8.2 s | 2.2 to 2.3 s |
| Agent first message | 0.6 s | 1.2 s | 0.8 s | 11.0 s |
| First message p90 | 0.7 s | 1.6 s | 1.0 s | 34.8 s |
| Agent whole request | 8.2 s | 12.5 s | 8.3 s | 27.1 s |

Same images and method as us-east-1, driver in Tokyo. Every request succeeded. The order matches us-east-1: V1 fastest at low rate and slow at 5 per second, V2 flat under load but slow to its first message. The 331 MB CLI on new V2 sandboxes took 10 to 49 s to read the first time, on V1 under 0.1 s. MicroVMs and warm pools were not measured in Tokyo.

### EKS Fargate and Nitro Sandboxes (added 2026-11-10)

Two more options, measured five days later with the same app and the same experiments. **EKS Fargate** runs each sandbox pod in its own Fargate microVM, through a Fargate profile on the main cluster. **Nitro Sandboxes** (announced 2026-11-09) run each pod in its own VM on the Nitro hypervisor with `runtimeClassName: isolated-sandbox`; they ran on a separate EKS Auto Mode cluster in the same VPC and subnets, on the same m8i.2xlarge type and zone as the x86 node groups, because Auto Mode ships the runtime and the main cluster already runs its own Karpenter. Both size the VM from the pod's requests, not its limits, so each has a small size (0.25 vCPU, 512 MiB, for echo, bursts and arrivals) and a 2 vCPU, 8 GB size that matches the other sandboxes' limit (agent, build, workloads). gVisor with V1, and gVisor with Kata, ran in the same period as anchors for Fargate and Nitro.

|  | Start p50 | Start p90 | Warm pool claim | Agent first message | Agent whole request | Build whole request | Build, 95% CI of p50 |
|---|---|---|---|---|---|---|---|
| Nitro period: gVisor | 1.09 s | 1.14 s | 0.07 s | 1.7 s | 10.0 s | 19.0 s | 18.0 to 19.3 s |
| Nitro period: Kata | 3.87 s | 3.93 s | 0.07 s | 2.3 s | 13.7 s | 27.4 s | 26.4 to 28.2 s |
| **Nitro Sandboxes** | 4.46 s | 4.76 s | 0.08 s | 2.7 s | 14.8 s | 24.3 s | 23.1 to 26.0 s |
| Fargate period: gVisor | 1.11 s | 1.17 s |  | 1.7 s | 9.7 s | 19.0 s | 17.5 to 20.4 s |
| Fargate period: AgentCore V1 | 0.62 s | 0.85 s |  | 2.0 s | 9.5 s | 19.6 s | 19.1 to 21.0 s |
| **EKS Fargate** | 57.71 s | 64.21 s | none | 1.9 s | 65.0 s | 76.2 s | 74.1 to 79.5 s |

Start is 20 runs per option, shuffled; agent and build tasks are 12 runs per option (144 runs, 0 failed or failed pytest). Fargate's start is the same at both sizes (58.2 s at 2 vCPU, 8 GB) because every pod gets a new microVM and pulls the image; image caching (SOCI) does not apply to EKS Fargate. Once started, Fargate runs the agent about as fast as the others: agent time after start 8.0 s, gVisor 7.7 s. Nitro starts close to Kata and a warm pool claim takes the same time as gVisor's. Its first message is the slowest of its period, and its build sits between gVisor and Kata. Warm pools were not used in the agent rows.

|  | Burst of 10 | Burst of 50 | Burst of 100 | 1 per second | 5 per second | 5 per second, p90 |
|---|---|---|---|---|---|---|
| Nitro, nodes ready (rounds 2 and 3) | 5.1 to 5.5 s | 12.2 to 12.4 s | 24.2 to 24.5 s | 4.11 s | 25.49 s | 60.56 s |
| Nitro, round 1 with new nodes | 9.7 s | 34.2 s | 34.9 s |  |  |  |
| EKS Fargate | 57.1 s | 59.5 s | 61.3 s | 57.31 s | 56.78 s | 63.08 s |
| Earlier: gVisor, 4 nodes | 1.33 s | 2.85 s | 5.18 s | 0.94 s | 1.02 s | n/t |
| Earlier: Kata, 8 nodes | 4.07 s | 5.83 s | 11.55 s | 3.92 s | 4.90 s | n/t |

Three rounds each, 0 failed sandboxes. Fargate stays at about one minute whatever the size or rate, within its default launch quota (100 at once, 20 per second, doc). Nitro on nodes that were already up still queues: about 5 s for 10, 12 s for 50 and 24 s for 100 at once. Its first round waited for Auto Mode to add nodes. At 5 new sessions per second Nitro's p50 rose to 25.5 s with every sandbox deleted after its first reply, so the limit was start throughput, not capacity. The earlier gVisor and Kata rows ran in another period with more nodes held.

|  | runc x86 | gVisor x86 | Kata nested | Nitro | Fargate |
|---|---|---|---|---|---|
| Compile stdlib (s) | 0.81 | 0.97 | 1.70 | 0.80 | 2.03 |
| pytest, 70 tests (s) | 0.38 | 0.43 | 0.80 | 0.35 | 0.62 |
| 2,000 small files (s) | 0.08 | 0.07 | 0.88 | 0.08 | 0.22 |
| Pure Python (s) | 0.13 | 0.13 | 0.13 | 0.13 | 0.27 |
| getppid (ns) | 106.6 | 2,846.4 | 60.8 | 82.5 | 529.0 |
| open+close (µs) | 1.5 | 4.1 | 104.0 | 1.0 | 4.5 |
| fork+exec (µs) | 346.2 | 1,793.3 | 2,684.8 | 268.4 | 563.1 |
| Sequential write with fsync (MB/s) | 499 | 3,642 | 484 | 50 | 129 |

Nitro and Fargate are the 2 vCPU, 8 GB size, 3 sandboxes each; runc, gVisor and Kata are the earlier m8i.2xlarge runs. Nitro ran on the same CPU as the m8i nodes (Xeon 6975P-C) and its syscalls are as cheap as runc's: it pays neither gVisor's syscall cost nor Kata's virtio-fs file cost. Its sequential write was 50 MB/s, a tenth of runc's; we did not find out why. Fargate ran on an older CPU (Xeon Platinum 8259CL), so pure Python took about twice as long, and its syscalls and files are slower too. Both show their own guest kernel: Nitro 6.18.54 on a 6.18.56 host, Fargate 6.1.189.

Nitro pause and resume with an EBS volume, through agent-sandbox `operatingMode: Suspended` and back to `Running`. Each cycle created a sandbox with a new 10 GiB gp3 volume, wrote a value to a file on the volume and to process memory, suspended, resumed and read both back:

|  | New sandbox with volume | Suspend | Resume | File kept | Memory kept |
|---|---|---|---|---|---|
| p50 (5 cycles) | 12.6 s | 2.0 s | 16.4 s | 5/5 | 0/5 |
| max | 17.8 s | 2.1 s | 22.8 s |  |  |

Resume is a new pod and a new VM that mounts the same volume (5 of 5 new process, 5 of 5 on the same node), so it carries disk state, not memory. Compare MicroVM resume, which kept memory, and AgentCore session storage, which kept files.

Agents at the same time (whole request, 4 batches): Nitro 15.1 s at 5 and 16.3 s at 20, Fargate 65.8 s and 67.2 s, 0 failed. A 2 vCPU, 8 GB Nitro sandbox reserves its memory in full, so only 3 fit on an m8i.2xlarge and 20 at once need at least 7 nodes. First read of the 331 MB CLI on a new sandbox: Fargate 0.05 s, Nitro 0.51 s, so neither has the first-read delay of V2 and MicroVM.

Security defaults as in the table below, without hardening: both mount the service account token and can reach the Kubernetes API, other sandboxes and the internet, and neither has CAP_SYS_ADMIN or /dev/kvm. Nitro answers IMDS but only on the allowed paths, so no role is listed; credentials come from Pod Identity. Fargate has no IMDS. Fargate needed IRSA because Pod Identity does not run on Fargate, and DaemonSets do not run there either.

### Long requests with no bytes sent until the end

| Length | gVisor | Kata + QEMU | AgentCore V1 | AgentCore V2 | Lambda MicroVMs |
|---|---|---|---|---|---|
| 360 s | n/t | n/t | completed | completed | n/t |
| 600 s | n/t | n/t | completed | completed | n/t |
| 840 s | n/t | n/t | completed | completed | completed |
| 960 s | n/t | n/t | error at 899 s | error at 899 s | HTTP 502 at 900 s |
| 1200 s | completed | completed | error at 899 s | error at 899 s | HTTP 502 at 900 s |
| 1500 s, 15 s heartbeat | n/t | n/t | completed | completed | completed |

A handful of runs that locate a boundary. AgentCore clients use TCP keepalive. Requests through a NAT gateway without keepalive can be dropped at its documented 350 s idle timeout on any platform, so we removed those runs from the comparison; turn keepalive on in your client. The failure near 900 s matches AgentCore's documented 15 minute synchronous limit. AgentCore documents 60 minutes for streaming, not tested to that length.

### Cost scenarios, monthly compute in USD

| Scenario | Avg concurrent | V1 | V2 | MicroVM, 2 GB to tested 4 GB | gVisor, autoscaled | gVisor, peak | Kata, autoscaled | Kata, peak | V1, no stop | V2, no stop | gVisor, Graviton3 | gVisor, high memory | Nitro, Auto Mode | Fargate, smallest size | Fargate, 2 vCPU 8 GB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Interactive assistant | 35 | 1,067 | 833 | 3,430 to 6,624 | 1,011 | 1,697 | 1,354 | 2,726 | 2,199 | 1,653 | 869 | 1,354 | 1,085 | 729 | 3,560 |
| Short code execution | 17 | 1,084 | 1,234 | 3,948 to 5,546 | 1,011 | 1,697 | 1,354 | 2,040 | 12,410 | 9,434 | 869 | 1,011 | 1,085 | 1,239 | 4,640 |
| Coding agent with builds | 21 | 1,171 | 1,399 | 3,857 to 3,857 | 1,354 | 2,383 | 1,354 | 2,383 | 1,346 | 1,590 | 1,141 | 1,354 | 1,465 | 843 | 2,124 |
| Build-heavy agents, mostly on CPU | 21 | 2,804 | 3,726 | 3,857 to 3,857 | 2,040 | 4,441 | 2,383 | 5,127 | 2,978 | 3,917 | 1,686 | 2,040 | 2,225 | 1,850 | 2,124 |
| Steady high concurrency | 200 | 8,615 | 8,588 | 31,943 to 50,343 | 3,069 | 3,412 | 5,814 | 6,157 | 73,848 | 55,824 | 2,503 | 4,784 | 3,366 | 4,494 | 33,681 |

The scenarios are illustrations in `analysis/cost_model.py`; change them and rerun. Prices were checked against the public pages and the Pricing API on 2026-11-03, and the formulas reproduce AWS's worked examples (V2 $6,704 against $6,703, MicroVM $1,124 against $1,124). AgentCore idle memory and EKS overhead are measured. V1 and V2 assume the app stops each session; the no-stop columns add the default 15 minute idle tail at measured tail memory, and EKS has the same need to delete idle sandboxes. MicroVM use above its baseline may add charges. EKS includes the control plane, 2 system nodes, NAT Gateway and gp3 disks; on an existing cluster the interactive gVisor figure falls to $686. Excluded everywhere: LLM tokens, per-GB NAT and transfer, logs, staff, discounts. For the interactive shape, autoscaled gVisor and V2 break even near 43 average concurrent sessions, 71 with 30 warm pods, and never when sized for peak. These are first crossings; node counts step, so gVisor stays cheaper from 57, or 86 with 30 warm pods. MicroVM suspend adds snapshot write and read charges and pays off only when each idle period passes about 5 minutes at 2 GB, so the table shows no suspend. These are estimates, not a bill.

Nitro and Fargate columns were added on 2026-11-10 with prices from the Pricing API. Nitro uses the EKS formula with the RuntimeClass's 256 MiB pod overhead and the Auto Mode fee of $0.0508 an hour per m8i.2xlarge; with a custom AMI on your own node group there is no fee and it matches gVisor. Fargate bills $0.04048 per vCPU-hour and $0.004445 per GB-hour from image pull to pod end, with a one minute minimum, so each session also pays its measured one minute start; the cluster's fixed costs stay. The smallest size gives a session only its average CPU, because a Fargate pod cannot burst past its size; the 2 vCPU, 8 GB column is the size we tested.

### Security defaults: what a workload can see and reach

| Check | gVisor | Kata + QEMU | AgentCore V1 | AgentCore V2 | Lambda MicroVMs |
|---|---|---|---|---|---|
| CAP_SYS_ADMIN | no | no | yes | yes | no |
| Role listed through metadata | no | no | yes | yes | yes |
| Service account token mounted | yes | yes | no | no | no |
| Kubernetes API reachable | yes | yes | N/A | N/A | N/A |
| Internet egress in this setup | yes | yes | yes | yes | yes |
| io_uring | absent | callable | callable | callable | callable |
| /dev/kvm | no | no | no | no | no |

With VPC CNI network policy turned on, a warm pool sandbox got: peer timeout, Kubernetes API timeout, internet open, Pod Identity endpoint TimeoutError. The policy Agent Sandbox generates excludes 169.254.0.0/16, so AWS credential lookup failed with CredentialRetrievalError on gVisor and Kata. Add an exception for the Pod Identity endpoint, or inject credentials another way. A Sandbox created directly, without a SandboxTemplate, gets no policy and stayed open.

These are benign checks of defaults from inside a sandbox, not a penetration test, and say nothing about escape resistance. The role seen through metadata is the session's execution role. By default an EKS sandbox could reach another sandbox. Isolation between managed sessions is not covered here.

EKS ran as tested, not hardened. The AWS blog series recommends Pod Security restricted, non-root, dropped capabilities and no service account token; we did not apply them in this table. Warm pool templates did not mount the token. We recorded Pod Identity reachability only with network policy on (timeout), not in the default state. MicroVM internet egress was requested explicitly through its connector.

### Observability with no extra configuration

|  | gVisor / Kata (EKS) | AgentCore V1 / V2 | Lambda MicroVMs |
|---|---|---|---|
| App logs | kubectl logs while the pod lives, HTTP 404 after delete | CloudWatch, automatic | CloudWatch, with an execution role |
| Platform metrics | Nothing in this setup. EKS add-ons such as Container Insights were not installed or evaluated | Invocations, Sessions, Latency, Throttles, OverheadLatency, vCPU, memory | No service metrics in a full scan of the account's CloudWatch (log ingestion only) |
| Per-session usage | Build it | USAGE_LOGS after one delivery setting, 1 s granularity | Compute from run time |
| Control plane logs | All 5 types off by default | CloudTrail (doc) | CloudTrail (doc) |

### Density and environment

Host memory per idle sandbox: runc 32 MB, gVisor 58 MB, Kata 375 MB. Kata's RuntimeClass adds a 250m CPU pod overhead, so with a 250m request a node holds roughly half as many sandboxes.

## Method

- **Same app.** `app/` is one image with the Claude Agent SDK. MicroVMs build `FROM` that image. EKS and AgentCore pull it directly. Sandboxes are limited to 2 vCPU and 8 GiB, except MicroVMs at a 4 GB, 2 vCPU billed baseline that see 8 vCPU.
- **Same region.** Everything runs in `us-east-1`, including the driver; the Tokyo repeat ran its driver in `ap-northeast-1`. Paths still differ: EKS is reached on the Pod IP, managed services on public endpoints.
- **Same definition.** Timing starts just before the first call that asks for a sandbox and ends when the app answers. Agent readiness is measured separately.
- **Controls.** runc on the same nodes, gVisor and runc on Graviton3 to match the managed CPU, and Kata on `m8i.metal-48xl` to separate nested virtualization from Kata itself.
- **No capacity or quota penalty.** Results set by a quota or too few nodes were left out or measured again.
- **Order and failures.** The headline agent and cold start tables shuffle backends in each cycle so that none owns a time of day. The follow-up comparisons (mitigations, SDKs, network mode, builds, concurrency) each shuffled their arms in one period. Metal ran in its own period. Failures are recorded and counted; only failures are left out of timing, and slow runs stay in.
- **Claims.** `analysis/verify_claims.py` fails if a claim stops holding.

### Experiments

| What | Code |
|---|---|
| Cold start, image size, start-up work, first session on a new runtime | `cold_start`, `deploy.py --which fresh` |
| Packaging and network mode | `deploy.py --which pkg`, `deploy.py --which balance` |
| Round trip on an open sandbox | `warm_latency` |
| Workloads, syscalls, disk, network | `bench_suite`, `net_suite` |
| Claude Agent SDK task, first versus repeat start | `agent_e2e`, `agent_spaced`, `agent_concurrent`, `agent_first_vs_repeat`, `scripts/chain_same.sh`, `scripts/chain_quiet2.sh` |
| Bursts, sustained arrivals | `burst`, `sustained` |
| Reclamation, state wipe, suspend and resume, node scale | `idle_reclaim`, `state_wipe`, `suspend_resume`, `microvm_idle_policy`, `node_scale`, `scripts/kata_scale.py` |
| AgentCore billing inputs | `usage_sessions`, `usage_agent`, `analysis/fetch_usage.py` |
| Observability audit | `ops_experiments.py observability` |
| Security defaults | `security`, `cross_session` |
| Density, CPU census | `ops_experiments.py density`, `hw_census` |
| Long requests | `long_request` |
| First touch of files and tools | `first_touch` |
| Follow-ups: Strands Agents, file size, mitigations and warming, session storage, network mode, build, concurrency, Tokyo | `bench/followup/driver/xrun.py`, `bench/followup/app/x_entry.py`, `bench/followup/driver/*.json` |
| Follow-ups: Karpenter | `bench/followup/driver/kp.py`, `bench/followup/driver/kp_chain.sh` |
| Follow-ups: EKS Fargate and Nitro Sandboxes | `bench/followup/driver/fg_chain.sh`, `nt_chain.sh`, `na_chain.sh`, `nt_pause.py`, `infra/terraform/fargate.tf`, `infra/terraform/nitro.tf`, `infra/k8s/nitro*.yaml` |

## Limits of this test

- Mostly one region with a partial repeat in Tokyo, three days, one account, one application. Results can change with region, quotas, capacity and time. The first-read result depends on how large a file the agent reads first.
- Network paths differ between platforms, so round trips are not a pure runtime comparison.
- This test shows when the first read is slow and what removes it, not why it is slow inside the platform.
- Kata ran with its default virtio-fs. Block-device rootfs and memory-backed work directories were not tested.
- Not tested: 8 hour and 14 day sessions, Spot, gVisor on KVM, raised MicroVM quotas, EKS hardening options, X-Ray traces, Seoul, MicroVMs and warm pools in Tokyo, session storage on V1 and MicroVM.
- Some follow-ups have small samples (8 to 16 runs), so read their confidence intervals. The Strands app is ours, with 3 tools.
- Fargate and Nitro were measured on one day, five days after the others, against same-period anchors. Nitro ran on a separate Auto Mode cluster, with its own driver, in the same VPC and zone. Nitro was only tested in isolated mode, with defaults for its network and DNS limits.
- Security results describe defaults and are not a statement about escape resistance.
- Cost scenarios use assumed traffic. The AgentCore committed price status could not be confirmed and is not used.
- `results/raw/` also keeps runs left out of the tables, including the invalid `cold_uncached.jsonl`.

## Layout and reproduction

```
app/        agent image, workloads, probes
bench/      driver: backends, experiments, deployment; follow-ups in bench/followup/
infra/      Terraform and Kubernetes manifests
scripts/    chains that ran each round, result sync
analysis/   summary, facts, cost model, claim checks, README generator
results/    raw JSONL and generated summaries (account id removed)
```

```bash
cd infra/terraform && terraform init && terraform apply
# replace ACCOUNT_ID in infra/k8s/*.yaml, build images with Dockerfile*, install agent-sandbox and kata-deploy
kubectl apply -f infra/k8s/base.yaml -f infra/k8s/warmpools.yaml
# copy bench/ and scripts/ into the driver pod, then:
python deploy.py --which all
sh /work/scripts/chain_r1.sh
sh /work/scripts/chain_same.sh
scripts/pull_results.sh
python3 analysis/analyze.py && python3 analysis/cost_model.py && python3 analysis/followup.py && python3 analysis/facts.py
python3 analysis/verify_claims.py && python3 analysis/make_readme.py
```

**This is a disposable test bed, not a reference architecture.** The driver has cluster-admin, a privileged helper runs on nodes, the app's endpoint is unauthenticated inside the VPC, IAM is broad, and the EKS API endpoint is public. See the comments in `infra/terraform/iam.tf`. Delete it when you finish.
