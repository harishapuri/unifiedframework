# MAWS — multi-agent workflow supervisor

GitHub: [harishapuri/MAWS](https://github.com/harishapuri/MAWS)

This is the **orchestrator hive** from *Design of Multi Agent Autonomous Workflow Systems Using Agentic AI Frameworks*. Named agents share one environment (Checkov + telemetry + bus). The supervisor assigns work. Scoring still lives in [unifiedframework](https://github.com/harishapuri/unifiedframework) (CRC η × ZeroGuard Ψ × InfraAgent Ω → one DSA pick).

It is **not** a fourth scoring plane. Patches stay `apply: false`. Autonomy **α2**. Stop/wait compensates by staying on blue.

```bash
git clone https://github.com/harishapuri/MAWS.git
cd MAWS
python3 -m maws.demo          # http://127.0.0.1:8874/
python3 -m maws.automate      # seven stories, exit 1 if a pick drifts
```

## Related repos

| Repo | Role |
| --- | --- |
| [unifiedframework](https://github.com/harishapuri/unifiedframework) | Fused scores, bus, audit (source of `vendor/unified_framework`) |
| [infraagent](https://github.com/harishapuri/infraagent) | CRC / CI-CD |
| [CICD_Compliance](https://github.com/harishapuri/CICD_Compliance) | Stay-up |
| [ZeroGuard](https://github.com/harishapuri/ZeroGuard) | Trust |

`iter_flow` in unified_framework delegates to this package when `MAWS_ROOT`, sibling `../maws`, or `vendor/maws` is present.

```bash
export UNIFIED_FRAMEWORK=/path/to/unifiedframework
export MAWS_ROOT=/path/to/maws   # optional; sibling folder is enough
```

Full figures: [ARCHITECTURE.md](ARCHITECTURE.md). Plan: [PLAN.md](PLAN.md).

## Hive agents

| Agent | Job |
| --- | --- |
| Supervisor | Task allocation, stay-on-blue compensation |
| IngestAgent | Checkov + telemetry JSON |
| CrcAgent | η, residual-high |
| ZeroGuardAgent | pillars, Ξ, Γ, Ψ |
| InfraAgent | φ, κ, Ω |
| DsaAgent | go / wait / stop |
| RpaAgent | suggest-only hold / scale / canary / rollback |
| AuditAgent | SHA-256 chain |

CRC still runs first because η multiplies Ψ and Ω.

## CLI

```bash
python3 -m maws vendor/unified_framework/examples/checkov_fail.json \
  --telemetry vendor/unified_framework/examples/telemetry_hot.json
```

`--enforce` exits `2` on BLOCK. Default is shadow.

## Tests

```bash
python3 -m unittest tests.test_maws -v
```

## Layout

| Path | Role |
| --- | --- |
| `maws/supervisor.py` | `iter_maws` generator |
| `maws/agents.py` | Thin wrappers around unified scores |
| `maws/demo.py` | SSE hive on :8874 |
| `vendor/unified_framework/` | Shared gate library |
