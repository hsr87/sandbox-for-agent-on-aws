# Agent sandboxes on AWS, measured

[한국어](README.ko.md)

The same Claude Agent SDK application, run on five sandbox options on AWS and measured from a driver in the same region. Measured in `us-east-1`, 2026-11-03 to 04, with several rounds and follow-up tests. Measured numbers are generated from `results/raw/`. Measured values are the default; anything taken from documentation is marked (doc), and anything not tested is marked n/t.

## Results vary

These results come from one region (us-east-1), two days, one account and one application. They can change with region, quotas, account limits, available capacity, instance type, image, application and time of day. Treat them as a starting point and repeat them with your own agent before you decide.

## Key findings

| Finding | Evidence |
|---|---|
| No option wins everywhere. The order changes with what you measure. | Small agent task, same period and shuffled, whole request: gVisor 9.9 s, V1 10.4 s, Kata 14.3 s, MicroVM 17.4 s, V2 33.3 s. 100 at once on echo: V2 2.28 s, gVisor 5.18 s, V1 8.18 s, Kata 11.55 s. |
| V1's start depends on arrival rate and packaging. | Same-period low rate p50 0.49 s, p90 0.70 s. 5 per second 7.37 s, 1.5 GB image 17.61 s, direct code 2.80 s, VPC mode 7.36 s. |
| V2 starts in 1.8 to 3.5 s across the conditions tested, on echo, in the range AWS published. | Low rate 1.92 s, 5 per second 1.79 s, 100 at once 2.28 s, new 1.5 GB runtime 1.79 s, VPC mode 1.83 s, VPC mode at 100 at once 3.49 s. |
| An agent with a large binary can wait long for its first message on V2. These are not errors. A slow first read fits the pattern, which is our interpretation. | V2 first message on new runtimes: p50 15.6 s, p90 40.5 s, 45% over 20 s, 20 of 20 succeeded. After a quiet hour: V2 29.9 s, MicroVM 5.1 s. CLI binary on a new V2 sandbox: first read 38.0 s, second 0.04 s. |
| On V2, only CLI file mapping kept the first 8 runs of a new runtime under 20 s. Running the CLI before the snapshot did not help those first runs but was faster in later rounds. Startup warm-up had no clear effect. | V2 first message: CLI file mapping 2.2 s (p90 6.0 s). Running the CLI before the snapshot: first 10 runs 11.3 s (p90 40.0 s), later rounds 5.1, 5.2 s against 22.9, 31.3 s with none. Startup warm-up 14.1 s (p90 40.9 s). |
| EKS improves a lot when tuned. | Warm pods that ran the task before ready: first message gVisor 0.4 s, Kata 0.5 s; whole request 6.8 s and 7.3 s. These pods cost nodes while they wait. |
| Differences on a build mix CPU, storage and isolation. Only Kata nested against metal isolates one factor. | Build task: gVisor 19.0 s, V1 19.6 s, MicroVM 21.1 s, V2 25.8 s, Kata metal 24.4 s, Kata nested 28.3 s. |
| Cost depends on scale and session shape. | Interactive scenario with explicit stop: V2 $833, gVisor $1,011, V1 $1,067, MicroVM from $3,430. Without a stop V2 $1,653, V1 $2,199. Steady scenario: gVisor $3,069, V2 $8,588. |

## Which option for which situation

| Situation | First choice | Measured reason | Avoid or check |
|---|---|---|---|
| Sparse interactive sessions, small team | AgentCore V1 | Whole request 10.4 s, first message 2.2 s, deploy about 3 s, metrics with no setup. Scenario $1,067 a month, V2 $833, gVisor $1,011 to $869 | Start time depends on the arrival rate: 0.49 s at low rate, 7.37 s at 5 new sessions per second |
| V1, but steady arrivals and a small package | AgentCore V1, direct code | 3.28 s at low rate, 2.80 s at 5 per second, 3.31 s for 100 at once, deploy about 30 s | Package limits apply (250 MB zipped, 750 MB unzipped, doc). Not tested in VPC mode |
| Large bursts or large images with no spare nodes held, when the app does not need a large first read | AgentCore V2 | 2.28 s for 100 at once, 1.79 s for a new 1.5 GB runtime. With nodes ready, gVisor is faster at small scale (1.02 s at 5 per second, V2 1.79 s) and slower at 100 (5.18 s). MicroVM ties V2 up to its quota (1.78 s) | Agents that load a large binary: first message p50 15.6 s, p90 40.5 s on new runtimes. Deploy about 200 s. Not in Seoul (doc) |
| Agents on V2 that must start fast from the first run | V2, CLI file mapped before the snapshot | First message p50 2.2 s, p90 6.6 s after a quiet hour, none of 8 runs over 20 s. Without it p50 29.9 s | Small sample, this binary only. Billed memory with the file mapped was not measured. On MicroVMs the benefit is not established, since the interval overlaps no mitigation |
| Must run inside your VPC | EKS if you run it, otherwise AgentCore V2 for start time | EKS is always in the VPC: gVisor 1.07 s start, 9.9 s whole request. AgentCore VPC mode: start V2 1.83 s, V1 7.33 s. 100 at once V2 3.49 s, V1 11.16 s | Whole request V1 13.5 s, V2 20.3 s: intervals overlap at 8 runs, so no ranking. First deploy V1 268 s, V2 518 s |
| Sessions that sit idle until reclaimed | AgentCore V2 | Idle until the default 15 minute reclaim billed 0.26 GB-h on V2 and 0.73 on V1, $0.0049 and $0.0078 | Both versions end an idle session at 15 minutes by default, so state does not survive longer unless you change the timeout. Measured on this image. An AWS blog example shows V2 memory depends on the app |
| Steady high concurrency with a platform team | gVisor + Agent Sandbox | Steady scenario $3,069 a month ($2,503 on Graviton3), V2 $8,588. 5.18 s for 100 at once on prepared nodes | Staff cost is not included. A new node adds about 41 s. Metrics, reclamation and policy are yours. The default is not hardened |
| Lowest agent readiness, willing to pay for idle capacity | EKS Warm Pool that runs the task before ready | First message gVisor 0.4 s, Kata 0.5 s. Whole request 6.8 s and 7.3 s | Warm pods cost nodes (30 pods move the interactive break-even from 43 to 71 sessions). The warm-up itself calls the model. 10 runs each |
| A guest kernel on your own cluster | Kata + QEMU + Agent Sandbox | Guest kernel per pod, 3.89 s start, 11.55 s for 100 at once on 8 nodes. Metal lowers the build task from 28.3 s to 24.4 s | 375 MB per idle sandbox against 58 MB, and half as many per node. Needs nested virtualization or metal. Only virtio-fs tested |
| Build-heavy agents, mostly on CPU | gVisor, V1 or MicroVM, decide on cost and operations | Build task: gVisor 19.0 s, V1 19.6 s, MicroVM 21.1 s, gVisor Graviton3 21.3 s, Kata metal 24.4 s, V2 25.8 s, Kata 28.3 s. Some near values overlap | Monthly scenario: gVisor $2,040, Kata $2,383, V1 $2,804, V2 $3,726, MicroVM $3,857. gVisor's rootfs is memory-backed here, MicroVM saw 8 vCPU, and managed CPU generations vary, so this mixes more than isolation |
| Sessions that pause and continue with memory intact, or your own harness | Lambda MicroVMs | Resume 0.27 s by API, 8.4 s by traffic, memory and disk kept in every run. Whole request 17.4 s, p90 39.6 s | Baseline billed while running, costing more than the stopped and autoscaled options in our scenarios at the tested size. Suspending pays off only when each idle period passes about 5 minutes at 2 GB. Default 5 per second RunMicrovm quota. Routing is yours |
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

### Bursts and sustained arrivals

|  | gVisor | Kata + QEMU | AgentCore V1 | AgentCore V2 | Lambda MicroVMs |
|---|---|---|---|---|---|
| Burst of 10 | 1.33 s | 4.07 s | 0.96 s | 1.89 s | 1.99 s |
| Burst of 50 | 2.85 s | 5.83 s | 8.01 s | 2.35 s | removed |
| Burst of 100 | 5.18 s | 11.55 s | 8.18 s | 2.28 s | removed |
| Sustained 1/s | 0.94 s | 3.92 s | 7.34 s | 1.84 s | 1.75 s |
| Sustained 5/s | 1.02 s | 4.90 s | 7.39 s | 1.79 s | 1.78 s |

Bursts are the median of 3 rounds from a dedicated 8 vCPU driver, with 4 gVisor nodes and 8 Kata nodes holding the image, so node scale-up is not included. A new node adds about 41 s for gVisor and 192 s for Kata. MicroVM above its default RunMicrovm quota of 5 per second was removed because the quota, not the platform, set the value; the quota is adjustable and was not raised. V1 is the 276 MB container with the earlier /ping. Warm pools with prepared pools: gVisor 1.93 s for 50, Kata 0.96 s for 40, one round. EKS completion is polled, which can add up to 0.5 s at 100. gVisor's p50 grows with size (1.33 s at 10, 5.18 s at 100), which may be a control path limit; we did not investigate. One request of a burst of 50 failed in the final rounds on V1 with the documented /ping (a 504), a runtime not shown in this table.

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

#### Mitigations (first message, whole request)

| Mitigation | V2 | MicroVM |
|---|---|---|
| None, new runtime, first 8 runs | 23.4 s (p90 36.9), 39.8 s | 3.1 s (p90 12.5), 15.6 s |
| Map the CLI file before the snapshot | 2.2 s (p90 6.0), 15.6 s | 1.9 s (p90 4.4), 13.9 s |
| None, new runtime after a quiet hour | 29.9 s (p90 37.6), 47.6 s | 5.1 s (p90 17.5), 22.5 s |
| CLI file mapping, after a quiet hour | 2.2 s (p90 6.6), 17.7 s | 1.9 s (p90 6.0), 10.6 s |
| Import, CLI, pytest and a full task at startup | 14.1 s (p90 40.9), 31.8 s | 4.3 s (p90 9.5), 16.0 s |
| Run the CLI before the snapshot, first 10 runs | 11.3 s (p90 40.0), 29.5 s | 6.5 s (p90 32.8), 24.5 s |

Each condition is 8 to 12 runs, a small sample. Mapping runs the CLI once, then maps the file and reads every page before the snapshot. After a quiet hour on V2, runs over 20 s are 0 of 8 with mapping against 5 of 8 without (Fisher p about 0.03). Running the CLI before the snapshot did not help the first runs of a new runtime. Billed memory with the file mapped was not measured. On MicroVM the intervals with and without mapping overlap.

V1 direct code had no such delay (first message 2.0 s, whole request 15.0 s). V2 direct code did (28.5 s, 50.5 s). Dropping the page cache on EKS nodes shows the same effect at smaller scale: gVisor 2.8 s first message, Kata 3.2 s. Whole request then becomes gVisor 12.4 s and Kata 16.2 s. So EKS's advantage here partly reflects a local disk and a warm page cache.

#### Agents at the same time (whole request)

|  | 5 at once | 20 at once |
|---|---|---|
| gVisor, 4 nodes | 10.5 s | 11.1 s |
| gVisor Warm Pool, 4 nodes | 9.0 s | 10.3 s |
| Kata, 8 nodes | 13.5 s | 14.9 s |
| Kata Warm Pool, 8 nodes | 10.7 s | 11.0 s |
| AgentCore V1 | 10.1 s | 10.2 s |
| AgentCore V2 | 19.9 s | 14.6 s |
| Lambda MicroVMs | 19.6 s | 19.4 s |

No failures. Two runs per size, all from the same dedicated driver. Managed runtimes had seen agent runs, so these are not new-runtime values. V2 and MicroVM ran about 4.5 hours after the others. V2 ran its 5-agent batches first, so its lower value at 20 is not a gain from scale.

#### Build task (whole request, 8 runs)

|  | Whole request | p90 | 95% CI of p50 |
|---|---|---|---|
| gVisor x86 | 19.0 s | 19.8 s | 16.9 to 19.6 s |
| AgentCore V1 | 19.6 s | 21.3 s | 17.0 to 21.1 s |
| Lambda MicroVMs | 21.1 s | 23.8 s | 19.4 to 22.1 s |
| gVisor Graviton3 | 21.3 s | 22.2 s | 20.5 to 22.1 s |
| Kata metal | 24.4 s | 25.5 s | 23.0 to 25.3 s |
| AgentCore V2 | 25.8 s | 31.5 s | 23.6 to 29.1 s |
| Kata nested | 28.3 s | 28.6 s | 27.9 to 28.4 s |

MicroVM sees 8 vCPU with a 2 vCPU billed baseline, and the rest are limited to 2 vCPU, so this favours it on parallel work; use above the baseline may add charges, as in the AWS pricing example. gVisor's root filesystem is memory-backed here, which helps its file work and counts against pod memory. V2 and MicroVM ran on runtimes that already had 12 runs. Managed CPU generations vary by session, x86 EKS is a different CPU, and these rows were not run in one shuffled period. Do not rank values whose intervals overlap.

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

gVisor's fast disk numbers are not comparable: its root filesystem is a memory-backed overlay here (3,642 MB/s write with fsync). arm64 gVisor was also slower on pure Python (1.7x runc on Graviton3), which x86 did not show. We did not analyze why.

### Reclamation and lifecycle

|  | Observed |
|---|---|
| V2 with 60 s idle timeout | Alive at 60 s (3/3), gone at 70 s (0/3 alive) |
| V1 with 60 s idle timeout | Alive at 60 s (3/3), 1/3 alive at 70 s, gone at 90 s (0/3 alive) |
| AgentCore explicit stop, same session id | New instance, memory and disk gone, 5/5 on V1 and V2 |
| MicroVM idle policy 60 s, then suspended 120 s | SUSPENDED after 67 s, TERMINATED after 121 s |
| MicroVM resume | API 0.27 s, traffic 8.4 s. Memory and disk kept in every run, up to 2 GB held |
| EKS sandbox delete to pod gone | gVisor 2.3 s, Kata 2.0 s |
| EKS new node to first sandbox, then node removal | gVisor 41 s and 173 s. Kata 192 s including 132 s kata-deploy, and 183 s. Managed node group, Karpenter n/t |

Deploy times for comparison: EKS cluster and nodes about 19 minutes by one Terraform apply, not counting runtime install; MicroVM image about 160 s; AgentCore in the packaging table.

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

| Scenario | Avg concurrent | V1 | V2 | MicroVM, 2 GB to tested 4 GB | gVisor, autoscaled | gVisor, peak | Kata, autoscaled | Kata, peak | V1, no stop | V2, no stop | gVisor, Graviton3 | gVisor, high memory |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Interactive assistant | 35 | 1,067 | 833 | 3,430 to 6,624 | 1,011 | 1,697 | 1,354 | 2,726 | 2,199 | 1,653 | 869 | 1,354 |
| Short code execution | 17 | 1,084 | 1,234 | 3,948 to 5,546 | 1,011 | 1,697 | 1,354 | 2,040 | 12,410 | 9,434 | 869 | 1,011 |
| Coding agent with builds | 21 | 1,171 | 1,399 | 3,857 to 3,857 | 1,354 | 2,383 | 1,354 | 2,383 | 1,346 | 1,590 | 1,141 | 1,354 |
| Build-heavy agents, mostly on CPU | 21 | 2,804 | 3,726 | 3,857 to 3,857 | 2,040 | 4,441 | 2,383 | 5,127 | 2,978 | 3,917 | 1,686 | 2,040 |
| Steady high concurrency | 200 | 8,615 | 8,588 | 31,943 to 50,343 | 3,069 | 3,412 | 5,814 | 6,157 | 73,848 | 55,824 | 2,503 | 4,784 |

The scenarios are illustrations in `analysis/cost_model.py`; change them and rerun. Prices were checked against the public pages and the Pricing API on 2026-11-03, and the formulas reproduce AWS's worked examples (V2 $6,704 against $6,703, MicroVM $1,124 against $1,124). AgentCore idle memory and EKS overhead are measured. V1 and V2 assume the app stops each session; the no-stop columns add the default 15 minute idle tail at measured tail memory, and EKS has the same need to delete idle sandboxes. MicroVM use above its baseline may add charges. EKS includes the control plane, 2 system nodes, NAT Gateway and gp3 disks; on an existing cluster the interactive gVisor figure falls to $686. Excluded everywhere: LLM tokens, per-GB NAT and transfer, logs, staff, discounts. For the interactive shape, autoscaled gVisor and V2 break even near 43 average concurrent sessions, 71 with 30 warm pods, and never when sized for peak. These are first crossings; node counts step, so gVisor stays cheaper from 57, or 86 with 30 warm pods. MicroVM suspend adds snapshot write and read charges and pays off only when each idle period passes about 5 minutes at 2 GB, so the table shows no suspend. These are estimates, not a bill.

### Security defaults: what a workload can see and reach

| Check | gVisor | Kata + QEMU | AgentCore V1 | AgentCore V2 | Lambda MicroVMs |
|---|---|---|---|---|---|
| CAP_SYS_ADMIN | no | no | yes | yes | no |
| Role listed through metadata | no | no | yes | yes | yes |
| Service account token mounted | yes | yes | no | no | no |
| Kubernetes API reachable | yes | yes | N/A | N/A | N/A |
| Peer sandbox reachable | yes | yes | undetermined | undetermined | undetermined |
| Internet egress in this setup | yes | yes | yes | yes | yes |
| io_uring | absent | callable | callable | callable | callable |
| /dev/kvm | no | no | no | no | no |

With VPC CNI network policy turned on, a warm pool sandbox got: peer timeout, Kubernetes API timeout, internet open, Pod Identity endpoint TimeoutError. The policy Agent Sandbox generates excludes 169.254.0.0/16, so AWS credential lookup failed with CredentialRetrievalError on gVisor and Kata. Add an exception for the Pod Identity endpoint, or inject credentials another way. A Sandbox created directly, without a SandboxTemplate, gets no policy and stayed open.

These are benign checks of defaults from inside a sandbox, not a penetration test, and say nothing about escape resistance. The role seen through metadata is the session's execution role. Managed sessions share the same link-local addresses, so our cross-session test could not determine isolation, and we do not claim it.

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
- **Same region.** Everything runs in `us-east-1`, including the driver. Paths still differ: EKS is reached on the Pod IP, managed services on public endpoints.
- **Same definition.** Timing starts just before the first call that asks for a sandbox and ends when the app answers. Agent readiness is measured separately.
- **Controls.** runc on the same nodes, gVisor and runc on Graviton3 to match the managed CPU, and Kata on `m8i.metal-48xl` to separate nested virtualization from Kata itself.
- **No capacity or quota penalty.** Results set by a quota or too few nodes were left out or measured again.
- **Order and failures.** The headline agent and cold start tables shuffle backends in each cycle so that none owns a time of day. Builds, mitigations and metal ran in their own periods. Failures are recorded and counted; only failures are left out of timing, and slow runs stay in.
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

## Limits of this test

- One region, two days, one account, one application. Results can change with region, quotas, capacity and time. The first-read result depends on this SDK's large CLI binary.
- Network paths differ between platforms, so round trips are not a pure runtime comparison.
- The cause of the slow first read is our interpretation, not a statement from AWS.
- Kata ran with its default virtio-fs. Block-device rootfs and memory-backed work directories were not tested.
- Not tested: 8 hour and 14 day sessions, Karpenter, Spot, gVisor on KVM, raised MicroVM quotas, EKS hardening options, session storage, X-Ray traces, Seoul or other regions.
- Some follow-ups have small samples (8 to 12 runs), so read their confidence intervals.
- Security results describe defaults and are not a statement about escape resistance.
- Cost scenarios use assumed traffic. The AgentCore committed price status could not be confirmed and is not used.
- `results/raw/` also keeps runs left out of the tables, including the invalid `cold_uncached.jsonl`.

## Layout and reproduction

```
app/        agent image, workloads, probes
bench/      driver: backends, experiments, deployment
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
python3 analysis/analyze.py && python3 analysis/cost_model.py && python3 analysis/facts.py
python3 analysis/verify_claims.py && python3 analysis/make_readme.py
```

**This is a disposable test bed, not a reference architecture.** The driver has cluster-admin, a privileged helper runs on nodes, the app's endpoint is unauthenticated inside the VPC, IAM is broad, and the EKS API endpoint is public. See the comments in `infra/terraform/iam.tf`. Delete it when you finish.
