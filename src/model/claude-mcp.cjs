// Stdio MCP adapter to the local, authenticated game bridge owned by this process.
const readline = require('node:readline');
const endpoint = process.env.MINECRAFT_MCP_ENDPOINT;
const token = process.env.MINECRAFT_MCP_TOKEN;
const send = value => process.stdout.write(JSON.stringify(value) + '\n');
readline.createInterface({ input: process.stdin }).on('line', async line => {
  let request;
  try { request = JSON.parse(line); } catch { return; }
  if (request.id == null) return;
  try {
    let result;
    if (request.method === 'initialize') result = { protocolVersion: '2024-11-05', capabilities: { tools: {} }, serverInfo: { name: 'minecraft', version: '1.0.0' } };
    else if (request.method === 'ping') result = {};
    else if (request.method === 'tools/list' || request.method === 'tools/call') {
      const res = await fetch(endpoint, { method: 'POST', headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' }, body: JSON.stringify({ method: request.method, params: request.params }) });
      if (!res.ok) throw new Error(`Bridge HTTP ${res.status}`);
      result = await res.json();
    } else throw new Error('Unsupported MCP method');
    send({ jsonrpc: '2.0', id: request.id, result });
  } catch (e) { send({ jsonrpc: '2.0', id: request.id, error: { code: -32603, message: e.message } }); }
});
