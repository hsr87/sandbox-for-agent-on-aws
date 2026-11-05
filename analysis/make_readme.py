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
        f"The same Claude Agent SDK application, run on five sandbox options on AWS and measured from a driver in the same region. Measured in `us-east-1`, 2026-11-03 to 04, with several rounds and follow-up tests. Measured numbers are generated from `results/raw/`. Measured values are the default; anything taken from documentation is marked (doc), and anything not tested is marked n/t.",
        f"같은 Claude Agent SDK 앱을 AWS의 샌드박스 다섯 가지에 올리고, 같은 리전의 측정기에서 쟀습니다. `us-east-1`에서 2026-11-03~04에 여러 라운드와 후속 시험을 돌렸습니다. 측정 숫자는 `results/raw/`에서 생성합니다. 표시가 없으면 측정값이고, 문서에서 가져온 값은 (문서), 시험하지 않은 항목은 n/t로 표시합니다."))

    FA, CS, LR = F["fair"]["agent"], F["fair"]["concurrent_scaled"], F["fair"]["low_rate"]
    C8 = F["fair"]["crossed_first8"]


    H, HC = narrative.headline(F), narrative.headline_cold(F)
    MT = F["fair"]["model_time_range"]
    Q = lambda k: FA.get(k)
    d.append(t("## Results vary", "## 결과는 달라질 수 있습니다"))
    d.append(narrative.variability(t))
    d.append(t("## Key findings", "## 핵심 결과"))
    d.append(table([
        [t("Finding", "결과"), t("Evidence", "근거")],
        [t("No option wins everywhere. The order changes with what you measure.", "모든 면에서 앞서는 구성은 없습니다. 무엇을 재느냐에 따라 순서가 바뀝니다."), t(f"Small agent task, same period and shuffled, whole request: gVisor {H['gv']['total_p50']:.1f} s, V1 {H['v1']['total_p50']:.1f} s, Kata {H['kt']['total_p50']:.1f} s, MicroVM {H['lm']['total_p50']:.1f} s, V2 {H['v2']['total_p50']:.1f} s. 100 at once on echo: V2 {s('burst.v2.100.p50')}, gVisor {s('burst.gv.100.p50')}, V1 {s('burst.v1.100.p50')}, Kata {s('burst.kt.100.p50')}.", f"같은 시기에 순서를 섞은 작은 에이전트 태스크의 요청 전체: gVisor {H['gv']['total_p50']:.1f} s, V1 {H['v1']['total_p50']:.1f} s, Kata {H['kt']['total_p50']:.1f} s, MicroVM {H['lm']['total_p50']:.1f} s, V2 {H['v2']['total_p50']:.1f} s. echo 동시 100개: V2 {s('burst.v2.100.p50')}, gVisor {s('burst.gv.100.p50')}, V1 {s('burst.v1.100.p50')}, Kata {s('burst.kt.100.p50')}.")],
        [t("V1's start depends on arrival rate and packaging.", "V1 시작은 유입 속도와 패키징에 좌우됩니다."), t(f"Same-period low rate p50 {HC['v1']['p50']:.2f} s, p90 {HC['v1']['p90']:.2f} s. 5 per second {s('sus.v1np.5.p50')}, 1.5 GB image {s('sus.v1large.5.p50')}, direct code {s('sus.v1zip.5.p50')}, VPC mode {s('sus.v1vpc.5.p50')}.", f"같은 시기 저빈도 p50 {HC['v1']['p50']:.2f} s, p90 {HC['v1']['p90']:.2f} s. 초당 5건 {s('sus.v1np.5.p50')}, 1.5 GB 이미지 {s('sus.v1large.5.p50')}, 코드 직접 배포 {s('sus.v1zip.5.p50')}, VPC 모드 {s('sus.v1vpc.5.p50')}.")],
        [t("V2 starts in 1.8 to 3.5 s across the conditions tested, on echo, in the range AWS published.", "V2는 echo 기준 시험한 조건에서 1.8~3.5초로, AWS 발표치와 같은 범위입니다."), t(f"Low rate {HC['v2']['p50']:.2f} s, 5 per second {s('sus.v2.5.p50')}, 100 at once {s('burst.v2.100.p50')}, new 1.5 GB runtime {s('fresh.V2.large.first')}, VPC mode {s('cold.v2vpc.p50')}, VPC mode at 100 at once {s('burst.v2vpc.100.p50')}.", f"저빈도 {HC['v2']['p50']:.2f} s, 초당 5건 {s('sus.v2.5.p50')}, 동시 100개 {s('burst.v2.100.p50')}, 새 1.5 GB 런타임 {s('fresh.V2.large.first')}, VPC 모드 {s('cold.v2vpc.p50')}, VPC 모드 동시 100개 {s('burst.v2vpc.100.p50')}.")],
        [t("An agent with a large binary can wait long for its first message on V2. These are not errors. A slow first read fits the pattern, which is our interpretation.", "큰 바이너리를 쓰는 에이전트는 V2에서 첫 메시지를 오래 기다릴 수 있습니다. 오류가 아닙니다. 첫 읽기 지연과 패턴이 맞지만 이는 저희 해석입니다."), t(f"V2 first message on new runtimes: p50 {H['v2']['first_p50']:.1f} s, p90 {H['v2']['first_p90']:.1f} s, {H['v2']['slow_share'] * 100:.0f}% over 20 s, {H['v2']['n']} of {H['v2']['tried']} succeeded. After a quiet hour: V2 {FA['ac-v2-q2|quiet2']['first_p50']:.1f} s, MicroVM {FA['lm-q2|quiet2']['first_p50']:.1f} s. CLI binary on a new V2 sandbox: first read {F['touch.v2.read_cli_binary.first']:.1f} s, second {F['touch.v2.read_cli_binary.second']:.2f} s.", f"새 런타임 V2 첫 메시지: p50 {H['v2']['first_p50']:.1f}초, p90 {H['v2']['first_p90']:.1f}초, {H['v2']['slow_share'] * 100:.0f}%가 20초 초과, {H['v2']['tried']}회 중 {H['v2']['n']}회 성공. 조용한 한 시간 뒤: V2 {FA['ac-v2-q2|quiet2']['first_p50']:.1f}초, MicroVM {FA['lm-q2|quiet2']['first_p50']:.1f}초. 새 V2 샌드박스의 CLI 바이너리: 첫 읽기 {F['touch.v2.read_cli_binary.first']:.1f}초, 두 번째 {F['touch.v2.read_cli_binary.second']:.2f}초.")],
        [t("On V2, only CLI file mapping kept the first 8 runs of a new runtime under 20 s. Running the CLI before the snapshot did not help those first runs but was faster in later rounds. Startup warm-up had no clear effect.", "V2 새 런타임의 첫 8회가 모두 20초 미만이었던 것은 CLI 파일 매핑뿐입니다. 스냅샷 전 CLI 실행은 그 앞쪽 실행에는 효과가 없었지만 이후 라운드에서는 빨랐습니다. 시작 시 예열은 뚜렷한 효과가 없었습니다."), t(f"V2 first message: CLI file mapping {FA['ac-v2-pin|pin']['first_p50']:.1f} s (p90 {FA['ac-v2-pin|pin']['first_p90']:.1f} s). Running the CLI before the snapshot: first 10 runs {FA['ac-v2-prewarm|first10']['first_p50']:.1f} s (p90 {FA['ac-v2-prewarm|first10']['first_p90']:.1f} s), later rounds {F['fair']['prewarm_rounds']['ac-v2|r2']['prewarm']:.1f}, {F['fair']['prewarm_rounds']['ac-v2|r3']['prewarm']:.1f} s against {F['fair']['prewarm_rounds']['ac-v2|r2']['plain']:.1f}, {F['fair']['prewarm_rounds']['ac-v2|r3']['plain']:.1f} s with none. Startup warm-up {FA['ac-v2-warm|pkg']['first_p50']:.1f} s (p90 {FA['ac-v2-warm|pkg']['first_p90']:.1f} s).", f"V2 첫 메시지: CLI 파일 매핑 {FA['ac-v2-pin|pin']['first_p50']:.1f}초(p90 {FA['ac-v2-pin|pin']['first_p90']:.1f}초). 스냅샷 전 CLI 실행: 첫 10회 {FA['ac-v2-prewarm|first10']['first_p50']:.1f}초(p90 {FA['ac-v2-prewarm|first10']['first_p90']:.1f}초), 이후 라운드 {F['fair']['prewarm_rounds']['ac-v2|r2']['prewarm']:.1f}초, {F['fair']['prewarm_rounds']['ac-v2|r3']['prewarm']:.1f}초(무처리 {F['fair']['prewarm_rounds']['ac-v2|r2']['plain']:.1f}초, {F['fair']['prewarm_rounds']['ac-v2|r3']['plain']:.1f}초). 시작 시 예열 {FA['ac-v2-warm|pkg']['first_p50']:.1f}초(p90 {FA['ac-v2-warm|pkg']['first_p90']:.1f}초).")],
        [t("EKS improves a lot when tuned.", "EKS도 튜닝하면 크게 빨라집니다."), t(f"Warm pods that ran the task before ready: first message gVisor {FA['eks-x86-gvisor-warm-init|init']['first_p50']:.1f} s, Kata {FA['eks-x86-kata-warm-init|init']['first_p50']:.1f} s; whole request {FA['eks-x86-gvisor-warm-init|init']['total_p50']:.1f} s and {FA['eks-x86-kata-warm-init|init']['total_p50']:.1f} s. These pods cost nodes while they wait.", f"준비 전에 태스크를 실행한 Warm Pod: 첫 메시지 gVisor {FA['eks-x86-gvisor-warm-init|init']['first_p50']:.1f} s, Kata {FA['eks-x86-kata-warm-init|init']['first_p50']:.1f} s, 요청 전체 {FA['eks-x86-gvisor-warm-init|init']['total_p50']:.1f} s, {FA['eks-x86-kata-warm-init|init']['total_p50']:.1f} s. 대기 중에도 노드 비용이 듭니다.")],
        [t("Differences on a build mix CPU, storage and isolation. Only Kata nested against metal isolates one factor.", "빌드 태스크의 차이에는 CPU, 스토리지, 격리가 섞입니다. 한 요인만 분리한 비교는 Kata 중첩과 메탈뿐입니다."), t(f"Build task: gVisor {FA['eks-x86-gvisor|heavy']['total_p50']:.1f} s, V1 {FA['ac-v1-np|heavy']['total_p50']:.1f} s, MicroVM {FA['lm-fa|heavy']['total_p50']:.1f} s, V2 {FA['ac-v2-fa|heavy']['total_p50']:.1f} s, Kata metal {FA['eks-metal-kata|heavy']['total_p50']:.1f} s, Kata nested {FA['eks-x86-kata|heavy']['total_p50']:.1f} s.", f"빌드 태스크: gVisor {FA['eks-x86-gvisor|heavy']['total_p50']:.1f} s, V1 {FA['ac-v1-np|heavy']['total_p50']:.1f} s, MicroVM {FA['lm-fa|heavy']['total_p50']:.1f} s, V2 {FA['ac-v2-fa|heavy']['total_p50']:.1f} s, Kata 메탈 {FA['eks-metal-kata|heavy']['total_p50']:.1f} s, Kata 중첩 {FA['eks-x86-kata|heavy']['total_p50']:.1f} s.")],
        [t("Cost depends on scale and session shape.", "비용은 규모와 세션 패턴에 달렸습니다."), t(f"Interactive scenario with explicit stop: V2 ${C['interactive']['agentcore_v2']:,.0f}, gVisor ${C['interactive']['eks_gvisor_autoscaled']:,.0f}, V1 ${C['interactive']['agentcore_v1']:,.0f}, MicroVM from ${C['interactive']['microvm_always_running']:,.0f}. Without a stop V2 ${C['interactive']['agentcore_v2_no_stop']:,.0f}, V1 ${C['interactive']['agentcore_v1_no_stop']:,.0f}. Steady scenario: gVisor ${C['steady']['eks_gvisor_autoscaled']:,.0f}, V2 ${C['steady']['agentcore_v2']:,.0f}.", f"명시적 중지를 가정한 대화형 시나리오: V2 ${C['interactive']['agentcore_v2']:,.0f}, gVisor ${C['interactive']['eks_gvisor_autoscaled']:,.0f}, V1 ${C['interactive']['agentcore_v1']:,.0f}, MicroVM ${C['interactive']['microvm_always_running']:,.0f}부터. 중지하지 않으면 V2 ${C['interactive']['agentcore_v2_no_stop']:,.0f}, V1 ${C['interactive']['agentcore_v1_no_stop']:,.0f}. 지속 시나리오: gVisor ${C['steady']['eks_gvisor_autoscaled']:,.0f}, V2 ${C['steady']['agentcore_v2']:,.0f}.")],
    ]))

    d.append(t("## Which option for which situation", "## 어떤 상황에 무엇을 권장하나"))
    d.append(table([[t("Situation", "상황"), t("First choice", "먼저 볼 선택"), t("Measured reason", "측정 근거"), t("Avoid or check", "피하거나 확인할 점")]] + narrative.recommendations(F, t)))

    d.append(t("## Results", "## 결과"))
    d.append(t("Values are p50 unless marked. Where confidence intervals overlap, we do not call it a difference. First message runs from the `query()` call, after the SDK import, to the first object the SDK yields, which comes before the first model stream event. It leaves out sandbox start and the SDK import. Whole request is sandbox start plus the agent call: SDK import, task, the harness's pytest and network.", "표시가 없으면 p50입니다. 신뢰 구간이 겹치면 차이로 보지 않습니다. 첫 메시지는 SDK import 뒤 `query()`를 호출한 때부터 SDK가 첫 객체를 줄 때까지로, 첫 모델 스트림 이벤트보다 앞선 시점입니다. 샌드박스 시작과 SDK import는 빠집니다. 요청 전체는 샌드박스 시작과 에이전트 호출을 더한 값으로, SDK import, 태스크, 하네스의 pytest, 네트워크가 들어 있습니다."))
    d.append(t("### Cold start, from request to echo reply", "### 콜드 스타트, 요청부터 echo 응답까지"))
    if F["fair"].get("same", {}).get("cold"):
        SC = F["fair"]["same"]["cold"]
        d.append(t("Same period, shuffled, one round on new managed runtimes after 10 agent runs on each:", "같은 시기에 순서를 섞어, 새 관리형 런타임마다 에이전트를 10회 돌린 뒤 잰 1라운드:"))
        d.append(table([["", "gVisor x86", "gVisor Graviton3", "Kata", "AgentCore V1", "AgentCore V2", "Lambda MicroVMs"], ["p50"] + [f"{SC[k]['p50']:.2f} s" for k in ("gv", "g3gv", "kt", "v1", "v2", "lm")], ["p90"] + [f"{SC[k]['p90']:.2f} s" for k in ("gv", "g3gv", "kt", "v1", "v2", "lm")], [t("Share under 3 s", "3초 미만 비율")] + [f"{SC[k]['fast_share'] * 100:.0f}%" for k in ("gv", "g3gv", "kt", "v1", "v2", "lm")], [t("Arrival interval per option", "구성별 도착 간격")] + [f"{SC[k]['arrival_s']:.0f} s" for k in ("gv", "g3gv", "kt", "v1", "v2", "lm")]]))
    d.append(t("Other conditions and earlier rounds:", "다른 조건과 앞선 라운드:"))
    KN = ["gv", "kt", "v1np", "v2np", "lm"]
    rows = [[""] + P, ["p50"] + [s(f"cold.{k}.p50") for k in KN], ["p90"] + [s(f"cold.{k}.p90") for k in KN]]
    rows.append([t("1.5 GB image", "1.5 GB 이미지")] + [s(f"cold.{k}.large.p50") for k in K])
    rows.append([t("10 s start-up work", "10초 초기화")] + [s(f"cold.{k}.heavy.p50") for k in K])
    rows.append([t("n / failures", "표본 / 실패")] + [f"{F[f'cold.{k}.n']} / {F[f'cold.{k}.fail']}" for k in KN])
    d.append(table(rows))
    d.append(t(f"V1 and V2 use the image with the documented /ping, except the 1.5 GB and start-up rows, which use the earlier /ping. Warm pools: gVisor {F['cold.gvw.p50'] * 1000:.0f} ms, Kata {F['cold.ktw.p50'] * 1000:.0f} ms, paying for the pods kept ready. Baselines: runc {s('cold.rc.p50')}, Kata on metal {s('cold.ktm.p50')}. Warm calls from the driver take about 1 ms on EKS, {F['warm.lm.p50ms']:.1f} ms on MicroVM, {F['warm.v1.p50ms']:.0f} ms on V1 and {F['warm.v2.p50ms']:.0f} ms on V2, so differences within 0.1 s should not be ranked.", f"V1, V2는 문서대로 고친 /ping 이미지이고, 1.5 GB와 초기화 행만 이전 /ping입니다. Warm Pool: gVisor {F['cold.gvw.p50'] * 1000:.0f} ms, Kata {F['cold.ktw.p50'] * 1000:.0f} ms, 대신 미리 띄운 Pod 비용을 냅니다. 기준선: runc {s('cold.rc.p50')}, 메탈 Kata {s('cold.ktm.p50')}. 측정기에서 warm 호출은 EKS 약 1 ms, MicroVM {F['warm.lm.p50ms']:.1f} ms, V1 {F['warm.v1.p50ms']:.0f} ms, V2 {F['warm.v2.p50ms']:.0f} ms이므로 0.1초 안의 차이로 순위를 매기면 안 됩니다."))
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
    d.append(t("The docs conflict on the direct code limit (1.6 and 25 sessions per second). New runtime values are the p50 of the first call on 3 separate runtimes. The 1.5 GB row, the new runtime cells of the 276 MB rows and the 276 MB V2 sustained and burst values use the earlier /ping. Failures left out of these p50s: V2 VPC 1 of 30 at low rate (throttled, not retried in this test), V2 2 of 600 at 5 per second (a 504 and an internal error), V1 1 of 1,200 at 10 per second.", "문서에서 코드 직접 배포 한도가 초당 1.6건과 25건으로 엇갈립니다. 새 런타임 값은 런타임 3개의 첫 호출 p50입니다. 1.5 GB 행, 276 MB 행의 새 런타임 칸, 276 MB V2의 지속 유입과 버스트 값은 이전 /ping입니다. 이 p50에서 빠진 실패는 저빈도 V2 VPC 30회 중 1건(스로틀, 이 시험은 재시도 안 함), 초당 5건 V2 600회 중 2건(504와 내부 오류), 초당 10건 V1 1,200회 중 1건입니다."))
    d.append(t("### Bursts and sustained arrivals", "### 버스트와 지속 유입"))
    rows = [[""] + P]
    for n in ("10", "50", "100"):
        rows.append([t(f"Burst of {n}", f"동시 {n}개")] + [s(f"burst.{k}.{n}.p50") if f"burst.{k}.{n}.p50" in F else t("removed", "제거") for k in K])
    for r in ("1", "5"):
        rows.append([t(f"Sustained {r}/s", f"초당 {r}건")] + [s(f"sus.{k}.{r}.p50") for k in K])
    d.append(table(rows))
    d.append(t(f"Bursts are the median of 3 rounds from a dedicated 8 vCPU driver, with 4 gVisor nodes and 8 Kata nodes holding the image, so node scale-up is not included. A new node adds about {F['scale.gv.total']:.0f} s for gVisor and {F['scale.kt.total']:.0f} s for Kata. MicroVM above its default RunMicrovm quota of 5 per second was removed because the quota, not the platform, set the value; the quota is adjustable and was not raised. V1 is the 276 MB container with the earlier /ping. Warm pools with prepared pools: gVisor {s('burst.gvw.50.p50')} for 50, Kata {s('burst.ktw.40.p50')} for 40, one round. EKS completion is polled, which can add up to 0.5 s at 100. gVisor's p50 grows with size ({s('burst.gv.10.p50')} at 10, {s('burst.gv.100.p50')} at 100), which may be a control path limit; we did not investigate. One request of a burst of 50 failed in the final rounds on V1 with the documented /ping (a 504), a runtime not shown in this table.", f"버스트는 전용 8 vCPU 측정기에서 3라운드 중앙값이며, 이미지를 적재한 gVisor 4노드, Kata 8노드 조건입니다. 노드 증설 시간은 들어 있지 않습니다. 새 노드가 필요하면 gVisor 약 {F['scale.gv.total']:.0f}초, Kata 약 {F['scale.kt.total']:.0f}초가 더 듭니다. MicroVM의 기본 RunMicrovm 쿼터(초당 5건) 초과 구간은 플랫폼이 아니라 쿼터가 값을 정하므로 제거했습니다. 쿼터는 조정 가능하며 올리지 않았습니다. V1은 이전 /ping의 276 MB 컨테이너입니다. Warm Pool: gVisor 50개 {s('burst.gvw.50.p50')}, Kata 40개 {s('burst.ktw.40.p50')}, 1라운드. EKS 완료는 폴링으로 확인해 100개에서 최대 0.5초가 더해질 수 있습니다. gVisor p50은 크기에 따라 늘어나는데(10개 {s('burst.gv.10.p50')}, 100개 {s('burst.gv.100.p50')}) 컨트롤 경로 한계일 수 있으며 조사하지 않았습니다. 최종 라운드에서 문서대로 고친 /ping의 V1(이 표에 없는 런타임)이 동시 50개 중 1건 실패했습니다(504)."))
    d.append(t("### One real task through the Claude Agent SDK", "### Claude Agent SDK 실제 태스크"))
    ag = lambda v: [f"{v['first_p50']:.1f} s", f"{v['first_p90']:.1f} s", f"{v['slow_share'] * 100:.0f}%", f"{v['total_p50']:.1f} s", f"{v['total_p90']:.1f} s", f"{v['total_ci'][0]:.1f} to {v['total_ci'][1]:.1f} s", f"{v['n']}/{v['tried']}"]
    head = ["", t("First message", "첫 메시지"), "p90", t("Over 20 s", "20초 초과"), t("Whole request", "요청 전체"), "p90", t("95% CI of p50", "p50 95% CI"), t("Succeeded", "성공")]
    d.append(table([head] + [[n] + ag(H[k]) for n, k in (("gVisor x86", "gv"), ("gVisor Graviton3", "g3gv"), (t("Kata nested", "Kata 중첩"), "kt"), ("AgentCore V1", "v1"), (t("AgentCore V2, new runtimes", "AgentCore V2, 새 런타임"), "v2"), (t("MicroVMs, new images", "MicroVM, 새 이미지"), "lm"))]))
    d.append(t(f"This table is one same-period shuffled test: two new managed runtimes per option, 10 runs each, so each option gets the same arrival pattern. It is the small coding task and the time includes the harness's final pytest. Model time p50 ranged from {MT[0]:.1f} to {MT[1]:.1f} s across rounds, about 1 s higher on some V2 and MicroVM rounds, and no run failed. EKS is x86, with Graviton3 as a CPU control. EKS nodes keep a warm page cache and managed sandboxes do not, which is part of the difference.", f"이 표는 같은 시기에 순서를 섞은 한 시험입니다. 구성마다 새 관리형 런타임 2개, 각 10회라서 도착 패턴이 같습니다. 작은 코딩 태스크이며 시간에는 하네스의 마지막 pytest가 들어 있습니다. 모델 시간 p50은 라운드별 {MT[0]:.1f}~{MT[1]:.1f}초로 일부 V2, MicroVM 라운드가 약 1초 높았고, 실패한 실행은 없었습니다. EKS는 x86이고 Graviton3가 CPU 대조군입니다. EKS 노드는 페이지 캐시가 채워져 있고 관리형 샌드박스는 그렇지 않은 점도 차이의 일부입니다."))
    d.append(t("#### Mitigations (first message, whole request)", "#### 완화책 (첫 메시지, 요청 전체)"))
    rows = [[t("Mitigation", "완화책"), "V2", "MicroVM"]]
    fm = lambda v: f"{v['first_p50']:.1f} s (p90 {v['first_p90']:.1f}), {v['total_p50']:.1f} s" if v else "n/t"
    rows.append([t("None, new runtime, first 8 runs", "없음, 새 런타임, 앞 8회"), fm(C8["ac-v2"]), fm(C8["lm"])])
    rows.append([t("Map the CLI file before the snapshot", "스냅샷 전 CLI 파일 매핑"), fm(FA["ac-v2-pin|pin"]), fm(FA["lm-pin|pin"])])
    if Q("ac-v2-q2|quiet2"):
        rows.append([t("None, new runtime after a quiet hour", "없음, 조용한 한 시간 후 새 런타임"), fm(Q("ac-v2-q2|quiet2")), fm(Q("lm-q2|quiet2"))])
    if Q("ac-v2-pinq2|quiet2"):
        rows.append([t("CLI file mapping, after a quiet hour", "CLI 파일 매핑, 조용한 한 시간 후"), fm(Q("ac-v2-pinq2|quiet2")), fm(Q("lm-pinq2|quiet2"))])
    rows.append([t("Import, CLI, pytest and a full task at startup", "시작 시 import, CLI, pytest, 전체 태스크 실행"), fm(FA["ac-v2-warm|pkg"]), fm(FA["lm-warm|pkg"])])
    rows.append([t("Run the CLI before the snapshot, first 10 runs", "스냅샷 전 CLI 실행, 첫 10회"), fm(FA["ac-v2-prewarm|first10"]), fm(FA["lm-prewarm|first10"])])
    d.append(table(rows))
    d.append(t(f"Each condition is 8 to 12 runs, a small sample. Mapping runs the CLI once, then maps the file and reads every page before the snapshot. After a quiet hour on V2, runs over 20 s are 0 of 8 with mapping against 5 of 8 without (Fisher p about 0.03). Running the CLI before the snapshot did not help the first runs of a new runtime. Billed memory with the file mapped was not measured. On MicroVM the intervals with and without mapping overlap.", "조건별 8~12회의 작은 표본입니다. 매핑은 스냅샷 전에 CLI를 한 번 실행하고 파일을 매핑해 모든 페이지를 읽어 둡니다. 조용한 한 시간 뒤 V2의 20초 초과는 매핑 8회 중 0회, 없음 8회 중 5회입니다(Fisher p 약 0.03). 스냅샷 전 CLI 실행은 새 런타임의 앞쪽 실행을 줄이지 못했습니다. 매핑 시 과금 메모리는 재지 않았습니다. MicroVM은 매핑 유무의 신뢰 구간이 겹칩니다."))
    d.append(t(f"V1 direct code had no such delay (first message {FA['ac-v1-zip|pkg']['first_p50']:.1f} s, whole request {FA['ac-v1-zip|pkg']['total_p50']:.1f} s). V2 direct code did ({FA['ac-v2-zip|pkg']['first_p50']:.1f} s, {FA['ac-v2-zip|pkg']['total_p50']:.1f} s). Dropping the page cache on EKS nodes shows the same effect at smaller scale: gVisor {F['fair']['dropcache']['eks-x86-gvisor']['first_p50']:.1f} s first message, Kata {F['fair']['dropcache']['eks-x86-kata']['first_p50']:.1f} s. Whole request then becomes gVisor {F['fair']['dropcache']['eks-x86-gvisor']['total_p50']:.1f} s and Kata {F['fair']['dropcache']['eks-x86-kata']['total_p50']:.1f} s. So EKS's advantage here partly reflects a local disk and a warm page cache.", f"V1 코드 직접 배포에는 이 지연이 없었습니다(첫 메시지 {FA['ac-v1-zip|pkg']['first_p50']:.1f}초, 요청 전체 {FA['ac-v1-zip|pkg']['total_p50']:.1f}초). V2 코드 직접 배포에는 있었습니다({FA['ac-v2-zip|pkg']['first_p50']:.1f}초, {FA['ac-v2-zip|pkg']['total_p50']:.1f}초). EKS 노드의 페이지 캐시를 비우면 같은 효과가 작게 나타납니다. 첫 메시지 gVisor {F['fair']['dropcache']['eks-x86-gvisor']['first_p50']:.1f}초, Kata {F['fair']['dropcache']['eks-x86-kata']['first_p50']:.1f}초. 요청 전체는 gVisor {F['fair']['dropcache']['eks-x86-gvisor']['total_p50']:.1f}초, Kata {F['fair']['dropcache']['eks-x86-kata']['total_p50']:.1f}초가 됩니다. 즉 여기서 EKS의 이점 일부는 로컬 디스크와 페이지 캐시 덕분입니다."))
    d.append(t("#### Agents at the same time (whole request)", "#### 동시 실행 에이전트 (요청 전체)"))
    CX = F["fair"]["concurrent"]
    cc = lambda v: f"{v['total_p50']:.1f} s"
    rows = [["", t("5 at once", "동시 5개"), t("20 at once", "동시 20개")]]
    for n, a, b_ in (("gVisor, 4 nodes", CS["eks-x86-gvisor|5"], CS["eks-x86-gvisor|20"]), (t("gVisor Warm Pool, 4 nodes", "gVisor Warm Pool, 4노드"), CS["eks-x86-gvisor-warm-agent|5"], CS["eks-x86-gvisor-warm-agent|20"]), ("Kata, 8 nodes", CS["eks-x86-kata|5"], CS["eks-x86-kata|20"]), (t("Kata Warm Pool, 8 nodes", "Kata Warm Pool, 8노드"), CS["eks-x86-kata-warm-agent|5"], CS["eks-x86-kata-warm-agent|20"]), ("AgentCore V1", CS["ac-v1-np|5"], CS["ac-v1-np|20"]), ("AgentCore V2", CS.get("ac-v2-np|5", CX["ac-v2|5"]), CS.get("ac-v2-np|20", CX["ac-v2|20"])), ("Lambda MicroVMs", CS.get("lm|5", CX["lm|5"]), CS.get("lm|20", CX["lm|20"]))):
        rows.append([n, cc(a), cc(b_)])
    d.append(table(rows))
    d.append(t("No failures. Two runs per size, all from the same dedicated driver. Managed runtimes had seen agent runs, so these are not new-runtime values. V2 and MicroVM ran about 4.5 hours after the others. V2 ran its 5-agent batches first, so its lower value at 20 is not a gain from scale.", "실패는 없었습니다. 크기별 2회이며 모두 같은 전용 측정기에서 쟀습니다. 관리형 런타임은 에이전트를 이미 실행했으므로 새 런타임 값이 아닙니다. V2와 MicroVM은 다른 구성보다 약 4.5시간 늦게 쟀습니다. V2는 동시 5개를 먼저 돌렸으므로 20개의 값이 더 낮아도 규모의 이득으로 볼 수 없습니다."))
    d.append(t("#### Build task (whole request, 8 runs)", "#### 빌드 태스크 (요청 전체, 8회)"))
    rows = [["", t("Whole request", "요청 전체"), "p90", t("95% CI of p50", "p50 95% CI")]]
    for n, k in (("gVisor x86", "eks-x86-gvisor|heavy"), ("AgentCore V1", "ac-v1-np|heavy"), ("Lambda MicroVMs", "lm-fa|heavy"), ("gVisor Graviton3", "eks-g3-gvisor|heavy"), ("Kata metal", "eks-metal-kata|heavy"), ("AgentCore V2", "ac-v2-fa|heavy"), ("Kata nested", "eks-x86-kata|heavy")):
        v = FA[k]
        rows.append([n, f"{v['total_p50']:.1f} s", f"{v['total_p90']:.1f} s", f"{v['total_ci'][0]:.1f} to {v['total_ci'][1]:.1f} s"])
    d.append(table(rows))
    d.append(t("MicroVM sees 8 vCPU with a 2 vCPU billed baseline, and the rest are limited to 2 vCPU, so this favours it on parallel work; use above the baseline may add charges, as in the AWS pricing example. gVisor's root filesystem is memory-backed here, which helps its file work and counts against pod memory. V2 and MicroVM ran on runtimes that already had 12 runs. Managed CPU generations vary by session, x86 EKS is a different CPU, and these rows were not run in one shuffled period. Do not rank values whose intervals overlap.", "MicroVM은 기준 2 vCPU로 과금하면서 8 vCPU가 보이고 나머지는 2 vCPU로 제한되므로 병렬 작업에서 유리하며, AWS 가격 예시처럼 기준을 넘는 사용은 추가 과금될 수 있습니다. gVisor는 루트 파일시스템이 메모리 기반이라 파일 작업에 유리하고 Pod 메모리를 씁니다. V2와 MicroVM은 이미 12회 실행한 런타임입니다. 관리형은 세션마다 CPU 세대가 다르고 x86 EKS와 CPU가 다르며, 이 행들은 한 번에 순서를 섞어 잰 것이 아닙니다. 구간이 겹치는 값끼리는 순위를 매기지 마세요."))
    d.append(t("### Workloads and syscalls", "### 워크로드와 시스템 콜"))
    d.append(t("Compare within one CPU. x86 runs on m8i.2xlarge. Managed values are Graviton3 sessions only. Times in seconds, lower is better.", "같은 CPU끼리 비교하세요. x86은 m8i.2xlarge입니다. 관리형은 Graviton3 세션만 집계했습니다. 단위는 초이고 낮을수록 좋습니다."))
    cols = [("rc", "runc x86"), ("gv", "gVisor x86"), ("kt", "Kata nested"), ("ktm", "Kata metal"), ("g3rc", "runc G3"), ("g3gv", "gVisor G3")]
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
    d.append(t(f"gVisor's fast disk numbers are not comparable: its root filesystem is a memory-backed overlay here ({F['suite.gv.disk_seq.write_MBps']:,.0f} MB/s write with fsync). arm64 gVisor was also slower on pure Python ({F['suite.g3gv.cpu_python.seconds'] / F['suite.g3rc.cpu_python.seconds']:.1f}x runc on Graviton3), which x86 did not show. We did not analyze why.", f"gVisor의 빠른 디스크 수치는 비교할 수 없습니다. 여기서는 루트 파일시스템이 메모리 기반 오버레이입니다(fsync 쓰기 {F['suite.gv.disk_seq.write_MBps']:,.0f} MB/s). arm64 gVisor는 순수 Python도 느렸는데(Graviton3에서 runc의 {F['suite.g3gv.cpu_python.seconds'] / F['suite.g3rc.cpu_python.seconds']:.1f}배), x86에서는 나타나지 않았습니다. 원인은 분석하지 않았습니다."))
    d.append(t("### Reclamation and lifecycle", "### 회수와 수명 주기"))
    i1, i2 = F["idle.v1np"], F["idle.v2np"]
    d.append(table([
        ["", t("Observed", "관측")],
        [t("V2 with 60 s idle timeout", "V2, 유휴 60초 설정"), t(f"Alive at 60 s ({i2['60']['alive']}/{i2['60']['n']}), gone at 70 s ({i2['70']['alive']}/{i2['70']['n']} alive)", f"60초 생존 {i2['60']['alive']}/{i2['60']['n']}, 70초 생존 {i2['70']['alive']}/{i2['70']['n']}")],
        [t("V1 with 60 s idle timeout", "V1, 유휴 60초 설정"), t(f"Alive at 60 s ({i1['60']['alive']}/{i1['60']['n']}), {i1['70']['alive']}/{i1['70']['n']} alive at 70 s, gone at 90 s ({i1['90']['alive']}/{i1['90']['n']} alive)", f"60초 생존 {i1['60']['alive']}/{i1['60']['n']}, 70초 생존 {i1['70']['alive']}/{i1['70']['n']}, 90초 생존 {i1['90']['alive']}/{i1['90']['n']}")],
        [t("AgentCore explicit stop, same session id", "AgentCore 명시적 중지 후 같은 세션 ID"), t("New instance, memory and disk gone, 5/5 on V1 and V2", "새 인스턴스, 메모리와 디스크 사라짐, V1과 V2 모두 5/5")],
        [t("MicroVM idle policy 60 s, then suspended 120 s", "MicroVM 유휴 정책 60초, 일시 중지 120초"), t(f"SUSPENDED after {F['mvidle.suspend_p50']:.0f} s, TERMINATED after {F['mvidle.term_p50']:.0f} s", f"{F['mvidle.suspend_p50']:.0f}초 후 SUSPENDED, {F['mvidle.term_p50']:.0f}초 후 TERMINATED")],
        [t("MicroVM resume", "MicroVM 재개"), t(f"API {s('susp.0MB.api.resume_p50')}, traffic {s('susp.0MB.traffic.resume_p50', 1)}. Memory and disk kept in every run, up to 2 GB held", f"API {s('susp.0MB.api.resume_p50')}, 트래픽 {s('susp.0MB.traffic.resume_p50', 1)}. 2 GB까지 모든 실행에서 메모리와 디스크 유지")],
        [t("EKS sandbox delete to pod gone", "EKS 샌드박스 삭제부터 Pod 제거"), f"gVisor {s('gone.gv.p50', 1)}, Kata {s('gone.kt.p50', 1)}"],
        [t("EKS new node to first sandbox, then node removal", "EKS 새 노드부터 첫 샌드박스, 노드 제거"), t(f"gVisor {F['scale.gv.total']:.0f} s and {F['scale.gv.removed']:.0f} s. Kata {F['scale.kt.total']:.0f} s including {F['scale.kt.install']:.0f} s kata-deploy, and {F['scale.kt.removed']:.0f} s. Managed node group, Karpenter n/t", f"gVisor {F['scale.gv.total']:.0f}초, {F['scale.gv.removed']:.0f}초. Kata {F['scale.kt.total']:.0f}초(kata-deploy {F['scale.kt.install']:.0f}초 포함), {F['scale.kt.removed']:.0f}초. 관리형 노드 그룹 기준, Karpenter n/t")],
    ]))
    d.append(t(f"Deploy times for comparison: EKS cluster and nodes about 19 minutes by one Terraform apply, not counting runtime install; MicroVM image about {F['deploy.lm']:.0f} s; AgentCore in the packaging table.", f"비교용 배포 시간: EKS 클러스터와 노드는 Terraform 적용 1회에 약 19분(런타임 설치 제외), MicroVM 이미지 약 {F['deploy.lm']:.0f}초, AgentCore는 패키징 표를 보세요."))
    d.append(t("### Long requests with no bytes sent until the end", "### 끝날 때까지 바이트를 보내지 않는 장기 요청"))
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
    d.append(t("A handful of runs that locate a boundary. AgentCore clients use TCP keepalive. Requests through a NAT gateway without keepalive can be dropped at its documented 350 s idle timeout on any platform, so we removed those runs from the comparison; turn keepalive on in your client. The failure near 900 s matches AgentCore's documented 15 minute synchronous limit. AgentCore documents 60 minutes for streaming, not tested to that length.", "경계를 찾기 위한 소수의 실행입니다. AgentCore 클라이언트는 TCP keepalive를 켰습니다. keepalive 없이 NAT Gateway를 거치면 문서상 유휴 타임아웃 350초에 어느 플랫폼에서나 끊길 수 있어, 그 실행은 비교에서 뺐습니다. 클라이언트에서 keepalive를 켜세요. 900초 부근의 실패는 AgentCore 문서의 동기 15분 한도와 일치합니다. 다만 오류 문구는 런타임 초기화 시간 초과로 나옵니다. 문서의 스트리밍 한도 60분까지는 시험하지 않았습니다."))
    d.append(t("### Cost scenarios, monthly compute in USD", "### 비용 시나리오, 월 컴퓨트 비용(USD)"))
    rows = [[t("Scenario", "시나리오"), t("Avg concurrent", "평균 동시"), "V1", "V2", t("MicroVM, 2 GB to tested 4 GB", "MicroVM, 2 GB부터 시험한 4 GB까지"), t("gVisor, autoscaled", "gVisor 자동 축소"), t("gVisor, peak", "gVisor 피크 고정"), t("Kata, autoscaled", "Kata 자동 축소"), t("Kata, peak", "Kata 피크 고정"), t("V1, no stop", "V1, 중지 안 함"), t("V2, no stop", "V2, 중지 안 함"), t("gVisor, Graviton3", "gVisor, Graviton3"), t("gVisor, high memory", "gVisor, 메모리 높음")]]
    for k in ("interactive", "code_exec", "coding", "build_heavy", "steady"):
        v = C[k]
        lo, hi = sorted((v["microvm_always_running"], v["microvm_tested_size"]))
        rows.append([v["label"], f"{v['avg_concurrency']:.0f}", f"{v['agentcore_v1']:,.0f}", f"{v['agentcore_v2']:,.0f}", f"{lo:,.0f} to {hi:,.0f}" if lang == "en" else f"{lo:,.0f}~{hi:,.0f}"] + [f"{v[m]:,.0f}" for m in ("eks_gvisor_autoscaled", "eks_gvisor_peak", "eks_kata_autoscaled", "eks_kata_peak", "agentcore_v1_no_stop", "agentcore_v2_no_stop", "eks_gvisor_autoscaled_graviton3", "eks_gvisor_autoscaled_mem_high")])
    d.append(table(rows))
    ck = F["cost"]["aws_example_check"]
    d.append(t(f"The scenarios are illustrations in `analysis/cost_model.py`; change them and rerun. Prices were checked against the public pages and the Pricing API on 2026-11-03, and the formulas reproduce AWS's worked examples (V2 ${ck['agentcore_v2_support_monthly_1m']:,.0f} against ${ck['aws_says_agentcore_v2']:,}, MicroVM ${ck['microvm_ci_monthly_10k']:,.0f} against ${ck['aws_says_microvm_ci']:,.0f}). AgentCore idle memory and EKS overhead are measured. V1 and V2 assume the app stops each session; the no-stop columns add the default 15 minute idle tail at measured tail memory, and EKS has the same need to delete idle sandboxes. MicroVM use above its baseline may add charges. EKS includes the control plane, 2 system nodes, NAT Gateway and gp3 disks; on an existing cluster the interactive gVisor figure falls to ${C['interactive']['eks_gvisor_autoscaled_existing_cluster']:,.0f}. Excluded everywhere: LLM tokens, per-GB NAT and transfer, logs, staff, discounts. For the interactive shape, autoscaled gVisor and V2 break even near {be} average concurrent sessions, {F['cost']['break_even_concurrency_interactive_gvisor_warm30_vs_v2']} with 30 warm pods, and never when sized for peak. These are first crossings; node counts step, so gVisor stays cheaper from {F['cost']['gvisor_stays_cheaper_from']}, or {F['cost']['gvisor_warm30_stays_cheaper_from']} with 30 warm pods. MicroVM suspend adds snapshot write and read charges and pays off only when each idle period passes about {F['cost']['suspend_breakeven_idle_s_smallest'] / 60:.0f} minutes at 2 GB, so the table shows no suspend. These are estimates, not a bill.", f"시나리오는 `analysis/cost_model.py`의 예시이며, 바꿔서 다시 돌릴 수 있습니다. 가격은 2026-11-03에 공개 페이지와 Pricing API로 대조했고, 공식은 AWS 계산 예시를 재현합니다(V2 ${ck['agentcore_v2_support_monthly_1m']:,.0f}, AWS ${ck['aws_says_agentcore_v2']:,}. MicroVM ${ck['microvm_ci_monthly_10k']:,.0f}, AWS ${ck['aws_says_microvm_ci']:,.0f}). AgentCore 유휴 메모리와 EKS 오버헤드는 측정값입니다. V1, V2는 앱이 세션을 중지한다고 가정했고, 중지 안 함 열은 기본 15분 유휴 구간을 측정된 유휴 메모리로 더한 값입니다. EKS도 유휴 샌드박스를 지워야 하는 것은 같습니다. MicroVM은 기준을 넘는 사용에 추가 과금될 수 있습니다. EKS에는 컨트롤 플레인, 시스템 노드 2대, NAT Gateway, gp3 디스크가 들어 있고, 기존 클러스터라면 대화형 gVisor는 ${C['interactive']['eks_gvisor_autoscaled_existing_cluster']:,.0f}로 내려갑니다. 모든 구성에서 LLM 토큰, GB당 NAT와 전송, 로그, 인건비, 할인을 뺐습니다. 대화형 시나리오에서 gVisor 자동 축소와 V2의 손익 분기는 평균 동시 약 {be}개, Warm Pod 30개를 두면 {F['cost']['break_even_concurrency_interactive_gvisor_warm30_vs_v2']}개이며, 피크 고정이면 없습니다. 처음 넘는 지점이며 노드 수가 계단식이라, 계속 gVisor가 싼 것은 {F['cost']['gvisor_stays_cheaper_from']}개, Warm Pod 30개면 {F['cost']['gvisor_warm30_stays_cheaper_from']}개부터입니다. MicroVM 일시 중지는 스냅샷 쓰기와 읽기 비용이 붙어 2 GB 기준 유휴 구간이 약 {F['cost']['suspend_breakeven_idle_s_smallest'] / 60:.0f}분을 넘어야 이득이므로 표에는 일시 중지 없는 값을 적었습니다. 추정치이며 청구서가 아닙니다."))
    d.append(t("### Security defaults: what a workload can see and reach", "### 보안 기본값: 워크로드가 보고 닿는 것"))
    S = F["security"]
    cfg = [("eks-x86-gvisor/default"), ("eks-x86-kata/default"), ("ac-v1/default"), ("ac-v2/default"), ("lm/default")]
    yn = lambda b: t("yes", "예") if b else t("no", "아니오")
    d.append(table([
        [t("Check", "점검")] + P,
        ["CAP_SYS_ADMIN"] + [yn(int(S[c]["cap_eff"], 16) & (1 << 21)) for c in cfg],
        [t("Role listed through metadata", "메타데이터로 역할 조회")] + [yn(S[c]["imds"]["role_listed"]) for c in cfg],
        [t("Service account token mounted", "SA 토큰 마운트")] + [yn(S[c]["k8s_sa_token_mounted"]) for c in cfg],
        [t("Kubernetes API reachable", "Kubernetes API 연결")] + [yn(True) if S[c]["k8s_api_tcp"] == "open" else "N/A" for c in cfg],
        [t("Peer sandbox reachable", "다른 샌드박스 연결")] + [yn(S[c]["peer_sandbox_tcp"] == "open") if S[c]["peer_sandbox_tcp"] != "not-tested" else t("undetermined", "판정 불가") for c in cfg],
        [t("Internet egress in this setup", "이번 구성의 인터넷 외부 통신")] + [yn(S[c]["egress_internet_https"] == "open") for c in cfg],
        ["io_uring"] + [t("absent", "없음") if S[c]["io_uring_setup"]["errno"] == "ENOSYS" else t("callable", "호출 가능") for c in cfg],
        ["/dev/kvm"] + [yn(S[c]["dev_kvm"]) for c in cfg],
    ]))
    v = S["eks-x86-gvisor-warm/np-enforced"]
    d.append(t(f"With VPC CNI network policy turned on, a warm pool sandbox got: peer {v['peer_sandbox_tcp']}, Kubernetes API {v['k8s_api_tcp']}, internet {v['egress_internet_https']}, Pod Identity endpoint {v['extra']['pod_identity_169_254_170_23']}. The policy Agent Sandbox generates excludes 169.254.0.0/16, so AWS credential lookup failed with CredentialRetrievalError on gVisor and Kata. Add an exception for the Pod Identity endpoint, or inject credentials another way. A Sandbox created directly, without a SandboxTemplate, gets no policy and stayed open.", f"VPC CNI NetworkPolicy를 켜자 Warm Pool 샌드박스에서: 다른 샌드박스 {v['peer_sandbox_tcp']}, Kubernetes API {v['k8s_api_tcp']}, 인터넷 {v['egress_internet_https']}, Pod Identity 엔드포인트 {v['extra']['pod_identity_169_254_170_23']}. Agent Sandbox가 만든 정책은 169.254.0.0/16을 제외하므로, gVisor와 Kata 모두 AWS 자격 증명 조회가 CredentialRetrievalError로 실패했습니다. Pod Identity 엔드포인트에 예외를 넣거나 자격 증명을 다른 방식으로 주입해야 합니다. SandboxTemplate 없이 직접 만든 Sandbox는 정책이 없어 그대로 열려 있었습니다."))
    d.append(t("These are benign checks of defaults from inside a sandbox, not a penetration test, and say nothing about escape resistance. The role seen through metadata is the session's execution role. Managed sessions share the same link-local addresses, so our cross-session test could not determine isolation, and we do not claim it.", "샌드박스 안에서 기본값을 확인한 무해한 점검이며 침투 시험이 아닙니다. 탈출 내성에 대해서는 아무것도 말하지 않습니다. 메타데이터로 보이는 역할은 그 세션의 실행 역할입니다. 관리형 세션은 같은 링크 로컬 주소를 쓰므로 세션 간 시험으로는 격리를 판정할 수 없었고, 격리를 주장하지 않습니다."))
    d.append(t("EKS ran as tested, not hardened. The AWS blog series recommends Pod Security restricted, non-root, dropped capabilities and no service account token; we did not apply them in this table. Warm pool templates did not mount the token. We recorded Pod Identity reachability only with network policy on (timeout), not in the default state. MicroVM internet egress was requested explicitly through its connector.", "EKS는 시험한 그대로이며 강화하지 않았습니다. AWS 블로그 시리즈는 Pod Security restricted, non-root, capability 제거, SA 토큰 끄기를 권장하며, 이 표에는 적용하지 않았습니다. Warm Pool 템플릿은 토큰을 마운트하지 않았습니다. Pod Identity 도달 여부는 네트워크 정책을 켠 상태(시간 초과)만 기록했고, 기본 상태는 기록하지 않았습니다. MicroVM의 인터넷 외부 통신은 커넥터로 명시적으로 요청했습니다."))
    d.append(t("### Observability with no extra configuration", "### 추가 설정 없는 관측성"))
    d.append(table([
        ["", "gVisor / Kata (EKS)", "AgentCore V1 / V2", "Lambda MicroVMs"],
        [t("App logs", "앱 로그"), t("kubectl logs while the pod lives, HTTP 404 after delete", "Pod가 있는 동안 kubectl logs, 삭제 후 HTTP 404"), t("CloudWatch, automatic", "CloudWatch 자동"), t("CloudWatch, with an execution role", "실행 역할이 있으면 CloudWatch")],
        [t("Platform metrics", "플랫폼 지표"), t("Nothing in this setup. EKS add-ons such as Container Insights were not installed or evaluated", "이번 구성에는 없음. Container Insights 같은 EKS 애드온은 설치, 평가하지 않음"), "Invocations, Sessions, Latency, Throttles, OverheadLatency, vCPU, memory", t("No service metrics in a full scan of the account's CloudWatch (log ingestion only)", "계정 CloudWatch 전체 조회에서 서비스 지표 없음(로그 수신 지표만)")],
        [t("Per-session usage", "세션별 사용량"), t("Build it", "직접 구성"), t("USAGE_LOGS after one delivery setting, 1 s granularity", "전달 설정 1회 후 USAGE_LOGS, 1초 단위"), t("Compute from run time", "실행 시간으로 계산")],
        [t("Control plane logs", "컨트롤 플레인 로그"), t("All 5 types off by default", "5종 모두 기본 꺼짐"), "CloudTrail (doc)", "CloudTrail (doc)"],
    ]))
    d.append(t("### Density and environment", "### 밀도와 실행 환경"))
    d.append(t(f"Host memory per idle sandbox: runc {F['density.rc.mb']:.0f} MB, gVisor {F['density.gv.mb']:.0f} MB, Kata {F['density.kt.mb']:.0f} MB. Kata's RuntimeClass adds a 250m CPU pod overhead, so with a 250m request a node holds roughly half as many sandboxes.", f"유휴 샌드박스당 호스트 메모리: runc {F['density.rc.mb']:.0f} MB, gVisor {F['density.gv.mb']:.0f} MB, Kata {F['density.kt.mb']:.0f} MB. Kata의 RuntimeClass는 Pod당 CPU 250m를 더하므로, 요청 250m 기준 노드당 수용량이 절반 정도로 줄어듭니다."))

    d.append(t("## Method", "## 방법"))
    d.append(t("""- **Same app.** `app/` is one image with the Claude Agent SDK. MicroVMs build `FROM` that image. EKS and AgentCore pull it directly. Sandboxes are limited to 2 vCPU and 8 GiB, except MicroVMs at a 4 GB, 2 vCPU billed baseline that see 8 vCPU.
- **Same region.** Everything runs in `us-east-1`, including the driver. Paths still differ: EKS is reached on the Pod IP, managed services on public endpoints.
- **Same definition.** Timing starts just before the first call that asks for a sandbox and ends when the app answers. Agent readiness is measured separately.
- **Controls.** runc on the same nodes, gVisor and runc on Graviton3 to match the managed CPU, and Kata on `m8i.metal-48xl` to separate nested virtualization from Kata itself.
- **No capacity or quota penalty.** Results set by a quota or too few nodes were left out or measured again.
- **Order and failures.** The headline agent and cold start tables shuffle backends in each cycle so that none owns a time of day. Builds, mitigations and metal ran in their own periods. Failures are recorded and counted; only failures are left out of timing, and slow runs stay in.
- **Claims.** `analysis/verify_claims.py` fails if a claim stops holding.""", """- **같은 앱.** `app/`는 Claude Agent SDK가 든 이미지 하나입니다. MicroVM은 이 이미지를 `FROM`으로 빌드하고, EKS와 AgentCore는 그대로 가져옵니다. 샌드박스 한도는 2 vCPU, 8 GiB이며 MicroVM만 과금 기준 4 GB, 2 vCPU에 8 vCPU가 보입니다.
- **같은 리전.** 측정기까지 모두 `us-east-1`입니다. 경로 차이는 남습니다. EKS는 Pod IP로, 관리형은 공용 엔드포인트로 호출합니다.
- **같은 정의.** 샌드박스를 요청하는 첫 호출 직전부터 앱이 답할 때까지 잽니다. 에이전트 준비 시간은 따로 잽니다.
- **대조군.** 같은 노드의 runc, 관리형과 같은 CPU의 Graviton3 위 gVisor와 runc, 중첩 가상화를 분리하기 위한 `m8i.metal-48xl` 위 Kata.
- **용량과 쿼터의 불이익 없음.** 쿼터나 노드 부족이 정한 결과는 빼거나 재측정했습니다.
- **순서와 실패.** 대표 에이전트와 콜드 스타트 표는 사이클마다 백엔드 순서를 섞었습니다. 빌드, 완화책, 메탈은 각자의 시기에 돌렸습니다. 실패도 기록하고 집계하며, 시간 집계에서는 실패만 뺍니다. 느린 실행은 그대로 둡니다.
- **주장.** `analysis/verify_claims.py`는 주장이 깨지면 실패합니다."""))
    d.append(t("### Experiments", "### 실험과 코드"))
    d.append(table([
        [t("What", "내용"), t("Code", "코드")],
        [t("Cold start, image size, start-up work, first session on a new runtime", "콜드 스타트, 이미지 크기, 초기화, 새 런타임 첫 세션"), "`cold_start`, `deploy.py --which fresh`"],
        [t("Packaging and network mode", "패키징과 네트워크 모드"), "`deploy.py --which pkg`, `deploy.py --which balance`"],
        [t("Round trip on an open sandbox", "열린 샌드박스 왕복"), "`warm_latency`"],
        [t("Workloads, syscalls, disk, network", "워크로드, 시스템 콜, 디스크, 네트워크"), "`bench_suite`, `net_suite`"],
        [t("Claude Agent SDK task, first versus repeat start", "Claude Agent SDK 태스크, 첫 실행과 반복"), "`agent_e2e`, `agent_spaced`, `agent_concurrent`, `agent_first_vs_repeat`, `scripts/chain_same.sh`, `scripts/chain_quiet2.sh`"],
        [t("Bursts, sustained arrivals", "버스트, 지속 유입"), "`burst`, `sustained`"],
        [t("Reclamation, state wipe, suspend and resume, node scale", "회수, 상태 초기화, 일시 중지와 재개, 노드 스케일"), "`idle_reclaim`, `state_wipe`, `suspend_resume`, `microvm_idle_policy`, `node_scale`, `scripts/kata_scale.py`"],
        [t("AgentCore billing inputs", "AgentCore 과금 입력"), "`usage_sessions`, `usage_agent`, `analysis/fetch_usage.py`"],
        [t("Observability audit", "관측성 점검"), "`ops_experiments.py observability`"],
        [t("Security defaults", "보안 기본값"), "`security`, `cross_session`"],
        [t("Density, CPU census", "밀도, CPU 분포"), "`ops_experiments.py density`, `hw_census`"],
        [t("Long requests", "장기 요청"), "`long_request`"],
        [t("First touch of files and tools", "파일과 도구의 첫 접근"), "`first_touch`"],
    ]))
    d.append(t("## Limits of this test", "## 이 실험의 한계"))
    d.append(t("""- One region, two days, one account, one application. Results can change with region, quotas, capacity and time. The first-read result depends on this SDK's large CLI binary.
- Network paths differ between platforms, so round trips are not a pure runtime comparison.
- The cause of the slow first read is our interpretation, not a statement from AWS.
- Kata ran with its default virtio-fs. Block-device rootfs and memory-backed work directories were not tested.
- Not tested: 8 hour and 14 day sessions, Karpenter, Spot, gVisor on KVM, raised MicroVM quotas, EKS hardening options, session storage, X-Ray traces, Seoul or other regions.
- Some follow-ups have small samples (8 to 12 runs), so read their confidence intervals.
- Security results describe defaults and are not a statement about escape resistance.
- Cost scenarios use assumed traffic. The AgentCore committed price status could not be confirmed and is not used.
- `results/raw/` also keeps runs left out of the tables, including the invalid `cold_uncached.jsonl`.""", """- 한 리전, 이틀, 한 계정, 앱 하나입니다. 결과는 리전, 쿼터, 용량, 시간에 따라 달라질 수 있습니다. 첫 읽기 결과는 이 SDK의 큰 CLI 바이너리에 좌우됩니다.
- 플랫폼마다 네트워크 경로가 달라 왕복은 런타임만의 비교가 아닙니다.
- 느린 첫 읽기의 원인은 저희 해석이며 AWS의 설명이 아닙니다.
- Kata는 기본 virtio-fs로 돌렸습니다. 블록 디바이스 rootfs와 메모리 기반 작업 디렉터리는 시험하지 않았습니다.
- 시험하지 않은 것: 8시간과 14일 세션, Karpenter, Spot, KVM 플랫폼의 gVisor, MicroVM 쿼터 증설 후, EKS 강화 옵션, 세션 스토리지, X-Ray 트레이스, 서울과 다른 리전.
- 일부 후속 시험은 표본이 적습니다(8~12회). 신뢰 구간을 함께 보세요.
- 보안 결과는 기본값 설명이며 탈출 내성에 대한 진술이 아닙니다.
- 비용 시나리오의 트래픽은 가정입니다. AgentCore 약정 가격은 상태를 확인하지 못해 쓰지 않았습니다.
- `results/raw/`에는 표에서 뺀 실행도 남아 있습니다. `cold_uncached.jsonl`은 무효 실험입니다."""))
    d.append(t("## Layout and reproduction", "## 구성과 재현"))
    d.append("""```
app/        """ + t("agent image, workloads, probes", "에이전트 이미지, 워크로드, 프로브") + """
bench/      """ + t("driver: backends, experiments, deployment", "측정기: 백엔드, 실험, 배포") + """
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
python3 analysis/analyze.py && python3 analysis/cost_model.py && python3 analysis/facts.py
python3 analysis/verify_claims.py && python3 analysis/make_readme.py
```""")
    d.append(t("**This is a disposable test bed, not a reference architecture.** The driver has cluster-admin, a privileged helper runs on nodes, the app's endpoint is unauthenticated inside the VPC, IAM is broad, and the EKS API endpoint is public. See the comments in `infra/terraform/iam.tf`. Delete it when you finish.", "**이것은 쓰고 버리는 시험 환경이며 참조 아키텍처가 아닙니다.** 드라이버는 cluster-admin이고, 노드에 특권 도우미가 돌며, 앱 엔드포인트는 VPC 안에서 인증이 없고, IAM도 넓고, EKS API 엔드포인트가 공개되어 있습니다. `infra/terraform/iam.tf`의 주석을 참고하세요. 끝나면 삭제하세요."))
    return "\n\n".join(d) + "\n"


(ROOT / "README.md").write_text(render("en"))
(ROOT / "README.ko.md").write_text(re.sub(r"(\d) to (\d)", r"\1~\2", re.sub(r"(?<![A-Za-z])(\d[\d,.]*) s(?![A-Za-z0-9])", r"\1초", render("ko"))))
print("README written", len(render("en")), len(render("ko")))
