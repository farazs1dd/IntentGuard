const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

// DOM simulation, not browser automation: no remote debugging or external calls.
class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.dataset = {}; this.listeners = {};
    this.disabled = false; this.checked = false; this._text = ""; this.value = "";
    const classes = new Set();
    this.classList = {toggle(name, force) {
      if (force) classes.add(name); else classes.delete(name);
    }};
  }
  append(...nodes) { this.children.push(...nodes); }
  prepend(...nodes) { this.children.unshift(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; this._text = ""; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(n => n.textContent || "").join(""); }
  set innerHTML(value) { throw new Error("Untrusted HTML rendering is not allowed"); }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  async fire(name) {
    for (const handler of this.listeners[name] || []) {
      await handler({target: this, preventDefault() {}});
    }
  }
  all() { return this.children.flatMap(c => c instanceof Element ? [c, ...c.all()] : []); }
  querySelectorAll(selector) {
    const matches = selector.split(",").map(s => s.trim());
    return this.all().filter(element => matches.some(part => {
      if (part.startsWith("[data-")) {
        const key = part.slice(6, -1).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
        return Object.hasOwn(element.dataset, key);
      }
      return element.tag === part;
    }));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

function documentFromHTML(html) {
  const root = new Element("root"), stack = [root], ids = new Map();
  for (const token of html.match(/<[^>]*>|[^<]+/g)) {
    if (token.startsWith("<!")) continue;
    if (token.startsWith("</")) {
      const tag = token.match(/^<\/([\w-]+)/)[1];
      while (stack.length > 1 && stack.pop().tag !== tag) {}
    } else if (token.startsWith("<")) {
      const match = token.match(/^<([\w-]+)(.*)>$/s);
      if (!match) continue;
      const element = new Element(match[1]);
      for (const attr of match[2].matchAll(/([\w-]+)="([^"]*)"/g)) {
        element[attr[1]] = attr[2];
      }
      stack.at(-1).append(element);
      if (element.id) ids.set(element.id, element);
      if (!["input", "link", "meta", "br", "hr", "img"].includes(element.tag)) stack.push(element);
    } else {
      stack.at(-1)._text += token;
      if (stack.at(-1).tag === "textarea") stack.at(-1).value += token;
    }
  }
  return {
    root, getElementById: id => ids.get(id),
    createElement: tag => new Element(tag),
    querySelectorAll: selector => root.querySelectorAll(selector)
  };
}

async function harness({transport = "https", gatewayAvailable = false} = {}) {
  const repo = path.resolve(__dirname, "..");
  const document = documentFromHTML(fs.readFileSync(path.join(repo, "composition_dashboard.html"), "utf8"));
  const db = {compositions: [], runs: [], policies: [], approvals: [], sessions: [],
    capabilities: {gateway: {ready: true, available: gatewayAvailable, message: "Gateway configured"}, live: {ready: false}}};
  const requests = [], jobs = [], storage = new Map();
  const info = {ready: true, preflight_ready: true, transport, preflight: null};
  let clock = 0;
  const snapshot = () => structuredClone({...db, snapshot_at: ++clock});
  const sandbox = {
    document, console, Map, JSON, Date, Promise,
    location: {protocol: "http:", host: "localhost:8001"},
    localStorage: {getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, String(value)), removeItem: key => storage.delete(key)},
    crypto: {randomUUID: () => "fixture-call"}, confirm: () => true,
    setInterval() {}, setTimeout() {}, WebSocket: class {},
    fetch: async (url, options = {}) => {
      const body = options.body ? JSON.parse(options.body) : undefined;
      requests.push({url, body});
      let data;
      if (url === "/api/state") data = snapshot();
      else if (url === "/api/gateway") data = structuredClone(info);
      else if (url === "/api/compositions") {
        data = {id: "gateway-comp", ...body, hash: "fixture-hash"};
        db.compositions.unshift(data);
      } else if (url === "/api/gateway/preflight") {
        assert.equal(body.approve_budget, true);
        if (transport === "http") assert.equal(body.acknowledge_http, true);
        info.preflight = {status: "passed"}; data = info.preflight;
      } else if (url === "/api/campaigns" && body) {
        data = {
          id: "campaign-1", ...body, status: "draft", stage: "analyzing", provenance: "gateway_agentic",
          budget: {requests: 0, input_tokens: 0, output_tokens: 0, cost_known: false, usd: 0,
            limits: body.limits},
          estimate: {requests: 140}, proposals: [], analysis: {hypotheses: [{id: "h1"}]}
        };
        jobs.unshift(data);
      } else if (url === "/api/campaigns") data = structuredClone(jobs);
      else if (url === "/api/campaigns/campaign-1") data = structuredClone(jobs[0]);
      else if (url.endsWith("/start")) {
        assert.equal(body.approve_budget, true);
        const job = jobs[0];
        if (job.stage === "analyzing") job.status = "corpus_review";
        else if (job.stage === "discovery") {
          job.status = "policy_review";
          job.proposals = [
            {id: "supported", name: "Recipients", supported: true, rules: [{kind: "recipients"}]},
            {id: "unsupported", name: "Recommendation", supported: false, rules: []}
          ];
        } else job.status = "complete";
        data = {status: "queued"};
      } else if (url.endsWith("/review")) {
        const job = jobs[0];
        assert.equal(body.approve, true);
        if (job.status === "corpus_review") {
          assert.deepEqual(body.policy_ids, []);
          job.stage = "discovery";
        } else {
          assert.deepEqual(body.policy_ids, ["supported"]);
          job.stage = "validation";
        }
        job.status = "partial"; data = structuredClone(job);
      } else throw new Error("Unexpected UI request " + url);
      return {ok: true, json: async () => data};
    }
  };
  sandbox.window = sandbox;
  const context = vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(repo, "static/assurance.js"), "utf8"), context);
  vm.runInContext(fs.readFileSync(path.join(repo, "static/campaigns.js"), "utf8"), context);
  const settle = async () => {
    for (let i = 0; i < 10; i++) await new Promise(resolve => setImmediate(resolve));
    assert.equal(vm.runInContext("busy", context), false);
  };
  const poll = async () => {
    await vm.runInContext("refreshCampaigns()", context);
    await settle();
  };
  await settle();
  const byId = id => document.getElementById(id);
  const click = async text => {
    const button = document.querySelectorAll("button").find(b => b.textContent === text);
    assert.ok(button, "Missing button " + text);
    assert.equal(button.disabled, false, "Disabled button " + text);
    await button.fire("click");
    await settle();
  };
  return {context, document, byId, click, settle, poll, requests, jobs};
}

test("gateway campaign consent, corpus review and supported policy selection", async () => {
  const app = await harness();
  app.byId("mode").value = "gateway";
  app.byId("name").value = "Gateway composition";
  app.byId("model").value = "operator-route";
  await app.byId("composition-form").fire("submit");
  await app.settle(); await app.poll();
  assert.match(app.byId("composition-info").textContent, /GATEWAY/);
  assert.equal(app.byId("new-session").disabled, true);
  assert.equal(app.byId("gateway-preflight").querySelector("button").disabled, true);
  app.byId("preflight-consent").checked = true;
  await app.byId("preflight-consent").fire("change");
  app.byId("block-probe").value = "Operator-approved fixture";
  app.byId("preflight-cap").value = "3";
  await app.byId("gateway-preflight").fire("submit");
  await app.settle(); await app.poll();
  app.byId("business-context").value = "Only share with the approved analyst.";
  app.byId("campaign-cases").value = "10";
  await app.byId("campaign-form").fire("submit");
  await app.settle(); await app.poll();
  assert.equal(app.jobs[0].status, "draft");
  assert.equal(app.requests.filter(r => r.url.endsWith("/start")).length, 0);
  const run = async expected => {
    app.byId("campaign-consent").checked = true;
    await app.byId("campaign-consent").fire("change");
    await app.click("Approve budget & run next stage");
    assert.equal(app.byId("campaign-consent").checked, false);
    await app.poll();
    assert.equal(app.jobs[0].status, expected);
    assert.match(app.byId("campaign-items").textContent, new RegExp(expected));
  };
  await run("corpus_review");
  await app.click("Inspect campaign");
  assert.match(app.byId("campaign-evidence").textContent, /hypotheses/);
  await app.click("Approve hypotheses & discovery corpus");
  await app.poll();
  assert.equal(app.requests.filter(r => r.url.endsWith("/start")).length, 1);
  await run("policy_review");
  const boxes = app.byId("campaign-items").querySelectorAll("input");
  assert.equal(boxes[1].disabled, true);
  boxes[0].checked = true; await boxes[0].fire("change");
  await app.poll();
  assert.equal(app.byId("campaign-items").querySelectorAll("input")[0].checked, true);
  await app.click("Freeze selected policies for held-out validation");
  await app.poll();
  await run("complete");
  assert.equal(app.requests.filter(r => r.url.endsWith("/start")).length, 3);
});

test("deployed HTTP gateway defaults and transport consent remain explicit", async () => {
  const app = await harness({transport: "http", gatewayAvailable: true});
  assert.equal(app.byId("mode").value, "gateway");
  app.byId("preflight-consent").checked = true;
  await app.byId("preflight-consent").fire("change");
  const submit = app.byId("gateway-preflight").querySelector("button");
  assert.equal(submit.disabled, true);
  app.byId("http-consent").checked = true;
  await app.byId("http-consent").fire("change");
  assert.equal(submit.disabled, false);
  app.byId("block-probe").value = "Operator-approved fixture";
  app.byId("preflight-cap").value = "3";
  await app.byId("gateway-preflight").fire("submit");
  await app.settle();
  const sent = app.requests.find(r => r.url === "/api/gateway/preflight");
  assert.equal(sent.body.acknowledge_http, true);
  assert.equal(app.byId("http-consent").checked, false);
  assert.equal(app.byId("preflight-consent").checked, false);
});
