const WebSocket = require("ws");
const dgram = require("dgram");
const { crc32 } = require("crc");

const WS_PORT = process.env.WS_PORT || 9001;
const UDP_HOST = process.env.UDP_HOST || "127.0.0.1";
const UDP_PORT = process.env.UDP_PORT || 9999;
const UDP_ACK_TIMEOUT_MS = Number(process.env.UDP_ACK_TIMEOUT_MS || 1500);

const wss = new WebSocket.Server({ port: WS_PORT });
let broadcastSocket = null;
let connectedClients = [];

console.log(`WebSocket proxy starting on ws://0.0.0.0:${WS_PORT}`);
console.log(`Forwarding votes to UDP server at ${UDP_HOST}:${UDP_PORT}`);

// Build vote packet in Python server's binary format
function buildVotePacket(vote) {
  const MAGIC = Buffer.from("VOTE");
  const VERSION = 1;
  const TYPE_VOTE = 1;

  const packet = Buffer.alloc(26); // 4 + 1 + 1 + 2 + 4 + 4 + 2 + 8 bytes
  let offset = 0;

  // Magic: VOTE
  MAGIC.copy(packet, offset);
  offset += 4;

  // Version: 1
  packet[offset] = VERSION;
  offset += 1;

  // Type: 1 (vote)
  packet[offset] = TYPE_VOTE;
  offset += 1;

  // poll_id (2 bytes, big-endian)
  packet.writeUInt16BE(vote.poll_id || 1, offset);
  offset += 2;

  // client_id (4 bytes, big-endian)
  packet.writeUInt32BE(vote.clientId || 0, offset);
  offset += 4;

  // sequence (4 bytes, big-endian)
  packet.writeUInt32BE(vote.sequence || 0, offset);
  offset += 4;

  // option_id (2 bytes, big-endian): A=1, B=2, C=3
  const optionMap = { A: 1, B: 2, C: 3 };
  packet.writeUInt16BE(optionMap[vote.option] || 0, offset);
  offset += 2;

  // timestamp_ms (8 bytes, big-endian)
  const timestamp = BigInt(vote.timestamp || Date.now());
  packet.writeBigUInt64BE(timestamp, offset);
  offset += 8;

  console.log(`Built vote packet (26 bytes base): poll_id=${vote.poll_id || 1}, client_id=${vote.clientId}, option=${vote.option}, timestamp=${vote.timestamp}`);

  // Calculate CRC32 and append
  const crcValue = crc32(packet);
  const withCrc = Buffer.alloc(30);
  packet.copy(withCrc, 0);
  withCrc.writeUInt32BE(crcValue, 26);

  console.log(`CRC32: ${crcValue.toString(16).padStart(8, '0')}`);

  return withCrc;
}

// Broadcast message to all connected WebSocket clients
function broadcastToClients(message) {
  connectedClients = connectedClients.filter((client) => client.readyState === WebSocket.OPEN);

  connectedClients.forEach((client) => {
    try {
      client.send(JSON.stringify(message));
    } catch (err) {
      console.error("Error broadcasting to client:", err.message);
    }
  });
}

// Create UDP socket for sending votes
function parseAckPacket(buffer) {
  // ACK packet format from Python: !4sBBHIIb + CRC32
  if (!Buffer.isBuffer(buffer) || buffer.length !== 21) {
    return null;
  }

  const base = buffer.subarray(0, 17);
  const packetCrc = buffer.readUInt32BE(17);
  const computed = (crc32(base) >>> 0);
  if (computed !== packetCrc) {
    return null;
  }

  const magic = base.subarray(0, 4).toString("ascii");
  const version = base.readUInt8(4);
  const pktType = base.readUInt8(5);
  if (magic !== "VOTE" || version !== 1 || pktType !== 2) {
    return null;
  }

  return {
    pollId: base.readUInt16BE(6),
    clientId: base.readUInt32BE(8),
    sequence: base.readUInt32BE(12),
    statusCode: base.readInt8(16),
  };
}

function mapStatus(statusCode) {
  if (statusCode === 1) {
    return "accepted";
  }
  if (statusCode === 2) {
    return "duplicate";
  }
  return "invalid";
}

function sendVoteToUDP(votePacket, voteMeta) {
  return new Promise((resolve, reject) => {
    const client = dgram.createSocket("udp4");
    let timer = null;

    const cleanup = () => {
      if (timer) {
        clearTimeout(timer);
      }
      client.removeAllListeners("message");
      client.removeAllListeners("error");
      client.close();
    };

    client.on("error", (err) => {
      console.error(`UDP socket error: ${err.message}`);
      cleanup();
      reject(err);
    });

    client.on("message", (msg) => {
      const ack = parseAckPacket(msg);
      if (!ack) {
        return;
      }

      // Match ACK to the vote request this socket sent.
      if (ack.clientId !== (voteMeta.clientId >>> 0) || ack.sequence !== (voteMeta.sequence >>> 0)) {
        return;
      }

      cleanup();
      resolve(ack);
    });
    
    console.log(`Sending ${votePacket.length} byte packet to ${UDP_HOST}:${UDP_PORT}`);
    console.log(`Packet hex: ${votePacket.toString("hex")}`);
    
    client.send(votePacket, UDP_PORT, UDP_HOST, (err) => {
      if (err) {
        console.error(`UDP send error: ${err.message}`);
        cleanup();
        reject(err);
      } else {
        console.log("Vote packet sent successfully to UDP server");
        timer = setTimeout(() => {
          cleanup();
          reject(new Error(`UDP ACK timeout after ${UDP_ACK_TIMEOUT_MS}ms`));
        }, UDP_ACK_TIMEOUT_MS);
      }
    });
  });
}

// WebSocket connection handler
wss.on("connection", (ws) => {
  console.log(`Client connected. Total clients: ${wss.clients.size}`);
  connectedClients.push(ws);

  // Send initial connection acknowledgment
  ws.send(
    JSON.stringify({
      type: "connected",
      wsPort: WS_PORT,
      message: "Connected to WebSocket proxy",
    })
  );

  ws.on("message", async (data) => {
    try {
      const message = JSON.parse(data);

      if (message.type === "vote") {
        console.log(`Vote received from client: Option ${message.option}, ClientID ${message.clientId}`);
        try {
          const votePacket = buildVotePacket(message);
          const ack = await sendVoteToUDP(votePacket, {
            clientId: message.clientId || 0,
            sequence: message.sequence || 0,
          });
          const status = mapStatus(ack.statusCode);
          ws.send(
            JSON.stringify({
              type: "vote_ack",
              status,
              code: ack.statusCode,
              clientId: message.clientId,
              option: message.option,
            })
          );
        } catch (err) {
          console.error("Error sending vote to UDP:", err.message);
          ws.send(
            JSON.stringify({
              type: "vote_error",
              error: "Failed to send vote to server",
              clientId: message.clientId,
            })
          );
        }
      } else if (message.type === "ping") {
        ws.send(JSON.stringify({ type: "pong" }));
      }
    } catch (err) {
      console.error("Error processing message:", err.message);
      ws.send(
        JSON.stringify({
          type: "error",
          error: "Invalid message format",
        })
      );
    }
  });

  ws.on("close", () => {
    connectedClients = connectedClients.filter((client) => client !== ws);
    console.log(`Client disconnected. Total clients: ${wss.clients.size}`);
  });

  ws.on("error", (err) => {
    console.error("WebSocket error:", err.message);
  });
});

console.log("WebSocket proxy server ready for connections");
