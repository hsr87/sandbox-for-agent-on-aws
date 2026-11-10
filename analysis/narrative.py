#!/usr/bin/env python3
"""Text shared by the README, the deck and the report, so that the recommendations and the reasons for each experiment read the same everywhere.
Every number comes from results/facts.json. Call with a chooser t(en, ko)."""


def _fmt(F, t):
    A = F["fair"]["agent"]
    C = F["fair"]["concurrent_scaled"]
    L = F["fair"]["low_rate"]

    def sec(x, n=1):
        return t(f"{x:.{n}f} s", f"{x:.{n}f}초")

    return A, C, L, sec


def headline(F):
    """The same-period shuffled round when present, otherwise the closest earlier rounds. Keys: gv, g3gv, kt, v1, v2, lm."""
    A, L = F["fair"]["agent"], F["fair"]["low_rate"]
    same = F["fair"].get("same", {}).get("agent") or {}
    base = {"gv": L["gv"], "g3gv": L["g3gv"], "kt": L["kt"], "v1": A["ac-v1-np|np2"], "v2": A["ac-v2|crossed"], "lm": A["lm|crossed"]}
    return {k: same.get(k, v) for k, v in base.items()}


def headline_cold(F):
    same = F["fair"].get("same", {}).get("cold") or {}
    base = {"gv": ("cold.gv.p50", "cold.gv.p90"), "g3gv": ("cold.g3gv.p50", "cold.g3gv.p90"), "kt": ("cold.kt.p50", "cold.kt.p90"), "v1": ("cold.v1np.p50", "cold.v1np.p90"), "v2": ("cold.v2np.p50", "cold.v2np.p90"), "lm": ("cold.lm.p50", "cold.lm.p90")}
    return {k: same[k] if k in same else {"p50": F[a], "p90": F[b]} for k, (a, b) in base.items()}


def recommendations(F, t):
    """Situation, first choice, measured reason, when to avoid or what to check."""
    A, C, L, sec = _fmt(F, t)
    S = F["cost"]["scenarios"]
    H, HC = headline(F), headline_cold(F)
    pin = A.get("ac-v2-pinq2|quiet2") or A["ac-v2-pin|pin"]
    usd = lambda x: f"${x:,.0f}"
    I = S["interactive"]
    FU = F["fu"]
    M, N, B, ST, SC = FU["mitigation"], FU["network"], FU["build"], FU["store"], FU["store_cycle"]
    KP, KT, KK = FU["kp_scale"], FU["kp_trace"], FU["kp_kata"]
    NT, NA, FG = FU["new"]["nt"], FU["new"]["na"], FU["new"]["fg"]
    return [
        [t("Sparse interactive sessions, small team", "간헐적인 대화형 세션, 작은 팀"), "AgentCore V1",
         t(f"Whole request {sec(H['v1']['total_p50'])}, first message {sec(H['v1']['first_p50'])}, deploy about {F['deploy.v1']:.0f} s, metrics with no setup. Scenario {usd(I['agentcore_v1'])} a month, V2 {usd(I['agentcore_v2'])}, gVisor {usd(I['eks_gvisor_autoscaled'])} to {usd(I['eks_gvisor_autoscaled_graviton3'])}", f"전체 시간 {sec(H['v1']['total_p50'])}, 첫 메시지 {sec(H['v1']['first_p50'])}, 배포 약 {F['deploy.v1']:.0f}초, 지표 기본 제공. 대화형 시나리오 월 {usd(I['agentcore_v1'])}(V2 {usd(I['agentcore_v2'])}, gVisor {usd(I['eks_gvisor_autoscaled_graviton3'])}~{usd(I['eks_gvisor_autoscaled'])})"),
         t(f"Start time depends on the arrival rate: {sec(HC['v1']['p50'], 2)} at low rate, {sec(F['sus.v1np.5.p50'], 2)} at 5 new sessions per second", f"시작 시간이 유입 속도에 따라 달라집니다. 저빈도 {sec(HC['v1']['p50'], 2)}, 초당 5건 {sec(F['sus.v1np.5.p50'], 2)}")],
        [t("V1, but steady arrivals and a small package", "V1에서 유입이 꾸준하고 패키지가 작을 때"), t("AgentCore V1, direct code", "AgentCore V1 코드 직접 배포"),
         t(f"{sec(F['cold.v1zip.p50'], 2)} at low rate, {sec(F['sus.v1zip.5.p50'], 2)} at 5 per second, {sec(F['burst.v1zip.100.p50'], 2)} for 100 at once, deploy about {F['deploy.v1zip']:.0f} s", f"저빈도 {sec(F['cold.v1zip.p50'], 2)}, 초당 5건 {sec(F['sus.v1zip.5.p50'], 2)}, 동시 100개 {sec(F['burst.v1zip.100.p50'], 2)}, 배포 약 {F['deploy.v1zip']:.0f}초"),
         t("Package limits apply (250 MB zipped, 750 MB unzipped, doc). Not tested in VPC mode", "패키지 한도가 있습니다(압축 250 MB, 해제 750 MB, 문서). VPC 모드는 실험하지 않았습니다")],
        [t("Large bursts or large images with no spare nodes held, when the app does not need a large first read", "노드를 미리 두지 않고 큰 버스트나 큰 이미지를 처리해야 하며, 앱이 시작할 때 큰 파일을 읽지 않을 때"), "AgentCore V2",
         t(f"{sec(F['burst.v2.100.p50'], 2)} for 100 at once, {sec(F['fresh.V2.large.first'], 2)} for a new 1.5 GB runtime. With nodes ready, gVisor is faster at small scale ({sec(F['sus.gv.5.p50'], 2)} at 5 per second, V2 {sec(F['sus.v2.5.p50'], 2)}) and slower at 100 ({sec(F['burst.gv.100.p50'], 2)}). MicroVM ties V2 up to its quota ({sec(F['sus.lm.5.p50'], 2)})", f"동시 100개 {sec(F['burst.v2.100.p50'], 2)}, 새 1.5 GB 런타임 {sec(F['fresh.V2.large.first'], 2)}. 노드가 준비돼 있으면 작은 규모에서는 gVisor가 더 빠르고(초당 5건 {sec(F['sus.gv.5.p50'], 2)}, V2 {sec(F['sus.v2.5.p50'], 2)}) 100개에서는 더 느립니다({sec(F['burst.gv.100.p50'], 2)}). MicroVM은 쿼터 안에서 V2와 비슷합니다({sec(F['sus.lm.5.p50'], 2)})"),
         t(f"Agents that load a large binary: first message p50 {sec(H['v2']['first_p50'])}, p90 {sec(H['v2']['first_p90'])} on new runtimes. Deploy about {F['deploy.v2']:.0f} s. Not in Seoul (doc)", f"큰 바이너리를 읽는 에이전트는 새 런타임에서 첫 메시지가 p50 {sec(H['v2']['first_p50'])}, p90 {sec(H['v2']['first_p90'])}입니다. 배포 약 {F['deploy.v2']:.0f}초. 서울 리전 없음(문서)")],
        [t("Agents on V2 that must start fast from the first run", "V2에서 첫 실행부터 빨라야 하는 에이전트"), t("V2, large file mapped before the snapshot or fetched from S3 at session start", "V2 + 큰 파일을 스냅샷 전에 매핑하거나 세션 시작 시 S3에서 받기"),
         t(f"First message p50: mapped {sec(M['v2_map']['first']['p50'])}, fetched from S3 {sec(M['v2_s3']['first']['p50'])}, nothing {sec(M['v2_none']['first']['p50'])}. Runs over 20 s out of {M['v2_none']['first']['n']}: {M['v2_map']['first']['over20']}, {M['v2_s3']['first']['over20']} and {M['v2_none']['first']['over20']}", f"첫 메시지 p50: 매핑 {sec(M['v2_map']['first']['p50'])}, S3에서 받기 {sec(M['v2_s3']['first']['p50'])}, 조치 없음 {sec(M['v2_none']['first']['p50'])}. {M['v2_none']['first']['n']}회 중 20초를 넘은 횟수: {M['v2_map']['first']['over20']}회, {M['v2_s3']['first']['over20']}회, {M['v2_none']['first']['over20']}회"),
         t(f"Periodic warm-up calls help less ({sec(M['v2_w5k1']['first']['p50'])} at 5 minutes) and only for the runtime they call. Running the CLI before the snapshot was not consistent. Mapping and fetching did not raise billed memory", f"주기적 예열 호출은 효과가 작고(5분 간격 {sec(M['v2_w5k1']['first']['p50'])}) 호출한 런타임에만 듣습니다. 스냅샷 전 CLI 실행은 효과가 일정하지 않았습니다. 매핑과 S3 받기는 과금 메모리를 늘리지 않았습니다")],
        [t("Must run inside your VPC", "VPC 안에서 실행해야 할 때"), t("EKS if you run it, otherwise AgentCore V2 for start time", "직접 운영할 수 있으면 EKS, 아니면 AgentCore V2(시작 시간 기준)"),
         t(f"EKS is always in the VPC: gVisor {sec(HC['gv']['p50'], 2)} start, {sec(H['gv']['total_p50'])} whole request. AgentCore VPC mode: start V2 {sec(F['cold.v2vpc.p50'], 2)}, V1 {sec(F['cold.v1vpc.p50'], 2)}. 100 at once V2 {sec(F['burst.v2vpc.100.p50'], 2)}, V1 {sec(F['burst.v1vpc.100.p50'], 2)}", f"EKS는 항상 VPC 안에서 동작합니다. gVisor 시작 {sec(HC['gv']['p50'], 2)}, 전체 시간 {sec(H['gv']['total_p50'])}. AgentCore VPC 모드 시작: V2 {sec(F['cold.v2vpc.p50'], 2)}, V1 {sec(F['cold.v1vpc.p50'], 2)}. 동시 100개: V2 {sec(F['burst.v2vpc.100.p50'], 2)}, V1 {sec(F['burst.v1vpc.100.p50'], 2)}"),
         t(f"VPC mode did not change the agent's whole request against public mode: V1 {sec(N['v1_vpc']['whole']['p50'])} and {sec(N['v1_public']['whole']['p50'])}, V2 {sec(N['v2_vpc']['whole']['p50'])} and {sec(N['v2_public']['whole']['p50'])}. First deploy V1 {F['deploy.v1vpc']:.0f} s, V2 {F['deploy.v2vpc']:.0f} s", f"VPC 모드와 퍼블릭 모드의 에이전트 전체 시간은 차이가 없었습니다(V1 {sec(N['v1_vpc']['whole']['p50'])} 대 {sec(N['v1_public']['whole']['p50'])}, V2 {sec(N['v2_vpc']['whole']['p50'])} 대 {sec(N['v2_public']['whole']['p50'])}). 첫 배포는 V1 {F['deploy.v1vpc']:.0f}초, V2 {F['deploy.v2vpc']:.0f}초")],
        [t("Sessions that sit idle until reclaimed", "회수될 때까지 유휴 상태로 남는 세션"), "AgentCore V2",
         t(f"Idle until the default 15 minute reclaim billed {F['usage.idle_only_30min.v2np.gbh']:.2f} GB-h on V2 and {F['usage.idle_only_30min.v1np.gbh']:.2f} on V1, ${F['usage.idle_only_30min.v2np.cost']:.4f} and ${F['usage.idle_only_30min.v1np.cost']:.4f}", f"기본 15분 회수까지의 유휴 과금: V2 {F['usage.idle_only_30min.v2np.gbh']:.2f} GB-h(${F['usage.idle_only_30min.v2np.cost']:.4f}), V1 {F['usage.idle_only_30min.v1np.gbh']:.2f} GB-h(${F['usage.idle_only_30min.v1np.cost']:.4f})"),
         t("Both versions end an idle session at 15 minutes by default, so state does not survive longer unless you change the timeout. Measured on this image. An AWS blog example shows V2 memory depends on the app", "두 버전 모두 기본값에서는 15분 유휴 후 세션을 끝내므로, 타임아웃을 바꾸지 않으면 상태가 그보다 오래 남지 않습니다. 이 이미지로 측정한 값이며, AWS 블로그 사례를 보면 V2 메모리 사용량은 앱에 따라 다릅니다")],
        [t("Steady high concurrency with a platform team", "동시 세션이 꾸준히 많고 플랫폼 팀이 있을 때"), "gVisor + Agent Sandbox",
         t(f"Steady scenario {usd(S['steady']['eks_gvisor_autoscaled'])} a month ({usd(S['steady']['eks_gvisor_autoscaled_graviton3'])} on Graviton3), V2 {usd(S['steady']['agentcore_v2'])}. {sec(F['burst.gv.100.p50'], 2)} for 100 at once on prepared nodes", f"지속 시나리오 월 {usd(S['steady']['eks_gvisor_autoscaled'])}(Graviton3 {usd(S['steady']['eks_gvisor_autoscaled_graviton3'])}), V2 {usd(S['steady']['agentcore_v2'])}. 노드가 준비돼 있으면 동시 100개 {sec(F['burst.gv.100.p50'], 2)}"),
         t(f"Staff cost is not included. A new node adds about {F['scale.gv.total']:.0f} s. Metrics, reclamation and policy are yours. The default is not hardened", f"인건비는 빠져 있습니다. 새 노드가 필요하면 약 {F['scale.gv.total']:.0f}초가 더 걸립니다. 지표, 회수, 정책을 직접 운영해야 하고, 기본값은 강화되어 있지 않습니다")],
        [t("Lowest agent readiness, willing to pay for idle capacity", "에이전트 준비 시간이 가장 중요하고 유휴 용량 비용을 감수할 때"), t("EKS Warm Pool that runs the task before ready", "태스크를 미리 실행해 둔 EKS Warm Pool"),
         t(f"First message gVisor {sec(A['eks-x86-gvisor-warm-init|init']['first_p50'])}, Kata {sec(A['eks-x86-kata-warm-init|init']['first_p50'])}. Whole request {sec(A['eks-x86-gvisor-warm-init|init']['total_p50'])} and {sec(A['eks-x86-kata-warm-init|init']['total_p50'])}", f"첫 메시지 gVisor {sec(A['eks-x86-gvisor-warm-init|init']['first_p50'])}, Kata {sec(A['eks-x86-kata-warm-init|init']['first_p50'])}. 전체 시간 {sec(A['eks-x86-gvisor-warm-init|init']['total_p50'])}, {sec(A['eks-x86-kata-warm-init|init']['total_p50'])}"),
         t(f"Warm pods cost nodes (30 pods move the interactive break-even from {F['cost']['break_even_concurrency_interactive_gvisor_vs_v2']} to {F['cost']['break_even_concurrency_interactive_gvisor_warm30_vs_v2']} sessions). The warm-up itself calls the model. 10 runs each", f"Warm Pod 수만큼 노드 비용이 듭니다(30개를 두면 대화형 손익 분기점이 동시 {F['cost']['break_even_concurrency_interactive_gvisor_vs_v2']}개에서 {F['cost']['break_even_concurrency_interactive_gvisor_warm30_vs_v2']}개로 올라갑니다). 예열 자체도 모델을 호출합니다. 각 10회 측정")],
        [t("A guest kernel on your own cluster", "자체 클러스터에서 게스트 커널이 필요할 때"), "Kata + QEMU + Agent Sandbox",
         t(f"Guest kernel per pod, {sec(F['cold.kt.p50'], 2)} start, {sec(F['burst.kt.100.p50'], 2)} for 100 at once on 8 nodes. Metal lowers the build task from {sec(A['eks-x86-kata|heavy']['total_p50'])} to {sec(A['eks-metal-kata|heavy']['total_p50'])}", f"Pod마다 게스트 커널, 시작 {sec(F['cold.kt.p50'], 2)}, 8노드에서 동시 100개 {sec(F['burst.kt.100.p50'], 2)}. 메탈 노드에서는 빌드 태스크가 {sec(A['eks-x86-kata|heavy']['total_p50'])}에서 {sec(A['eks-metal-kata|heavy']['total_p50'])}로 줄어듭니다"),
         t(f"{F['density.kt.mb']:.0f} MB per idle sandbox against {F['density.gv.mb']:.0f} MB, and half as many per node. Needs nested virtualization or metal. Only virtio-fs tested", f"유휴 샌드박스당 {F['density.kt.mb']:.0f} MB(gVisor {F['density.gv.mb']:.0f} MB)로 노드당 수용량이 절반입니다. 중첩 가상화나 메탈 인스턴스가 필요합니다. virtio-fs만 실험했습니다")],
        [t("Build-heavy agents, mostly on CPU", "CPU를 많이 쓰는 빌드 에이전트"), t("gVisor or V1, decide on cost and operations", "gVisor 또는 V1(비용과 운영 부담으로 선택)"),
         t(f"Build task, shuffled in one period: gVisor {sec(B['gvisor']['whole']['p50'])}, V1 {sec(B['v1']['whole']['p50'])}, gVisor Graviton3 {sec(B['gvisor_g3']['whole']['p50'])}, MicroVM {sec(B['lm']['whole']['p50'])}, Kata {sec(B['kata']['whole']['p50'])}, V2 {sec(B['v2']['whole']['p50'])}. gVisor and V1 overlap", f"같은 시간대에 순서를 섞어 측정한 빌드 태스크: gVisor {sec(B['gvisor']['whole']['p50'])}, V1 {sec(B['v1']['whole']['p50'])}, gVisor Graviton3 {sec(B['gvisor_g3']['whole']['p50'])}, MicroVM {sec(B['lm']['whole']['p50'])}, Kata {sec(B['kata']['whole']['p50'])}, V2 {sec(B['v2']['whole']['p50'])}. gVisor와 V1은 신뢰 구간이 겹칩니다"),
         t(f"Monthly scenario: gVisor {usd(S['build_heavy']['eks_gvisor_autoscaled'])}, Kata {usd(S['build_heavy']['eks_kata_autoscaled'])}, V1 {usd(S['build_heavy']['agentcore_v1'])}, V2 {usd(S['build_heavy']['agentcore_v2'])}, MicroVM {usd(S['build_heavy']['microvm_tested_size'])}. gVisor's rootfs is memory-backed here and managed CPU generations vary, so this mixes more than isolation", f"월 시나리오: gVisor {usd(S['build_heavy']['eks_gvisor_autoscaled'])}, Kata {usd(S['build_heavy']['eks_kata_autoscaled'])}, V1 {usd(S['build_heavy']['agentcore_v1'])}, V2 {usd(S['build_heavy']['agentcore_v2'])}, MicroVM {usd(S['build_heavy']['microvm_tested_size'])}. gVisor는 루트 파일시스템이 메모리 기반이고 관리형은 CPU 세대가 섞여 있어, 격리 방식만의 차이는 아닙니다")],
        [t("Sessions that pause and continue with memory intact, or your own harness", "메모리를 유지한 채 멈췄다 이어 가는 세션, 직접 만든 하네스"), "Lambda MicroVMs",
         t(f"Resume {sec(F['susp.0MB.api.resume_p50'], 2)} by API, {sec(F['susp.0MB.traffic.resume_p50'])} by traffic, memory and disk kept in every run. Whole request {sec(H['lm']['total_p50'])}, p90 {sec(H['lm']['total_p90'])}", f"재개: API {sec(F['susp.0MB.api.resume_p50'], 2)}, 트래픽 {sec(F['susp.0MB.traffic.resume_p50'])}. 모든 실행에서 메모리와 디스크가 유지됐습니다. 전체 시간 {sec(H['lm']['total_p50'])}, p90 {sec(H['lm']['total_p90'])}"),
         t(f"Baseline billed while running, costing more than the stopped and autoscaled options in our scenarios at the tested size. Suspending pays off only when each idle period passes about {F['cost']['suspend_breakeven_idle_s_smallest'] / 60:.0f} minutes at 2 GB. Default 5 per second RunMicrovm quota. Routing is yours", f"실행 중에는 기준 자원 전체가 과금되어, 실험한 크기에서는 세션 중지나 자동 축소를 쓰는 구성보다 시나리오 비용이 높습니다. 일시 중지는 2 GB 기준으로 유휴 구간이 약 {F['cost']['suspend_breakeven_idle_s_smallest'] / 60:.0f}분을 넘어야 이득입니다. RunMicrovm 기본 쿼터는 초당 5건이고, 라우팅은 직접 구현해야 합니다")],
        [t("EKS that scales nodes from zero", "노드를 0개부터 늘리는 EKS"), t("gVisor + Karpenter, do-not-disrupt on session pods", "gVisor + Karpenter, 세션 Pod에 do-not-disrupt"),
         t(f"First sandbox on an empty cluster {sec(KP['1']['p50'])}, 50 sandboxes all ready in {sec(KP['50']['all_ready'])}. In a {KT['default']['hours'] * 60:.0f} minute trace, default consolidation ended {KT['default']['lost']} of {KT['default']['sessions']} sessions and do-not-disrupt ended {KT['keep']['lost']} of {KT['keep']['sessions']}", f"빈 클러스터에서 첫 샌드박스 {sec(KP['1']['p50'])}, 50개 모두 준비 {sec(KP['50']['all_ready'])}. {KT['default']['hours'] * 60:.0f}분 트레이스에서 기본 통합 설정은 세션 {KT['default']['sessions']}개 중 {KT['default']['lost']}개를 끊었고, do-not-disrupt는 {KT['keep']['sessions']}개 중 {KT['keep']['lost']}개였습니다"),
         t(f"do-not-disrupt used about {(KT['keep']['node_h_per_pod_h'] / KT['default']['node_h_per_pod_h'] - 1) * 100:.0f}% more node hours per session hour. Kata on a new Karpenter node took about {min(KK['usable']):.0f} to {max(KK['usable']):.0f} s, mostly kata-deploy, so keep Kata nodes warm", f"세션 시간당 노드 시간이 약 {(KT['keep']['node_h_per_pod_h'] / KT['default']['node_h_per_pod_h'] - 1) * 100:.0f}% 늘었습니다. Kata는 Karpenter 새 노드에서 쓸 수 있을 때까지 {min(KK['usable']):.0f}~{max(KK['usable']):.0f}초(대부분 kata-deploy)가 걸려 노드를 미리 두어야 합니다")],
        [t("Keep work files when an AgentCore session stops and restarts", "AgentCore 세션을 멈췄다 다시 시작해도 작업 파일을 유지해야 할 때"), t("AgentCore session storage (preview)", "AgentCore 세션 스토리지(프리뷰)"),
         t(f"Stopped and restarted with the same session ID {SC['cycles']} times: /tmp was empty every time and the file in session storage was kept every time ({SC['file_kept']} of {SC['cycles']}). Reading the 331 MB CLI from it took {sec(SC['first_read']['p50'])}. With the CLI there, first message after a restart {sec(ST['store|resume']['first']['p50'])}", f"같은 세션 ID로 {SC['cycles']}회 중지 후 재시작: /tmp는 매번 비었고, 세션 스토리지의 파일은 {SC['cycles']}회 중 {SC['file_kept']}회 남았습니다. 거기서 331 MB CLI를 읽는 데 {sec(SC['first_read']['p50'])}. CLI를 세션 스토리지에 두면 재시작 후 첫 메시지 {sec(ST['store|resume']['first']['p50'])}"),
         t("Preview, tested on V2 only. The first copy into it is extra (from S3, about 2 s for 331 MB)", "프리뷰 기능이며 V2에서만 실험했습니다. 처음 복사하는 시간이 따로 듭니다(S3에서 331 MB 약 2초)")],
        [t("A VM per pod on EKS, without nested virtualization or metal", "EKS에서 Pod마다 VM이 필요하지만 중첩 가상화나 메탈은 쓰기 어려울 때"), t("Nitro Sandboxes (EKS Auto Mode)", "Nitro Sandboxes (EKS Auto Mode)"),
         t(f"Own guest kernel per pod. Start {sec(NT['cold']['nt-c']['p50'], 2)}, warm pool claim {sec(NT['cold']['nt-w']['p50'], 2)}. Syscalls close to runc (open+close {NT['suite']['nt-b']['syscalls']['open_close_ns'] / 1000:.1f} µs, Kata {F['sys.kt.open_close_ns'] / 1000:.0f} µs). Build {sec(NT['heavy']['nitro']['whole']['p50'])}, Kata {sec(NA['heavy']['kata']['whole']['p50'])} in the same period", f"Pod마다 게스트 커널. 시작 {sec(NT['cold']['nt-c']['p50'], 2)}, Warm Pool 할당 {sec(NT['cold']['nt-w']['p50'], 2)}. 시스템 콜 비용이 runc와 비슷합니다(open+close {NT['suite']['nt-b']['syscalls']['open_close_ns'] / 1000:.1f} µs, Kata {F['sys.kt.open_close_ns'] / 1000:.0f} µs). 빌드 {sec(NT['heavy']['nitro']['whole']['p50'])}, 같은 시간대 Kata {sec(NA['heavy']['kata']['whole']['p50'])}"),
         t(f"The VM gets the pod's requests and its memory is reserved in full, so set requests to what the agent needs (3 sandboxes of 2 vCPU, 8 GB per m8i.2xlarge). 5 new sessions per second queued to {sec(NT['sustained']['nt-c']['5.0']['p50'])}. Sequential write {NT['suite']['nt-b']['disk_seq']['write_MBps']:.0f} MB/s. Kubernetes 1.36 or later, US regions on EKS (doc), Auto Mode fee unless you build the AMI", f"VM은 Pod의 requests만큼 받고 메모리를 모두 예약하므로, requests를 에이전트가 실제로 쓸 만큼 잡아야 합니다(m8i.2xlarge 한 대에 2 vCPU, 8 GB 샌드박스 3개). 초당 5건에서는 대기가 생겨 {sec(NT['sustained']['nt-c']['5.0']['p50'])}였습니다. 순차 쓰기 {NT['suite']['nt-b']['disk_seq']['write_MBps']:.0f} MB/s. 쿠버네티스 1.36 이상, EKS에서는 미국 리전(문서). AMI를 직접 빌드하지 않으면 Auto Mode 요금이 듭니다")],
        [t("Pause and resume with work files kept, on EKS", "EKS에서 작업 파일을 유지한 채 멈췄다 이어 갈 때"), t("Nitro Sandboxes + agent-sandbox Suspended with an EBS volume", "Nitro Sandboxes + EBS 볼륨 + agent-sandbox Suspended"),
         t(f"Suspend {sec(NT['pause_resume']['suspend']['p50'])}, resume {sec(NT['pause_resume']['resume']['p50'])}, the file on the volume kept {NT['pause_resume']['disk_kept']} of {NT['pause_resume']['cycles']} times. While suspended the sandbox holds no node capacity; the volume is still billed", f"중지 {sec(NT['pause_resume']['suspend']['p50'])}, 재개 {sec(NT['pause_resume']['resume']['p50'])}, 볼륨의 파일은 {NT['pause_resume']['cycles']}회 중 {NT['pause_resume']['disk_kept']}회 유지. 중지한 동안에는 노드 용량을 차지하지 않고 볼륨 비용만 듭니다"),
         t(f"Memory is not kept ({NT['pause_resume']['memory_kept']} of {NT['pause_resume']['cycles']}); resume is a new VM. A single-attach volume pins the sandbox to one zone. MicroVM resume kept memory", f"메모리는 유지되지 않습니다({NT['pause_resume']['cycles']}회 중 {NT['pause_resume']['memory_kept']}회). 재개는 새 VM입니다. 볼륨이 한 가용 영역에 묶입니다. 메모리까지 유지된 것은 MicroVM 재개였습니다")],
        [t("A few sessions at a time, no nodes to manage, start time not critical", "동시 세션이 적고 노드를 관리하고 싶지 않으며 시작 시간이 중요하지 않을 때"), "EKS Fargate",
         t(f"No node groups. Agent time after start {sec(FG['agent']['fargate']['agent'])}, gVisor {sec(FG['agent']['gvisor']['agent'])}. Coding scenario {usd(S['coding']['fargate'])} a month at the smallest size, {usd(S['coding']['fargate_tested_size'])} at 2 vCPU, 8 GB", f"노드 그룹이 필요 없습니다. 시작을 뺀 에이전트 시간 {sec(FG['agent']['fargate']['agent'])}(gVisor {sec(FG['agent']['gvisor']['agent'])}). 코딩 시나리오 월 {usd(S['coding']['fargate'])}(최소 크기), {usd(S['coding']['fargate_tested_size'])}(2 vCPU, 8 GB)"),
         t(f"Every sandbox starts in about {sec(FG['cold']['fg-fs']['p50'], 0)} and that minute is billed. No warm pool, no gVisor or Kata, no DaemonSets, no Pod Identity (IRSA instead). An older CPU here: pure Python {FG['suite']['fg-fb']['cpu_python']['seconds'] / NT['suite']['nt-b']['cpu_python']['seconds']:.1f}x Nitro", f"샌드박스마다 시작에 약 {sec(FG['cold']['fg-fs']['p50'], 0)}가 걸리고 이 시간도 과금됩니다. Warm Pool, gVisor, Kata, DaemonSet, Pod Identity를 쓸 수 없습니다(IRSA 사용). 이번에는 이전 세대 CPU가 배정돼 순수 Python이 Nitro의 {FG['suite']['fg-fb']['cpu_python']['seconds'] / NT['suite']['nt-b']['cpu_python']['seconds']:.1f}배 걸렸습니다")],
        [t("Already running EKS", "이미 EKS를 운영 중일 때"), "gVisor + Agent Sandbox",
         t(f"Interactive scenario adds {usd(I['eks_gvisor_autoscaled_existing_cluster'])} a month on an existing cluster, {usd(I['agentcore_v2'])} on V2", f"기존 클러스터에 더하면 대화형 시나리오 월 {usd(I['eks_gvisor_autoscaled_existing_cluster'])}(V2 {usd(I['agentcore_v2'])})"),
         t("Assumes ideal scale-down. Sized for peak the node count doubles", "이상적인 축소를 가정한 값입니다. 피크에 맞춰 노드를 고정하면 노드 수가 약 두 배입니다")],
        [t("Seoul region required", "서울 리전이 필수일 때"), t("AgentCore V1 or EKS", "AgentCore V1 또는 EKS"),
         t("V2 and MicroVMs are not in Seoul (doc, 2026-11-03)", "V2와 MicroVM은 서울 리전에 없습니다(문서, 2026-11-03)"),
         t("Nothing here was measured in Seoul", "서울에서는 아무것도 측정하지 않았습니다")],
    ]


def variability(t):
    return t(
        "These results come mostly from one region (us-east-1), with part repeated in ap-northeast-1, over three days plus one more day for Fargate and Nitro, one account and one application. They can change with region, quotas, account limits, available capacity, instance type, image, application and time of day. Treat them as a starting point and repeat them with your own agent before you decide.",
        "이 결과는 대부분 한 리전(us-east-1)에서 나왔고, 일부만 도쿄(ap-northeast-1)에서 다시 측정했습니다. 사흘 동안(Fargate와 Nitro는 하루 더) 한 계정에서 앱 하나로 측정한 결과입니다. 리전, 쿼터, 계정 한도, 가용 용량, 인스턴스 종류, 이미지, 애플리케이션, 시간대에 따라 결과가 달라질 수 있습니다. 출발점으로 참고하시고, 결정하기 전에 실제로 운영할 에이전트로 다시 측정해 보시기 바랍니다.")


def removed(t):
    """What was thrown out or measured again because a quota, capacity or a mistake of ours shaped it."""
    return [
        [t("MicroVM bursts of 50 and 100, 10 per second", "MicroVM 동시 50, 100개, 초당 10건"), t("The default RunMicrovm quota of 5 per second set the result", "기본 RunMicrovm 쿼터(초당 5건)가 결과를 결정"), t("Removed. Burst of 10 and up to 5 per second stay. Not tested above the quota", "제거. 동시 10개와 초당 5건까지만 남김. 쿼터를 넘는 구간은 실험하지 않음")],
        [t("EKS bursts", "EKS 버스트"), t("Earlier runs had too few nodes for the size and a small driver", "이전 실행은 크기에 비해 노드가 적고 측정기가 작았음"), t("Measured again 3 times: 4 gVisor nodes, 8 Kata nodes, image on every node, dedicated 8 vCPU driver", "gVisor 4노드, Kata 8노드, 모든 노드에 이미지 적재, 전용 8 vCPU 측정기로 3회 재측정")],
        [t("Concurrent agents on one EKS node", "EKS 노드 1대의 동시 에이전트"), t("Capacity set the result (Kata 31.1 s at 10), managed had no such limit", "용량이 결과를 결정(Kata 10개 31.1초). 관리형에는 이런 제약이 없음"), t("Measured again on 4 and 8 nodes. One-node runs are kept only as density evidence", "4노드, 8노드에서 재측정. 1노드 결과는 밀도 근거로만 남김")],
        [t("Long silent requests without keepalive", "keepalive 없는 장기 무응답 요청"), t("The driver's NAT gateway dropped them at 350 s, not AgentCore", "AgentCore가 아니라 측정기의 NAT Gateway가 350초에 끊음"), t("Removed from the comparison. Only keepalive runs are compared", "비교에서 제거. keepalive 실행만 비교")],
        [t("V1 and V2 /ping", "V1, V2의 /ping"), t("Our /ping reported a new timestamp every time, so V1 stayed alive and billed more", "우리 /ping이 매번 새 시각을 보고해 V1이 회수되지 않고 과금이 늘어남"), t("Fixed the image and measured reclamation and billing again. V1 is now gone in 70 to 90 s", "이미지를 고쳐 회수와 과금을 재측정. V1이 이제 70~90초에 회수됨")],
        [t("\"Traffic makes V2 fast\"", "\"트래픽을 받으면 V2가 빨라진다\""), t("Load was confounded with run order", "부하와 실행 순서가 뒤섞여 있었음"), t("Withdrawn after a crossed test with new runtimes", "새 런타임으로 교차 실험한 뒤 철회")],
        [t("V1 low-rate control during the sustained test", "지속 유입 실험 중의 V1 저빈도 대조군"), t("It ran while the same runtime's ready environments were being used up", "같은 런타임의 준비된 환경이 소진되는 동안 실행됨"), t("Excluded", "제외")],
        [t("First quiet-period test", "첫 유휴 구간 실험"), t("Other experiments used AgentCore and MicroVMs during the wait", "대기 중에 다른 실험이 AgentCore와 MicroVM을 사용함"), t("Excluded. Run again with nothing else in the account", "제외. 계정에 다른 부하가 없는 상태로 재측정")],
        [t("Headline agent values", "대표 에이전트 수치"), t("Each option's value came from a different round, and managed results moved a lot over time", "구성마다 다른 라운드의 값을 썼는데, 관리형 결과는 시점에 따라 크게 달랐음"), t("Measured again in one shuffled period on new runtimes. Earlier rounds stay as a separate table", "새 런타임으로 같은 시간대에 순서를 섞어 재측정. 이전 라운드는 별도 표로 남김")],
        [t("Concurrent agents on V2 and MicroVM", "V2, MicroVM의 동시 에이전트"), t("They used a smaller driver than the other options", "다른 구성보다 작은 측정기를 사용함"), t("Measured again from the dedicated driver", "같은 전용 측정기로 재측정")],
        [t("Cost model", "비용 모델"), t("EKS left out the fixed parts, and V1 inputs came from the /ping bug", "EKS 고정비 누락, V1 입력에 /ping 오류 반영"), t("Added control plane, system nodes, NAT, disks. Formulas reproduce the AWS worked examples", "컨트롤 플레인, 시스템 노드, NAT, 디스크 추가. 공식이 AWS 계산 예시를 재현")],
    ]


WHY = {
    "cold": ("To compare start time alone when requests are sparse.", "요청이 드물 때 샌드박스 시작 시간만 비교하기 위해서입니다."),
    "package": ("To see whether V1 start time depends on image size and network mode.", "V1 시작 시간이 이미지 크기와 네트워크 모드에 좌우되는지 확인하기 위해서입니다."),
    "burst": ("Code execution and evaluation send many requests at once, so we compared them with capacity out of the way.", "코드 실행과 평가는 요청이 한꺼번에 몰리므로, 용량 제약을 없앤 상태에서 동시 처리 성능을 보기 위해서입니다."),
    "agent": ("Echo says little about a real agent, so every option ran the same SDK task.", "echo로는 실제 에이전트 성능을 알 수 없어, 모든 구성에서 같은 SDK 태스크를 실행해 비교하기 위해서입니다."),
    "crossed": ("V2 looked faster during a load test, so we separated load, gap and run order.", "부하 실험 중 V2가 빨라 보여서, 부하, 요청 간격, 실행 순서 중 무엇이 영향을 주는지 가려내기 위해서입니다."),
    "diag": ("To check whether slow runs were hidden errors.", "느린 실행이 숨은 오류인지 확인하기 위해서입니다."),
    "mitigate": ("To test the first-read explanation and find something customers can use.", "지연이 파일 첫 읽기 때문인지 확인하고, 실제로 쓸 수 있는 해결책을 찾기 위해서입니다."),
    "concurrent": ("To find contention for nodes, the model or storage that a single run hides.", "동시 실행에서만 드러나는 노드, 모델, 스토리지 경쟁을 확인하기 위해서입니다."),
    "heavy": ("The small task barely uses the sandbox, so we added a build that does.", "작은 태스크는 샌드박스 자원을 거의 쓰지 않아, 부하가 큰 빌드로 차이를 보기 위해서입니다."),
    "isolation": ("Each isolation method pays its cost on different syscalls.", "격리 방식마다 비용이 드러나는 시스템 콜이 다르기 때문입니다."),
    "fleet": ("Managed services pick the CPU, so we checked whether results vary by session.", "관리형은 CPU를 직접 고를 수 없어 세션마다 성능이 달라지는지 확인하기 위해서입니다."),
    "reclaim": ("You pay until a session is reclaimed, so we measured when it actually goes away.", "회수될 때까지 비용이 나가므로 세션이 실제로 사라지는 시점을 확인하기 위해서입니다."),
    "long": ("Agents can stay silent for minutes, so we looked for where connections break.", "에이전트가 몇 분씩 응답 없이 일할 때 어디서 연결이 끊기는지 찾기 위해서입니다."),
    "setup": ("Deploy and scale-up time decide how fast a team can make changes.", "배포와 용량 추가 시간이 변경 속도를 좌우하기 때문입니다."),
    "density": ("On EKS the bill follows how many sandboxes fit on a node.", "EKS 비용은 노드당 샌드박스 수로 정해지기 때문입니다."),
    "usage": ("Public prices alone do not give the bill, so we read the real billing inputs.", "공개 단가만으로는 청구액을 알 수 없어, 실제 과금 입력값을 확인하기 위해서입니다."),
    "cost": ("Latency alone cannot settle a decision, so we priced the same scenarios on every option.", "지연 시간만으로는 결정할 수 없어, 같은 시나리오의 비용을 비교하기 위해서입니다."),
    "security": ("Isolation helps less if the defaults inside are open, so we checked what a workload can reach.", "격리가 있어도 기본값이 열려 있으면 위험하므로, 워크로드가 접근할 수 있는 범위를 확인하기 위해서입니다."),
    "sdk": ("The slow first message could belong to one SDK, so we ran a second agent SDK with a small install on every option.", "첫 메시지 지연이 특정 SDK만의 문제인지 보려고, 설치 크기가 작은 다른 에이전트 SDK를 모든 구성에서 실행하기 위해서입니다."),
    "size": ("To see how the first read of a file grows with its size.", "파일 크기에 따라 첫 읽기 시간이 어떻게 늘어나는지 보기 위해서입니다."),
    "store": ("To see whether files survive a session restart and how fast they read back.", "세션을 다시 시작해도 파일이 남는지, 다시 읽는 속도가 어떤지 보기 위해서입니다."),
    "iso": ("To see whether warming one runtime helps another runtime that uses the same image.", "한 런타임을 예열하면 같은 이미지를 쓰는 다른 런타임도 빨라지는지 보기 위해서입니다."),
    "karpenter": ("Holding nodes costs money, so we measured scaling from zero and what consolidation does to live sessions.", "노드를 미리 두면 비용이 들기 때문에, 노드를 0개부터 늘리는 시간과 노드 통합이 실행 중인 세션에 주는 영향을 측정했습니다."),
    "tokyo": ("To check that the pattern is not peculiar to one region.", "결과가 한 리전에만 해당하는지 확인하기 위해서입니다."),
    "newopts": ("To compare two newer options, Nitro Sandboxes and node-free Fargate, on the same terms.", "새로 나온 Nitro Sandboxes와 노드 없이 쓰는 Fargate를 같은 기준으로 비교하기 위해서입니다."),
    "observability": ("To see what debugging and billing data exists with no setup.", "별도 설정 없이도 디버깅과 비용 확인에 필요한 정보가 얼마나 남는지 확인하기 위해서입니다."),
}


def why(key, t):
    en, ko = WHY[key]
    return t(en, ko)
