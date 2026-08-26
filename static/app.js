const PILLAR_LABELS = {
  P1_resources: "Keep data in the right place",
  P2_comms: "Private connections",
  P3_session: "One login at a time",
  P4_dynamic_policy: "Rules that can change",
  P5_integrity: "Data is locked",
  P6_authz: "Sign-in plus extra code",
  P7_telemetry: "We watch the logs",
};

const NODE_ORDER = ["ingest", "crc", "zeroguard", "infraagent", "gate", "audit"];

const DEMO = window.DEMO || {};
const FROM_FILE = location.protocol === "file:";
const API_BASE = FROM_FILE ? (DEMO.origin || "http://127.0.0.1:8871") : "";

let currentSource = null;
let sawEvent = false;

function showOffline(on) {
  const el = document.getElementById("offlineBanner");
  if (!el) return;
  el.classList.toggle("hidden", !on);
  if (on && DEMO.cmd) {
    const cmd = document.getElementById("offlineCmd");
    if (cmd) cmd.textContent = DEMO.cmd;
  }
}

function wirePeerNav() {
  const peers = DEMO.peers || {};
  document.querySelectorAll("a[data-peer]").forEach((a) => {
    const peer = peers[a.dataset.peer];
    if (!peer) return;
    a.href = FROM_FILE ? peer.file : peer.http;
  });
}

function colorFor(value) {
  if (value >= 0.7) return "var(--ok)";
  if (value >= 0.4) return "var(--warn)";
  return "var(--bad)";
}

function gateClass(dsa) {
  if (dsa === "BLOCK") return "block";
  if (dsa === "WARN") return "warn";
  return "allow";
}

function setActiveNode(stageKey) {
  const idx = stageKey === "__all_done__" ? NODE_ORDER.length : NODE_ORDER.indexOf(stageKey);
  NODE_ORDER.forEach((key, i) => {
    const el = document.querySelector(`.flow-node[data-stage="${key}"]`);
    if (!el) return;
    el.classList.remove("active", "done");
    if (i < idx) el.classList.add("done");
    else if (i === idx) el.classList.add("active");
  });
}

function setText(id, text) {
  const node = document.getElementById(id);
  if (node) node.textContent = text;
}

function resetFlowDiagram() {
  document.querySelectorAll(".flow-node").forEach((node) => node.classList.remove("active", "done"));
  setText("flowIngest", "Security scan + live traffic");
  setText("flowCrc", "Did the rules pass?");
  setText("flowZeroguard", "Is the setup locked down?");
  setText("flowInfraagent", "Will it stay healthy?");
  setText("flowGate", "Go / wait / stop");
  setText("flowAudit", "Written down and sealed");
  setActiveHive(null);
  setText("hiveTask", "Waiting for assignment…");
}

function setActiveHive(agent) {
  document.querySelectorAll(".hive-cell").forEach((el) => {
    const name = el.getAttribute("data-agent");
    el.classList.toggle("active", Boolean(agent) && name === agent);
    if (agent && name === agent) el.classList.add("seen");
  });
}

function noteHive(ev, fallback) {
  if (ev.agent) setActiveHive(ev.agent);
  const task = ev.task || fallback;
  if (task) setText("hiveTask", (ev.agent ? ev.agent + " · " : "") + String(task).split("_").join(" "));
}

function logEvent(ev, message) {
  const list = document.getElementById("eventLog");
  if (!list) return;
  const empty = list.querySelector(".log-empty");
  if (empty) empty.remove();
  const li = document.createElement("li");
  const now = new Date();
  const ts = now.toLocaleTimeString(undefined, { hour12: false }) + "." + String(now.getMilliseconds()).padStart(3, "0");
  li.className = `stage-${ev.stage} ${ev.detail && ev.detail.dsa ? gateClass(ev.detail.dsa) : ""}`.trim();
  li.innerHTML = `<span class="log-time">${ts}</span>${message}`;
  list.appendChild(li);
  list.scrollTop = list.scrollHeight;
  while (list.children.length > 60) list.removeChild(list.firstChild);
}

function updateCrcPanel(crc) {
  if (!document.getElementById("crcEta")) return;
  document.getElementById("crcEta").textContent = crc.eta.toFixed(3);
  document.getElementById("crcResidual").textContent = crc.residual_high ? "still risky" : "clear";
  document.getElementById("crcResidual").style.color = crc.residual_high ? "var(--bad)" : "var(--ok)";
  document.getElementById("crcPassed").textContent = crc.n_passed;
  document.getElementById("crcFailed").textContent = crc.n_failed;

  if (crc.top_failed) {
    const findingsEl = document.getElementById("crcFindings");
    if (!findingsEl) return;
    findingsEl.innerHTML = "";
    crc.top_failed.forEach((f) => {
      const li = document.createElement("li");
      li.innerHTML = `${f.check_id} <span class="fname">${f.resource} · debt ${f.debt}</span>`;
      findingsEl.appendChild(li);
    });
    if (crc.top_failed.length === 0) {
      findingsEl.innerHTML = '<li style="border-color: var(--ok); color: var(--muted);">No failed checks</li>';
    }
  }
}

function updateZgPanel(zeroguard) {
  if (!document.getElementById("zgPsi")) return;
  document.getElementById("zgPsi").textContent = zeroguard.psi.toFixed(3);
  document.getElementById("zgXi").textContent = zeroguard.xi.toFixed(3);
  document.getElementById("zgGamma").textContent = zeroguard.gamma.toFixed(3);

  const pillarsEl = document.getElementById("zgPillars");
  if (!pillarsEl) return;
  pillarsEl.innerHTML = "";
  Object.entries(zeroguard.pillars).forEach(([key, value]) => {
    const row = document.createElement("div");
    row.className = "pillar-row";
    row.innerHTML = `
      <span>${PILLAR_LABELS[key] || key}</span>
      <span class="pillar-bar"><span class="pillar-fill" style="width:${Math.round(value * 100)}%; background:${colorFor(value)}"></span></span>
      <span>${value.toFixed(2)}</span>
    `;
    pillarsEl.appendChild(row);
  });
}

function updateIaPanel(infraagent) {
  if (!document.getElementById("iaOmega")) return;
  document.getElementById("iaOmega").textContent = infraagent.omega.toFixed(3);
  document.getElementById("iaKappa").textContent = infraagent.kappa.toFixed(3);

  const horizonsEl = document.getElementById("iaHorizons");
  if (!horizonsEl) return;
  horizonsEl.innerHTML = "";
  [["1h", infraagent.phi_1h], ["6h", infraagent.phi_6h], ["24h", infraagent.phi_24h]].forEach(([label, value]) => {
    const div = document.createElement("div");
    div.className = "horizon";
    div.innerHTML = `<div class="h-label">in ${label}</div><div class="h-value" style="color:${colorFor(1 - value)}">${value.toFixed(2)}</div>`;
    horizonsEl.appendChild(div);
  });
}

const GATE_WORDS = {
  ALLOW: "Send customers to the new chatbot.",
  WARN: "Hold the switch — a human should look before customers leave blue.",
  BLOCK: "Keep customers on the old chatbot.",
  BLOCK_BUILD: "Stop the build. Customers stay on the old chatbot.",
  BLOCK_DEPLOYMENT: "Do not move customers off the old chatbot.",
  ROLLBACK: "Undo. Put every customer back on the old chatbot.",
};

function updateGateBanner(decision) {
  const banner = document.getElementById("gateBanner");
  if (!banner) return;
  banner.classList.remove("hidden", "allow", "warn", "block");
  banner.classList.add(gateClass(decision.dsa));
  const plain = GATE_WORDS[decision.action] || GATE_WORDS[decision.dsa] || "";
  const word = decision.dsa === "BLOCK" ? "Stop" : decision.dsa === "WARN" ? "Wait" : "Go";
  setText("gateAction", word);
  setText("gateReasons", [plain, decision.reasons.join("; ")].filter(Boolean).join(" "));
}

function updateAuditPanel(auditDetail, decision, shadow) {
  const chain = document.getElementById("chainOk");
  if (chain) {
    chain.textContent = auditDetail.chain_ok ? "intact" : "broken";
    chain.style.color = auditDetail.chain_ok ? "var(--ok)" : "var(--bad)";
  }
  const actionPart = decision ? `  ${decision.action}` : "";
  setText("auditEntry", `Record #${auditDetail.index} sealed` + actionPart);
}

function renderFinal(data) {
  const { crc, zeroguard, infraagent, governance } = data;
  if (crc) updateCrcPanel(crc);
  if (zeroguard) updateZgPanel(zeroguard);
  if (infraagent) updateIaPanel(infraagent);
  updateGateBanner(governance.decision);
  updateAuditPanel(governance.audit, governance.decision, governance.shadow);

  const busEl = document.getElementById("busLog");
  if (!busEl) return;
  busEl.innerHTML = "";
  (governance.bus || []).forEach((m) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="kind-badge">${m.kind}</span><span>${m.source} → ${m.priority}</span>`;
    busEl.appendChild(li);
  });
}

function setActiveStoryButton(story) {
  document.querySelectorAll(".story-btn:not(.auto)").forEach((b) => {
    b.classList.toggle("active", b.dataset.story === story);
  });
}

function setAutoplayRunning(running) {
  const btn = document.getElementById("autoplayBtn");
  if (btn) {
    btn.classList.toggle("running", running);
    btn.textContent = running ? "■ Stop" : "▶ Play every story";
  }
  document.querySelectorAll(".story-btn:not(.auto)").forEach((b) => (b.disabled = running));
}

function handleEvent(ev) {
  switch (ev.stage) {
    case "scenario_start":
      resetFlowDiagram();
      setActiveStoryButton(ev.story);
      setText("scenarioBlurb", ev.detail.blurb);
      logEvent(ev, `▶ ${ev.detail.blurb}`);
      break;
    case "ingest":
      setActiveNode("ingest");
      noteHive(ev, "load scan");
      setText("flowIngest", "reading the scan…");
      logEvent(ev, "Reading the security scan and live traffic");
      break;
    case "ingested":
      noteHive(ev, "loaded");
      setText("flowIngest", `${ev.detail.n_passed} passed / ${ev.detail.n_failed} failed`);
      logEvent(ev, `Scan done: ${ev.detail.n_passed} passed, ${ev.detail.n_failed} failed`);
      break;
    case "crc":
      setActiveNode("crc");
      noteHive(ev, "score rules");
      setText("flowCrc", ev.detail.residual_high ? "leftover risk — high" : "rules look fine");
      updateCrcPanel(ev.detail);
      logEvent(ev, `Code checks: ${Math.round(ev.detail.eta * 100)}% of rules passed`);
      break;
    case "zeroguard":
      setActiveNode("zeroguard");
      noteHive(ev, "score trust");
      setText("flowZeroguard", `trust ${Math.round(ev.detail.psi * 100)}%`);
      updateZgPanel(ev.detail);
      logEvent(ev, `Trust checks: ${Math.round(ev.detail.psi * 100)}% · extra access ${Math.round(ev.detail.gamma * 100)}%`);
      break;
    case "infraagent":
      setActiveNode("infraagent");
      noteHive(ev, "score stay-up");
      setText("flowInfraagent", `trouble in 1h ${Math.round(ev.detail.phi_1h * 100)}%`);
      updateIaPanel(ev.detail);
      logEvent(ev, `Stay-up checks: ${Math.round(ev.detail.omega * 100)}% healthy · 1-hour trouble ${Math.round(ev.detail.phi_1h * 100)}%`);
      break;
    case "gate": {
      setActiveNode("gate");
      noteHive(ev, "decide");
      const word = ev.detail.dsa === "BLOCK" ? "Stop" : ev.detail.dsa === "WARN" ? "Wait" : "Go";
      setText("flowGate", word);
      const gateNode = document.querySelector('.flow-node[data-stage="gate"]');
      if (gateNode) gateNode.classList.add(gateClass(ev.detail.dsa));
      updateGateBanner(ev.detail);
      logEvent(ev, `Decision: <b>${word}</b> — ${ev.detail.reasons.join("; ")}`);
      break;
    }
    case "compensate":
      noteHive(ev, ev.detail && ev.detail.policy);
      logEvent(ev, ev.detail && ev.detail.blue_stays_live
        ? "MAWS compensation: stay on blue. Do not apply patches."
        : "MAWS: go is allowed. Human still applies the switch.");
      break;
    case "audit":
      setActiveNode("audit");
      noteHive(ev, "seal");
      setText("flowAudit", ev.detail.chain_ok ? "signed and intact" : "log is broken");
      updateAuditPanel(ev.detail);
      logEvent(ev, `Signed log #${ev.detail.index} — ${ev.detail.chain_ok ? "intact" : "broken"}`);
      break;
    case "done":
      setActiveNode("__all_done__");
      renderFinal(ev.detail);
      logEvent(ev, "Finished — one decision, written down");
      break;
    case "stream_done":
      setAutoplayRunning(false);
      logEvent(ev, "— all stories finished —");
      break;
    default:
      break;
  }
}

function startStream(story) {
  if (currentSource) {
    currentSource.close();
    currentSource = null;
  }
  sawEvent = false;
  showOffline(false);
  const es = new EventSource(`${API_BASE}/api/stream?story=${encodeURIComponent(story)}`);
  currentSource = es;
  if (story === "all") setAutoplayRunning(true);
  es.onmessage = (msg) => {
    sawEvent = true;
    showOffline(false);
    const ev = JSON.parse(msg.data);
    handleEvent(ev);
    if (ev.stage === "stream_done") {
      es.close();
      currentSource = null;
    }
  };
  es.onerror = () => {
    es.close();
    currentSource = null;
    setAutoplayRunning(false);
    if (!sawEvent) showOffline(true);
  };
}

document.querySelectorAll(".story-btn:not(.auto)").forEach((btn) => {
  btn.addEventListener("click", () => startStream(btn.dataset.story));
});

document.getElementById("autoplayBtn").addEventListener("click", () => {
  if (currentSource) {
    currentSource.close();
    currentSource = null;
    setAutoplayRunning(false);
    logEvent({ stage: "manual" }, "— autoplay stopped by user —");
    return;
  }
  startStream("all");
});

document.querySelectorAll(".artifact").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".plane").forEach((p) => p.classList.remove("highlight"));
    const el = document.getElementById(btn.dataset.target);
    if (el) {
      el.classList.add("highlight");
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
      setTimeout(() => el.classList.remove("highlight"), 1400);
    }
  });
});

wirePeerNav();

// Kick off the pass story automatically so the dashboard is never empty.
startStream("pass");
