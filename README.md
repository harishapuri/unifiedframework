# Unified CRC + ZeroGuard + InfraAgent gate

GitHub: [harishapuri/unifiedframework](https://github.com/harishapuri/unifiedframework)

One closed-loop CI/CD decision system. A Checkov scan and a telemetry window go in. **One pick** comes out: go, wait, or stop — plus fused scores and a SHA-256 audit row.

This repo is the **shared library and fused demo**. Plane products clone or vendor it; they do not reimplement the bus.

```bash
git clone https://github.com/harishapuri/unifiedframework.git
cd unifiedframework
```

## Plane repos (each is its own GitHub project)

| GitHub | Paper / plane | Local demo |
| --- | --- | --- |
| [CICD_Compliance](https://github.com/harishapuri/CICD_Compliance) | CRC (207) — rules / CI-CD | http://127.0.0.1:8871/ · `python3 -m cicd.demo` |
| [infraagent](https://github.com/harishapuri/infraagent) | InfraAgent (1239) — stay-up | http://127.0.0.1:8872/ · `python3 -m infra.demo` |
| [ZeroGuard](https://github.com/harishapuri/ZeroGuard) | ZeroGuard (2143) — trust | http://127.0.0.1:8873/ · `python3 -m zeroguard.demo` |
| [MAWS](https://github.com/harishapuri/MAWS) | MAWS hive orchestrator | http://127.0.0.1:8874/ · `python3 -m maws.demo` |
| **This repo** | Fused gate (all three) | http://127.0.0.1:8877/ · `python3 -m framework.webdemo` |

Each plane repo vendors a snapshot of this library under `vendor/unified_framework`. Set `UNIFIED_FRAMEWORK` to this checkout to override vendor. Each plane GitHub repo has its own `ARCHITECTURE.md`, `INDUSTRY_VS_OURS.md`, and `PLAN.md` written for that plane. This repo’s copies: [ARCHITECTURE.md](ARCHITECTURE.md), [INDUSTRY_VS_OURS.md](INDUSTRY_VS_OURS.md), [PLAN.md](PLAN.md).

The three source papers are cooperating planes, not three products:

| Paper | Plane | What it answers |
| --- | --- | --- |
| CRC (207) | Rules | Did the scanner find trouble in code, image, or setup? |
| ZeroGuard (2143) | Trust | Open doors, extra permissions, unusual grants? |
| InfraAgent (1239) | Stay-up | Will it fail soon, or will we run out of room? |

Join rule: CRC policy adherence **η** multiplies both ZeroGuard posture **Ψ** and InfraAgent posture **Ω**. Then one DSA gate speaks. A security suggestion beats a rollout suggestion. Suggested patches are never auto-applied.

The **[MAWS](https://github.com/harishapuri/MAWS)** repo is the supervisor hive (`iter_flow` delegates to `maws.supervisor.iter_maws` when that package is on disk). It does not change the scores.

This folder is the **Checkov-fed gate** (stdlib Python). A separate bank-chatbot page can illustrate the same mechanism as a **story**. The story is not a measured evaluation. Do not file story-page numbers as results.

---

## What this is (and is not)

**This is**

- Real Checkov JSON in (`checkov -o json`)
- Optional Datadog / Prometheus-shaped metrics, including demand history
- Three heuristic scores on one typed bus
- One gate: `ALLOW` / `WARN` / `BLOCK_BUILD` / `BLOCK_DEPLOYMENT` / `ROLLBACK`
- A hash-chained audit file, plus a sidecar for what actually happened later
- Shadow mode by default (never fails CI until you pass `--enforce`)

**This is not**

- A production T-GAN, Prophet, or Code Llama
- A measured accuracy, false-alarm, MTTD, or dollar-saved study
- Auto-merge of chatbot SQL or IAM
- Proof that a fictional “Northstar Bank” exists — that name is the demo story only

Paper-reported F1 / MTTD / cost figures belong to the published research systems. Do not paste them into a petition as if this repo measured them. Use the scorecard on **your** incidents before `--enforce`.

---

## Upstream to downstream

```
Upstream     Commit / image / IaC / runtime / demand history
                ↓
Ingest       Checkov JSON + Datadog/Prometheus alias mapper
                ↓
Planes       CRC (η)   ·   ZeroGuard (Ψ)   ·   InfraAgent (Ω)
                ↓
Fuse         Typed bus + orchestrator
                ↓
Decide       DSA  →  go / wait / stop
                ↓
Downstream   Suggest only  ·  signed audit  ·  traffic switch last
                ↓
Later        record-outcome  →  scorecard  →  maybe --enforce
```

Customers (or production traffic) move **only after** go. If chatbot or fraud would stop, they stay on the old copy.

Full figures: [ARCHITECTURE.md](ARCHITECTURE.md). Industry comparison: [INDUSTRY_VS_OURS.md](INDUSTRY_VS_OURS.md). Module plan: [PLAN.md](PLAN.md).

---

## Sites in this repo

| Port | Command | What it is |
| --- | --- | --- |
| **8800** | `python3 -m hub` | Home + completed-flow GIF. Links to the gate demo. |
| **8877** | `python3 -m framework.webdemo` | **Proof.** Real pipeline, staged. Checkov fixtures. Go / wait / stop. |

Start from this folder (Python 3.9+, no extra packages):

```bash
python3 -m framework.webdemo    # http://127.0.0.1:8877/
python3 -m hub                  # http://127.0.0.1:8800
```

If the three plane repos sit next to this checkout on the Desktop, `framework.webdemo` can start their demos on 8871–8873. Each plane page is solo; this page still shows all three planes.

---

## CLI — Checkov → one gate

Stdlib only. Default is **shadow** (exit 0 even on BLOCK). `--enforce` exits `2` on BLOCK.

```bash
# Fail: open SG + public bucket + wildcard IAM + hot traffic
python3 -m framework.cli examples/checkov_fail.json \
  --telemetry examples/telemetry_hot.json \
  --service chatbot-api

# Pass
python3 -m framework.cli examples/checkov_pass.json \
  --telemetry examples/telemetry_ok.json \
  --service chatbot-api

# Your scan from a git repo — copy examples/scan_target.placeholder.json and set git_url
python3 -m framework.cli --scan examples/scan_target.placeholder.json

# Or a Checkov file you already have
checkov -d infra/ -o json > /tmp/checkov.json
python3 -m framework.cli /tmp/checkov.json \
  --telemetry /tmp/metrics.json \
  --service chatbot-api

# Datadog-shaped series + Holt on demand history
python3 -m framework.cli examples/checkov_pass.json \
  --telemetry examples/telemetry_datadog.json \
  --service chatbot-api
```

JSON shape: `{ crc, zeroguard, infraagent, governance }`.

Audit rows append to `data/audit.jsonl` (hash-linked). Bus events sit beside it as `data/audit.jsonl.bus`. Both are gitignored.

### After a real release — score the pick

The signed file is never rewritten. Outcomes go in `data/outcomes.jsonl`.

```bash
python3 -m framework.cli record-outcome <hash-prefix> incident --note "chatbot 5xx"
python3 -m framework.cli record-outcome <hash-prefix> ok
python3 -m framework.cli scorecard
```

Actuals: `ok` | `incident` | `rollback` | `brownout`.

`--enforce` only when scorecard says `ready_for_enforce` (enough labels, no missed stops). That is the only honest path from demo to CI.

---

## Browser demo (port 8877)

`python3 -m framework.webdemo` streams the **same** `framework/flow.py` used by the CLI. The page is not a fake animation on top of a precomputed blob.

| Scenario | Checkov | Telemetry | Gate |
| --- | --- | --- | --- |
| Pass | clean | calm | `ALLOW` |
| Capacity warn | clean | demand > capacity | `WARN` |
| Rising errors | clean | φ_6h high, φ_1h not | `WARN` |
| Fail | open SG + public bucket + wildcard IAM | hot | `BLOCK_DEPLOYMENT` |
| Secure but hot | clean | hot | `ROLLBACK` (stay-up alone) |
| Open SG, calm | broken IaC | calm | `BLOCK_DEPLOYMENT` (rules/trust alone) |
| Severe outage | clean | φ_1h > 0.85 | `ROLLBACK` |

Play one story, or play all. Demo audit is `data/demo_audit.jsonl` so it never mixes with CLI/CI. Delete it to reset the demo chain.

If the page says **log is broken**, the hash chain was forked (two writers). The gate now locks, reloads the tip, and repairs a forked file by keeping the valid prefix (`*.broken` holds the rest). A Stop decision is not a broken log.

---

## What the gate computes

```
η   = passed / (passed + failed)          CRC
Ψ   = exp(-λ Φ̄) · Ξ · exp(-λ δ̄) · exp(-λ Γ̄) · η
Ω   = exp(-α φ̄) · exp(-α κ̄) · exp(-α δ̄) · η

BLOCK  if  φ_1h > 0.7  OR  residual-high  OR  critical IaC
WARN   if  φ_6h > 0.5  OR  any ZTA pillar < 0.5  OR  κ > 0.15
PASS   otherwise → ALLOW
```

Autonomy default **α2**: audit, annotate, block high/critical. Do not auto-apply patches.

DQN (story app only) cannot `ALLOW` through a DSA `BLOCK`.

Conflict: GRA owns security attributes. RPA owns canary and scale. Both emit **suggest only** (`apply: false`).

### Telemetry JSON

Canonical keys (aliases from Datadog `series` / Prometheus `data.result` are mapped):

| Key | Meaning |
| --- | --- |
| `error_rate` | Fraction of failed requests |
| `cpu` | 0–1 utilization |
| `latency_p95_ms` | p95 latency |
| `capacity` | Provisioned headroom (1.0 = current) |
| `demand_forecast` | Expected load (or last demand point) |
| `privilege_excess` | Extra IAM (0–1) |
| `drift` | Config drift (0–1) |
| `history.demand` | Optional series — Holt fills demand if you omit `demand_forecast` |

See `examples/telemetry_ok.json`, `telemetry_hot.json`, `telemetry_datadog.json`, `telemetry_history_hot.json`.

---

## Planes (shipped here vs story app)

| Step | This repo (8877 / CLI) | Story demo (synthetic sensors) |
| --- | --- | --- |
| CRC sensors | Checkov passed/failed + debt | GBDT code, RF+SVM image, IaC scorer, IsolationForest |
| CRC score | η, residual-high, critical IaC | Same idea from detectors + NIST/CIS/SOC2/PCI |
| ZeroGuard | Checkov IDs → 7 NIST pillars, Ξ, Γ, Ψ | ICA graph → ZTPA attention → IAEA set-cover → GRA + SIS |
| InfraAgent | Snapshot φ; Holt κ on history | T-GAN window + neighbor graph; CFA smoothing |
| Gate | `framework/infraagent/dsa.py` | Same thresholds via orchestrator |
| Evidence | `data/audit.jsonl` + outcomes sidecar | `artifacts/audit.jsonl` |

Same join. Different sensors. The petition proof is **this** repo on real Checkov JSON.

---

## Tests

```bash
python3 -m unittest tests.test_gate tests.test_flow tests.test_improvements tests.test_audit tests.test_maws -v
```

Covers fail/pass/cross-plane stories, shadow vs `--enforce`, Holt capacity, Datadog mapping, durable bus, two-writer audit (no fork), and repair of a broken chain.

---

## Folder map

| Path | Role |
| --- | --- |
| [framework/flow.py](framework/flow.py) | Pipeline; delegates to MAWS hive when present |
| [framework/locate_maws.py](framework/locate_maws.py) | Find sibling / `MAWS_ROOT` / `vendor/maws` |
| [framework/cli.py](framework/cli.py) | Shadow / `--enforce` / `record-outcome` / `scorecard` |
| [framework/webdemo.py](framework/webdemo.py) | SSE demo on :8877 |
| [framework/ingest/](framework/ingest/) | Checkov + telemetry mappers |
| [framework/crc/](framework/crc/) | η, residual |
| [framework/zeroguard/](framework/zeroguard/) | Pillars, Ξ, Γ, Ψ |
| [framework/infraagent/](framework/infraagent/) | φ, κ, Ω, DSA, suggest-only RPA |
| [framework/bus.py](framework/bus.py) | Priority bus (file; Redis if `REDIS_URL`) |
| [framework/audit.py](framework/audit.py) | SHA-256 chain + lock + repair |
| [framework/outcome.py](framework/outcome.py) | Sidecar actuals + scorecard |
| [examples/](examples/) | Checkov + telemetry fixtures |
| [tests/](tests/) | Gate, flow, ingest, audit |
| [hub/](hub/) | Home site on :8800 |
| [static/](static/) | Gate demo UI |
| [data/](data/) | Runtime audit/bus (gitignored) |

---

## Environment

| Variable | Effect |
| --- | --- |
| `FRAMEWORK_BUS_PATH` | Persist the bus at this path |
| `REDIS_URL` or `FRAMEWORK_REDIS_URL` | Redis Streams if the `redis` package is installed; else file |
| `UNIFIED_FRAMEWORK` | Plane repos: path to this checkout instead of `vendor/` |
| `MAWS_ROOT` | Path to the MAWS hive repo instead of sibling `../maws` or `vendor/maws` |

---

## Build order (do not skip ahead)

1. **Done.** Fusion, Checkov ingest, shadow DSA, signed audit.
2. **Done.** File-backed bus, Datadog/Prometheus mapper, Holt CFA, outcome scorecard, suggest-only RPA, audit lock/repair.
3. **Next.** Label real releases. Run `scorecard` for weeks.
4. **Later.** XGBoost φ on incident-labeled windows. Longer CFA on stored utilization.
5. **Last.** Ticket/PR comments from templates. Still never auto-apply chatbot or IAM.

---

## Petition language (short)

Banks already scan and already watch production. Those signals live in separate tools, so a release can look green in CI and still open a door, grant extra permissions, or move traffic onto a copy that will fail within the hour. This work puts those signals through one orchestrator. The only customer-facing output is go, wait, or stop. The old system stays live until that output is go. Every pick is hash-chained and later scored against what actually happened.

That is the claim: **one fused gate, not three unread reports.** The Northstar chatbot is how you *show* it. The Checkov CLI and the scorecard are how you *prove* it.
