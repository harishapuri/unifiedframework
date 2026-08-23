# Unified InfraAgent + ZeroGuard + CRC Framework

Complete implementation plan for one closed-loop system that joins three papers:

1. **CRC (207)** — Compliance-Driven Security Automation in AI-Augmented CI/CD
2. **ZeroGuard (2143)** — Multi-Agent Zero-Trust IaC Security Remediation
3. **InfraAgent (1239)** — Predictive Deployment Failure Detection and Autonomous Remediation

The three planes share one message bus, one autonomy policy, one hash-chained audit log, and **one gate**. They are not three products.

**Shipped first:** decision fusion on real Checkov JSON (`framework/`), heuristic η/Ψ/Ω, shadow gate, SHA-256 audit. Redis, CFA/Prophet, XGBoost failure model, and LLM remediations come later — see README build order.

---

## 1. Why they must run together

| Gap if built alone | What the other papers supply |
| --- | --- |
| CRC scores a commit but cannot reason about IAM blast radius or 6-hour failure probability | ZeroGuard Ψ / pillars; InfraAgent φ_h and Ω |
| ZeroGuard patches IaC but does not decide canary vs rollback under capacity pressure | InfraAgent CFA κ and RPA rollout |
| InfraAgent forecasts outages but ignores NIST ZTA and STRIDE compliance debt | CRC η; ZeroGuard Ξ and Γ |

Join rule: **policy adherence η from CRC multiplies both ZeroGuard Ψ and InfraAgent Ω.** DSA and DQN then consume the same fused signal.

```
η  = (# passed CRC controls) / (# controls)
Ψ  = exp(-λ1 Φ̄) · Ξ · exp(-λ2 δ̄) · exp(-λ3 Γ̄) · η     (ZeroGuard Def. 6)
Ω  = exp(-α1 φ̄) · exp(-α2 κ̄) · exp(-α3 δ̄) · η           (InfraAgent Def. 4)

Gate:
  BLOCK  if φ_1h > 0.7  OR  CRC residual-high  OR  ZTPA σ = critical
  WARN   if φ_6h > 0.5  OR  any ZTA pillar fail
  PASS   otherwise, subject to DQN ALLOW
```

Shared autonomy `α0–α3` (default **α2**): audit-only → annotated PR → block high/critical → auto-apply low-risk patches.

---

## 2. Architecture

```
Artifacts (code, image, IaC, telemetry)
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│ CRC sensors (heuristic η from Checkov today)              │
└───────────────────────────┬───────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
 ZeroGuard plane      Shared backbone      InfraAgent plane
 pillars + Γ + Ψ      typed bus            φ / κ / Ω + DSA
 GRA later            SHA-256 audit        CFA / T-GAN / RPA later
                      CCO+COIO
        └───────────────────┬───────────────────┘
                            ▼
                 Single gate: ALLOW / WARN /
                 BLOCK_BUILD / BLOCK_DEPLOY / ROLLBACK
```

### 2.1 Shared backbone

| Piece | Contract |
| --- | --- |
| Message bus | Kinds: `RiskReport`, `ZtaScore`, `IamProposal`, `PatchSet`, `Forecast`, `GateDecision`, `Outcome`. Priority: safety > identity > capacity > advisory |
| Audit chain | SHA-256 of `{event, traces, action, outcome, prev}` |
| Knowledge store | Cosine over bag-of-features (RAG stand-in) keyed by smell / failure class — **not shipped** |
| Orchestrator | Every run emits CRC + ZeroGuard + InfraAgent before DSA. If GRA (security patch) and RPA (rollout) hit the same service later: **GRA wins security attributes; RPA owns traffic and capacity** |

### 2.2 CRC plane

Shipped: `framework/crc/eta.py` — `η`, mean IaC debt, residual-high.

Later (from EB2NIW): code GBDT, container RF+SVM, Isolation Forest telemetry, deterministic NIST/CIS/SOC2 controls, constrained DQN (`dqn_may_allow` is already False on DSA BLOCK).

### 2.3 ZeroGuard plane

Shipped: `framework/zeroguard/pillars.py` — Checkov ID → 7 NIST SP 800-207 pillars, `Ξ`, `Γ`, `Ψ`.

Later: ICA graph, ZTPA attention, IAEA set-cover, GRA template patches + Rego.

### 2.4 InfraAgent plane

Shipped: `framework/infraagent/forecast.py` (heuristic φ/κ/Ω) and `dsa.py` (Eq. 7 + residual / ZTA critical).

Later: T-GAN / XGBoost φ, Prophet CFA κ, RPA canary/rollback templates.

---

## 3. One pipeline run (shipped)

1. Ingest Checkov JSON + optional telemetry JSON.
2. CRC publishes `RiskReport` (`η`, residual).
3. ZeroGuard publishes `ZtaScore` (`Ψ`, pillars, `Γ`).
4. InfraAgent publishes `Forecast` (`φ`, `κ`, `Ω`).
5. DSA classifies PASS/WARN/BLOCK (DQN cannot ALLOW through a BLOCK).
6. Append audit entry. Publish `Outcome`. Return `{crc, zeroguard, infraagent, governance}`.

---

## 4. Demo stories

**Success:** clean IaC + healthy telemetry → high Ψ / Ω → ALLOW.

**Fail:** `0.0.0.0/0` + public bucket + wildcard IAM + rising errors → ZTPA critical + high `φ_1h` → DSA BLOCK.

**Cross-plane:** healthy traffic still BLOCKs on open SG; clean IaC still BLOCKs on hot `φ_1h`.

---

## 5. File map (this repo)

| Path | Role |
| --- | --- |
| `framework/bus.py` | File-backed priority bus (Redis Streams if REDIS_URL) |
| `framework/outcome.py` | Sidecar actuals + scorecard (audit chain stays immutable) |
| `framework/infraagent/rpa.py` | Suggest-only hold / scale / canary / rollback |
| `framework/audit.py` | SHA-256 chain |
| `framework/ingest/checkov.py` | Real Checkov JSON |
| `framework/ingest/telemetry.py` | Metrics JSON |
| `framework/crc/eta.py` | η + residual |
| `framework/zeroguard/pillars.py` | Ξ Γ Ψ |
| `framework/infraagent/forecast.py` | φ κ Ω |
| `framework/infraagent/dsa.py` | Gate |
| `framework/flow.py` | Staged generator (single source of truth for CLI + demo) |
| `framework/orchestrator.py` | Runs `flow.iter_flow` to completion (CLI, tests) |
| `framework/cli.py` | Shadow / `--enforce` |
| `framework/webdemo.py` | Stdlib SSE server: animated, auto-playable flow site |

CRC live UI demo remains in `~/Desktop/EB2NIW`.

### Known heuristic gap

Given the current debt weighting (`framework/zeroguard/pillars.py::classify_check`, minimum debt 2), any Checkov failure already pushes `phi_bar_debt` above the 0.35 `residual_high` threshold. Two decide-time branches are therefore unreachable until real severity-weighted debt is calibrated on incident data: `BLOCK_BUILD` (only reachable when `residual`/`critical` are False but `dsa == BLOCK`) and a pillar-only `WARN` (any failed check already trips `residual_high` first). Not a correctness bug — documented here so the XGBoost/Prophet upgrade (build order step 3–4) recalibrates debt weights with this in mind.

---

## 6. Build order

1. **Done:** bus, audit chain, fused `η/Ψ/Ω` orchestrator, Checkov ingest, shadow DSA.
2. **Done:** file-backed bus (Redis optional), Datadog/Prometheus mapper, Holt CFA on `history`, outcome scorecard, suggest-only RPA.
3. XGBoost `φ` on incident-labeled telemetry (graph attention later).
4. Prophet / longer CFA windows once utilization is stored.
5. Constrained DQN; ticket/PR comments from RPA templates — still never auto-apply.
