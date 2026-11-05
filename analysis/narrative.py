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
    return [
        [t("Sparse interactive sessions, small team", "간헐적 대화형 세션, 작은 팀"), "AgentCore V1",
         t(f"Whole request {sec(H['v1']['total_p50'])}, first message {sec(H['v1']['first_p50'])}, deploy about {F['deploy.v1']:.0f} s, metrics with no setup. Scenario {usd(I['agentcore_v1'])} a month, V2 {usd(I['agentcore_v2'])}, gVisor {usd(I['eks_gvisor_autoscaled'])} to {usd(I['eks_gvisor_autoscaled_graviton3'])}", f"요청 전체 {sec(H['v1']['total_p50'])}, 첫 메시지 {sec(H['v1']['first_p50'])}, 배포 약 {F['deploy.v1']:.0f}초, 지표 기본 제공. 시나리오 월 {usd(I['agentcore_v1'])}, V2 {usd(I['agentcore_v2'])}, gVisor {usd(I['eks_gvisor_autoscaled_graviton3'])}~{usd(I['eks_gvisor_autoscaled'])}"),
         t(f"Start time depends on the arrival rate: {sec(HC['v1']['p50'], 2)} at low rate, {sec(F['sus.v1np.5.p50'], 2)} at 5 new sessions per second", f"시작 시간은 유입 속도에 좌우됩니다. 저빈도 {sec(HC['v1']['p50'], 2)}, 초당 5건 {sec(F['sus.v1np.5.p50'], 2)}")],
        [t("V1, but steady arrivals and a small package", "V1을 쓰면서 유입이 꾸준하고 패키지가 작을 때"), t("AgentCore V1, direct code", "AgentCore V1 코드 직접 배포"),
         t(f"{sec(F['cold.v1zip.p50'], 2)} at low rate, {sec(F['sus.v1zip.5.p50'], 2)} at 5 per second, {sec(F['burst.v1zip.100.p50'], 2)} for 100 at once, deploy about {F['deploy.v1zip']:.0f} s", f"저빈도 {sec(F['cold.v1zip.p50'], 2)}, 초당 5건 {sec(F['sus.v1zip.5.p50'], 2)}, 동시 100개 {sec(F['burst.v1zip.100.p50'], 2)}, 배포 약 {F['deploy.v1zip']:.0f}초"),
         t("Package limits apply (250 MB zipped, 750 MB unzipped, doc). Not tested in VPC mode", "패키지 한도 적용(압축 250 MB, 해제 750 MB, 문서). VPC 모드는 미시험")],
        [t("Large bursts or large images with no spare nodes held, when the app does not need a large first read", "여분 노드 없이 큰 버스트나 큰 이미지를 받고, 앱이 큰 파일을 처음 읽지 않을 때"), "AgentCore V2",
         t(f"{sec(F['burst.v2.100.p50'], 2)} for 100 at once, {sec(F['fresh.V2.large.first'], 2)} for a new 1.5 GB runtime. With nodes ready, gVisor is faster at small scale ({sec(F['sus.gv.5.p50'], 2)} at 5 per second, V2 {sec(F['sus.v2.5.p50'], 2)}) and slower at 100 ({sec(F['burst.gv.100.p50'], 2)}). MicroVM ties V2 up to its quota ({sec(F['sus.lm.5.p50'], 2)})", f"동시 100개 {sec(F['burst.v2.100.p50'], 2)}, 새 1.5 GB 런타임 {sec(F['fresh.V2.large.first'], 2)}. 노드가 준비되면 작은 규모는 gVisor가 빠르고(초당 5건 {sec(F['sus.gv.5.p50'], 2)}, V2 {sec(F['sus.v2.5.p50'], 2)}) 100개는 느립니다({sec(F['burst.gv.100.p50'], 2)}). MicroVM은 쿼터까지 V2와 비슷합니다({sec(F['sus.lm.5.p50'], 2)})"),
         t(f"Agents that load a large binary: first message p50 {sec(H['v2']['first_p50'])}, p90 {sec(H['v2']['first_p90'])} on new runtimes. Deploy about {F['deploy.v2']:.0f} s. Not in Seoul (doc)", f"큰 바이너리를 읽는 에이전트는 새 런타임의 첫 메시지 p50 {sec(H['v2']['first_p50'])}, p90 {sec(H['v2']['first_p90'])}. 배포 약 {F['deploy.v2']:.0f}초. 서울 없음(문서)")],
        [t("Agents on V2 that must start fast from the first run", "V2에서 첫 실행부터 빨라야 하는 에이전트"), t("V2, CLI file mapped before the snapshot", "V2, 스냅샷 전에 CLI 파일 매핑"),
         t(f"First message p50 {sec(pin['first_p50'])}, p90 {sec(pin['first_p90'])} after a quiet hour, none of {pin['n']} runs over 20 s. Without it p50 {sec(A['ac-v2-q2|quiet2']['first_p50'])}", f"조용한 한 시간 뒤 첫 메시지 p50 {sec(pin['first_p50'])}, p90 {sec(pin['first_p90'])}, {pin['n']}회 모두 20초 미만. 매핑하지 않으면 p50 {sec(A['ac-v2-q2|quiet2']['first_p50'])}"),
         t("Small sample, this binary only. Billed memory with the file mapped was not measured. On MicroVMs the benefit is not established, since the interval overlaps no mitigation", "표본이 적고 이 바이너리에서만 시험했습니다. 매핑 시 과금 메모리는 재지 않았습니다. MicroVM에서는 신뢰 구간이 무처리와 겹쳐 효과가 입증되지 않았습니다")],
        [t("Must run inside your VPC", "VPC 안에서 실행 필수"), t("EKS if you run it, otherwise AgentCore V2 for start time", "운영할 수 있으면 EKS, 아니면 시작 시간은 AgentCore V2"),
         t(f"EKS is always in the VPC: gVisor {sec(HC['gv']['p50'], 2)} start, {sec(H['gv']['total_p50'])} whole request. AgentCore VPC mode: start V2 {sec(F['cold.v2vpc.p50'], 2)}, V1 {sec(F['cold.v1vpc.p50'], 2)}. 100 at once V2 {sec(F['burst.v2vpc.100.p50'], 2)}, V1 {sec(F['burst.v1vpc.100.p50'], 2)}", f"EKS는 항상 VPC 안입니다. gVisor 시작 {sec(HC['gv']['p50'], 2)}, 요청 전체 {sec(H['gv']['total_p50'])}. AgentCore VPC 모드: 시작 V2 {sec(F['cold.v2vpc.p50'], 2)}, V1 {sec(F['cold.v1vpc.p50'], 2)}. 동시 100개 V2 {sec(F['burst.v2vpc.100.p50'], 2)}, V1 {sec(F['burst.v1vpc.100.p50'], 2)}"),
         t(f"Whole request V1 {sec(A['ac-v1-vpc|vpc']['total_p50'])}, V2 {sec(A['ac-v2-vpc|vpc']['total_p50'])}: intervals overlap at {A['ac-v1-vpc|vpc']['n']} runs, so no ranking. First deploy V1 {F['deploy.v1vpc']:.0f} s, V2 {F['deploy.v2vpc']:.0f} s", f"요청 전체 V1 {sec(A['ac-v1-vpc|vpc']['total_p50'])}, V2 {sec(A['ac-v2-vpc|vpc']['total_p50'])}: {A['ac-v1-vpc|vpc']['n']}회로 신뢰 구간이 겹쳐 순위를 매기지 않습니다. 첫 배포 V1 {F['deploy.v1vpc']:.0f}초, V2 {F['deploy.v2vpc']:.0f}초")],
        [t("Sessions that sit idle until reclaimed", "회수될 때까지 유휴로 남는 세션"), "AgentCore V2",
         t(f"Idle until the default 15 minute reclaim billed {F['usage.idle_only_30min.v2np.gbh']:.2f} GB-h on V2 and {F['usage.idle_only_30min.v1np.gbh']:.2f} on V1, ${F['usage.idle_only_30min.v2np.cost']:.4f} and ${F['usage.idle_only_30min.v1np.cost']:.4f}", f"기본 15분 회수까지의 유휴 과금 V2 {F['usage.idle_only_30min.v2np.gbh']:.2f} GB-h, V1 {F['usage.idle_only_30min.v1np.gbh']:.2f} GB-h, ${F['usage.idle_only_30min.v2np.cost']:.4f}, ${F['usage.idle_only_30min.v1np.cost']:.4f}"),
         t("Both versions end an idle session at 15 minutes by default, so state does not survive longer unless you change the timeout. Measured on this image. An AWS blog example shows V2 memory depends on the app", "두 버전 모두 기본값으로 유휴 15분에 세션을 끝내므로, 타임아웃을 바꾸지 않으면 상태가 그 이상 남지 않습니다. 이 이미지의 값입니다. AWS 블로그 사례를 보면 V2 메모리는 앱에 좌우됩니다")],
        [t("Steady high concurrency with a platform team", "지속적 대량 동시성과 플랫폼 팀"), "gVisor + Agent Sandbox",
         t(f"Steady scenario {usd(S['steady']['eks_gvisor_autoscaled'])} a month ({usd(S['steady']['eks_gvisor_autoscaled_graviton3'])} on Graviton3), V2 {usd(S['steady']['agentcore_v2'])}. {sec(F['burst.gv.100.p50'], 2)} for 100 at once on prepared nodes", f"지속 시나리오 월 {usd(S['steady']['eks_gvisor_autoscaled'])}(Graviton3 {usd(S['steady']['eks_gvisor_autoscaled_graviton3'])}), V2 {usd(S['steady']['agentcore_v2'])}. 노드가 준비됐을 때 동시 100개 {sec(F['burst.gv.100.p50'], 2)}"),
         t(f"Staff cost is not included. A new node adds about {F['scale.gv.total']:.0f} s. Metrics, reclamation and policy are yours. The default is not hardened", f"인건비 제외. 새 노드는 약 {F['scale.gv.total']:.0f}초 추가. 지표, 회수, 정책은 직접 운영. 기본값은 강화되어 있지 않음")],
        [t("Lowest agent readiness, willing to pay for idle capacity", "에이전트 준비 시간 최우선, 유휴 용량 비용 감수"), t("EKS Warm Pool that runs the task before ready", "준비 전에 태스크를 실행한 EKS Warm Pool"),
         t(f"First message gVisor {sec(A['eks-x86-gvisor-warm-init|init']['first_p50'])}, Kata {sec(A['eks-x86-kata-warm-init|init']['first_p50'])}. Whole request {sec(A['eks-x86-gvisor-warm-init|init']['total_p50'])} and {sec(A['eks-x86-kata-warm-init|init']['total_p50'])}", f"첫 메시지 gVisor {sec(A['eks-x86-gvisor-warm-init|init']['first_p50'])}, Kata {sec(A['eks-x86-kata-warm-init|init']['first_p50'])}. 요청 전체 {sec(A['eks-x86-gvisor-warm-init|init']['total_p50'])}, {sec(A['eks-x86-kata-warm-init|init']['total_p50'])}"),
         t(f"Warm pods cost nodes (30 pods move the interactive break-even from {F['cost']['break_even_concurrency_interactive_gvisor_vs_v2']} to {F['cost']['break_even_concurrency_interactive_gvisor_warm30_vs_v2']} sessions). The warm-up itself calls the model. 10 runs each", f"Warm Pod만큼 노드 비용이 듭니다(30개면 대화형 손익 분기 {F['cost']['break_even_concurrency_interactive_gvisor_vs_v2']}개에서 {F['cost']['break_even_concurrency_interactive_gvisor_warm30_vs_v2']}개로). 예열 자체도 모델을 호출합니다. 각 10회")],
        [t("A guest kernel on your own cluster", "자체 클러스터에서 게스트 커널 필요"), "Kata + QEMU + Agent Sandbox",
         t(f"Guest kernel per pod, {sec(F['cold.kt.p50'], 2)} start, {sec(F['burst.kt.100.p50'], 2)} for 100 at once on 8 nodes. Metal lowers the build task from {sec(A['eks-x86-kata|heavy']['total_p50'])} to {sec(A['eks-metal-kata|heavy']['total_p50'])}", f"Pod마다 게스트 커널, 시작 {sec(F['cold.kt.p50'], 2)}, 8노드에서 동시 100개 {sec(F['burst.kt.100.p50'], 2)}. 메탈이면 빌드 태스크 {sec(A['eks-x86-kata|heavy']['total_p50'])}에서 {sec(A['eks-metal-kata|heavy']['total_p50'])}로 단축"),
         t(f"{F['density.kt.mb']:.0f} MB per idle sandbox against {F['density.gv.mb']:.0f} MB, and half as many per node. Needs nested virtualization or metal. Only virtio-fs tested", f"유휴 샌드박스당 {F['density.kt.mb']:.0f} MB(gVisor {F['density.gv.mb']:.0f} MB), 노드당 수용량 절반. 중첩 가상화나 메탈 필요. virtio-fs만 시험")],
        [t("Build-heavy agents, mostly on CPU", "CPU를 많이 쓰는 빌드 에이전트"), t("gVisor, V1 or MicroVM, decide on cost and operations", "gVisor, V1, MicroVM 중 비용과 운영으로 결정"),
         t(f"Build task: gVisor {sec(A['eks-x86-gvisor|heavy']['total_p50'])}, V1 {sec(A['ac-v1-np|heavy']['total_p50'])}, MicroVM {sec(A['lm-fa|heavy']['total_p50'])}, gVisor Graviton3 {sec(A['eks-g3-gvisor|heavy']['total_p50'])}, Kata metal {sec(A['eks-metal-kata|heavy']['total_p50'])}, V2 {sec(A['ac-v2-fa|heavy']['total_p50'])}, Kata {sec(A['eks-x86-kata|heavy']['total_p50'])}. Some near values overlap", f"빌드 태스크: gVisor {sec(A['eks-x86-gvisor|heavy']['total_p50'])}, V1 {sec(A['ac-v1-np|heavy']['total_p50'])}, MicroVM {sec(A['lm-fa|heavy']['total_p50'])}, gVisor Graviton3 {sec(A['eks-g3-gvisor|heavy']['total_p50'])}, Kata 메탈 {sec(A['eks-metal-kata|heavy']['total_p50'])}, V2 {sec(A['ac-v2-fa|heavy']['total_p50'])}, Kata {sec(A['eks-x86-kata|heavy']['total_p50'])}. 가까운 값 일부는 구간이 겹침"),
         t(f"Monthly scenario: gVisor {usd(S['build_heavy']['eks_gvisor_autoscaled'])}, Kata {usd(S['build_heavy']['eks_kata_autoscaled'])}, V1 {usd(S['build_heavy']['agentcore_v1'])}, V2 {usd(S['build_heavy']['agentcore_v2'])}, MicroVM {usd(S['build_heavy']['microvm_tested_size'])}. gVisor's rootfs is memory-backed here, MicroVM saw 8 vCPU, and managed CPU generations vary, so this mixes more than isolation", f"월 시나리오: gVisor {usd(S['build_heavy']['eks_gvisor_autoscaled'])}, Kata {usd(S['build_heavy']['eks_kata_autoscaled'])}, V1 {usd(S['build_heavy']['agentcore_v1'])}, V2 {usd(S['build_heavy']['agentcore_v2'])}, MicroVM {usd(S['build_heavy']['microvm_tested_size'])}. gVisor 루트FS가 메모리 기반이고 MicroVM에 8 vCPU가 보이며 관리형은 CPU 세대가 섞여, 격리 비용만의 차이가 아닙니다")],
        [t("Sessions that pause and continue with memory intact, or your own harness", "메모리를 유지한 채 멈췄다 이어 가는 세션, 직접 만든 하네스"), "Lambda MicroVMs",
         t(f"Resume {sec(F['susp.0MB.api.resume_p50'], 2)} by API, {sec(F['susp.0MB.traffic.resume_p50'])} by traffic, memory and disk kept in every run. Whole request {sec(H['lm']['total_p50'])}, p90 {sec(H['lm']['total_p90'])}", f"재개 API {sec(F['susp.0MB.api.resume_p50'], 2)}, 트래픽 {sec(F['susp.0MB.traffic.resume_p50'])}, 모든 실행에서 메모리와 디스크 유지. 요청 전체 {sec(H['lm']['total_p50'])}, p90 {sec(H['lm']['total_p90'])}"),
         t(f"Baseline billed while running, costing more than the stopped and autoscaled options in our scenarios at the tested size. Suspending pays off only when each idle period passes about {F['cost']['suspend_breakeven_idle_s_smallest'] / 60:.0f} minutes at 2 GB. Default 5 per second RunMicrovm quota. Routing is yours", f"실행 중 기준 자원 전액 과금으로, 시험한 크기에서 세션 중지와 자동 축소를 쓰는 구성보다 시나리오 비용이 높습니다. 일시 중지는 2 GB 기준 유휴 구간이 약 {F['cost']['suspend_breakeven_idle_s_smallest'] / 60:.0f}분을 넘어야 이득입니다. RunMicrovm 기본 쿼터 초당 5건. 라우팅은 직접")],
        [t("Already running EKS", "이미 EKS를 운영 중"), "gVisor + Agent Sandbox",
         t(f"Interactive scenario adds {usd(I['eks_gvisor_autoscaled_existing_cluster'])} a month on an existing cluster, {usd(I['agentcore_v2'])} on V2", f"기존 클러스터에 더하면 대화형 시나리오 월 {usd(I['eks_gvisor_autoscaled_existing_cluster'])}, V2 {usd(I['agentcore_v2'])}"),
         t("Assumes ideal scale-down. Sized for peak the node count doubles", "이상적인 축소를 가정합니다. 피크에 맞춰 고정하면 노드 수가 약 두 배")],
        [t("Seoul region required", "서울 리전 필수"), t("AgentCore V1 or EKS", "AgentCore V1 또는 EKS"),
         t("V2 and MicroVMs are not in Seoul (doc, 2026-11-03)", "V2와 MicroVM은 서울 없음(문서, 2026-11-03)"),
         t("Nothing here was measured in Seoul", "서울에서는 아무것도 측정하지 않았습니다")],
    ]


def variability(t):
    return t(
        "These results come from one region (us-east-1), two days, one account and one application. They can change with region, quotas, account limits, available capacity, instance type, image, application and time of day. Treat them as a starting point and repeat them with your own agent before you decide.",
        "이 결과는 한 리전(us-east-1), 이틀, 한 계정, 앱 하나에서 나왔습니다. 리전, 쿼터, 계정 한도, 가용 용량, 인스턴스 종류, 이미지, 애플리케이션, 시간대에 따라 달라질 수 있습니다. 출발점으로 삼고, 결정 전에 자사 에이전트로 다시 측정해 보시기 바랍니다.")


def removed(t):
    """What was thrown out or measured again because a quota, capacity or a mistake of ours shaped it."""
    return [
        [t("MicroVM bursts of 50 and 100, 10 per second", "MicroVM 동시 50, 100개, 초당 10건"), t("The default RunMicrovm quota of 5 per second set the result", "기본 RunMicrovm 쿼터(초당 5건)가 결과를 결정"), t("Removed. Burst of 10 and up to 5 per second stay. Not tested above the quota", "제거. 동시 10개와 초당 5건까지만 남김. 쿼터 위는 미시험")],
        [t("EKS bursts", "EKS 버스트"), t("Earlier runs had too few nodes for the size and a small driver", "이전 실행은 크기에 비해 노드가 적고 측정기가 작았음"), t("Measured again 3 times: 4 gVisor nodes, 8 Kata nodes, image on every node, dedicated 8 vCPU driver", "gVisor 4노드, Kata 8노드, 모든 노드에 이미지 적재, 전용 8 vCPU 측정기로 3회 재측정")],
        [t("Concurrent agents on one EKS node", "EKS 노드 1대의 동시 에이전트"), t("Capacity set the result (Kata 31.1 s at 10), managed had no such limit", "용량이 결과를 결정(Kata 10개 31.1초). 관리형에는 이런 제약이 없음"), t("Measured again on 4 and 8 nodes. One-node runs are kept only as density evidence", "4노드, 8노드에서 재측정. 1노드 결과는 밀도 근거로만 남김")],
        [t("Long silent requests without keepalive", "keepalive 없는 장기 무응답 요청"), t("The driver's NAT gateway dropped them at 350 s, not AgentCore", "AgentCore가 아니라 측정기의 NAT Gateway가 350초에 끊음"), t("Removed from the comparison. Only keepalive runs are compared", "비교에서 제거. keepalive 실행만 비교")],
        [t("V1 and V2 /ping", "V1, V2의 /ping"), t("Our /ping reported a new timestamp every time, so V1 stayed alive and billed more", "우리 /ping이 매번 새 시각을 보고해 V1이 회수되지 않고 과금이 늘어남"), t("Fixed the image and measured reclamation and billing again. V1 is now gone in 70 to 90 s", "이미지를 고쳐 회수와 과금을 재측정. V1이 이제 70~90초에 회수됨")],
        [t("\"Traffic makes V2 fast\"", "\"트래픽을 받으면 V2가 빨라진다\""), t("Load was confounded with run order", "부하와 실행 순서가 뒤섞여 있었음"), t("Withdrawn after a crossed test with new runtimes", "새 런타임으로 교차 시험한 뒤 철회")],
        [t("V1 low-rate control during the sustained test", "지속 유입 시험 중의 V1 저빈도 대조군"), t("It ran while the same runtime's ready environments were being used up", "같은 런타임의 준비된 환경이 소진되는 동안 실행됨"), t("Excluded", "제외")],
        [t("First quiet-period test", "첫 조용한 구간 시험"), t("Other experiments used AgentCore and MicroVMs during the wait", "대기 중에 다른 실험이 AgentCore와 MicroVM을 사용함"), t("Excluded. Run again with nothing else in the account", "제외. 계정에 다른 부하가 없는 상태로 재측정")],
        [t("Headline agent values", "대표 에이전트 수치"), t("Each option's value came from a different round, and managed results moved a lot over time", "구성마다 다른 라운드의 값을 썼는데, 관리형 결과는 시점에 따라 크게 달랐음"), t("Measured again in one shuffled period on new runtimes. Earlier rounds stay as a separate table", "새 런타임으로 같은 시기에 순서를 섞어 재측정. 이전 라운드는 별도 표로 남김")],
        [t("Concurrent agents on V2 and MicroVM", "V2, MicroVM의 동시 에이전트"), t("They used a smaller driver than the other options", "다른 구성보다 작은 측정기를 사용함"), t("Measured again from the dedicated driver", "같은 전용 측정기로 재측정")],
        [t("Cost model", "비용 모델"), t("EKS left out the fixed parts, and V1 inputs came from the /ping bug", "EKS 고정비 누락, V1 입력에 /ping 오류 반영"), t("Added control plane, system nodes, NAT, disks. Formulas reproduce the AWS worked examples", "컨트롤 플레인, 시스템 노드, NAT, 디스크 추가. 공식이 AWS 계산 예시를 재현")],
    ]


WHY = {
    "cold": ("To compare start time alone when requests are sparse.", "요청이 드물 때 샌드박스 시작 시간만 비교하기 위해서입니다."),
    "package": ("To see whether V1 start time depends on image size and network mode.", "V1 시작 시간이 이미지 크기와 네트워크 모드에 좌우되는지 확인하기 위해서입니다."),
    "burst": ("Code execution and evaluation send many requests at once, so we compared them with capacity out of the way.", "코드 실행과 평가는 요청이 한꺼번에 몰리므로, 용량 제약 없이 동시 처리 능력을 보기 위해서입니다."),
    "agent": ("Echo says little about a real agent, so every option ran the same SDK task.", "echo로는 실제 에이전트 성능을 알 수 없어 같은 SDK 태스크로 비교했습니다."),
    "crossed": ("V2 looked faster during a load test, so we separated load, gap and run order.", "부하 시험 중 V2가 빨라 보여, 부하, 간격, 실행 순서 중 무엇이 영향을 주는지 가리기 위해서입니다."),
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
    "usage": ("Public prices alone do not give the bill, so we read the real billing inputs.", "공개 단가만으로는 청구액을 알 수 없어 실제 과금 입력을 확인했습니다."),
    "cost": ("Latency alone cannot settle a decision, so we priced the same scenarios on every option.", "지연만으로는 결정할 수 없어 같은 시나리오의 비용을 비교했습니다."),
    "security": ("Isolation helps less if the defaults inside are open, so we checked what a workload can reach.", "격리가 있어도 기본값이 열려 있으면 위험하므로, 워크로드가 접근할 수 있는 범위를 확인했습니다."),
    "observability": ("To see what debugging and billing data exists with no setup.", "디버깅과 비용 확인에 필요한 정보가 설정 없이 얼마나 남는지 확인했습니다."),
}


def why(key, t):
    en, ko = WHY[key]
    return t(en, ko)
