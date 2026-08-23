# Industry deploy vs our fused chatbot gate

**Northstar Bank** ships a customer chatbot with two copies: **blue** (customers now) and **green** (empty new assistant). The question is not “can we build the image?” It is “when is it safe to move customers?”

Today a bank gets three reports and a human still decides. We produce one **go / wait / stop** before anyone leaves the old chatbot, write that pick in a signed log, and later score whether we were right.

Complete figures: [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Typical bank deploy today

1. Write code and open a PR. Reviewers look at chatbot text and SQL.
2. CI runs tests. Checkov, SAST, and image scan each post their own report.
3. The image goes to a registry. The scan is often advisory.
4. Stage, then a change meeting. Capacity and identity are someone else’s ticket.
5. Platform flips traffic. Customers move first.
6. Dashboards fire after the fact. Rollback is a human after the outage.

Many tools. Many owners. No single fused decision **before** customers leave the old assistant.

---

## Our deploy

1. Same two copies. Blue stays live until the gate says go.
2. One Checkov scan plus live traffic enter together. Datadog series and Prometheus exports map into the same keys — no hand-built fixture required.
3. Three checks in one run:
   - **Rules (CRC):** did the scanner find trouble in code, image, or setup?
   - **Trust (ZeroGuard):** open doors, extra permissions, unusual grant patterns.
   - **Stay-up (InfraAgent):** will the chat graph fail, will we run out of room? If demand history is present, Holt forecasts capacity before the switch.
4. One decision: **go**, **wait**, or **stop**. A security fix beats a rollout suggestion when both fire. Suggested hold / scale / canary / rollback is never auto-applied.
5. Sign the log. Every pick is hash-chained. Events sit on a durable bus so a restart mid-release does not lose the chain.
6. Then move customers. If chatbot or fraud stops, they never leave blue.
7. After the release, label what actually happened (`ok`, `incident`, `rollback`, `brownout`). A scorecard counts false stops vs missed stops. CI is not allowed to fail a pipeline until that record is clean.

---

## Where we are better

| Area | Typical deploy | Ours | Why it helps a bank |
|---|---|---|---|
| Decision | Three dashboards, a human merges them | One go / wait / stop | Release manager sees one answer |
| When customers move | After CI is green, often before ops agrees | Only after code + trust + stay-up agree | A clean PR cannot ship an open door or a failing chat graph |
| Cross-plane block | Security pass can still brown out the assistant | Safe setup + hot traffic still stops | Fraud/chat spikes block the switch even if Checkov is clean |
| Identity | IAM review is a later ticket | Extra permissions scored in the same run | Wildcard chatbot roles show up before live customers |
| Capacity | Autoscaler reacts after load hits | Holt forecast on real demand history, then wait | Wait instead of paging at 2am |
| Evidence | CI logs in five systems | Signed hash chain + durable event bus | An examiner can replay why customers stayed on blue |
| After the fact | Pages fire; nobody scores the gate | Outcome scorecard vs the original pick | You can prove shadow mode before `--enforce` |
| Default | Ship unless someone objects | Stay on blue unless the gate says go | Safer for deposits, cards, and chat-driven transfers |
| Fixes | A ticket, or an auto-merge you cannot defend | Suggest only — hold, scale, canary, rollback | A human applies the change. Chatbot SQL is never rewritten by the gate |

---

## Benefits you can claim

The valuable claim is not “we trained a giant model.” Banks already have scanners and monitors. We added the missing layer: **fusion, a single gate, a signed trail, and a score of whether that gate was right.**

- One decision instead of three unread reports.
- Customers move **after** the fused pick, not after a green CI badge.
- Real Checkov JSON and real exporter metrics go in. The story demo stays synthetic on purpose; the gate is the proof.
- Shadow first: log go / wait / stop, then label incidents. `--enforce` only after the scorecard says the log is clean.
- Conservative default: audit, annotate, block serious issues. Suggest a patch. Do not apply it.

That is the petition-grade story: real inputs where they exist, heuristics first, enforcement only after the log matches real outcomes.

---

## What improved versus the old path

- **Fusion.** Rules, trust, and stay-up become one DSA pick.
- **Customer path.** Login → Chatbot → Fraud → Ledger → traffic switch. The switch cannot run if chatbot or fraud stops.
- **Conflict rule.** A security fix wins over a rollout suggestion. Rollout still owns canary and scale.
- **Durable evidence.** Bus and audit survive a crash mid-release. Outcomes append beside the chain so history is never rewritten.
- **Capacity before the flip.** Rising demand history can wait even when the last snapshot looks fine.
- **Honesty after the release.** False stops and missed stops are counted, not guessed.
- **Language.** Pages say go / wait / stop so a risk officer can follow without paper jargon.

---

## What we do not claim

Industry already has Checkov, Datadog, and IAM reviews. The edge is the **join**, not a production T-GAN or Code Llama.

| Still later | Why we left it |
|---|---|
| Story site is synthetic | It is the bank narrative. Point examiners at the Checkov-fed gate. Never file story-page numbers (accuracy, false alarms, minutes, dollars) as measured results — those scripted figures are gone. |
| Failure probability is still a formula | XGBoost needs weeks of labeled incidents. Holt capacity was the safer first upgrade. |
| Patches are templates | Auto-writing chatbot SQL or IAM is the most dangerous upgrade. Suggest, do not merge. |
| Redis / Kafka | File-backed bus is enough for a single Friday release. Streams when you run many workers. |

---

## Short paragraph you can reuse

Banks already scan code, images, and infrastructure, and they already watch production. Those signals live in separate tools, so a chatbot release can look “green” in CI and still open a network door, grant extra permissions, or move customers onto a copy that will fail within the hour. This work puts those signals through one orchestrator. Policy adherence, zero-trust posture, and predicted stay-up are scored together. Datadog or Prometheus exports map into the same run. Demand history can force a wait before the switch. The only customer-facing output is go, wait, or stop. Suggested remediations are never applied automatically. The old chatbot stays live until the output is go. Every decision is hash-chained and later scored against what actually happened. That is a safer Friday release for a bank assistant, and it is evidence you can show: one fused gate, not three unread reports.
