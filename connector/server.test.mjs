import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";
import { TOOLS, workerEnvironment } from "./server.mjs";

const directory = path.dirname(fileURLToPath(import.meta.url));
const python = process.env.CRM_PROTON_PYTHON || (process.platform === "win32" ? "C:\\Python313\\python.exe" : "/usr/bin/python3");

test("worker environment strips credentials, key logging, Python injection, and proxy settings", () => {
  assert.deepEqual(workerEnvironment({ SystemRoot: "windows", LOCALAPPDATA: "private", TEMP: "temp",
    SSLKEYLOGFILE: "must-not-write", PYTHONPATH: "evil", DATABASE_URL: "secret", OPENAI_API_KEY: "secret",
    PROTON_PASSWORD: "secret", HTTP_PROXY: "evil", PATH: "untrusted" }),
  { SystemRoot: "windows", LOCALAPPDATA: "private", TEMP: "temp" });
});

test("tool surface has no arbitrary path, host, password, deletion, attachment execution, or send-policy setter", () => {
  assert.equal(TOOLS.length, 8);
  for (const tool of TOOLS) {
    assert.equal(tool.schema.additionalProperties, false);
    for (const field of Object.keys(tool.schema.properties)) {
      assert.doesNotMatch(field, /password|token|host|path|url|command|sending_enabled/);
    }
  }
  const send = TOOLS.find(t => t.name === "proton_send_draft");
  assert.equal(send.annotations.readOnlyHint, false);
  assert.equal(send.annotations.idempotentHint, false);
  assert.equal(send.annotations.openWorldHint, true);
  assert.deepEqual(send.schema.required, ["draft_id", "expected_digest"]);
  assert.equal(Object.hasOwn(send.schema.properties, "confirmation"), false);
  for (const name of ["proton_check_connection", "proton_list_messages", "proton_read_message"]) {
    const read = TOOLS.find(t => t.name === name);
    assert.equal(read.annotations.openWorldHint, true);
    assert.equal(read.annotations.readOnlyHint, true);
  }
});

test("worker rejects oversized and malformed IPC without echoing data", () => {
  for (const input of ["private-marker-not-json", "x".repeat(300001), JSON.stringify({ tool: "proton_status", arguments: {}, injected: true })]) {
    const run = spawnSync(python, ["-E", "-s", "-S", path.join(directory, "worker.py")],
      { input, encoding: "utf8", windowsHide: true, env: workerEnvironment(), timeout: 10000 });
    assert.equal(run.status, 0);
    assert.equal(run.stderr, "");
    assert.equal(JSON.parse(run.stdout).ok, false);
    assert.doesNotMatch(run.stdout, /private-marker/);
  }
});

for (const negotiationMode of ["legacy", "auto"]) {
  test(`actual STDIO MCP handshake and safe unconfigured status (${negotiationMode})`, async () => {
    const temporary = await mkdtemp(path.join(os.tmpdir(), "crm-proton-mcp-test-"));
    const transport = new StdioClientTransport({ command: process.execPath,
      args: [path.join(directory, "server.mjs")], cwd: directory,
      env: { ...process.env, LOCALAPPDATA: temporary, CRM_PROTON_PYTHON: python }, stderr: "pipe" });
    const client = new Client({ name: "proton-synthetic-test", version: "1.0.0" }, { capabilities: {}, negotiationMode });
    let errors = "";
    transport.stderr?.on("data", chunk => { errors += chunk.toString(); });
    try {
      await client.connect(transport);
      const list = await client.listTools();
      assert.deepEqual(list.tools.map(t => t.name), TOOLS.map(t => t.name));
      const status = await client.callTool({ name: "proton_status", arguments: {} });
      if (process.platform === "win32") {
        assert.equal(status.structuredContent.ok, true);
        assert.equal(status.structuredContent.result.configured, false);
        assert.equal(status.structuredContent.result.network_accessed, false);
      } else {
        assert.equal(status.structuredContent.ok, false);
      }
      if (process.platform === 'win32') {
        const result = await client.callTool({name: 'proton_send_draft', arguments: {
          draft_id: '00000000-0000-4000-8000-000000000001', expected_digest: 'a'.repeat(64)}});
        assert.equal(result.structuredContent.ok, false);
        assert.match(result.structuredContent.error, /not configured|setup|enroll/i);
      }
      for (const [name, args] of [["proton_status", { host: "remote.example" }],
        ["proton_list_messages", { folder: "Trash" }], ["proton_read_message", { uid: 1 }],
        ["proton_send_draft", { confirmation: "yes" }], ["proton_prepare_draft", { to: ["a@example.gov"], body: "x" }]]) {
        const refused = await client.callTool({ name, arguments: args });
        assert.equal(refused.isError, true, name);
      }
      assert.equal(errors, "");
    } finally {
      await client.close();
      // Only this test-owned temporary directory is ever removed.
      assert.ok(path.resolve(temporary).startsWith(path.resolve(os.tmpdir()) + path.sep));
      await rm(temporary, { recursive: true, force: true });
    }
  });
}
