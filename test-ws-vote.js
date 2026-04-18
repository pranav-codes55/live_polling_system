const WebSocket = require("ws");

const WS_URL = "ws://localhost:9001";

async function testWebSocketVote() {
  const ws = new WebSocket(WS_URL);

  ws.on("open", () => {
    console.log("Connected to WebSocket proxy");
    
    // Send a vote
    const vote = {
      type: "vote",
      token: "test-token",
      username: "testuser",
      option: "C",
      clientId: 999999,
      sequence: 42,
      optionId: 3,
      timestamp: Date.now(),
    };

    console.log("Sending vote:", vote);
    ws.send(JSON.stringify(vote));
  });

  ws.on("message", (data) => {
    console.log("Received from proxy:", data);
    ws.close();
  });

  ws.on("error", (err) => {
    console.error("WebSocket error:", err.message);
  });

  ws.on("close", () => {
    console.log("WebSocket closed");
  });
}

testWebSocketVote().catch(err => console.error(err));
