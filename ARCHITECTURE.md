# Complete architecture

Three scoring papers plus a **MAWS hive**. CRC, ZeroGuard, and InfraAgent still share a bus, a signed audit, and a **single go / wait / stop**. [MAWS](https://github.com/harishapuri/MAWS) is the supervisor: it assigns named agents, publishes on the bus, and compensates stop/wait by staying on blue. It is not a fourth score. The bank chatbot is the illustration at the bottom — not a separate product.

## All in one — MAWS hive, upstream to downstream

```mermaid
flowchart TB
  subgraph UPSTREAM
    SRC[Commit]
    IMG[Image]
    IAC[IaC]
    TEL[Runtime]
    DEM[Demand]
  end

  subgraph hive [MAWS hive]
    SUP[Supervisor]
    IN[IngestAgent]
    AgCrc[CrcAgent]
    AgZg[ZeroGuardAgent]
    AgIa[InfraAgent]
    AgDsa[DsaAgent]
    RPA[RpaAgent suggest only]
    AUD[AuditAgent]
    SUP -->|assign| IN
    SUP -->|assign| AgCrc
    SUP -->|assign| AgZg
    SUP -->|assign| AgIa
    SUP -->|assign| AgDsa
    SUP -->|assign| RPA
    SUP -->|assign| AUD
  end

  SRC --> IN
  IMG --> IN
  IAC --> IN
  TEL --> IN
  DEM --> IN

  subgraph planeCrc [CRC rules]
    direction TB
    GBDT[GBDT vuln] --> ENS[RF plus SVM image]
    ENS --> IACS[IaC scorer]
    IACS --> ISO[IsolationForest]
    ISO --> CTL[NIST CIS SOC2 PCI]
    CTL --> ETA["eta plus residual"]
  end

  subgraph planeZg [ZeroGuard trust]
    direction TB
    ICA[ICA graph] --> ZTPA[ZTPA attention]
    ZTPA --> PILL["P1 to P7"]
    PILL --> IAEA[IAEA Gamma]
    IAEA --> GRA[GRA plus SIS]
    GRA --> PSI["Psi times eta"]
  end

  subgraph planeIa [InfraAgent stay-up]
    direction TB
    TGAN[T-GAN conv] --> ATTN[Neighbor attention]
    ATTN --> PHI["phi 1h 6h 24h"]
    PHI --> CFA[CFA Holt]
    CFA --> KAP["kappa"]
    KAP --> OME["Omega times eta"]
  end

  AgCrc --> ETA
  AgZg --> PSI
  AgIa --> OME
  ETA --> BUS[Typed bus]
  PSI --> BUS
  OME --> BUS
  BUS --> AgDsa
  AgDsa -->|stop| BLUE[Stay on blue]
  AgDsa -->|wait| HOLD[Hold or canary]
  AgDsa -->|go| GREEN[Move to green]
  SUP -->|compensate| BLUE
  BLUE --> RPA
  HOLD --> RPA
  GREEN --> RPA
  RPA --> AUD
  AUD --> SC[Scorecard then enforce]
```

CRC still runs **before** ZeroGuard and InfraAgent because η multiplies Ψ and Ω. RPA `apply = false`.

```
Artifacts          Checkov / tfsec JSON          Datadog / Prometheus
(code, image, IaC, telemetry, demand history)
                         │                              │
                         └──────────┬───────────────────┘
                                    ▼
                         MAWS Supervisor (task allocation)
                     sibling ../maws  or  vendor/maws
                     framework/flow.py → iter_maws
                                    │
                         IngestAgent
                     framework/ingest/checkov.py
                     framework/ingest/telemetry.py
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        CrcAgent              ZeroGuardAgent         InfraAgent
        η, residual           7 NIST pillars        φ_1h / φ_6h / φ_24h
        critical IaC          Ξ, Γ, Ψ               Holt κ, Ω
        RiskReport            ZtaScore              Forecast
        framework/crc         framework/zeroguard   framework/infraagent
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    ▼
                    Typed priority bus  (MAWS environment)
              safety > identity > capacity > advisory
              file-backed (audit.jsonl.bus); Redis optional
                                    │
                                    ▼
                         DsaAgent  (autonomy α2)
              ALLOW | WARN | BLOCK_BUILD |
              BLOCK_DEPLOYMENT | ROLLBACK
              DQN cannot ALLOW through a BLOCK
                     │                    │
                     ▼                    ▼
              RpaAgent suggest-only   AuditAgent SHA-256
              apply = false           immutable hash link
              GRA wins security       Outcome sidecar
              Supervisor compensates  scorecard
              stay-on-blue on wait/stop
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

  subgraph hive [MAWS hive]
    SUP[Supervisor]
    IN[IngestAgent]
    CRC[CrcAgent]
    ZG[ZeroGuardAgent]
    IA[InfraAgent]
    BUS[MessageBus]
    DSA[DsaAgent]
    SUP --> IN --> CRC --> BUS
    IN --> ZG --> BUS
    IN --> IA --> BUS
    BUS --> DSA
  end

  subgraph evidence [Evidence]
    AUD[AuditAgent]
    SC[Outcome scorecard]
    RPA[RpaAgent suggest only]
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
  SUP -->|compensate| BLU
```

## One pipeline run

```mermaid
sequenceDiagram
  participant CLI as CLI or demo
  participant Sup as MAWS Supervisor
  participant In as IngestAgent
  participant CRC as CrcAgent
  participant ZG as ZeroGuardAgent
  participant IA as InfraAgent
  participant Bus as Bus
  participant DSA as DsaAgent
  participant Rpa as RpaAgent
  participant Aud as AuditAgent

  CLI->>Sup: Checkov JSON + metrics
  Sup->>In: load scan
  In->>CRC: findings
  CRC->>Bus: RiskReport source CrcAgent
  In->>ZG: findings + telemetry
  ZG->>Bus: ZtaScore source ZeroGuardAgent
  In->>IA: telemetry + history
  IA->>Bus: Forecast source InfraAgent
  Sup->>DSA: fuse and decide
  DSA->>Bus: GateDecision
  alt BLOCK or WARN
    Sup->>Sup: compensate stay on blue
  else ALLOW
    Sup->>Sup: green allowed apply still false
  end
  DSA->>Rpa: suggest only
  Rpa->>Bus: PatchSet apply false
  DSA->>Aud: action + traces + prev hash
  Note over DSA: never auto-apply
```

## Three planes plus the hive

| Plane | Paper | Shipped | Question it answers |
|---|---|---|---|
| **MAWS** | Agentic workflows | Supervisor, named agents, bus as environment, stay-on-blue compensation. Repo: [MAWS](https://github.com/harishapuri/MAWS) | Who assigns the work, and does anyone auto-apply? No. |
| **CRC** | 207 | Checkov → η, debt, residual-high | Did the scanner find trouble? |
| **ZeroGuard** | 2143 | 7 NIST SP 800-207 pillars, Ξ, Γ, Ψ | Open doors or extra permissions? |
| **InfraAgent** | 1239 | Heuristic φ, Holt κ, Ω, DSA, suggest-only RPA | Will it fail or run out of room? |

Join: **η multiplies both Ψ and Ω.** MAWS publishes all three on the bus before DsaAgent speaks. CRC still runs first.

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
MAWS Supervisor assigns agents
              ↓
CRC η  ×  ZeroGuard Ψ  and  InfraAgent Ω
              ↓
        DsaAgent one pick
              ↓
   RpaAgent suggest-only  +  AuditAgent SHA-256
   compensate: stay on blue unless go
              ↓
     later: ok / incident / rollback
```

