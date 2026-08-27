# Architecture — MAWS hive

MAWS is the supervisor. CRC, ZeroGuard, and InfraAgent remain specialist agents. One bus. One DSA pick.

```mermaid
flowchart TB
  subgraph hive [MAWS hive]
    SUP[Supervisor]
    IN[IngestAgent]
    CRC[CrcAgent]
    ZG[ZeroGuardAgent]
    IA[InfraAgent]
    DSA[DsaAgent]
    RPA[RpaAgent]
    AUD[AuditAgent]
    SUP --> IN
    SUP --> CRC
    SUP --> ZG
    SUP --> IA
    SUP --> DSA
    SUP --> RPA
    SUP --> AUD
  end
  GIT[Git clone] --> IN
  CK[Checkov] --> IN
  SARIF[SARIF] --> IN
  TRIVY[Trivy] --> IN
  TEL[Telemetry] --> IN
  CRC --> BUS[MessageBus]
  ZG --> BUS
  IA --> BUS
  DSA -->|ALLOW| GRN[Promote intent]
  DSA -->|WARN or BLOCK| BLUE[Hold / stay on blue]
  RPA -->|apply false| HUM[Human]
  AUD --> CORP[Actor + evidence + traffic intent]
  CORP -->|apply false| MESH[Platform mesh]
```

CRC runs before ZeroGuard and InfraAgent because η multiplies Ψ and Ω.

Gate math is unchanged. See unified [ARCHITECTURE.md](../unified_framework/ARCHITECTURE.md) when checked out as a sibling.
