#!/usr/bin/env python3
import re
"""Generates README.md and README.ko.md from results/facts.json, so the numbers cannot drift from the data."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import narrative

ROOT = Path(__file__).resolve().parent.parent
F = json.loads((ROOT / "results" / "facts.json").read_text())
ROUNDS = sorted(F["cold.v1.rounds"])


def table(rows):
    out = ["| " + " | ".join(str(c) for c in rows[0]) + " |", "|" + "---|" * len(rows[0])]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows[1:]]
    return "\n".join(out)


def s(k, n=2):
    return f"{F[k]:.{n}f} s" if k in F else "n/t"


def pct(a, b):
    return f"{(1 - F[b] / F[a]) * 100:.0f}%"


def lcell(b, sec, mode="sleep", t=None):
    for r in F["long"]:
        if r["backend"] == b and r["requested_s"] == sec and (r.get("mode") or "sleep") == mode:
            if r["ok"]:
                return t("completed", "완료")
            if r.get("error") == "ConnectionError":
                return t(f"HTTP 502 at {r['wall_s']:.0f} s", f"{r['wall_s']:.0f}초에 HTTP 502")
            return t("no response", "응답 없음")
    return "n/t"


def render(lang):
    t = (lambda en, ko: en) if lang == "en" else (lambda en, ko: ko)
    P = ["gVisor", "Kata + QEMU", "AgentCore V1", "AgentCore V2", "Lambda MicroVMs"]
    K = ["gv", "kt", "v1", "v2", "lm"]
    A = "agent_task_then_5min_idle"
    I = "idle_only_5min"
    Y = "alloc1gb_30s_cpu_5min_idle"
    C = F["cost"]["scenarios"]
    be = F["cost"]["break_even_concurrency_interactive_gvisor_vs_v2"]
    other = t("[한국어](README.ko.md)", "[English](README.md)")
    d = []
    d.append(t("# Agent sandboxes on AWS, measured", "# AWS 에이전트 샌드박스 실측 비교"))
    d.append(other)
    d.append(t(
        f"The same Claude Agent SDK application, run on five sandbox options on AWS and measured from a driver in the same region. Measured in `us-east-1`, 2026-11-03 to 05, with several rounds and follow-up tests, and part repeated in `ap-northeast-1`. EKS Fargate and Nitro Sandboxes were added on 2026-11-10 with the same experiments. Measured numbers are generated from `results/raw/`. Measured values are the default; anything taken from documentation is marked (doc), and anything not tested is marked n/t.",
        f"같은 Claude Agent SDK 앱을 AWS의 샌드박스 다섯 가지에 올리고, 같은 리전에 둔 측정기에서 측정했습니다. 2026-11-03~05에 `us-east-1`에서 여러 라운드와 후속 실험을 진행했고, 일부는 `ap-northeast-1`에서 다시 측정했습니다. 2026-11-10에는 EKS Fargate와 Nitro Sandboxes를 같은 실험으로 추가 측정했습니다. 모든 수치는 `results/raw/`의 원시 데이터에서 생성합니다. 별도 표시가 없으면 측정값입니다. 문서에서 가져온 값에는 (문서), 실험하지 않은 항목에는 n/t를 붙였습니다."))

    FA, CS, LR = F["fair"]["agent"], F["fair"]["concurrent_scaled"], F["fair"]["low_rate"]
    C8 = F["fair"]["crossed_first8"]


    H, HC = narrative.headline(F), narrative.headline_cold(F)
    NX0 = F["fu"]["new"]
    MT = F["fair"]["model_time_range"]
    Q = lambda k: FA.get(k)
    FU = F["fu"]
    M, IS, SZ, SD, BD, CN, NW, ST, SCY = FU["mitigation"], FU["iso"], FU["size"], FU["sdk"], FU["build"], FU["conc"], FU["network"], FU["store"], FU["store_cycle"]
    KP, KT, KK, TK = FU["kp_scale"], FU["kp_trace"], FU["kp_kata"], FU["tokyo"]
    sc = lambda x, n=1: t(f"{x:.{n}f} s", f"{x:.{n}f}초")
    d.append(t("## Results vary", "## 결과는 달라질 수 있습니다"))
    d.append(narrative.variability(t))
    d.append(t("## Key findings", "## 핵심 결과"))
    d.append(table([
        [t("Finding", "결과"), t("Evidence", "근거")],
        [t("No option wins everywhere. The order changes with what you measure.", "모든 면에서 앞서는 구성은 없습니다. 무엇을 측정하느냐에 따라 순위가 바뀝니다."), t(f"Small agent task, same period and shuffled, whole request: gVisor {H['gv']['total_p50']:.1f} s, V1 {H['v1']['total_p50']:.1f} s, Kata {H['kt']['total_p50']:.1f} s, MicroVM {H['lm']['total_p50']:.1f} s, V2 {H['v2']['total_p50']:.1f} s. 100 at once on echo: V2 {s('burst.v2.100.p50')}, gVisor {s('burst.gv.100.p50')}, V1 {s('burst.v1.100.p50')}, Kata {s('burst.kt.100.p50')}.", f"같은 시간대에 순서를 섞어 돌린 작은 에이전트 태스크의 전체 시간: gVisor {H['gv']['total_p50']:.1f} s, V1 {H['v1']['total_p50']:.1f} s, Kata {H['kt']['total_p50']:.1f} s, MicroVM {H['lm']['total_p50']:.1f} s, V2 {H['v2']['total_p50']:.1f} s. echo 동시 100개: V2 {s('burst.v2.100.p50')}, gVisor {s('burst.gv.100.p50')}, V1 {s('burst.v1.100.p50')}, Kata {s('burst.kt.100.p50')}.")],
        [t("V1's start depends on arrival rate and packaging.", "V1의 시작 시간은 유입 속도와 패키징 방식에 따라 달라집니다."), t(f"Same-period low rate p50 {HC['v1']['p50']:.2f} s, p90 {HC['v1']['p90']:.2f} s. 5 per second {s('sus.v1np.5.p50')}, 1.5 GB image {s('sus.v1large.5.p50')}, direct code {s('sus.v1zip.5.p50')}, VPC mode {s('sus.v1vpc.5.p50')}.", f"같은 시간대의 저빈도 p50 {HC['v1']['p50']:.2f} s, p90 {HC['v1']['p90']:.2f} s. 초당 5건에서는 기본 이미지 {s('sus.v1np.5.p50')}, 1.5 GB 이미지 {s('sus.v1large.5.p50')}, 코드 직접 배포 {s('sus.v1zip.5.p50')}, VPC 모드 {s('sus.v1vpc.5.p50')}.")],
        [t("V2 starts in 1.8 to 3.5 s across the conditions tested, on echo, in the range AWS published.", "echo 기준으로 V2는 실험한 모든 조건에서 1.8~3.5초에 시작했고, AWS가 발표한 수치와 같은 범위입니다."), t(f"Low rate {HC['v2']['p50']:.2f} s, 5 per second {s('sus.v2.5.p50')}, 100 at once {s('burst.v2.100.p50')}, new 1.5 GB runtime {s('fresh.V2.large.first')}, VPC mode {s('cold.v2vpc.p50')}, VPC mode at 100 at once {s('burst.v2vpc.100.p50')}.", f"저빈도 {HC['v2']['p50']:.2f} s, 초당 5건 {s('sus.v2.5.p50')}, 동시 100개 {s('burst.v2.100.p50')}, 새 1.5 GB 런타임 {s('fresh.V2.large.first')}, VPC 모드 {s('cold.v2vpc.p50')}, VPC 모드 동시 100개 {s('burst.v2vpc.100.p50')}.")],
        [t("On V2 and MicroVM a new session is slow the first time it reads a large file. The Claude Agent SDK, with its large CLI, waits long for its first message; the Strands Agents SDK, with a small install, does not.", "V2와 MicroVM에서는 새 세션이 큰 파일을 처음 읽을 때 오래 걸립니다. 그래서 큰 CLI를 포함한 Claude Agent SDK는 첫 메시지가 늦고, 설치 크기가 작은 Strands Agents SDK는 늦지 않습니다."), t(f"V2 first message on new runtimes: p50 {H['v2']['first_p50']:.1f} s, p90 {H['v2']['first_p90']:.1f} s, {H['v2']['slow_share'] * 100:.0f}% over 20 s, {H['v2']['n']} of {H['v2']['tried']} succeeded. 331 MB CLI on a new V2 sandbox: first read {F['touch.v2.read_cli_binary.first']:.1f} s, second {F['touch.v2.read_cli_binary.second']:.2f} s. First read of a 200 MB file p50: V2 {SZ['v2|200']['p50']:.1f} s, MicroVM {SZ['lm|200']['p50']:.1f} s, V1 {SZ['v1|200']['p50']:.2f} s. Until the first model event on V2: Claude Agent SDK {SD['v2|c']['ready']['p50']:.1f} s, Strands {SD['v2|s']['ready']['p50']:.1f} s.", f"새 런타임의 V2 첫 메시지: p50 {H['v2']['first_p50']:.1f}초, p90 {H['v2']['first_p90']:.1f}초, 20초 초과 {H['v2']['slow_share'] * 100:.0f}%, {H['v2']['tried']}회 중 {H['v2']['n']}회 성공. 새 V2 샌드박스에서 331 MB CLI 첫 읽기 {F['touch.v2.read_cli_binary.first']:.1f}초, 두 번째 읽기 {F['touch.v2.read_cli_binary.second']:.2f}초. 200 MB 파일 첫 읽기 p50: V2 {SZ['v2|200']['p50']:.1f}초, MicroVM {SZ['lm|200']['p50']:.1f}초, V1 {SZ['v1|200']['p50']:.2f}초. V2에서 첫 모델 이벤트까지: Claude Agent SDK {SD['v2|c']['ready']['p50']:.1f}초, Strands {SD['v2|s']['ready']['p50']:.1f}초.")],
        [t("Mapping the large file before the snapshot, or fetching it from S3 at session start, removes the wait. Periodic warm-up calls reduce it partly and only for the runtime they call.", "큰 파일을 스냅샷 전에 매핑해 두거나 세션 시작 시 S3에서 받으면 이 지연이 사라집니다. 주기적인 예열 호출은 지연을 일부만 줄이고, 호출한 런타임에만 효과가 있습니다."), t(f"Same period, V2 first message p50: mapped {M['v2_map']['first']['p50']:.1f} s, S3 {M['v2_s3']['first']['p50']:.1f} s, warm-up every 5 minutes {M['v2_w5k1']['first']['p50']:.1f} s, 4 every 10 minutes {M['v2_w10k4']['first']['p50']:.1f} s, nothing {M['v2_none']['first']['p50']:.1f} s. MicroVM: mapped {M['lm_map']['first']['p50']:.1f} s, S3 {M['lm_s3']['first']['p50']:.1f} s, nothing {M['lm_none']['first']['p50']:.1f} s. First read on the warmed runtime {IS['warmed']['p50']:.1f} s, on another runtime with the same image {IS['same_image']['p50']:.1f} s, on a runtime of its own {IS['alone']['p50']:.1f} s.", f"같은 시간대의 V2 첫 메시지 p50: 매핑 {M['v2_map']['first']['p50']:.1f}초, S3 {M['v2_s3']['first']['p50']:.1f}초, 5분 간격 예열 {M['v2_w5k1']['first']['p50']:.1f}초, 10분 간격 예열 4개 {M['v2_w10k4']['first']['p50']:.1f}초, 조치 없음 {M['v2_none']['first']['p50']:.1f}초. MicroVM: 매핑 {M['lm_map']['first']['p50']:.1f}초, S3 {M['lm_s3']['first']['p50']:.1f}초, 조치 없음 {M['lm_none']['first']['p50']:.1f}초. 첫 읽기: 예열한 런타임 {IS['warmed']['p50']:.1f}초, 같은 이미지를 쓰는 다른 런타임 {IS['same_image']['p50']:.1f}초, 예열하지 않은 런타임 {IS['alone']['p50']:.1f}초.")],
        [t("EKS improves a lot when tuned.", "EKS도 튜닝하면 크게 빨라집니다."), t(f"Warm pods that ran the task before ready: first message gVisor {FA['eks-x86-gvisor-warm-init|init']['first_p50']:.1f} s, Kata {FA['eks-x86-kata-warm-init|init']['first_p50']:.1f} s; whole request {FA['eks-x86-gvisor-warm-init|init']['total_p50']:.1f} s and {FA['eks-x86-kata-warm-init|init']['total_p50']:.1f} s. These pods cost nodes while they wait.", f"태스크를 미리 한 번 실행해 둔 Warm Pod: 첫 메시지 gVisor {FA['eks-x86-gvisor-warm-init|init']['first_p50']:.1f} s, Kata {FA['eks-x86-kata-warm-init|init']['first_p50']:.1f} s, 전체 시간 각각 {FA['eks-x86-gvisor-warm-init|init']['total_p50']:.1f} s, {FA['eks-x86-kata-warm-init|init']['total_p50']:.1f} s. 대기하는 동안에도 노드 비용이 듭니다.")],
        [t("On a build task gVisor and V1 are fastest and V2 is slowest.", "빌드 태스크에서는 gVisor와 V1이 가장 빠르고 V2가 가장 느립니다."), t(f"Shuffled in one period, whole request: gVisor {BD['gvisor']['whole']['p50']:.1f} s, V1 {BD['v1']['whole']['p50']:.1f} s, gVisor Graviton3 {BD['gvisor_g3']['whole']['p50']:.1f} s, MicroVM {BD['lm']['whole']['p50']:.1f} s, Kata {BD['kata']['whole']['p50']:.1f} s, V2 {BD['v2']['whole']['p50']:.1f} s. After the first message alone, V2 {BD['v2']['after_first']['p50']:.1f} s against V1 {BD['v1']['after_first']['p50']:.1f} s.", f"같은 시간대에 순서를 섞어 측정한 전체 시간: gVisor {BD['gvisor']['whole']['p50']:.1f}초, V1 {BD['v1']['whole']['p50']:.1f}초, gVisor Graviton3 {BD['gvisor_g3']['whole']['p50']:.1f}초, MicroVM {BD['lm']['whole']['p50']:.1f}초, Kata {BD['kata']['whole']['p50']:.1f}초, V2 {BD['v2']['whole']['p50']:.1f}초. 첫 메시지 이후만 비교해도 V2 {BD['v2']['after_first']['p50']:.1f}초, V1 {BD['v1']['after_first']['p50']:.1f}초입니다.")],
        [t("EKS can scale nodes from zero with Karpenter, but default consolidation ends running sessions.", "EKS는 Karpenter로 노드를 0개부터 늘릴 수 있지만, 기본 통합(consolidation) 설정에서는 실행 중인 세션이 끊깁니다."), t(f"First gVisor sandbox on an empty cluster {KP['1']['p50']:.1f} s, 50 all ready in {KP['50']['all_ready']:.1f} s. In a {KT['default']['hours'] * 60:.0f} minute trace: {KT['default']['lost']} of {KT['default']['sessions']} sessions ended by default consolidation, {KT['keep']['lost']} of {KT['keep']['sessions']} with do-not-disrupt, at about {(KT['keep']['node_h_per_pod_h'] / KT['default']['node_h_per_pod_h'] - 1) * 100:.0f}% more node hours.", f"빈 클러스터에서 첫 gVisor 샌드박스 {KP['1']['p50']:.1f}초, 50개 모두 준비 {KP['50']['all_ready']:.1f}초. {KT['default']['hours'] * 60:.0f}분 트레이스에서 기본 설정은 세션 {KT['default']['sessions']}개 중 {KT['default']['lost']}개가 끊겼고, do-not-disrupt를 붙이면 {KT['keep']['sessions']}개 중 {KT['keep']['lost']}개였습니다. 대신 노드 시간이 약 {(KT['keep']['node_h_per_pod_h'] / KT['default']['node_h_per_pod_h'] - 1) * 100:.0f}% 늘었습니다.")],
        [t("Tokyo showed the same pattern.", "도쿄에서도 같은 패턴이 나타났습니다."), t(f"ap-northeast-1 low-rate start: V1 {TK['cold']['v1']['p50']:.2f} s, gVisor {TK['cold']['gv']['p50']:.2f} s, V2 {TK['cold']['v2']['p50']:.2f} s, Kata {TK['cold']['kt']['p50']:.2f} s. Agent first message p50: V2 {TK['agent']['v2']['first']['p50']:.1f} s (p90 {TK['agent']['v2']['first']['p90']:.1f} s), the others {min(TK['agent'][k]['first']['p50'] for k in ('v1', 'gv', 'kt')):.1f} to {max(TK['agent'][k]['first']['p50'] for k in ('v1', 'gv', 'kt')):.1f} s.", f"ap-northeast-1 저빈도 시작: V1 {TK['cold']['v1']['p50']:.2f}초, gVisor {TK['cold']['gv']['p50']:.2f}초, V2 {TK['cold']['v2']['p50']:.2f}초, Kata {TK['cold']['kt']['p50']:.2f}초. 에이전트 첫 메시지 p50: V2 {TK['agent']['v2']['first']['p50']:.1f}초(p90 {TK['agent']['v2']['first']['p90']:.1f}초), 나머지 구성 {min(TK['agent'][k]['first']['p50'] for k in ('v1', 'gv', 'kt')):.1f}~{max(TK['agent'][k]['first']['p50'] for k in ('v1', 'gv', 'kt')):.1f}초.")],
        [t("Nitro Sandboxes give each pod its own VM at almost no syscall cost, and start close to Kata. They slow down under steady arrivals.", "Nitro Sandboxes는 Pod마다 VM을 따로 두면서도 시스템 콜 비용이 거의 없고, Kata와 비슷하게 시작합니다. 다만 요청이 꾸준히 몰리면 느려집니다."), t(f"Start {NX0['nt']['cold']['nt-c']['p50']:.2f} s (Kata {NX0['na']['cold']['na-kt']['p50']:.2f} s, gVisor {NX0['na']['cold']['na-gv']['p50']:.2f} s in the same period), warm pool claim {NX0['nt']['cold']['nt-w']['p50']:.2f} s. getppid {NX0['nt']['suite']['nt-b']['syscalls']['getppid_ns']:.0f} ns, open+close {NX0['nt']['suite']['nt-b']['syscalls']['open_close_ns'] / 1000:.1f} µs, close to runc. Build {NX0['nt']['heavy']['nitro']['whole']['p50']:.1f} s, between gVisor {NX0['na']['heavy']['gvisor']['whole']['p50']:.1f} s and Kata {NX0['na']['heavy']['kata']['whole']['p50']:.1f} s. 5 per second {NX0['nt']['sustained']['nt-c']['5.0']['p50']:.1f} s.", f"시작 {NX0['nt']['cold']['nt-c']['p50']:.2f}초(같은 시간대 Kata {NX0['na']['cold']['na-kt']['p50']:.2f}초, gVisor {NX0['na']['cold']['na-gv']['p50']:.2f}초), Warm Pool 할당 {NX0['nt']['cold']['nt-w']['p50']:.2f}초. getppid {NX0['nt']['suite']['nt-b']['syscalls']['getppid_ns']:.0f} ns, open+close {NX0['nt']['suite']['nt-b']['syscalls']['open_close_ns'] / 1000:.1f} µs로 runc와 비슷합니다. 빌드 {NX0['nt']['heavy']['nitro']['whole']['p50']:.1f}초로 gVisor {NX0['na']['heavy']['gvisor']['whole']['p50']:.1f}초와 Kata {NX0['na']['heavy']['kata']['whole']['p50']:.1f}초 사이. 초당 5건에서는 {NX0['nt']['sustained']['nt-c']['5.0']['p50']:.1f}초.")],
        [t("EKS Fargate needs no nodes, but every sandbox takes about a minute to start.", "EKS Fargate는 노드가 필요 없지만, 샌드박스마다 시작에 약 1분이 걸립니다."), t(f"Start p50 {NX0['fg']['cold']['fg-fs']['p50']:.1f} s at 0.25 vCPU and {NX0['fg']['cold']['fg-fb']['p50']:.1f} s at 2 vCPU, about the same at 100 at once and at 5 per second. After start the agent ran in {NX0['fg']['agent']['fargate']['agent']:.1f} s, gVisor {NX0['fg']['agent']['gvisor']['agent']:.1f} s in the same period.", f"시작 p50: 0.25 vCPU {NX0['fg']['cold']['fg-fs']['p50']:.1f}초, 2 vCPU {NX0['fg']['cold']['fg-fb']['p50']:.1f}초. 동시 100개와 초당 5건에서도 비슷했습니다. 시작한 뒤 에이전트 실행은 {NX0['fg']['agent']['fargate']['agent']:.1f}초로, 같은 시간대 gVisor {NX0['fg']['agent']['gvisor']['agent']:.1f}초와 비슷합니다.")],
        [t("Cost depends on scale and session shape.", "비용은 규모와 세션 패턴에 따라 달라집니다."), t(f"Interactive scenario with explicit stop: V2 ${C['interactive']['agentcore_v2']:,.0f}, gVisor ${C['interactive']['eks_gvisor_autoscaled']:,.0f}, V1 ${C['interactive']['agentcore_v1']:,.0f}, MicroVM from ${C['interactive']['microvm_always_running']:,.0f}. Without a stop V2 ${C['interactive']['agentcore_v2_no_stop']:,.0f}, V1 ${C['interactive']['agentcore_v1_no_stop']:,.0f}. Steady scenario: gVisor ${C['steady']['eks_gvisor_autoscaled']:,.0f}, V2 ${C['steady']['agentcore_v2']:,.0f}.", f"세션을 명시적으로 중지하는 대화형 시나리오: V2 ${C['interactive']['agentcore_v2']:,.0f}, gVisor ${C['interactive']['eks_gvisor_autoscaled']:,.0f}, V1 ${C['interactive']['agentcore_v1']:,.0f}, MicroVM ${C['interactive']['microvm_always_running']:,.0f}부터. 중지하지 않으면 V2 ${C['interactive']['agentcore_v2_no_stop']:,.0f}, V1 ${C['interactive']['agentcore_v1_no_stop']:,.0f}. 지속 시나리오: gVisor ${C['steady']['eks_gvisor_autoscaled']:,.0f}, V2 ${C['steady']['agentcore_v2']:,.0f}.")],
    ]))

    d.append(t("## Which option for which situation", "## 상황별 권장 구성"))
    d.append(table([[t("Situation", "상황"), t("First choice", "먼저 검토할 구성"), t("Measured reason", "측정 근거"), t("Avoid or check", "주의할 점")]] + narrative.recommendations(F, t)))

    d.append(t("## Results", "## 상세 결과"))
    d.append(t("Values are p50 unless marked. Where confidence intervals overlap, we do not call it a difference. First message runs from the `query()` call, after the SDK import, to the first object the SDK yields, which comes before the first model stream event. It leaves out sandbox start and the SDK import. Whole request is sandbox start plus the agent call: SDK import, task, the harness's pytest and network.", "별도 표시가 없으면 p50입니다. 신뢰 구간이 겹치면 차이가 있다고 보지 않습니다. 첫 메시지는 SDK를 import한 뒤 `query()`를 호출한 시점부터 SDK가 첫 객체를 돌려줄 때까지의 시간으로, 첫 모델 스트림 이벤트보다 앞섭니다. 샌드박스 시작과 SDK import 시간은 들어 있지 않습니다. 전체 시간은 샌드박스 시작 시간과 에이전트 호출 시간을 더한 값으로, SDK import, 태스크, 하네스의 pytest, 네트워크 시간이 모두 들어 있습니다."))
    d.append(t("### Cold start, from request to echo reply", "### 콜드 스타트, 요청부터 echo 응답까지"))
    if F["fair"].get("same", {}).get("cold"):
        SC = F["fair"]["same"]["cold"]
        d.append(t("Same period, shuffled, one round on new managed runtimes after 10 agent runs on each:", "같은 시간대에 순서를 섞어 1라운드 측정했습니다. 관리형은 새 런타임마다 에이전트를 10회 실행한 뒤에 측정했습니다."))
        d.append(table([["", "gVisor x86", "gVisor Graviton3", "Kata", "AgentCore V1", "AgentCore V2", "Lambda MicroVMs"], ["p50"] + [f"{SC[k]['p50']:.2f} s" for k in ("gv", "g3gv", "kt", "v1", "v2", "lm")], ["p90"] + [f"{SC[k]['p90']:.2f} s" for k in ("gv", "g3gv", "kt", "v1", "v2", "lm")], [t("Share under 3 s", "3초 미만 비율")] + [f"{SC[k]['fast_share'] * 100:.0f}%" for k in ("gv", "g3gv", "kt", "v1", "v2", "lm")], [t("Arrival interval per option", "구성별 요청 간격")] + [f"{SC[k]['arrival_s']:.0f} s" for k in ("gv", "g3gv", "kt", "v1", "v2", "lm")]]))
    d.append(t("Other conditions and earlier rounds:", "다른 조건과 이전 라운드의 결과입니다."))
    KN = ["gv", "kt", "v1np", "v2np", "lm"]
    rows = [[""] + P, ["p50"] + [s(f"cold.{k}.p50") for k in KN], ["p90"] + [s(f"cold.{k}.p90") for k in KN]]
    rows.append([t("1.5 GB image", "1.5 GB 이미지")] + [s(f"cold.{k}.large.p50") for k in K])
    rows.append([t("10 s start-up work", "초기화 10초")] + [s(f"cold.{k}.heavy.p50") for k in K])
    rows.append([t("n / failures", "횟수 / 실패")] + [f"{F[f'cold.{k}.n']} / {F[f'cold.{k}.fail']}" for k in KN])
    d.append(table(rows))
    d.append(t(f"V1 and V2 use the image with the documented /ping, except the 1.5 GB and start-up rows, which use the earlier /ping. Warm pools: gVisor {F['cold.gvw.p50'] * 1000:.0f} ms, Kata {F['cold.ktw.p50'] * 1000:.0f} ms, paying for the pods kept ready. Baselines: runc {s('cold.rc.p50')}, Kata on metal {s('cold.ktm.p50')}. Warm calls from the driver take about 1 ms on EKS, {F['warm.lm.p50ms']:.1f} ms on MicroVM, {F['warm.v1.p50ms']:.0f} ms on V1 and {F['warm.v2.p50ms']:.0f} ms on V2, so differences within 0.1 s should not be ranked.", f"V1과 V2는 /ping을 문서대로 고친 이미지로 측정했고, 1.5 GB 이미지와 초기화 행만 이전 /ping 이미지입니다. Warm Pool은 gVisor {F['cold.gvw.p50'] * 1000:.0f} ms, Kata {F['cold.ktw.p50'] * 1000:.0f} ms이지만 미리 띄워 둔 Pod 비용을 냅니다. 기준선은 runc {s('cold.rc.p50')}, 메탈 Kata {s('cold.ktm.p50')}입니다. 측정기에서 이미 열린 샌드박스를 호출하는 왕복 시간이 EKS 약 1 ms, MicroVM {F['warm.lm.p50ms']:.1f} ms, V1 {F['warm.v1.p50ms']:.0f} ms, V2 {F['warm.v2.p50ms']:.0f} ms이므로, 0.1초 안쪽의 차이로 순위를 매기면 안 됩니다."))
    d.append(t("### Packaging and network mode on AgentCore", "### AgentCore의 패키징과 네트워크 모드"))
    rows = [["", t("Low rate", "저빈도"), t("p90", "p90"), t("1 per second", "초당 1건"), t("5 per second", "초당 5건"), t("100 at once", "동시 100개"), t("New runtime", "새 런타임"), t("Deploy", "배포")]]
    def pk(label, c, b, fresh, dep):
        rows.append([label, s(f"cold.{c}.p50"), s(f"cold.{c}.p90"), s(f"sus.{c}.1.p50"), s(f"sus.{c}.5.p50"), s(f"burst.{b}.100.p50"), s(fresh, 1), f"{F[dep]:.0f} s"])
    pk(t("V1 container 276 MB", "V1 컨테이너 276 MB"), "v1np", "v1np", "fresh.V1.base.first", "deploy.v1")
    rows.append([t("V1 container 1.5 GB", "V1 컨테이너 1.5 GB"), s("cold.v1.large.p50"), s("cold.v1.large.p90"), s("sus.v1large.1.p50"), s("sus.v1large.5.p50"), s("burst.v1large.100.p50"), s("fresh.V1.large.first", 1), f"{F['deploy.v1large']:.0f} s"])
    pk(t("V1 direct code", "V1 코드 직접 배포"), "v1zip", "v1zip", "fresh.V1.zip.first", "deploy.v1zip")
    pk(t("V1 container 49 MB, no SDK", "V1 컨테이너 49 MB, SDK 없음"), "v1tiny", "v1tiny", "fresh.V1.tiny.first", "deploy.v1tiny")
    rows.append([t("V1 VPC mode", "V1 VPC 모드"), s("cold.v1vpc.p50"), s("cold.v1vpc.p90"), s("sus.v1vpc.1.p50"), s("sus.v1vpc.5.p50"), s("burst.v1vpc.100.p50"), "n/t", f"{F['deploy.v1vpc']:.0f} s"])
    rows.append([t("V2 container 276 MB", "V2 컨테이너 276 MB"), s("cold.v2np.p50"), s("cold.v2np.p90"), s("sus.v2.1.p50"), s("sus.v2.5.p50"), s("burst.v2.100.p50"), s("fresh.V2.base.first", 1), f"{F['deploy.v2']:.0f} s"])
    pk(t("V2 direct code", "V2 코드 직접 배포"), "v2zip", "v2zip", "fresh.V2.zip.first", "deploy.v2zip")
    rows.append([t("V2 VPC mode", "V2 VPC 모드"), s("cold.v2vpc.p50"), s("cold.v2vpc.p90"), s("sus.v2vpc.1.p50"), s("sus.v2vpc.5.p50"), s("burst.v2vpc.100.p50"), "n/t", f"{F['deploy.v2vpc']:.0f} s"])
    d.append(table(rows))
    d.append(t("The docs conflict on the direct code limit (1.6 and 25 sessions per second). New runtime values are the p50 of the first call on 3 separate runtimes. The 1.5 GB row, the new runtime cells of the 276 MB rows and the 276 MB V2 sustained and burst values use the earlier /ping. Failures left out of these p50s: V2 VPC 1 of 30 at low rate (throttled, not retried in this test), V2 2 of 600 at 5 per second (a 504 and an internal error), V1 1 of 1,200 at 10 per second.", "코드 직접 배포의 한도는 문서마다 초당 1.6건과 25건으로 다르게 나옵니다. 새 런타임 값은 런타임 3개에서 첫 호출의 p50입니다. 1.5 GB 행, 276 MB 행의 새 런타임 칸, 276 MB V2의 지속 유입과 버스트 값은 이전 /ping 이미지로 측정했습니다. 이 p50에서 제외한 실패는 저빈도 V2 VPC 30회 중 1건(스로틀, 이 실험은 재시도하지 않음), 초당 5건 V2 600회 중 2건(504와 내부 오류), 초당 10건 V1 1,200회 중 1건입니다."))
    d.append(t("The same agent task in VPC and public mode, shuffled in one period, 12 runs each:", "같은 에이전트 태스크를 VPC 모드와 퍼블릭 모드에서 같은 시간대에 순서를 섞어 각 12회 실행했습니다."))
    nw = lambda k: [sc(NW[k]['first']['p50']), sc(NW[k]['whole']['p50']), f"{NW[k]['whole']['ci'][0]:.1f} to {NW[k]['whole']['ci'][1]:.1f} s"]
    d.append(table([["", t("First message", "첫 메시지"), t("Whole request", "전체 시간"), t("95% CI of p50", "p50 95% CI")], [t("V1 VPC mode", "V1 VPC 모드")] + nw("v1_vpc"), [t("V1 public", "V1 퍼블릭")] + nw("v1_public"), [t("V2 VPC mode", "V2 VPC 모드")] + nw("v2_vpc"), [t("V2 public", "V2 퍼블릭")] + nw("v2_public")]))
    d.append(t("The intervals overlap within each version, so VPC mode did not change agent time. V2 is slower than V1 here because of the first read described below.", "버전별로 신뢰 구간이 겹치므로, VPC 모드는 에이전트 시간에 영향을 주지 않았습니다. 여기서 V2가 V1보다 느린 것은 아래에서 설명하는 첫 읽기 때문입니다."))
    d.append(t("### Bursts and sustained arrivals", "### 버스트와 지속 유입"))
    rows = [[""] + P]
    for n in ("10", "50", "100"):
        rows.append([t(f"Burst of {n}", f"동시 {n}개")] + [s(f"burst.{k}.{n}.p50") if f"burst.{k}.{n}.p50" in F else t("removed", "제거") for k in K])
    for r in ("1", "5"):
        rows.append([t(f"Sustained {r}/s", f"초당 {r}건")] + [s(f"sus.{k}.{r}.p50") for k in K])
    d.append(table(rows))
    d.append(t(f"Bursts are the median of 3 rounds from a dedicated 8 vCPU driver, with 4 gVisor nodes and 8 Kata nodes holding the image, so node scale-up is not included. A new node adds about {F['scale.gv.total']:.0f} s for gVisor and {F['scale.kt.total']:.0f} s for Kata. MicroVM above its default RunMicrovm quota of 5 per second was removed because the quota, not the platform, set the value; the quota is adjustable and was not raised. V1 is the 276 MB container with the earlier /ping. Warm pools with prepared pools: gVisor {s('burst.gvw.50.p50')} for 50, Kata {s('burst.ktw.40.p50')} for 40, one round. EKS completion is polled, which can add up to 0.5 s at 100. gVisor's p50 grows with size ({s('burst.gv.10.p50')} at 10, {s('burst.gv.100.p50')} at 100). One request of a burst of 50 failed in the final rounds on V1 with the documented /ping (a 504), a runtime not shown in this table.", f"버스트는 전용 8 vCPU 측정기로 3라운드 측정한 중앙값입니다. gVisor 4노드, Kata 8노드에 이미지를 미리 받아 둔 상태라 노드 증설 시간은 들어 있지 않습니다. 새 노드가 필요하면 gVisor는 약 {F['scale.gv.total']:.0f}초, Kata는 약 {F['scale.kt.total']:.0f}초가 더 걸립니다. MicroVM은 기본 RunMicrovm 쿼터(초당 5건)를 넘는 구간에서 플랫폼이 아니라 쿼터가 결과를 정하므로 제외했습니다. 쿼터는 조정할 수 있지만 올리지 않았습니다. V1은 이전 /ping을 쓰는 276 MB 컨테이너입니다. Warm Pool은 gVisor 50개 {s('burst.gvw.50.p50')}, Kata 40개 {s('burst.ktw.40.p50')}이며 1라운드만 측정했습니다. EKS는 완료를 폴링으로 확인하므로 100개에서 최대 0.5초가 더해질 수 있습니다. gVisor p50은 규모에 따라 늘어납니다(10개 {s('burst.gv.10.p50')}, 100개 {s('burst.gv.100.p50')}). 최종 라운드에서는 /ping을 문서대로 고친 V1 런타임(이 표에는 없음)에서 동시 50개 중 1건이 실패했습니다(504)."))
    d.append(t("### One real task through the Claude Agent SDK", "### Claude Agent SDK로 실제 태스크 실행"))
    ag = lambda v: [f"{v['first_p50']:.1f} s", f"{v['first_p90']:.1f} s", f"{v['slow_share'] * 100:.0f}%", f"{v['total_p50']:.1f} s", f"{v['total_p90']:.1f} s", f"{v['total_ci'][0]:.1f} to {v['total_ci'][1]:.1f} s", f"{v['n']}/{v['tried']}"]
    head = ["", t("First message", "첫 메시지"), "p90", t("Over 20 s", "20초 초과"), t("Whole request", "전체 시간"), "p90", t("95% CI of p50", "p50 95% CI"), t("Succeeded", "성공")]
    d.append(table([head] + [[n] + ag(H[k]) for n, k in (("gVisor x86", "gv"), ("gVisor Graviton3", "g3gv"), (t("Kata nested", "Kata 중첩"), "kt"), ("AgentCore V1", "v1"), (t("AgentCore V2, new runtimes", "AgentCore V2, 새 런타임"), "v2"), (t("MicroVMs, new images", "MicroVM, 새 이미지"), "lm"))]))
    d.append(t(f"This table is one same-period shuffled test: two new managed runtimes per option, 10 runs each, so each option gets the same arrival pattern. It is the small coding task and the time includes the harness's final pytest. Model time p50 ranged from {MT[0]:.1f} to {MT[1]:.1f} s across rounds, about 1 s higher on some V2 and MicroVM rounds, and no run failed. EKS is x86, with Graviton3 as a CPU control. EKS nodes keep a warm page cache and managed sandboxes do not, which is part of the difference.", f"이 표는 같은 시간대에 순서를 섞어 진행한 한 번의 실험입니다. 구성마다 새 관리형 런타임 2개에서 각 10회씩 실행해 요청 패턴을 맞췄습니다. 작은 코딩 태스크이며, 시간에는 하네스가 마지막에 돌리는 pytest가 들어 있습니다. 모델 시간 p50은 라운드별로 {MT[0]:.1f}~{MT[1]:.1f}초였고, 일부 V2, MicroVM 라운드에서 약 1초 높았습니다. 실패한 실행은 없었습니다. EKS는 x86이며, Graviton3는 CPU 차이를 보기 위한 대조군입니다. EKS 노드는 페이지 캐시가 채워져 있고 관리형 샌드박스는 그렇지 않다는 점도 차이의 일부입니다."))
    d.append(t("#### Another agent SDK: Strands Agents", "#### 다른 에이전트 SDK: Strands Agents"))
    d.append(t("Same task on every option, 20 runs each on managed (2 runtimes) and 10 on EKS, shuffled in one period. Ready is SDK import plus the time to the first model stream event, since the two SDKs report different first objects.", "모든 구성에서 같은 태스크를 같은 시간대에 순서를 섞어 실행했습니다. 관리형은 런타임 2개로 20회, EKS는 10회입니다. 두 SDK가 처음 돌려주는 객체가 서로 달라서, 여기서는 SDK import 시간과 첫 모델 스트림 이벤트까지의 시간을 더해 준비 시간으로 봅니다."))
    rows = [["", t("Claude Agent SDK, ready", "Claude Agent SDK 준비"), "p90", t("Strands, ready", "Strands 준비"), "p90", t("Claude, whole request", "Claude 전체 시간"), t("Strands, whole request", "Strands 전체 시간")]]
    for n, k in (("gVisor", "gv"), ("Kata", "kt"), ("AgentCore V1", "v1"), ("AgentCore V2", "v2"), ("Lambda MicroVMs", "lm")):
        c_, s_ = SD[f"{k}|c"], SD[f"{k}|s"]
        rows.append([n, sc(c_['ready']['p50']), sc(c_['ready']['p90']), sc(s_['ready']['p50']), sc(s_['ready']['p90']), sc(c_['whole']['p50']), sc(s_['whole']['p50'])])
    d.append(table(rows))
    d.append(t(f"All {FU['sdk_runs']} runs succeeded. The Strands app is ours, with 3 tools, and its install is far smaller than the Claude Agent SDK's bundled CLI. On V2 and MicroVM the gap is the first read; elsewhere the two differ by about 2 s.", f"{FU['sdk_runs']}회 모두 성공했습니다. Strands 앱은 도구 3개로 직접 만들었고, 설치 크기가 Claude Agent SDK에 포함된 CLI보다 훨씬 작습니다. V2와 MicroVM에서 생기는 큰 차이는 첫 읽기 때문이며, 다른 구성에서는 두 SDK의 차이가 약 2초입니다."))
    d.append(t("#### First read by file size", "#### 파일 크기별 첫 읽기"))
    rows = [[t("File", "파일"), "V1", "V2", "V2 p90", "MicroVM", "MicroVM p90"]]
    for mb in (10, 50, 100, 200):
        rows.append([f"{mb} MB", sc(SZ[f'v1|{mb}']['p50'], 2), sc(SZ[f'v2|{mb}']['p50']), sc(SZ[f'v2|{mb}']['p90']), sc(SZ[f'lm|{mb}']['p50']), sc(SZ[f'lm|{mb}']['p90'])])
    d.append(table(rows))
    d.append(t("8 new sessions per cell, one file of random bytes in the image, read once in a Strands app. The second read was under 0.1 s everywhere. Small files are fast; the wait grows with size and varies a lot between sessions.", "칸마다 새 세션에서 8회 측정했습니다. 이미지에 넣어 둔 무작위 바이트 파일 하나를 Strands 앱에서 한 번 읽었습니다. 두 번째 읽기는 모든 구성에서 0.1초 미만이었습니다. 작은 파일은 빠르지만, 파일이 커질수록 지연이 늘고 세션마다 편차도 커집니다."))
    d.append(t(f"V1 direct code had no such delay (first message {FA['ac-v1-zip|pkg']['first_p50']:.1f} s, whole request {FA['ac-v1-zip|pkg']['total_p50']:.1f} s). V2 direct code did ({FA['ac-v2-zip|pkg']['first_p50']:.1f} s, {FA['ac-v2-zip|pkg']['total_p50']:.1f} s). Dropping the page cache on EKS nodes shows the same effect at smaller scale: gVisor {F['fair']['dropcache']['eks-x86-gvisor']['first_p50']:.1f} s first message, Kata {F['fair']['dropcache']['eks-x86-kata']['first_p50']:.1f} s. Whole request then becomes gVisor {F['fair']['dropcache']['eks-x86-gvisor']['total_p50']:.1f} s and Kata {F['fair']['dropcache']['eks-x86-kata']['total_p50']:.1f} s. So EKS's advantage here partly reflects a local disk and a warm page cache.", f"V1 코드 직접 배포에는 이 지연이 없었지만(첫 메시지 {FA['ac-v1-zip|pkg']['first_p50']:.1f}초, 전체 시간 {FA['ac-v1-zip|pkg']['total_p50']:.1f}초), V2 코드 직접 배포에는 있었습니다({FA['ac-v2-zip|pkg']['first_p50']:.1f}초, {FA['ac-v2-zip|pkg']['total_p50']:.1f}초). EKS 노드의 페이지 캐시를 비우면 같은 현상이 작게 나타납니다. 첫 메시지는 gVisor {F['fair']['dropcache']['eks-x86-gvisor']['first_p50']:.1f}초, Kata {F['fair']['dropcache']['eks-x86-kata']['first_p50']:.1f}초, 전체 시간은 gVisor {F['fair']['dropcache']['eks-x86-gvisor']['total_p50']:.1f}초, Kata {F['fair']['dropcache']['eks-x86-kata']['total_p50']:.1f}초가 됩니다. 즉 이 실험에서 EKS가 유리한 이유 중 일부는 로컬 디스크와 페이지 캐시입니다."))
    d.append(t("#### Mitigations (first message, whole request)", "#### 완화책 (첫 메시지, 전체 시간)"))
    d.append(t(f"All arms ran in one period: 2 runtimes per arm, 8 probes each, 16 minutes apart, so each probe lands on a session that the arm itself has not touched for a while. Billed usage comes from USAGE_LOGS over the {FU['mitigation_span_h']:.1f} hours.", f"모든 조건을 같은 시간대에 실행했습니다. 조건마다 런타임 2개에 각각 8회씩 16분 간격으로 프로브를 보내, 매번 한동안 쓰이지 않은 세션에서 측정되도록 했습니다. 과금 사용량은 그 {FU['mitigation_span_h']:.1f}시간 동안의 USAGE_LOGS입니다."))
    mf = lambda k: [f"{sc(M[k]['first']['p50'])} (p90 {M[k]['first']['p90']:.1f})", f"{M[k]['first']['over20']}/{M[k]['first']['n']}", sc(M[k]['whole']['p50'])]
    rows = [[t("Mitigation", "완화책"), t("V2 first message", "V2 첫 메시지"), t("Over 20 s", "20초 초과"), t("Whole request", "전체 시간"), t("MicroVM first message", "MicroVM 첫 메시지"), t("Over 20 s", "20초 초과"), t("Whole request", "전체 시간")]]
    for label, v, l in ((t("None", "조치 없음"), "v2_none", "lm_none"), (t("Map the CLI file before the snapshot", "스냅샷 전에 CLI 파일 매핑"), "v2_map", "lm_map"), (t("Fetch the CLI from S3 at session start", "세션 시작 시 S3에서 CLI 받기"), "v2_s3", "lm_s3"), (t("Warm-up call every 5 minutes", "5분마다 예열 호출"), "v2_w5k1", None), (t("4 warm-up calls every 10 minutes", "10분마다 예열 호출 4개"), "v2_w10k4", None), (t("Run the CLI before the snapshot", "스냅샷 전에 CLI 실행"), "v2_pre", None)):
        rows.append([label] + mf(v) + (mf(l) if l else ["n/t", "", ""]))
    d.append(table(rows))
    U = lambda k: M[k]["usage"]
    d.append(t(f"Mapping and S3 did not raise billed memory: per probe session mapping used {U('v2_map')['gb_hours_per_probe_session'] * 1000:.0f} MB-h and S3 {U('v2_s3')['gb_hours_per_probe_session'] * 1000:.0f} MB-h against {U('v2_none')['gb_hours_per_probe_session'] * 1000:.0f} MB-h with none, because the sessions end sooner. Warm-up calls added about ${U('v2_w5k1')['extra_usd_per_h']:.4f} an hour per runtime at 5 minutes and ${U('v2_w10k4')['extra_usd_per_h']:.4f} with 4 every 10 minutes. Running the CLI before the snapshot was slower than none here, and one of its 16 runs timed out in SDK start-up; earlier rounds gave mixed results, so we do not recommend it. The CLI version differs by arm, so its size ranges from 292 to 337 MB.", f"매핑과 S3 받기는 과금 메모리를 늘리지 않았습니다. 세션이 빨리 끝나서 프로브 세션당 과금 메모리가 매핑 {U('v2_map')['gb_hours_per_probe_session'] * 1000:.0f} MB-h, S3 {U('v2_s3')['gb_hours_per_probe_session'] * 1000:.0f} MB-h로, 조치 없음({U('v2_none')['gb_hours_per_probe_session'] * 1000:.0f} MB-h)보다 오히려 적었습니다. 예열 호출은 런타임 하나당 시간당 약 ${U('v2_w5k1')['extra_usd_per_h']:.4f}(5분 간격), ${U('v2_w10k4')['extra_usd_per_h']:.4f}(10분 간격 4개)가 더 들었습니다. 스냅샷 전 CLI 실행은 이번에는 조치 없음보다 느렸고, 16회 중 1회는 SDK 시작 시간 초과로 실패했습니다. 이전 라운드에서도 결과가 엇갈려 권장하지 않습니다. 조건마다 CLI 버전이 달라 크기는 292~337 MB입니다."))
    d.append(t("Warming only helps the runtime it calls. One 331 MB file, read once per probe, 8 probes 16 minutes apart per runtime:", "예열은 호출한 런타임에만 효과가 있습니다. 331 MB 파일 하나를 프로브마다 한 번씩 읽었고, 런타임마다 16분 간격으로 8회 측정했습니다."))
    rows = [[t("Runtime", "런타임"), t("First read", "첫 읽기"), "p90", t("95% CI of p50", "p50 95% CI"), t("Over 20 s", "20초 초과")]]
    for label, k in ((t("Warmed every 5 minutes", "5분마다 예열한 런타임"), "warmed"), (t("Same image as a warmed runtime", "예열한 런타임과 같은 이미지를 쓰는 런타임"), "same_image"), (t("Same bytes in a different image layer", "같은 바이트를 다른 이미지 레이어에 둔 런타임"), "same_bytes"), (t("Its own image, not warmed", "자기 이미지만 쓰고 예열하지 않은 런타임"), "alone"), (t("Untouched until the last slot", "마지막 측정까지 한 번도 쓰지 않은 런타임"), "untouched")):
        v = IS[k]
        rows.append([label, sc(v['p50']), sc(v['p90']), f"{v['ci'][0]:.1f} to {v['ci'][1]:.1f} s", f"{v['over20']}/{v['n']}"])
    d.append(table(rows))
    d.append(t("Two runtimes per row, except the untouched row with 4 runtimes probed once. The runtimes next to a warmed one gained nothing over a runtime of its own.", "행마다 런타임 2개이며, 마지막 행만 런타임 4개를 한 번씩 측정했습니다. 예열한 런타임과 같은 이미지나 같은 바이트를 써도, 예열하지 않은 런타임보다 빨라지지 않았습니다."))
    d.append(t("#### Session storage", "#### 세션 스토리지"))
    rows = [[t("Where the CLI comes from (V2)", "CLI 위치 (V2)"), t("Fetch", "받기"), t("First message", "첫 메시지"), "p90", t("Whole request", "전체 시간")]]
    for label, k in ((t("In the image", "이미지 안"), "image|run"), (t("S3 to /tmp at session start", "세션 시작 시 S3에서 /tmp로 받기"), "tmp|fetch"), (t("S3 to session storage at session start", "세션 시작 시 S3에서 세션 스토리지로 받기"), "store|fetch"), (t("Already in session storage, after a restart", "세션 스토리지에 이미 있음(재시작 후)"), "store|resume")):
        v = ST[k]
        rows.append([label, sc(v['fetch']['p50']) if 'fetch' in v else "", sc(v['first']['p50']), sc(v['first']['p90']), sc(v['whole']['p50'])])
    d.append(table(rows))
    d.append(t(f"8 runs per row. In a separate test the session was stopped and restarted with the same id {SCY['cycles']} times: /tmp was empty each time ({SCY['new_vm']} of {SCY['cycles']}) and the 331 MB file in session storage was there each time ({SCY['file_kept']} of {SCY['cycles']}), read back in {SCY['first_read']['p50']:.2f} s, and {SCY['after_drop']['p50']:.2f} s after dropping the page cache. Session storage is in preview.", f"행마다 8회입니다. 별도 실험에서 같은 세션 ID로 세션을 {SCY['cycles']}회 중지했다가 다시 시작했습니다. /tmp는 매번 비어 있었고({SCY['cycles']}회 중 {SCY['new_vm']}회), 세션 스토리지에 둔 331 MB 파일은 매번 남아 있었습니다({SCY['cycles']}회 중 {SCY['file_kept']}회). 이 파일을 다시 읽는 데 {SCY['first_read']['p50']:.2f}초, 페이지 캐시를 비운 뒤에도 {SCY['after_drop']['p50']:.2f}초가 걸렸습니다. 세션 스토리지는 프리뷰 기능입니다."))
    d.append(t("#### Agents at the same time (whole request)", "#### 에이전트 동시 실행 (전체 시간)"))
    rows = [["", t("5 at once", "동시 5개"), t("20 at once", "동시 20개"), t("20 at once, p90", "동시 20개 p90"), t("First message at 20", "동시 20개 첫 메시지")]]
    for n, k in ((t("gVisor, 4 nodes", "gVisor, 4노드"), "gvisor"), (t("Kata, 8 nodes", "Kata, 8노드"), "kata"), ("AgentCore V1", "v1"), ("AgentCore V2", "v2"), ("Lambda MicroVMs", "lm")):
        rows.append([n, sc(CN[f"{k}|5"]['whole']['p50']), sc(CN[f"{k}|20"]['whole']['p50']), sc(CN[f"{k}|20"]['whole']['p90']), sc(CN[f"{k}|20"]['first']['p50'])])
    d.append(table(rows))
    d.append(t(f"Shuffled in one period, 4 batches per size, {sum(v['runs'] for v in CN.values())} runs, no failure and every pytest passed. Going from 5 to 20 at once did not slow any option by more than about 1.5 s. Managed runtimes had already run agents, so these are not new-runtime values.", f"같은 시간대에 순서를 섞어 규모마다 4배치씩, 모두 {sum(v['runs'] for v in CN.values())}회 실행했습니다. 실패는 없었고 pytest도 모두 통과했습니다. 동시 5개에서 20개로 늘려도 어느 구성이든 약 1.5초 넘게 느려지지 않았습니다. 관리형 런타임은 이미 에이전트를 실행한 상태였으므로 새 런타임 값은 아닙니다."))
    d.append(t(f"#### Build task (whole request, {BD['v1']['whole']['n']} runs)", f"#### 빌드 태스크 (전체 시간, {BD['v1']['whole']['n']}회)"))
    rows = [["", t("Whole request", "전체 시간"), "p90", t("95% CI of p50", "p50 95% CI"), t("After the first message", "첫 메시지 이후"), t("95% CI", "95% CI")]]
    for n, k in (("gVisor x86", "gvisor"), ("AgentCore V1", "v1"), ("gVisor Graviton3", "gvisor_g3"), ("Lambda MicroVMs", "lm"), (t("Kata nested", "Kata 중첩"), "kata"), ("AgentCore V2", "v2")):
        v = BD[k]
        rows.append([n, sc(v['whole']['p50']), sc(v['whole']['p90']), f"{v['whole']['ci'][0]:.1f} to {v['whole']['ci'][1]:.1f} s", sc(v['after_first']['p50']), f"{v['after_first']['ci'][0]:.1f} to {v['after_first']['ci'][1]:.1f} s"])
    d.append(table(rows))
    d.append(t(f"Shuffled in one period on runtimes that had not run the task before. After the first message is the agent's time minus its first message, so the first read of the CLI is out of it. Model time p50 was {min(v['model'] for v in BD.values()):.1f} to {max(v['model'] for v in BD.values()):.1f} s on every option. gVisor and V1 overlap. V2 stays slowest even after the first message. MicroVM sees 8 vCPU with a 2 vCPU billed baseline, gVisor's root filesystem is memory-backed here, and managed CPU generations vary by session, so this is not isolation cost alone. Kata on metal was measured separately and was faster than nested Kata.", f"태스크를 처음 실행하는 런타임에서 같은 시간대에 순서를 섞어 측정했습니다. 첫 메시지 이후는 에이전트 시간에서 첫 메시지를 뺀 값이라 CLI 첫 읽기가 빠집니다. 모델 시간 p50은 모든 구성에서 {min(v['model'] for v in BD.values()):.1f}~{max(v['model'] for v in BD.values()):.1f}초였습니다. gVisor와 V1은 신뢰 구간이 겹칩니다. V2는 첫 메시지 이후만 비교해도 가장 느립니다. MicroVM은 과금 기준이 2 vCPU인데 8 vCPU가 보이고, gVisor는 이 실험에서 루트 파일시스템이 메모리 기반이며, 관리형은 세션마다 CPU 세대가 달라서 격리 방식만의 차이는 아닙니다. 메탈 Kata는 따로 측정했고 중첩 Kata보다 빨랐습니다."))
    d.append(t("### Workloads and syscalls", "### 워크로드와 시스템 콜"))
    d.append(t("Compare within one CPU. x86 runs on m8i.2xlarge. Managed values are Graviton3 sessions only. Times in seconds, lower is better.", "같은 CPU끼리만 비교하세요. x86은 m8i.2xlarge입니다. 관리형은 Graviton3 세션만 집계했습니다. 단위는 초이며 낮을수록 좋습니다."))
    cols = [("rc", "runc x86"), ("gv", "gVisor x86"), ("kt", t("Kata nested", "Kata 중첩")), ("ktm", t("Kata metal", "Kata 메탈")), ("g3rc", "runc G3"), ("g3gv", "gVisor G3")]
    def bc(k, op):
        v = F.get(f"bycpu.{k}.Graviton3.{op}")
        return v
    head = [""] + [c[1] for c in cols] + ["V1 G3", "V2 G3", "MicroVM G3"]
    rows = [head]
    for op, label in (("compile_stdlib", t("Compile stdlib", "표준 라이브러리 컴파일")), ("pytest_project", t("pytest, 70 tests", "pytest 70개")), ("files_small", t("2,000 small files", "작은 파일 2,000개")), ("mem_touch", t("Touch 1 GB", "1 GB 접근")), ("cpu_python", t("Pure Python", "순수 Python"))):
        rows.append([label] + [f"{F[f'suite.{k}.{op}.seconds']:.2f}" for k, _ in cols] + [f"{bc(k, op):.2f}" if bc(k, op) else "n/t" for k in ("v1", "v2", "lm")])
    for fld, label, div in (("getppid_ns", "getppid (ns)", 1), ("open_close_ns", "open+close (µs)", 1000), ("fork_exec_ns", "fork+exec (µs)", 1000)):
        rows.append([label] + [f"{F[f'sys.{k}.{fld}'] / div:,.1f}" for k, _ in cols] + [f"{bc(k, fld) / div:,.1f}" if bc(k, fld) else "n/t" for k in ("v1", "v2", "lm")])
    d.append(table(rows))
    d.append(t(f"gVisor's fast disk numbers are not comparable: its root filesystem is a memory-backed overlay here ({F['suite.gv.disk_seq.write_MBps']:,.0f} MB/s write with fsync). arm64 gVisor was also slower on pure Python ({F['suite.g3gv.cpu_python.seconds'] / F['suite.g3rc.cpu_python.seconds']:.1f}x runc on Graviton3), which x86 did not show.", f"gVisor의 디스크 수치는 다른 구성과 비교할 수 없습니다. 이 구성에서는 루트 파일시스템이 메모리 기반 오버레이이기 때문입니다(fsync 쓰기 {F['suite.gv.disk_seq.write_MBps']:,.0f} MB/s). arm64 gVisor는 순수 Python에서도 느렸지만(Graviton3에서 runc의 {F['suite.g3gv.cpu_python.seconds'] / F['suite.g3rc.cpu_python.seconds']:.1f}배), x86에서는 그렇지 않았습니다."))
    d.append(t("### Reclamation and lifecycle", "### 회수와 수명 주기"))
    i1, i2 = F["idle.v1np"], F["idle.v2np"]
    d.append(table([
        ["", t("Observed", "결과")],
        [t("V2 with 60 s idle timeout", "V2, 유휴 타임아웃 60초"), t(f"Alive at 60 s ({i2['60']['alive']}/{i2['60']['n']}), gone at 70 s ({i2['70']['alive']}/{i2['70']['n']} alive)", f"60초에 {i2['60']['alive']}/{i2['60']['n']} 생존, 70초에 {i2['70']['alive']}/{i2['70']['n']} 생존")],
        [t("V1 with 60 s idle timeout", "V1, 유휴 타임아웃 60초"), t(f"Alive at 60 s ({i1['60']['alive']}/{i1['60']['n']}), {i1['70']['alive']}/{i1['70']['n']} alive at 70 s, gone at 90 s ({i1['90']['alive']}/{i1['90']['n']} alive)", f"60초에 {i1['60']['alive']}/{i1['60']['n']}, 70초에 {i1['70']['alive']}/{i1['70']['n']}, 90초에 {i1['90']['alive']}/{i1['90']['n']} 생존")],
        [t("AgentCore explicit stop, same session id", "AgentCore 명시적 중지 후 같은 세션 ID로 호출"), t("New instance, memory and disk gone, 5/5 on V1 and V2", "새 인스턴스로 시작해 메모리와 디스크가 비어 있음. V1, V2 모두 5/5")],
        [t("MicroVM idle policy 60 s, then suspended 120 s", "MicroVM 유휴 정책 60초, 일시 중지 120초"), t(f"SUSPENDED after {F['mvidle.suspend_p50']:.0f} s, TERMINATED after {F['mvidle.term_p50']:.0f} s", f"{F['mvidle.suspend_p50']:.0f}초 후 SUSPENDED, {F['mvidle.term_p50']:.0f}초 후 TERMINATED")],
        [t("MicroVM resume", "MicroVM 재개"), t(f"API {s('susp.0MB.api.resume_p50')}, traffic {s('susp.0MB.traffic.resume_p50', 1)}. Memory and disk kept in every run, up to 2 GB held", f"API {s('susp.0MB.api.resume_p50')}, 트래픽 {s('susp.0MB.traffic.resume_p50', 1)}. 2 GB까지 모든 실행에서 메모리와 디스크 유지")],
        [t("EKS sandbox delete to pod gone", "EKS 샌드박스 삭제부터 Pod 제거까지"), f"gVisor {s('gone.gv.p50', 1)}, Kata {s('gone.kt.p50', 1)}"],
        [t("EKS new node to first sandbox, then node removal", "EKS 새 노드의 첫 샌드박스까지, 노드 제거까지"), t(f"gVisor {F['scale.gv.total']:.0f} s and {F['scale.gv.removed']:.0f} s. Kata {F['scale.kt.total']:.0f} s including {F['scale.kt.install']:.0f} s kata-deploy, and {F['scale.kt.removed']:.0f} s. Managed node group; Karpenter below", f"gVisor {F['scale.gv.total']:.0f}초, {F['scale.gv.removed']:.0f}초. Kata {F['scale.kt.total']:.0f}초(kata-deploy {F['scale.kt.install']:.0f}초 포함), {F['scale.kt.removed']:.0f}초. 관리형 노드 그룹 기준이며 Karpenter는 아래 절 참고")],
    ]))
    d.append(t(f"Deploy times for comparison: EKS cluster and nodes about 19 minutes by one Terraform apply, not counting runtime install; MicroVM image about {F['deploy.lm']:.0f} s; AgentCore in the packaging table.", f"참고로 배포 시간은 EKS 클러스터와 노드가 Terraform 적용 한 번에 약 19분(런타임 설치 제외), MicroVM 이미지가 약 {F['deploy.lm']:.0f}초입니다. AgentCore는 패키징 표를 보세요."))
    d.append(t("### EKS nodes from zero with Karpenter", "### Karpenter로 EKS 노드를 0개부터 늘리기"))
    rows = [[t("gVisor sandboxes at once", "gVisor 샌드박스 수"), t("First ready (p50 of 5)", "첫 준비 (5회 p50)"), t("Pod p50", "Pod p50"), t("All ready", "모두 준비"), t("Node Ready", "노드 Ready")]]
    for n in ("1", "20", "50"):
        rows.append([n, sc(KP[n]['p50']), sc(KP[n]['p50']), sc(KP[n]['all_ready']), sc(KP[n]['node_ready'])])
    rows = [[r[0], r[2], r[3], r[4]] for r in rows]
    d.append(table(rows))
    d.append(t(f"Karpenter 1.15 with an m8i NodePool, from no nodes, 5 runs per size. A new node is Ready in about {KP['1']['node_ready']:.0f} s and the rest is image pull and pod start. Kata on a new Karpenter node took {min(KK['usable']):.0f} to {max(KK['usable']):.0f} s until a pod could run, of which kata-deploy took {min(KK['helm']):.0f} to {max(KK['helm']):.0f} s, so Kata nodes are better kept warm.", f"Karpenter 1.15와 m8i NodePool로, 노드가 하나도 없는 상태에서 규모마다 5회 측정했습니다. 새 노드는 약 {KP['1']['node_ready']:.0f}초에 Ready가 되고, 나머지는 이미지 받기와 Pod 시작 시간입니다. Kata는 Karpenter가 띄운 새 노드에서 Pod를 실행할 수 있을 때까지 {min(KK['usable']):.0f}~{max(KK['usable']):.0f}초가 걸렸고, 그중 kata-deploy가 {min(KK['helm']):.0f}~{max(KK['helm']):.0f}초였습니다. 그래서 Kata 노드는 미리 띄워 두는 편이 낫습니다."))
    kt = lambda k: [str(KT[k]['sessions']), str(KT[k]['lost']), sc(KT[k]['start']['p50'], 2), sc(KT[k]['start']['max']), f"{KT[k]['node_h']:.1f}", f"{KT[k]['node_h_per_pod_h']:.3f}"]
    d.append(table([["", t("Sessions", "세션"), t("Ended by consolidation", "통합으로 끊긴 세션"), t("Start p50", "시작 p50"), t("Start max", "시작 최대"), t("Node hours", "노드 시간"), t("Node hours per session hour", "세션 시간당 노드 시간")], [t("Default consolidation", "기본 통합 설정")] + kt("default"), ["do-not-disrupt"] + kt("keep")]))
    d.append(t(f"The same {KT['default']['hours'] * 60:.0f} minute trace of sessions that arrive, live a few minutes and end, run twice. In the default run Karpenter emptied nodes it judged underutilized twice, and those two disruptions account for every lost session. Marking session pods do-not-disrupt kept all of them, at the cost of slower scale-down. Most starts land on an existing node in about 1 s; the maximum is a new node.", f"세션이 들어와 몇 분 동안 실행되고 끝나는 같은 {KT['default']['hours'] * 60:.0f}분 트레이스를 두 번 실행했습니다. 기본 설정에서는 Karpenter가 사용률이 낮다고 판단한 노드를 두 번 비웠고, 끊긴 세션은 모두 이 두 번에서 나왔습니다. 세션 Pod에 do-not-disrupt를 붙이면 세션이 모두 유지되지만 축소가 느려집니다. 대부분의 세션은 기존 노드에서 약 1초 만에 시작했고, 최대값은 새 노드를 기다린 경우입니다."))
    d.append(t("### Tokyo (ap-northeast-1)", "### 도쿄 (ap-northeast-1)"))
    TB = TK["burst"]
    bb = lambda k: sc(TB[k + '|100']['min']) if round(TB[k + '|100']['min'], 1) == round(TB[k + '|100']['max'], 1) else f"{TB[k + '|100']['min']:.1f} to {TB[k + '|100']['max']:.1f} s"
    ta = TK["agent"]
    d.append(table([["", "gVisor", "Kata + QEMU", "AgentCore V1", "AgentCore V2"],
        [t("Low rate", "저빈도")] + [sc(TK['cold'][k]['p50'], 2) for k in ("gv", "kt", "v1", "v2")],
        [t("5 per second", "초당 5건")] + [sc(TK['sus5'][k]['p50'], 2) for k in ("gv", "kt", "v1", "v2")],
        [t("100 at once, 3 rounds", "동시 100개, 3라운드")] + [bb(k) for k in ("gv", "kt", "v1-b", "v2-b")],
        [t("Agent first message", "에이전트 첫 메시지")] + [sc(ta[k]['first']['p50']) for k in ("gv", "kt", "v1", "v2")],
        [t("First message p90", "첫 메시지 p90")] + [sc(ta[k]['first']['p90']) for k in ("gv", "kt", "v1", "v2")],
        [t("Agent whole request", "에이전트 전체 시간")] + [sc(ta[k]['whole']['p50']) for k in ("gv", "kt", "v1", "v2")]]))
    fr = TK["first_read"]
    d.append(t(f"Same images and method as us-east-1, driver in Tokyo. Every request succeeded. The order matches us-east-1: V1 fastest at low rate and slow at 5 per second, V2 flat under load but slow to its first message. The 331 MB CLI on new V2 sandboxes took {min(fr['v2']):.0f} to {max(fr['v2']):.0f} s to read the first time, on V1 under 0.1 s. MicroVMs and warm pools were not measured in Tokyo.", f"us-east-1과 같은 이미지와 방법을 썼고, 측정기는 도쿄에 두었습니다. 모든 요청이 성공했습니다. 구성 간 순위도 us-east-1과 같습니다. V1은 저빈도에서 가장 빠르지만 초당 5건에서는 느려지고, V2는 부하에는 흔들리지 않지만 첫 메시지가 늦습니다. 새 V2 샌드박스에서 331 MB CLI를 처음 읽는 데 {min(fr['v2']):.0f}~{max(fr['v2']):.0f}초가 걸렸고, V1은 0.1초 미만이었습니다. 도쿄에서는 MicroVM과 Warm Pool을 측정하지 않았습니다."))
    d.append(t("### EKS Fargate and Nitro Sandboxes (added 2026-11-10)", "### EKS Fargate와 Nitro Sandboxes (2026-11-10 추가)"))
    NX = FU["new"]
    fg, nt, na = NX["fg"], NX["nt"], NX["na"]
    d.append(t("Two more options, measured five days later with the same app and the same experiments. **EKS Fargate** runs each sandbox pod in its own Fargate microVM, through a Fargate profile on the main cluster. **Nitro Sandboxes** (announced 2026-11-09) run each pod in its own VM on the Nitro hypervisor with `runtimeClassName: isolated-sandbox`; they ran on a separate EKS Auto Mode cluster in the same VPC and subnets, on the same m8i.2xlarge type and zone as the x86 node groups, because Auto Mode ships the runtime and the main cluster already runs its own Karpenter. Both size the VM from the pod's requests, not its limits, so each has a small size (0.25 vCPU, 512 MiB, for echo, bursts and arrivals) and a 2 vCPU, 8 GB size that matches the other sandboxes' limit (agent, build, workloads). gVisor with V1, and gVisor with Kata, ran in the same period as anchors for Fargate and Nitro.",
                "다른 구성을 측정하고 닷새 뒤에 같은 앱과 같은 실험으로 두 가지를 더 측정했습니다. **EKS Fargate**는 기존 클러스터에 Fargate 프로필을 추가해 샌드박스 Pod마다 Fargate microVM을 따로 띄웁니다. **Nitro Sandboxes**(2026-11-09 발표)는 `runtimeClassName: isolated-sandbox`를 지정하면 Pod마다 Nitro 하이퍼바이저 위에 VM을 따로 띄웁니다. Auto Mode에 런타임이 들어 있고 기존 클러스터에는 이미 Karpenter가 있어서, 같은 VPC와 서브넷에 EKS Auto Mode 클러스터를 따로 만들고 x86 노드 그룹과 같은 m8i.2xlarge, 같은 가용 영역에서 측정했습니다. 두 구성 모두 Pod의 limits가 아니라 requests로 VM 크기를 정합니다. 그래서 작은 크기(0.25 vCPU, 512 MiB)로 echo, 버스트, 유입을 측정하고, 다른 샌드박스의 한도와 같은 2 vCPU, 8 GB 크기로 에이전트, 빌드, 워크로드를 측정했습니다. 기준선으로 Fargate는 gVisor, V1과, Nitro는 gVisor, Kata와 같은 시간대에 함께 측정했습니다."))
    ab = lambda b: [sc(b['cold']['p50'], 2), sc(b['first']['p50']), sc(b['whole']['p50']), f"{b['whole']['ci'][0]:.1f} to {b['whole']['ci'][1]:.1f} s"]
    cd_ = lambda c: [sc(c['p50'], 2), sc(c['p90'], 2)]
    rows = [["", t("Start p50", "시작 p50"), t("Start p90", "시작 p90"), t("Warm pool claim", "Warm Pool 할당"), t("Agent first message", "에이전트 첫 메시지"), t("Agent whole request", "에이전트 전체 시간"), t("Build whole request", "빌드 전체 시간"), t("Build, 95% CI of p50", "빌드 p50 95% CI")]]
    rows.append([t("Nitro period: gVisor", "Nitro 시간대: gVisor")] + cd_(na["cold"]["na-gv"]) + [sc(na["cold"]["na-wgv"]["p50"], 2), sc(na["agent"]["gvisor"]["first"]["p50"]), sc(na["agent"]["gvisor"]["whole"]["p50"]), sc(na["heavy"]["gvisor"]["whole"]["p50"]), f"{na['heavy']['gvisor']['whole']['ci'][0]:.1f} to {na['heavy']['gvisor']['whole']['ci'][1]:.1f} s"])
    rows.append([t("Nitro period: Kata", "Nitro 시간대: Kata")] + cd_(na["cold"]["na-kt"]) + [sc(na["cold"]["na-wkt"]["p50"], 2), sc(na["agent"]["kata"]["first"]["p50"]), sc(na["agent"]["kata"]["whole"]["p50"]), sc(na["heavy"]["kata"]["whole"]["p50"]), f"{na['heavy']['kata']['whole']['ci'][0]:.1f} to {na['heavy']['kata']['whole']['ci'][1]:.1f} s"])
    rows.append(["**Nitro Sandboxes**"] + cd_(nt["cold"]["nt-c"]) + [sc(nt["cold"]["nt-w"]["p50"], 2), sc(nt["agent"]["nitro"]["first"]["p50"]), sc(nt["agent"]["nitro"]["whole"]["p50"]), sc(nt["heavy"]["nitro"]["whole"]["p50"]), f"{nt['heavy']['nitro']['whole']['ci'][0]:.1f} to {nt['heavy']['nitro']['whole']['ci'][1]:.1f} s"])
    rows.append([t("Fargate period: gVisor", "Fargate 시간대: gVisor")] + cd_(fg["cold"]["fg-gv"]) + ["", sc(fg["agent"]["gvisor"]["first"]["p50"]), sc(fg["agent"]["gvisor"]["whole"]["p50"]), sc(fg["heavy"]["gvisor"]["whole"]["p50"]), f"{fg['heavy']['gvisor']['whole']['ci'][0]:.1f} to {fg['heavy']['gvisor']['whole']['ci'][1]:.1f} s"])
    rows.append([t("Fargate period: AgentCore V1", "Fargate 시간대: AgentCore V1")] + cd_(fg["cold"]["fg-v1"]) + ["", sc(fg["agent"]["v1"]["first"]["p50"]), sc(fg["agent"]["v1"]["whole"]["p50"]), sc(fg["heavy"]["v1"]["whole"]["p50"]), f"{fg['heavy']['v1']['whole']['ci'][0]:.1f} to {fg['heavy']['v1']['whole']['ci'][1]:.1f} s"])
    rows.append(["**EKS Fargate**"] + cd_(fg["cold"]["fg-fs"]) + [t("none", "없음"), sc(fg["agent"]["fargate"]["first"]["p50"]), sc(fg["agent"]["fargate"]["whole"]["p50"]), sc(fg["heavy"]["fargate"]["whole"]["p50"]), f"{fg['heavy']['fargate']['whole']['ci'][0]:.1f} to {fg['heavy']['fargate']['whole']['ci'][1]:.1f} s"])
    d.append(table(rows))
    nruns = sum(v["runs"] for blk in (fg["agent"], fg["heavy"], na["agent"], na["heavy"], nt["agent"], nt["heavy"]) for v in blk.values())
    nfail = sum(v["failed"] + v["pytest_failed"] for blk in (fg["agent"], fg["heavy"], na["agent"], na["heavy"], nt["agent"], nt["heavy"]) for v in blk.values())
    d.append(t(f"Start is 20 runs per option, shuffled; agent and build tasks are 12 runs per option ({nruns} runs, {nfail} failed or failed pytest). Fargate's start is the same at both sizes ({sc(fg['cold']['fg-fb']['p50'])} at 2 vCPU, 8 GB) because every pod gets a new microVM and pulls the image; image caching (SOCI) does not apply to EKS Fargate. Once started, Fargate runs the agent about as fast as the others: agent time after start {sc(fg['agent']['fargate']['agent'])}, gVisor {sc(fg['agent']['gvisor']['agent'])}. Nitro starts close to Kata and a warm pool claim takes the same time as gVisor's. Its first message is the slowest of its period, and its build sits between gVisor and Kata. Warm pools were not used in the agent rows.",
                f"시작은 구성마다 20회, 순서를 섞어 측정했습니다. 에이전트와 빌드 태스크는 구성마다 12회입니다(모두 {nruns}회, 실패나 pytest 실패 {nfail}회). Fargate는 Pod마다 새 microVM을 띄우고 이미지를 받으므로 크기와 관계없이 시작 시간이 같습니다(2 vCPU, 8 GB에서 {sc(fg['cold']['fg-fb']['p50'])}). EKS Fargate에는 이미지 캐시(SOCI)가 적용되지 않습니다. 시작한 뒤의 에이전트 실행은 다른 구성과 비슷합니다(시작을 뺀 에이전트 시간 {sc(fg['agent']['fargate']['agent'])}, gVisor {sc(fg['agent']['gvisor']['agent'])}). Nitro는 Kata와 비슷하게 시작하고, Warm Pool 할당은 gVisor와 같습니다. 첫 메시지는 같은 시간대 구성 중 가장 느리고, 빌드는 gVisor와 Kata 사이입니다. 에이전트 행에서는 Warm Pool을 쓰지 않았습니다."))
    fb, nb = fg["burst"]["fg-fs"], nt["burst"]["nt-c"]
    mid = lambda xs: sorted(xs)[len(xs) // 2]
    rows = [["", t("Burst of 10", "동시 10개"), t("Burst of 50", "동시 50개"), t("Burst of 100", "동시 100개"), t("1 per second", "초당 1건"), t("5 per second", "초당 5건"), t("5 per second, p90", "초당 5건 p90")]]
    rows.append([t("Nitro, nodes ready (rounds 2 and 3)", "Nitro, 노드 준비됨(2, 3라운드)")] + [f"{min(r['p50'] for r in nb[n][1:]):.1f} to {max(r['p50'] for r in nb[n][1:]):.1f} s" for n in ("10", "50", "100")] + [sc(nt["sustained"]["nt-c"]["1.0"]["p50"], 2), sc(nt["sustained"]["nt-c"]["5.0"]["p50"], 2), sc(nt["sustained"]["nt-c"]["5.0"]["p90"], 2)])
    rows.append([t("Nitro, round 1 with new nodes", "Nitro, 1라운드(새 노드 포함)")] + [sc(nb[n][0]["p50"]) for n in ("10", "50", "100")] + ["", "", ""])
    rows.append(["EKS Fargate"] + [sc(mid([r["p50"] for r in fb[n]])) for n in ("10", "50", "100")] + [sc(fg["sustained"]["fg-fs"]["1.0"]["p50"], 2), sc(fg["sustained"]["fg-fs"]["5.0"]["p50"], 2), sc(fg["sustained"]["fg-fs"]["5.0"]["p90"], 2)])
    rows.append([t("Earlier: gVisor, 4 nodes", "이전: gVisor, 4노드")] + [s(f"burst.gv.{n}.p50") for n in ("10", "50", "100")] + [s("sus.gv.1.p50"), s("sus.gv.5.p50"), "n/t"])
    rows.append([t("Earlier: Kata, 8 nodes", "이전: Kata, 8노드")] + [s(f"burst.kt.{n}.p50") for n in ("10", "50", "100")] + [s("sus.kt.1.p50"), s("sus.kt.5.p50"), "n/t"])
    d.append(table(rows))
    nbf = sum(r["failed"] for v in list(fb.values()) + list(nb.values()) for r in v)
    d.append(t(f"Three rounds each, {nbf} failed sandboxes. Fargate stays at about one minute whatever the size or rate, within its default launch quota (100 at once, 20 per second, doc). Nitro on nodes that were already up still queues: about 5 s for 10, 12 s for 50 and 24 s for 100 at once. Its first round waited for Auto Mode to add nodes. At 5 new sessions per second Nitro's p50 rose to {sc(nt['sustained']['nt-c']['5.0']['p50'])} with every sandbox deleted after its first reply, so the limit was start throughput, not capacity. The earlier gVisor and Kata rows ran in another period with more nodes held.",
                f"라운드마다 3회 측정했고 실패한 샌드박스는 {nbf}개입니다. Fargate는 기본 시작 쿼터(동시 100개, 초당 20건, 문서) 안에서는 규모와 유입 속도에 관계없이 약 1분입니다. Nitro는 노드가 이미 떠 있어도 대기열이 생겨 동시 10개 약 5초, 50개 약 12초, 100개 약 24초가 걸렸습니다. 1라운드는 Auto Mode가 노드를 추가하는 시간을 기다렸습니다. 초당 5건에서는 샌드박스를 첫 응답 뒤 바로 지웠는데도 Nitro p50이 {sc(nt['sustained']['nt-c']['5.0']['p50'])}로 늘었으므로, 용량이 아니라 시작 처리량이 한계였습니다. 이전 gVisor와 Kata 행은 노드를 더 많이 둔 다른 시간대의 값입니다."))
    S_ = lambda b, op, k="seconds": b[op][k]
    nsu, fsu = nt["suite"]["nt-b"], fg["suite"]["fg-fb"]
    rows = [["", "runc x86", "gVisor x86", t("Kata nested", "Kata 중첩"), "Nitro", "Fargate"]]
    for op, label in (("compile_stdlib", t("Compile stdlib (s)", "표준 라이브러리 컴파일(초)")), ("pytest_project", t("pytest, 70 tests (s)", "pytest 70개(초)")), ("files_small", t("2,000 small files (s)", "작은 파일 2,000개(초)")), ("cpu_python", t("Pure Python (s)", "순수 Python(초)"))):
        rows.append([label] + [f"{F[f'suite.{k}.{op}.seconds']:.2f}" for k in ("rc", "gv", "kt")] + [f"{S_(nsu, op):.2f}", f"{S_(fsu, op):.2f}"])
    for fld, label, div in (("getppid_ns", "getppid (ns)", 1), ("open_close_ns", "open+close (µs)", 1000), ("fork_exec_ns", "fork+exec (µs)", 1000)):
        rows.append([label] + [f"{F[f'sys.{k}.{fld}'] / div:,.1f}" for k in ("rc", "gv", "kt")] + [f"{nsu['syscalls'][fld] / div:,.1f}", f"{fsu['syscalls'][fld] / div:,.1f}"])
    rows.append([t("Sequential write with fsync (MB/s)", "fsync 순차 쓰기(MB/s)")] + [f"{F[f'suite.{k}.disk_seq.write_MBps']:,.0f}" for k in ("rc", "gv", "kt")] + [f"{nsu['disk_seq']['write_MBps']:,.0f}", f"{fsu['disk_seq']['write_MBps']:,.0f}"])
    d.append(table(rows))
    fcpu = list(fg["census"]["fg-fb"])[0]
    nname = nt["cpu_models"]["nt-b"][0].replace("Intel(R) Xeon(R) ", "Xeon ").replace(" CPU", "").split(" @")[0]
    fname = fg["cpu_models"]["fg-fb"][0].replace("Intel(R) Xeon(R) ", "Xeon ").replace(" CPU", "").split(" @")[0]
    d.append(t(f"Nitro and Fargate are the 2 vCPU, 8 GB size, 3 sandboxes each; runc, gVisor and Kata are the earlier m8i.2xlarge runs. Nitro ran on the same CPU as the m8i nodes ({nname}) and its syscalls are as cheap as runc's: it pays neither gVisor's syscall cost nor Kata's virtio-fs file cost. Its sequential write was {nsu['disk_seq']['write_MBps']:.0f} MB/s, a tenth of runc's; we did not find out why. Fargate ran on an older CPU ({fname}), so pure Python took about twice as long, and its syscalls and files are slower too. Both show their own guest kernel: Nitro {nt['census']['nt-b'][list(nt['census']['nt-b'])[0]]['kernel']} on a {nt['nodeinfo']['kernel']} host, Fargate {fg['census']['fg-fb'][fcpu]['kernel']}.",
                f"Nitro와 Fargate는 2 vCPU, 8 GB 크기로 각각 샌드박스 3개에서 측정했고, runc, gVisor, Kata는 이전 m8i.2xlarge 측정값입니다. Nitro는 m8i 노드와 같은 CPU({nname})에서 실행됐고 시스템 콜 비용이 runc와 비슷합니다. gVisor의 시스템 콜 비용도, Kata의 virtio-fs 파일 비용도 없습니다. 다만 순차 쓰기는 {nsu['disk_seq']['write_MBps']:.0f} MB/s로 runc의 10분의 1이었고, 원인은 확인하지 못했습니다. Fargate는 이전 세대 CPU({fname})에서 실행돼 순수 Python이 약 두 배 오래 걸렸고, 시스템 콜과 파일 작업도 더 느렸습니다. 두 구성 모두 게스트 커널이 따로 있습니다. Nitro는 호스트 {nt['nodeinfo']['kernel']} 위에서 게스트 {nt['census']['nt-b'][list(nt['census']['nt-b'])[0]]['kernel']}, Fargate는 {fg['census']['fg-fb'][fcpu]['kernel']}입니다."))
    PR = nt["pause_resume"]
    d.append(t("Nitro pause and resume with an EBS volume, through agent-sandbox `operatingMode: Suspended` and back to `Running`. Each cycle created a sandbox with a new 10 GiB gp3 volume, wrote a value to a file on the volume and to process memory, suspended, resumed and read both back:", "Nitro에서 EBS 볼륨을 붙인 채 agent-sandbox의 `operatingMode`를 `Suspended`로 바꿨다가 다시 `Running`으로 돌렸습니다. 매 사이클마다 새 10 GiB gp3 볼륨을 붙인 샌드박스를 만들고, 볼륨의 파일과 프로세스 메모리에 값을 쓴 뒤 중지, 재개하고 두 값을 다시 읽었습니다."))
    d.append(table([["", t("New sandbox with volume", "볼륨을 붙인 새 샌드박스"), t("Suspend", "중지"), t("Resume", "재개"), t("File kept", "파일 유지"), t("Memory kept", "메모리 유지")],
                    [f"p50 ({PR['cycles']} {t('cycles', '사이클')})", sc(PR["create"]["p50"]), sc(PR["suspend"]["p50"]), sc(PR["resume"]["p50"]), f"{PR['disk_kept']}/{PR['cycles']}", f"{PR['memory_kept']}/{PR['cycles']}"],
                    [t("max", "최대"), sc(PR["create"]["max"]), sc(PR["suspend"]["max"]), sc(PR["resume"]["max"]), "", ""]]))
    d.append(t(f"Resume is a new pod and a new VM that mounts the same volume ({PR['new_instance']} of {PR['cycles']} new process, {PR['same_node']} of {PR['cycles']} on the same node), so it carries disk state, not memory. Compare MicroVM resume, which kept memory, and AgentCore session storage, which kept files.", f"재개하면 새 Pod와 새 VM이 같은 볼륨을 마운트합니다({PR['cycles']}회 중 {PR['new_instance']}회 새 프로세스, {PR['same_node']}회 같은 노드). 그래서 디스크 상태는 이어지지만 메모리 상태는 이어지지 않습니다. MicroVM 재개는 메모리를 유지했고, AgentCore 세션 스토리지는 파일을 유지했습니다."))
    nc, fc = nt["conc"], fg["conc"]
    d.append(t(f"Agents at the same time (whole request, 4 batches): Nitro {sc(nc['nitro|5']['whole']['p50'])} at 5 and {sc(nc['nitro|20']['whole']['p50'])} at 20, Fargate {sc(fc['fargate|5']['whole']['p50'])} and {sc(fc['fargate|20']['whole']['p50'])}, {sum(v['failed'] for v in list(nc.values()) + list(fc.values()))} failed. A 2 vCPU, 8 GB Nitro sandbox reserves its memory in full, so only 3 fit on an m8i.2xlarge and 20 at once need at least 7 nodes. First read of the 331 MB CLI on a new sandbox: Fargate {sc(fg['first_touch']['fg-fp']['read_cli_binary_first']['p50'], 2)}" + (f", Nitro {sc(nt['first_touch']['nt-p']['read_cli_binary_first']['p50'], 2)}" if "nt-p" in nt["first_touch"] else "") + ", so neither has the first-read delay of V2 and MicroVM.",
                f"에이전트 동시 실행(전체 시간, 4배치): Nitro는 동시 5개 {sc(nc['nitro|5']['whole']['p50'])}, 20개 {sc(nc['nitro|20']['whole']['p50'])}, Fargate는 {sc(fc['fargate|5']['whole']['p50'])}, {sc(fc['fargate|20']['whole']['p50'])}였고 실패는 {sum(v['failed'] for v in list(nc.values()) + list(fc.values()))}회입니다. 2 vCPU, 8 GB Nitro 샌드박스는 메모리를 모두 예약하므로 m8i.2xlarge 한 대에 3개만 들어가고, 동시 20개에는 노드가 최소 7대 필요합니다. 새 샌드박스에서 331 MB CLI 첫 읽기는 Fargate {sc(fg['first_touch']['fg-fp']['read_cli_binary_first']['p50'], 2)}" + (f", Nitro {sc(nt['first_touch']['nt-p']['read_cli_binary_first']['p50'], 2)}" if "nt-p" in nt["first_touch"] else "") + "로, V2와 MicroVM의 첫 읽기 지연이 없습니다."))
    ns, fs = nt["security"]["nt-b"], fg["security"]["fg-fb"]
    d.append(t(f"Security defaults as in the table below, without hardening: both mount the service account token and can reach the Kubernetes API, other sandboxes and the internet, and neither has CAP_SYS_ADMIN or /dev/kvm. Nitro answers IMDS but only on the allowed paths, so no role is listed; credentials come from Pod Identity. Fargate has no IMDS. Fargate needed IRSA because Pod Identity does not run on Fargate, and DaemonSets do not run there either.",
                f"보안 기본값은 아래 표와 같은 방식으로 점검했고 강화 설정은 하지 않았습니다. 두 구성 모두 SA 토큰이 마운트되고, Kubernetes API, 다른 샌드박스, 인터넷에 연결할 수 있으며, CAP_SYS_ADMIN과 /dev/kvm은 없습니다. Nitro는 IMDS에 응답하지만 허용된 경로만 열려 있어 역할이 보이지 않고, 자격 증명은 Pod Identity로 받습니다. Fargate는 IMDS가 없습니다. Fargate에서는 Pod Identity가 동작하지 않아 IRSA를 썼고, DaemonSet도 실행되지 않습니다."))
    d.append(t("### Long requests with no bytes sent until the end", "### 끝날 때까지 응답 바이트가 없는 긴 요청"))
    def ka(b, sec):
        for r in F["long"]:
            if r["backend"] == b and r["requested_s"] == sec and r.get("mode") == "sleep_keepalive":
                return t("completed", "완료") if r["ok"] else t(f"error at {r['wall_s']:.0f} s", f"{r['wall_s']:.0f}초에 오류")
        return "n/t"
    rows = [[t("Length", "길이"), "gVisor", "Kata + QEMU", "AgentCore V1", "AgentCore V2", "Lambda MicroVMs"]]
    for sec in (360, 600, 840, 960, 1200):
        rows.append([f"{sec} s", lcell("eks-x86-gvisor", sec, t=t), lcell("eks-x86-kata", sec, t=t), ka("ac-v1", sec), ka("ac-v2", sec), lcell("lm", sec, t=t)])
    rows.append([t("1500 s, 15 s heartbeat", "1500초, 15초 하트비트"), "n/t", "n/t", lcell("ac-v1-probe3", 1500, "stream_sleep", t), lcell("ac-v2-probe3", 1500, "stream_sleep", t), lcell("lm-probe3", 1500, "stream_sleep", t)])
    d.append(table(rows))
    d.append(t("A handful of runs that locate a boundary. AgentCore clients use TCP keepalive. Requests through a NAT gateway without keepalive can be dropped at its documented 350 s idle timeout on any platform, so we removed those runs from the comparison; turn keepalive on in your client. The failure near 900 s matches AgentCore's documented 15 minute synchronous limit. AgentCore documents 60 minutes for streaming, not tested to that length.", "경계를 찾기 위해 몇 번만 실행했습니다. AgentCore 클라이언트에서는 TCP keepalive를 켰습니다. keepalive 없이 NAT Gateway를 거치면 문서에 나온 유휴 타임아웃 350초에서 어느 플랫폼이든 연결이 끊길 수 있어, 그런 실행은 비교에서 뺐습니다. 클라이언트에서 keepalive를 켜 두세요. 900초 부근의 실패는 AgentCore 문서의 동기 호출 한도 15분과 일치합니다. 다만 오류 메시지는 런타임 초기화 시간 초과로 나옵니다. 문서에 나온 스트리밍 한도 60분까지는 실험하지 않았습니다."))
    d.append(t("### Cost scenarios, monthly compute in USD", "### 비용 시나리오, 월 컴퓨트 비용(USD)"))
    rows = [[t("Scenario", "시나리오"), t("Avg concurrent", "평균 동시"), "V1", "V2", t("MicroVM, 2 GB to tested 4 GB", "MicroVM, 2 GB~실험한 4 GB"), t("gVisor, autoscaled", "gVisor 자동 축소"), t("gVisor, peak", "gVisor 피크 고정"), t("Kata, autoscaled", "Kata 자동 축소"), t("Kata, peak", "Kata 피크 고정"), t("V1, no stop", "V1, 중지 안 함"), t("V2, no stop", "V2, 중지 안 함"), t("gVisor, Graviton3", "gVisor, Graviton3"), t("gVisor, high memory", "gVisor, 메모리 높음"), t("Nitro, Auto Mode", "Nitro, Auto Mode"), t("Fargate, smallest size", "Fargate, 최소 크기"), t("Fargate, 2 vCPU 8 GB", "Fargate, 2 vCPU 8 GB")]]
    SCN_KO = {"interactive": "대화형 어시스턴트", "code_exec": "짧은 코드 실행", "coding": "빌드가 있는 코딩 에이전트", "build_heavy": "CPU 위주 빌드 에이전트", "steady": "지속적 대량 동시성"}
    for k in ("interactive", "code_exec", "coding", "build_heavy", "steady"):
        v = C[k]
        lo, hi = sorted((v["microvm_always_running"], v["microvm_tested_size"]))
        rows.append([t(v["label"], SCN_KO[k]), f"{v['avg_concurrency']:.0f}", f"{v['agentcore_v1']:,.0f}", f"{v['agentcore_v2']:,.0f}", f"{lo:,.0f} to {hi:,.0f}" if lang == "en" else f"{lo:,.0f}~{hi:,.0f}"] + [f"{v[m]:,.0f}" for m in ("eks_gvisor_autoscaled", "eks_gvisor_peak", "eks_kata_autoscaled", "eks_kata_peak", "agentcore_v1_no_stop", "agentcore_v2_no_stop", "eks_gvisor_autoscaled_graviton3", "eks_gvisor_autoscaled_mem_high", "nitro_auto_autoscaled", "fargate", "fargate_tested_size")])
    d.append(table(rows))
    ck = F["cost"]["aws_example_check"]
    d.append(t(f"The scenarios are illustrations in `analysis/cost_model.py`; change them and rerun. Prices were checked against the public pages and the Pricing API on 2026-11-03, and the formulas reproduce AWS's worked examples (V2 ${ck['agentcore_v2_support_monthly_1m']:,.0f} against ${ck['aws_says_agentcore_v2']:,}, MicroVM ${ck['microvm_ci_monthly_10k']:,.0f} against ${ck['aws_says_microvm_ci']:,.0f}). AgentCore idle memory and EKS overhead are measured. V1 and V2 assume the app stops each session; the no-stop columns add the default 15 minute idle tail at measured tail memory, and EKS has the same need to delete idle sandboxes. MicroVM use above its baseline may add charges. EKS includes the control plane, 2 system nodes, NAT Gateway and gp3 disks; on an existing cluster the interactive gVisor figure falls to ${C['interactive']['eks_gvisor_autoscaled_existing_cluster']:,.0f}. Excluded everywhere: LLM tokens, per-GB NAT and transfer, logs, staff, discounts. For the interactive shape, autoscaled gVisor and V2 break even near {be} average concurrent sessions, {F['cost']['break_even_concurrency_interactive_gvisor_warm30_vs_v2']} with 30 warm pods, and never when sized for peak. These are first crossings; node counts step, so gVisor stays cheaper from {F['cost']['gvisor_stays_cheaper_from']}, or {F['cost']['gvisor_warm30_stays_cheaper_from']} with 30 warm pods. MicroVM suspend adds snapshot write and read charges and pays off only when each idle period passes about {F['cost']['suspend_breakeven_idle_s_smallest'] / 60:.0f} minutes at 2 GB, so the table shows no suspend. These are estimates, not a bill.", f"시나리오는 `analysis/cost_model.py`에 있는 예시이며, 값을 바꿔 다시 계산할 수 있습니다. 가격은 2026-11-03에 공개 가격 페이지와 Pricing API로 확인했고, 계산식은 AWS 계산 예시를 그대로 재현합니다(V2 ${ck['agentcore_v2_support_monthly_1m']:,.0f}, AWS ${ck['aws_says_agentcore_v2']:,}. MicroVM ${ck['microvm_ci_monthly_10k']:,.0f}, AWS ${ck['aws_says_microvm_ci']:,.0f}). AgentCore 유휴 메모리와 EKS 오버헤드는 측정값입니다. V1, V2는 앱이 세션을 직접 중지한다고 가정했고, 중지 안 함 열은 기본 15분 유휴 구간을 측정한 유휴 메모리로 더한 값입니다. EKS에서도 유휴 샌드박스를 지워야 하는 점은 같습니다. MicroVM은 기준 자원을 넘게 쓰면 추가 과금될 수 있습니다. EKS 비용에는 컨트롤 플레인, 시스템 노드 2대, NAT Gateway, gp3 디스크가 들어 있으며, 기존 클러스터를 쓰면 대화형 gVisor는 ${C['interactive']['eks_gvisor_autoscaled_existing_cluster']:,.0f}로 내려갑니다. 모든 구성에서 LLM 토큰, GB당 NAT와 데이터 전송, 로그, 인건비, 할인은 뺐습니다. 대화형 시나리오에서 gVisor 자동 축소와 V2의 손익 분기점은 평균 동시 약 {be}개이고, Warm Pod 30개를 두면 {F['cost']['break_even_concurrency_interactive_gvisor_warm30_vs_v2']}개입니다. 피크에 맞춰 노드를 고정하면 손익 분기점이 없습니다. 이 값은 처음 역전되는 지점이며, 노드 수가 계단식으로 늘기 때문에 gVisor가 계속 싼 구간은 {F['cost']['gvisor_stays_cheaper_from']}개부터(Warm Pod 30개면 {F['cost']['gvisor_warm30_stays_cheaper_from']}개부터)입니다. MicroVM 일시 중지는 스냅샷 쓰기와 읽기 비용이 붙어 2 GB 기준으로 유휴 구간이 약 {F['cost']['suspend_breakeven_idle_s_smallest'] / 60:.0f}분을 넘어야 이득이므로, 표에는 일시 중지를 쓰지 않은 값을 적었습니다. 모두 추정치이며 실제 청구액이 아닙니다."))
    PZ = F["cost"]["prices"]
    d.append(t(f"Nitro and Fargate columns were added on 2026-11-10 with prices from the Pricing API. Nitro uses the EKS formula with the RuntimeClass's 256 MiB pod overhead and the Auto Mode fee of ${PZ['eks_auto_m8i.2xlarge_h']} an hour per m8i.2xlarge; with a custom AMI on your own node group there is no fee and it matches gVisor. Fargate bills ${PZ['fargate_x86']['vcpu_h']} per vCPU-hour and ${PZ['fargate_x86']['gb_h']} per GB-hour from image pull to pod end, with a one minute minimum, so each session also pays its measured one minute start; the cluster's fixed costs stay. The smallest size gives a session only its average CPU, because a Fargate pod cannot burst past its size; the 2 vCPU, 8 GB column is the size we tested.", f"Nitro와 Fargate 열은 2026-11-10에 Pricing API 가격으로 추가했습니다. Nitro는 EKS와 같은 식에 RuntimeClass의 Pod 오버헤드 256 MiB와 Auto Mode 관리 요금(m8i.2xlarge 한 대당 시간당 ${PZ['eks_auto_m8i.2xlarge_h']})을 더했습니다. 자체 노드 그룹에 커스텀 AMI로 올리면 이 요금이 없고 gVisor와 같아집니다. Fargate는 이미지를 받기 시작할 때부터 Pod가 끝날 때까지 vCPU 시간당 ${PZ['fargate_x86']['vcpu_h']}, GB 시간당 ${PZ['fargate_x86']['gb_h']}를 초 단위로 과금하고 최소 1분을 받으므로, 세션마다 측정한 약 1분의 시작 시간도 과금됩니다. 클러스터 고정비는 그대로 듭니다. 최소 크기 열은 세션에 평균 CPU만 주는 값입니다. Fargate Pod는 크기 이상으로 CPU를 쓸 수 없으므로, 실험한 크기인 2 vCPU, 8 GB 열도 함께 적었습니다."))
    d.append(t("### Security defaults: what a workload can see and reach", "### 보안 기본값: 워크로드가 볼 수 있고 접근할 수 있는 것"))
    S = F["security"]
    cfg = [("eks-x86-gvisor/default"), ("eks-x86-kata/default"), ("ac-v1/default"), ("ac-v2/default"), ("lm/default")]
    yn = lambda b: t("yes", "예") if b else t("no", "아니오")
    d.append(table([
        [t("Check", "점검")] + P,
        ["CAP_SYS_ADMIN"] + [yn(int(S[c]["cap_eff"], 16) & (1 << 21)) for c in cfg],
        [t("Role listed through metadata", "메타데이터로 역할 조회 가능")] + [yn(S[c]["imds"]["role_listed"]) for c in cfg],
        [t("Service account token mounted", "SA 토큰 마운트")] + [yn(S[c]["k8s_sa_token_mounted"]) for c in cfg],
        [t("Kubernetes API reachable", "Kubernetes API 접근")] + [yn(True) if S[c]["k8s_api_tcp"] == "open" else "N/A" for c in cfg],
        [t("Internet egress in this setup", "인터넷 외부 통신(이번 구성)")] + [yn(S[c]["egress_internet_https"] == "open") for c in cfg],
        ["io_uring"] + [t("absent", "없음") if S[c]["io_uring_setup"]["errno"] == "ENOSYS" else t("callable", "호출 가능") for c in cfg],
        ["/dev/kvm"] + [yn(S[c]["dev_kvm"]) for c in cfg],
    ]))
    v = S["eks-x86-gvisor-warm/np-enforced"]
    NP = lambda x: {"timeout": "시간 초과", "TimeoutError": "시간 초과", "open": "연결됨"}.get(x, x)
    d.append(t(f"With VPC CNI network policy turned on, a warm pool sandbox got: peer {v['peer_sandbox_tcp']}, Kubernetes API {v['k8s_api_tcp']}, internet {v['egress_internet_https']}, Pod Identity endpoint {v['extra']['pod_identity_169_254_170_23']}. The policy Agent Sandbox generates excludes 169.254.0.0/16, so AWS credential lookup failed with CredentialRetrievalError on gVisor and Kata. Add an exception for the Pod Identity endpoint, or inject credentials another way. A Sandbox created directly, without a SandboxTemplate, gets no policy and stayed open.", f"VPC CNI NetworkPolicy를 켜자 Warm Pool 샌드박스에서 다른 샌드박스는 {NP(v['peer_sandbox_tcp'])}, Kubernetes API는 {NP(v['k8s_api_tcp'])}, 인터넷은 {NP(v['egress_internet_https'])}, Pod Identity 엔드포인트는 {NP(v['extra']['pod_identity_169_254_170_23'])}였습니다. Agent Sandbox가 만드는 정책은 169.254.0.0/16을 허용 대상에서 빼므로, gVisor와 Kata 모두 AWS 자격 증명 조회가 CredentialRetrievalError로 실패했습니다. Pod Identity 엔드포인트를 예외로 허용하거나 자격 증명을 다른 방식으로 넣어 주어야 합니다. SandboxTemplate 없이 직접 만든 Sandbox에는 정책이 붙지 않아 모든 연결이 열려 있었습니다."))
    d.append(t("These are benign checks of defaults from inside a sandbox, not a penetration test, and say nothing about escape resistance. The role seen through metadata is the session's execution role. By default an EKS sandbox could reach another sandbox. Isolation between managed sessions is not covered here.", "샌드박스 안에서 기본값을 확인하는 무해한 점검이며 침투 테스트가 아닙니다. 탈출 내성에 대해서는 아무것도 말하지 않습니다. 메타데이터로 보이는 역할은 그 세션의 실행 역할입니다. EKS 샌드박스는 기본 설정에서 다른 샌드박스에 연결할 수 있었습니다. 관리형 세션 사이의 격리는 이 문서에서 다루지 않습니다."))
    d.append(t("EKS ran as tested, not hardened. The AWS blog series recommends Pod Security restricted, non-root, dropped capabilities and no service account token; we did not apply them in this table. Warm pool templates did not mount the token. We recorded Pod Identity reachability only with network policy on (timeout), not in the default state. MicroVM internet egress was requested explicitly through its connector.", "EKS는 실험한 그대로이며 강화 설정을 적용하지 않았습니다. AWS 블로그 시리즈는 Pod Security restricted, non-root 실행, capability 제거, SA 토큰 끄기를 권장하지만 이 표에는 적용하지 않았습니다. Warm Pool 템플릿은 토큰을 마운트하지 않았습니다. Pod Identity 접근 여부는 네트워크 정책을 켠 상태(시간 초과)만 기록했고 기본 상태는 기록하지 않았습니다. MicroVM의 인터넷 외부 통신은 커넥터로 명시적으로 열었습니다."))
    d.append(t("### Observability with no extra configuration", "### 별도 설정 없이 얻는 관측성"))
    d.append(table([
        ["", "gVisor / Kata (EKS)", "AgentCore V1 / V2", "Lambda MicroVMs"],
        [t("App logs", "앱 로그"), t("kubectl logs while the pod lives, HTTP 404 after delete", "Pod가 있는 동안 kubectl logs, 삭제 후 HTTP 404"), t("CloudWatch, automatic", "CloudWatch 자동"), t("CloudWatch, with an execution role", "실행 역할이 있으면 CloudWatch")],
        [t("Platform metrics", "플랫폼 지표"), t("Nothing in this setup. EKS add-ons such as Container Insights were not installed or evaluated", "이번 구성에는 없음. Container Insights 같은 EKS 애드온은 설치하거나 평가하지 않음"), "Invocations, Sessions, Latency, Throttles, OverheadLatency, vCPU, memory", t("No service metrics in a full scan of the account's CloudWatch (log ingestion only)", "계정 CloudWatch 전체를 조회해도 서비스 지표 없음(로그 수신 지표만 있음)")],
        [t("Per-session usage", "세션별 사용량"), t("Build it", "직접 구성"), t("USAGE_LOGS after one delivery setting, 1 s granularity", "로그 전달을 한 번 설정하면 USAGE_LOGS, 1초 단위"), t("Compute from run time", "실행 시간으로 계산")],
        [t("Control plane logs", "컨트롤 플레인 로그"), t("All 5 types off by default", "5종 모두 기본값 꺼짐"), t("CloudTrail (doc)", "CloudTrail (문서)"), t("CloudTrail (doc)", "CloudTrail (문서)")],
    ]))
    d.append(t("### Density and environment", "### 밀도와 실행 환경"))
    d.append(t(f"Host memory per idle sandbox: runc {F['density.rc.mb']:.0f} MB, gVisor {F['density.gv.mb']:.0f} MB, Kata {F['density.kt.mb']:.0f} MB. Kata's RuntimeClass adds a 250m CPU pod overhead, so with a 250m request a node holds roughly half as many sandboxes.", f"유휴 샌드박스 하나당 호스트 메모리는 runc {F['density.rc.mb']:.0f} MB, gVisor {F['density.gv.mb']:.0f} MB, Kata {F['density.kt.mb']:.0f} MB입니다. Kata의 RuntimeClass는 Pod마다 CPU 250m를 더하므로, Pod 요청이 250m이면 노드에 올릴 수 있는 샌드박스가 절반 정도로 줄어듭니다."))

    d.append(t("## Method", "## 측정 방법"))
    d.append(t("""- **Same app.** `app/` is one image with the Claude Agent SDK. MicroVMs build `FROM` that image. EKS and AgentCore pull it directly. Sandboxes are limited to 2 vCPU and 8 GiB, except MicroVMs at a 4 GB, 2 vCPU billed baseline that see 8 vCPU.
- **Same region.** Everything runs in `us-east-1`, including the driver; the Tokyo repeat ran its driver in `ap-northeast-1`. Paths still differ: EKS is reached on the Pod IP, managed services on public endpoints.
- **Same definition.** Timing starts just before the first call that asks for a sandbox and ends when the app answers. Agent readiness is measured separately.
- **Controls.** runc on the same nodes, gVisor and runc on Graviton3 to match the managed CPU, and Kata on `m8i.metal-48xl` to separate nested virtualization from Kata itself.
- **No capacity or quota penalty.** Results set by a quota or too few nodes were left out or measured again.
- **Order and failures.** The headline agent and cold start tables shuffle backends in each cycle so that none owns a time of day. The follow-up comparisons (mitigations, SDKs, network mode, builds, concurrency) each shuffled their arms in one period. Metal ran in its own period. Failures are recorded and counted; only failures are left out of timing, and slow runs stay in.
- **Claims.** `analysis/verify_claims.py` fails if a claim stops holding.""", """- **같은 앱.** `app/`는 Claude Agent SDK를 담은 이미지 하나입니다. MicroVM은 이 이미지를 `FROM`으로 빌드하고, EKS와 AgentCore는 이 이미지를 그대로 씁니다. 샌드박스 한도는 2 vCPU, 8 GiB입니다. MicroVM만 과금 기준이 4 GB, 2 vCPU이고 8 vCPU가 보입니다.
- **같은 리전.** 측정기를 포함해 모두 `us-east-1`에서 실행했습니다. 도쿄 재측정은 측정기도 `ap-northeast-1`에 두었습니다. 다만 호출 경로는 다릅니다. EKS는 Pod IP로, 관리형은 공용 엔드포인트로 호출합니다.
- **같은 정의.** 샌드박스를 요청하는 첫 호출 직전부터 앱이 응답할 때까지를 측정합니다. 에이전트 준비 시간은 따로 측정합니다.
- **대조군.** 같은 노드의 runc, 관리형과 CPU를 맞춘 Graviton3의 gVisor와 runc, 중첩 가상화의 영향을 분리하기 위한 `m8i.metal-48xl`의 Kata를 두었습니다.
- **용량과 쿼터로 인한 불이익 배제.** 쿼터나 노드 부족이 결과를 정한 경우는 제외하거나 다시 측정했습니다.
- **순서와 실패.** 대표 에이전트 표와 콜드 스타트 표는 사이클마다 백엔드 순서를 섞어, 특정 구성이 특정 시간대에 몰리지 않게 했습니다. 후속 비교(완화책, SDK, 네트워크 모드, 빌드, 동시 실행)도 각각 같은 시간대에 조건 순서를 섞었습니다. 메탈은 따로 실행했습니다. 실패도 모두 기록하고 집계하며, 시간 집계에서는 실패만 빼고 느린 실행은 그대로 둡니다.
- **주장 검증.** 문서의 주장이 데이터와 맞지 않으면 `analysis/verify_claims.py`가 실패합니다."""))
    d.append(t("### Experiments", "### 실험과 코드"))
    d.append(table([
        [t("What", "내용"), t("Code", "코드")],
        [t("Cold start, image size, start-up work, first session on a new runtime", "콜드 스타트, 이미지 크기, 초기화, 새 런타임 첫 세션"), "`cold_start`, `deploy.py --which fresh`"],
        [t("Packaging and network mode", "패키징과 네트워크 모드"), "`deploy.py --which pkg`, `deploy.py --which balance`"],
        [t("Round trip on an open sandbox", "이미 열린 샌드박스 왕복"), "`warm_latency`"],
        [t("Workloads, syscalls, disk, network", "워크로드, 시스템 콜, 디스크, 네트워크"), "`bench_suite`, `net_suite`"],
        [t("Claude Agent SDK task, first versus repeat start", "Claude Agent SDK 태스크, 첫 실행과 반복"), "`agent_e2e`, `agent_spaced`, `agent_concurrent`, `agent_first_vs_repeat`, `scripts/chain_same.sh`, `scripts/chain_quiet2.sh`"],
        [t("Bursts, sustained arrivals", "버스트, 지속 유입"), "`burst`, `sustained`"],
        [t("Reclamation, state wipe, suspend and resume, node scale", "회수, 상태 초기화, 일시 중지와 재개, 노드 확장"), "`idle_reclaim`, `state_wipe`, `suspend_resume`, `microvm_idle_policy`, `node_scale`, `scripts/kata_scale.py`"],
        [t("AgentCore billing inputs", "AgentCore 과금 입력"), "`usage_sessions`, `usage_agent`, `analysis/fetch_usage.py`"],
        [t("Observability audit", "관측성 점검"), "`ops_experiments.py observability`"],
        [t("Security defaults", "보안 기본값"), "`security`, `cross_session`"],
        [t("Density, CPU census", "밀도, CPU 분포"), "`ops_experiments.py density`, `hw_census`"],
        [t("Long requests", "장기 요청"), "`long_request`"],
        [t("First touch of files and tools", "파일과 도구의 첫 접근"), "`first_touch`"],
        [t("Follow-ups: Strands Agents, file size, mitigations and warming, session storage, network mode, build, concurrency, Tokyo", "후속: Strands Agents, 파일 크기, 완화책과 예열, 세션 스토리지, 네트워크 모드, 빌드, 동시 실행, 도쿄"), "`bench/followup/driver/xrun.py`, `bench/followup/app/x_entry.py`, `bench/followup/driver/*.json`"],
        [t("Follow-ups: Karpenter", "후속: Karpenter"), "`bench/followup/driver/kp.py`, `bench/followup/driver/kp_chain.sh`"],
        [t("Follow-ups: EKS Fargate and Nitro Sandboxes", "후속: EKS Fargate와 Nitro Sandboxes"), "`bench/followup/driver/fg_chain.sh`, `nt_chain.sh`, `na_chain.sh`, `nt_pause.py`, `infra/terraform/fargate.tf`, `infra/terraform/nitro.tf`, `infra/k8s/nitro*.yaml`"],
    ]))
    d.append(t("## Limits of this test", "## 이 실험의 한계"))
    d.append(t("""- Mostly one region with a partial repeat in Tokyo, three days, one account, one application. Results can change with region, quotas, capacity and time. The first-read result depends on how large a file the agent reads first.
- Network paths differ between platforms, so round trips are not a pure runtime comparison.
- This test shows when the first read is slow and what removes it, not why it is slow inside the platform.
- Kata ran with its default virtio-fs. Block-device rootfs and memory-backed work directories were not tested.
- Not tested: 8 hour and 14 day sessions, Spot, gVisor on KVM, raised MicroVM quotas, EKS hardening options, X-Ray traces, Seoul, MicroVMs and warm pools in Tokyo, session storage on V1 and MicroVM.
- Some follow-ups have small samples (8 to 16 runs), so read their confidence intervals. The Strands app is ours, with 3 tools.
- Fargate and Nitro were measured on one day, five days after the others, against same-period anchors. Nitro ran on a separate Auto Mode cluster, with its own driver, in the same VPC and zone. Nitro was only tested in isolated mode, with defaults for its network and DNS limits.
- Security results describe defaults and are not a statement about escape resistance.
- Cost scenarios use assumed traffic. The AgentCore committed price status could not be confirmed and is not used.
- `results/raw/` also keeps runs left out of the tables, including the invalid `cold_uncached.jsonl`.""", """- 대부분 한 리전에서 측정했고 도쿄에서는 일부만 다시 측정했습니다. 사흘 동안 한 계정에서 앱 하나로 측정했으므로, 리전, 쿼터, 용량, 시간에 따라 결과가 달라질 수 있습니다. 첫 읽기 결과는 에이전트가 처음 읽는 파일의 크기에 따라 달라집니다.
- 플랫폼마다 네트워크 경로가 달라서 왕복 시간은 런타임만 비교한 값이 아닙니다.
- 이 실험은 첫 읽기가 언제 느리고 무엇으로 해결되는지를 보여 줄 뿐, 플랫폼 내부에서 왜 느린지는 다루지 않습니다.
- Kata는 기본 virtio-fs로 실행했습니다. 블록 디바이스 rootfs와 메모리 기반 작업 디렉터리는 실험하지 않았습니다.
- 실험하지 않은 항목: 8시간과 14일 세션, Spot, KVM 플랫폼의 gVisor, 쿼터를 올린 MicroVM, EKS 강화 옵션, X-Ray 트레이스, 서울 리전, 도쿄의 MicroVM과 Warm Pool, V1과 MicroVM의 세션 스토리지.
- 일부 후속 실험은 표본이 적습니다(8~16회). 신뢰 구간을 함께 보세요. Strands 앱은 도구 3개로 직접 만든 앱입니다.
- Fargate와 Nitro는 다른 구성보다 닷새 늦게 하루 동안 측정했고, 같은 시간대의 기준선과 비교했습니다. Nitro는 같은 VPC와 가용 영역에 둔 별도 Auto Mode 클러스터에서 별도 측정기로 측정했습니다. Nitro는 isolated 모드만 실험했고, 네트워크와 DNS 한도는 기본값을 썼습니다.
- 보안 결과는 기본값을 설명할 뿐 탈출 내성을 평가한 것이 아닙니다.
- 비용 시나리오의 트래픽은 가정입니다. AgentCore 약정 가격은 제공 여부를 확인하지 못해 쓰지 않았습니다.
- `results/raw/`에는 표에서 뺀 실행도 남아 있습니다. `cold_uncached.jsonl`은 무효 실험입니다."""))
    d.append(t("## Layout and reproduction", "## 구성과 재현"))
    d.append("""```
app/        """ + t("agent image, workloads, probes", "에이전트 이미지, 워크로드, 프로브") + """
bench/      """ + t("driver: backends, experiments, deployment; follow-ups in bench/followup/", "측정기: 백엔드, 실험, 배포. 후속 실험은 bench/followup/") + """
infra/      """ + t("Terraform and Kubernetes manifests", "Terraform과 Kubernetes 매니페스트") + """
scripts/    """ + t("chains that ran each round, result sync", "라운드 실행 체인, 결과 동기화") + """
analysis/   """ + t("summary, facts, cost model, claim checks, README generator", "요약, 사실 추출, 비용 모델, 주장 검증, README 생성") + """
results/    """ + t("raw JSONL and generated summaries (account id removed)", "원시 JSONL과 생성된 요약(계정 ID 제거)") + """
```""")
    d.append("""```bash
cd infra/terraform && terraform init && terraform apply
# """ + t("replace ACCOUNT_ID in infra/k8s/*.yaml, build images with Dockerfile*, install agent-sandbox and kata-deploy", "infra/k8s/*.yaml의 ACCOUNT_ID를 바꾸고, Dockerfile*로 이미지를 빌드하고, agent-sandbox와 kata-deploy를 설치") + """
kubectl apply -f infra/k8s/base.yaml -f infra/k8s/warmpools.yaml
# """ + t("copy bench/ and scripts/ into the driver pod, then:", "bench/와 scripts/를 드라이버 Pod에 복사한 뒤:") + """
python deploy.py --which all
sh /work/scripts/chain_r1.sh
sh /work/scripts/chain_same.sh
scripts/pull_results.sh
python3 analysis/analyze.py && python3 analysis/cost_model.py && python3 analysis/followup.py && python3 analysis/facts.py
python3 analysis/verify_claims.py && python3 analysis/make_readme.py
```""")
    d.append(t("**This is a disposable test bed, not a reference architecture.** The driver has cluster-admin, a privileged helper runs on nodes, the app's endpoint is unauthenticated inside the VPC, IAM is broad, and the EKS API endpoint is public. See the comments in `infra/terraform/iam.tf`. Delete it when you finish.", "**이 환경은 실험용으로 쓰고 버리는 구성이며 참조 아키텍처가 아닙니다.** 드라이버에 cluster-admin 권한이 있고, 노드에서 특권 도우미가 실행되며, 앱 엔드포인트는 VPC 안에서 인증 없이 열려 있고, IAM 권한도 넓으며, EKS API 엔드포인트가 공개되어 있습니다. `infra/terraform/iam.tf`의 주석을 참고하세요. 실험이 끝나면 삭제하세요."))
    return "\n\n".join(d) + "\n"


(ROOT / "README.md").write_text(render("en"))
(ROOT / "README.ko.md").write_text(re.sub(r"(\d) to (\d)", r"\1~\2", re.sub(r"(?<![A-Za-z])(\d[\d,.]*) s(?![A-Za-z0-9])", r"\1초", render("ko"))))
print("README written", len(render("en")), len(render("ko")))
