const refs = {
  username: document.getElementById("username"),
  password: document.getElementById("password"),
  loginBtn: document.getElementById("login-btn"),
  loginState: document.getElementById("login-state"),
  voteFeedback: document.getElementById("vote-feedback"),
  totalPackets: document.getElementById("total-packets"),
  avgLoss: document.getElementById("avg-loss"),
  totalVotes: document.getElementById("total-votes"),
  duplicateVotes: document.getElementById("duplicate-votes"),
  countA: document.getElementById("count-a"),
  countB: document.getElementById("count-b"),
  countC: document.getElementById("count-c"),
  barA: document.getElementById("bar-a"),
  barB: document.getElementById("bar-b"),
  barC: document.getElementById("bar-c"),
  pctA: document.getElementById("pct-a"),
  pctB: document.getElementById("pct-b"),
  pctC: document.getElementById("pct-c"),
  timestamp: document.getElementById("timestamp")
};

const animated = {
  totalPackets: 0,
  avgLoss: 0,
  totalVotes: 0,
  duplicateVotes: 0,
  countA: 0,
  countB: 0,
  countC: 0
};

let login = {
  ready: false,
  username: "",
  token: "",
  clientId: 0,
  sequence: 0,
};

let ws = null;
let wsConnected = false;
let WS_PORT = 9001;

function animateValue(key, target) {
  const start = animated[key];
  const delta = target - start;
  const duration = 480;
  const started = performance.now();

  function tick(now) {
    const progress = Math.min(1, (now - started) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    const value = key === "avgLoss"
      ? Number((start + delta * eased).toFixed(2))
      : Math.round(start + delta * eased);
    animated[key] = value;
    refs[key].textContent = key === "avgLoss" ? `${value.toFixed(2)}` : String(value);
    if (progress < 1) requestAnimationFrame(tick);
  }

  requestAnimationFrame(tick);
}

function updateBars(tally) {
  const a = tally.A || 0;
  const b = tally.B || 0;
  const c = tally.C || 0;
  const total = Math.max(1, a + b + c);
  const aPct = (a / total) * 100;
  const bPct = (b / total) * 100;
  const cPct = (c / total) * 100;
  refs.barA.style.width = `${aPct}%`;
  refs.barB.style.width = `${bPct}%`;
  refs.barC.style.width = `${cPct}%`;
  refs.pctA.textContent = `${aPct.toFixed(1)}%`;
  refs.pctB.textContent = `${bPct.toFixed(1)}%`;
  refs.pctC.textContent = `${cPct.toFixed(1)}%`;

  animateValue("countA", a);
  animateValue("countB", b);
  animateValue("countC", c);
}

function averageLoss(lossAnalysis, isRatio = true) {
  const values = Object.values(lossAnalysis || {}).map(Number);
  if (!values.length) {
    return 0;
  }
  const sum = values.reduce((acc, value) => acc + value, 0);
  const avg = sum / values.length;
  return isRatio ? avg * 100 : avg;
}

function setFeedback(message, className) {
  refs.voteFeedback.className = `feedback ${className}`;
  refs.voteFeedback.textContent = message;
}

function stableClientId(username) {
  let value = 0;
  for (const ch of username) {
    value = (value * 131 + ch.charCodeAt(0)) % 900000;
  }
  return 100000 + value;
}

function stableSequence(username) {
  let value = 7;
  for (const ch of username) {
    value = (value * 257 + ch.charCodeAt(0)) % 100000;
  }
  return value;
}

function castVoteViaWebSocket(option) {
  if (!wsConnected) {
    setFeedback("WebSocket not connected. Using HTTP fallback...", "error");
    castVoteViaHTTP(option);
    return;
  }

  if (!login.ready) {
    setFeedback("Login first to cast a vote", "error");
    return;
  }

  const clientId = login.clientId;
  const sequenceNum = login.sequence;
  const optionMap = { A: 1, B: 2, C: 3 };

  const votePayload = {
    type: "vote",
    token: login.token,
    username: login.username,
    option: option,
    clientId: clientId,
    sequence: sequenceNum,
    optionId: optionMap[option],
    timestamp: Date.now(),
  };

  try {
    ws.send(JSON.stringify(votePayload));
    setFeedback(`Sending vote for Option ${option}...`, "pending");
  } catch (error) {
    console.error("WebSocket send failed:", error);
    setFeedback("WebSocket send failed, using HTTP fallback...", "error");
    castVoteViaHTTP(option);
  }
}

async function castVoteViaHTTP(option) {
  try {
    const response = await fetch("/api/vote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token: login.token,
        option,
      }),
    });

    const payload = await response.json();
    if (!response.ok) {
      setFeedback(payload.error || "Unable to send vote", "error");
      return;
    }

    setFeedback(`${payload.status} vote for Option ${payload.option}`, payload.status);
    refresh();
  } catch (error) {
    setFeedback("Vote request failed", "error");
  }
}

async function castVote(option) {
  if (!login.ready) {
    setFeedback("Login first to cast a vote", "error");
    return;
  }

  castVoteViaWebSocket(option);
}

async function performLogin() {
  const username = refs.username.value.trim();
  const password = refs.password.value.trim();
  if (!username || !password) {
    refs.loginState.textContent = "Enter username and password.";
    return;
  }

  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const payload = await response.json();
    if (!response.ok) {
      login = { ready: false, username: "", token: "" };
      refs.loginState.textContent = payload.error || "Login failed";
      setFeedback("Unauthorized user", "error");
      return;
    }

    login = {
      ready: true,
      username: payload.username,
      token: payload.token,
      clientId: stableClientId(payload.username),
      sequence: stableSequence(payload.username),
    };
    refs.loginState.textContent = `Logged in as ${payload.username}`;
    setFeedback("Login successful", "accepted");
  } catch (error) {
    refs.loginState.textContent = "Login service unavailable";
    setFeedback("Login request failed", "error");
  }
}

async function refresh() {
  try {
    const response = await fetch("/api/results", { cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();

    const totalPackets = (data.total_votes || 0) + (data.duplicate_votes || 0) + (data.invalid_packets || 0);
    const lossData = data.loss_analysis_percentage || data.loss_analysis || {};
    const loss = averageLoss(lossData, !data.loss_analysis_percentage);

    animateValue("totalPackets", totalPackets);
    animateValue("totalVotes", data.total_votes || 0);
    animateValue("duplicateVotes", data.duplicate_votes || 0);
    animateValue("avgLoss", loss);
    updateBars(data.tally || {});

    const ts = data.timestamp ? new Date(data.timestamp) : new Date();
    refs.timestamp.textContent = `Updated ${ts.toLocaleTimeString()}`;
  } catch (err) {
    refs.timestamp.textContent = "Reconnecting to data stream...";
  }
}

function connectWebSocket() {
  if (ws !== null) {
    return;
  }

  const WS_URL = `ws://${window.location.hostname}:${WS_PORT}`;
  console.log(`Connecting to WebSocket at ${WS_URL}`);
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log("WebSocket connected");
    wsConnected = true;
  };

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      if (message.type === "connected") {
        console.log("Connected to proxy:", message.message);
      } else if (message.type === "vote_ack") {
        console.log("Vote acknowledged:", message);
        setFeedback(`${message.status} vote for Option ${message.option}`, message.status);
        refresh();
      } else if (message.type === "vote_error") {
        console.error("Vote error:", message.error);
        setFeedback(message.error, "error");
      } else if (message.type === "pong") {
        // Keep-alive response
      }
    } catch (err) {
      console.error("Error parsing WebSocket message:", err);
    }
  };

  ws.onerror = (error) => {
    console.error("WebSocket error:", error);
    wsConnected = false;
  };

  ws.onclose = () => {
    console.log("WebSocket disconnected");
    wsConnected = false;
    ws = null;
    // Try to reconnect in 3 seconds
    setTimeout(connectWebSocket, 3000);
  };
}

async function fetchConfig() {
  try {
    const response = await fetch("/api/config");
    if (response.ok) {
      const config = await response.json();
      WS_PORT = config.ws_port || 9001;
      console.log(`WebSocket port from config: ${WS_PORT}`);
    }
  } catch (err) {
    console.error("Failed to fetch config:", err);
  }
}

refs.loginBtn.addEventListener("click", performLogin);
document.querySelectorAll("[data-option]").forEach((button) => {
  button.addEventListener("click", () => castVote(button.dataset.option));
});

// Fetch config and attempt WebSocket connection on page load
fetchConfig().then(() => connectWebSocket());

refresh();
setInterval(refresh, 1200);
