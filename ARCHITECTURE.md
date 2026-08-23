# Complete architecture

Three papers, one closed loop. CRC, ZeroGuard, and InfraAgent share a bus, an orchestrator, a signed audit, and a **single go / wait / stop**. The bank chatbot is the illustration at the bottom — not a separate product.

## All in one — upstream to downstream

```mermaid
flowchart TB
  subgraph UPSTREAM
    SRC[Commit]
    IMG[Image]
    IAC[IaC]
    TEL[Runtime]
    DEM[Demand]
  end

  SRC --> IN[Ingest mapper]
  IMG --> IN
  IAC --> IN
  TEL --> IN
  DEM --> IN

  IN --> CRC
  IN --> ZG
  IN --> IA

  subgraph CRC[CRC rules]
    direction TB
    GBDT[GBDT vuln] --> ENS[RF+SVM image]
    ENS --> IACS[IaC scorer]
    IACS --> ISO[IsolationForest]
    ISO --> CTL[NIST CIS SOC2 PCI]
    CTL --> ETA["η + residual"]
  end

  subgraph ZG[ZeroGuard trust]
    direction TB
    ICA[ICA graph] --> ZTPA[ZTPA attention]
    ZTPA --> PILL["P1–P7 Ξ σ"]
    PILL --> IAEA[IAEA Γ]
    IAEA --> GRA[GRA + SIS]
    GRA --> PSI["Ψ × η"]
  end

  subgraph IA[InfraAgent stay-up]
    direction TB
    TGAN[T-GAN conv] --> ATTN[Neighbor attention]
    ATTN --> PHI["φ 1h 6h 24h"]
    PHI --> CFA[CFA Holt]
    CFA --> KAP["κ 24 48 72h"]
    KAP --> OME["Ω × η"]
  end

  ETA --> BUS[Fuse on typed bus]
  PSI --> BUS
  OME --> BUS

  BUS --> DSA{DSA go / wait / stop}

  DSA -->|stop| BLUE[Stay on blue]
  DSA -->|wait| HOLD[Hold / 10% canary]
  DSA -->|go| GREEN[Move customers to green]

  BLUE --> SUG1[Suggest hold / rollback]
  HOLD --> SUG2[Suggest scale / canary]
  GREEN --> SUG3[Suggest promote]

  SUG1 --> AUD[SHA-256 audit]
  SUG2 --> AUD
  SUG3 --> AUD
  AUD --> SC[Scorecard then --enforce]
```

```
Artifacts          Checkov / tfsec JSON          Datadog / Prometheus
(code, image, IaC, telemetry, demand history)
                         │                              │
                         └──────────┬───────────────────┘
                                    ▼
                         Ingest + alias mapper
                     framework/ingest/checkov.py
                     framework/ingest/telemetry.py
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        CRC — rules           ZeroGuard — trust     InfraAgent — stay-up
        η, residual           7 NIST pillars        φ_1h / φ_6h / φ_24h
        critical IaC          Ξ, Γ, Ψ               Holt κ, Ω
        RiskReport            ZtaScore              Forecast
        framework/crc         framework/zeroguard   framework/infraagent
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    ▼
                    Typed priority bus + orchestrator
              safety > identity > capacity > advisory
              file-backed (audit.jsonl.bus); Redis optional
                                    │
                                    ▼
                         DSA gate  (autonomy α2)
              ALLOW | WARN | BLOCK_BUILD |
              BLOCK_DEPLOYMENT | ROLLBACK
              DQN cannot ALLOW through a BLOCK
                     │                    │
                     ▼                    ▼
              RPA suggest-only      SHA-256 audit chain
              apply = false         immutable hash link
              GRA wins security     Outcome sidecar
                                    scorecard
                                    │
                                    ▼
                         Traffic switch LAST
              blue stays live unless the pick is go
              Login → Chatbot → Fraud → Ledger → switch
```

## System context

```mermaid
flowchart LR
  subgraph sources [Sources]
    CK[Checkov / tfsec JSON]
    DD[Datadog / Prometheus]
    HIST[Demand history]
  end

  subgraph gate [Unified gate]
    IN[Ingest mapper]
    CRC[CRC rules]
    ZG[ZeroGuard trust]
    IA[InfraAgent stay-up]
    BUS[Bus + orchestrator]
    DSA[DSA go / wait / stop]
    IN --> CRC --> BUS
    IN --> ZG --> BUS
    IN --> IA --> BUS
    BUS --> DSA
  end

  subgraph evidence [Evidence]
    AUD[SHA-256 audit]
    SC[Outcome scorecard]
    RPA[Suggest-only patches]
  end

  subgraph effect [Effect]
    BLU[Blue stays live]
    GRN[Green empty until go]
  end

  CK --> IN
  DD --> IN
  HIST --> IN
  DSA --> AUD --> SC
  DSA --> RPA
  DSA -->|go| GRN
  DSA -->|wait or stop| BLU
```

## One pipeline run

```mermaid
sequenceDiagram
  participant CI as CI / CLI
  participant In as Ingest
  participant CRC as CRC
  participant ZG as ZeroGuard
  participant IA as InfraAgent
  participant Bus as Bus
  participant DSA as DSA gate
  participant Aud as Audit
  participant Ops as Release

  CI->>In: Checkov JSON + metrics
  In->>CRC: findings
  CRC->>Bus: RiskReport η
  In->>ZG: findings + telemetry
  ZG->>Bus: ZtaScore Ψ
  In->>IA: telemetry + history
  IA->>Bus: Forecast Ω φ κ
  Bus->>DSA: fused scores
  DSA->>Aud: action + traces + prev hash
  DSA->>Ops: go / wait / stop
  Note over DSA: PatchSet apply=false
  Ops-->>Aud: later: ok / incident / rollback
```

## Three planes

| Plane | Paper | Shipped in this repo | Story / later (EB2NIW) | Question it answers |
|---|---|---|---|---|
| **CRC** | 207 | Checkov → η, debt, residual-high | Code / image / runtime detectors, constrained DQN | Did the scanner find trouble? |
| **ZeroGuard** | 2143 | 7 NIST SP 800-207 pillars, Ξ, Γ, Ψ | ICA, ZTPA, IAEA, GRA + Rego | Open doors or extra permissions? |
| **InfraAgent** | 1239 | Heuristic φ, Holt κ, Ω, DSA, suggest-only RPA | T-GAN window, CFA bands | Will it fail or run out of room? |

Join: **η multiplies both Ψ and Ω.** One orchestrator run publishes all three before the gate.

## Gate

```
BLOCK  if  φ_1h > 0.7  OR  residual-high  OR  critical IaC
WARN   if  φ_6h > 0.5  OR  any ZTA pillar < 0.5  OR  κ > 0.15
PASS   otherwise → ALLOW

Conflict: GRA owns security attributes; RPA owns traffic and capacity.
Constraint: DQN cannot weaken a DSA BLOCK.
Autonomy α2: audit, annotate, block high/critical; never auto-apply.
```

## Feedback loop

```
shadow pick  →  customers stay or move  →  record actual
     ok | incident | rollback | brownout
                    ↓
              scorecard
     false stops vs missed stops
                    ↓
         ready_for_enforce?  →  --enforce in CI
```

The signed audit is never rewritten. Outcomes append beside it (`data/outcomes.jsonl`).

---

## CRC complete flow (paper 207)

```mermaid
flowchart TB
  subgraph sensors [Sensors]
    C[Commit source]
    B[Build image]
    I[IaC template]
    R[Runtime window]
  end

  subgraph models [Detectors]
    GBDT[GBDT vuln / CVSS]
    ENS[RF + SVM image risk]
    IAC[IaC risk scorer]
    ISO[IsolationForest anomaly]
  end

  C --> GBDT
  B --> ENS
  I --> IAC
  R --> ISO

  GBDT --> CTL[NIST CSF / CIS / SOC2 / ISO / PCI]
  ENS --> CTL
  IAC --> CTL
  ISO --> CTL

  CTL --> ETA["η = passed / total"]
  ETA --> RES[residual-high]
  RES --> RR[RiskReport on bus]
  RES --> DQN[Constrained DQN after DSA]
```

**Checkov gate (this repo):** skip the four ML sensors. `checkov -o json` is the control set. η and residual-high come from passed/failed debt. `dqn_may_allow` is already False on BLOCK.

## ZeroGuard complete flow (paper 2143)

```mermaid
flowchart TB
  IAC[IaC template] --> ICA["ICA graph G(V, Edep ∪ Eref ∪ Eiam)"]
  SVC[Service identity] --> IAEA["IAEA granted vs 30-day used"]
  ICA --> ZTPA[ZTPA 3-layer attention]
  ZTPA --> PILL["P1–P7  Ξ  σ 0..3"]
  ZTPA --> ZD[IsolationForest zero-day]
  IAEA --> GAM["Γ privilege excess"]
  PILL --> GRA[GRA templates + Rego]
  GRA --> SIS["Re-run ZTPA ≤ 3  SIS"]
  PILL --> PSI["Ψ = exp(-λΦ̄)·Ξ·exp(-λδ̄)·exp(-λΓ̄)·η"]
  GAM --> PSI
  ZD --> PSI
  PSI --> BUS[ZtaScore / IamProposal / PatchSet]
  SIS --> BUS
```

**Checkov gate:** classify each check onto the same 7 pillars. Γ from IAM failures + `privilege_excess`. No auto-patch. GRA still wins the conflict rule when a suggestion exists.

## InfraAgent complete flow (paper 1239)

```mermaid
flowchart TB
  WIN[Telemetry window] --> TGAN[T-GAN dilated conv]
  G[Service graph] --> ATTN[Neighbor attention]
  TGAN --> ATTN
  ATTN --> PHI["φ_1h / φ_6h / φ_24h"]
  HIST[Demand history] --> CFA[CFA Holt / smoothing]
  CFA --> KAP["κ 24h / 48h / 72h"]
  PHI --> OME["Ω = exp(-αφ̄)·exp(-ακ̄)·exp(-αδ̄)·η"]
  KAP --> OME
  OME --> DSA[DSA go / wait / stop]
  DSA --> RPA[RPA suggest only]
  GRA[GRA security patch] -.->|wins security attrs| RPA
  DSA --> SW[Traffic switch last]
```

**Checkov gate:** φ from error / cpu / p95 (rising history lifts φ_6h). κ from Holt on `history.demand` or snapshot deficit. Same DSA thresholds. RPA `apply = false`.

## How they meet

```
CRC η  ×  ZeroGuard Ψ  and  InfraAgent Ω
              ↓
        one DSA pick
              ↓
   suggest-only patch   +   SHA-256 audit
              ↓
     later: ok / incident / rollback
```

