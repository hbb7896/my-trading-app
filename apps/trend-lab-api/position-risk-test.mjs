import { test } from "node:test";
import assert from "node:assert/strict";
import {
  applyPositionAction as apply,
  cycleMetrics as metrics,
  simulatePosition as simulate,
  defaultRiskRules as rules,
  riskStatistics,
  fixed,
} from "./position-risk.mjs";
import { createApp } from "./server.mjs";
import {
  capitalPlan,
  unitOrder,
  configuredAccounts,
  accountOverview,
} from "./position-risk.mjs";

test("capital alone determines E, R, units and risk across the three accounts", () => {
  for (const [capital, oneE, oneR, unitBudget, unitRisk] of [
    ["70000000", 17500000, 875000, 4375000, 218750],
    ["13000000", 3250000, 162500, 812500, 40625],
    ["9000000", 2250000, 112500, 562500, 28125],
  ]) {
    const p = capitalPlan(capital);
    assert.deepEqual(
      [p.oneE, p.oneR, p.unitBudget, p.unitRisk],
      [oneE, oneR, unitBudget, unitRisk],
    );
  }
  assert.equal(capitalPlan("1").unitRisk, 0.003125);
  for (const invalid of ["0", "-1", "NaN", "1300.5", "1300万", "1000000000001"])
    assert.throws(() => capitalPlan(invalid));
  const order = unitOrder("13000000", "100000");
  assert.equal(order.quantity, 8);
  assert.equal(order.stop, 95000);
  assert.equal(order.buyAmount, 800000);
  assert.equal(order.unusedBudget, 12500);
});

test("account cycles fix capital-based R and cost-based E while preserving legacy cycles", () => {
  const action = {
    type: "buy",
    actionId: "account_first",
    at: "2026-11-16T09:00:00+09:00",
    ticker: "계좌 검증",
    price: "8125",
    quantity: "100",
    stop: "7718.75",
    basis: {
      mode: "account-capital-v1",
      accountId: "isa",
      capital: "13000000",
    },
  };
  let c = apply(null, action, "account-cycle");
  assert.deepEqual(
    [metrics(c).initialR, metrics(c).e, metrics(c).cr],
    [162500, 0.25, 0.25],
  );
  c = act(c, "mark", { price: "9750" });
  assert.equal(metrics(c).e, 0.25);
  assert.equal(metrics(c).unrealizedR, 1);
  c = act(c, "buy", { price: "8125", quantity: "100", stop: "7718.75" });
  assert.equal(metrics(c).e, 0.5);
  assert.equal(metrics(c).cr, 0.5);
  c = act(c, "sell", {
    price: "9750",
    allocations: [{ lotId: "account_first", quantity: "50" }],
  });
  assert.equal(metrics(c).e, 0.375);
  assert.equal(metrics(c).initialR, 162500);
  assert.throws(() =>
    act(c, "mark", {
      price: "9750",
      basis: { ...action.basis, capital: "9000000" },
    }),
  );
  assert.equal(metrics(start()).initialR, 1000000);
});

test("overview sums money across accounts without adding different R units", () => {
  const accounts = configuredAccounts({}).map((a) => ({
    ...a,
    capital:
      a.id === "isa" ? "13000000" : a.id === "general" ? "9000000" : "70000000",
  }));
  const make = (accountId, capital) =>
    apply(
      null,
      {
        type: "buy",
        actionId: "first",
        at: "2026-11-17T09:00:00Z",
        ticker: "합산 검증",
        price: "100",
        quantity: "10",
        stop: "95",
        basis: { mode: "account-capital-v1", accountId, capital },
      },
      accountId,
    );
  const result = accountOverview(
    [make("isa", "13000000"), make("general", "9000000"), start()],
    { ...rules, accounts },
  );
  assert.equal(result.totalCapital, 92000000);
  assert.equal(result.totalRiskAmount, 100);
  assert.equal(result.unassignedCycles, 1);
  assert.equal(result.accounts[0].active, 0);
  assert.equal(result.accounts[1].active, 1);
});

test("account settings persist; new cycles snapshot funds and old cycles never change on edits", async () => {
  const { mkdtempSync, rmSync } = await import("node:fs"),
    { tmpdir } = await import("node:os"),
    { join } = await import("node:path");
  const folder = mkdtempSync(join(tmpdir(), "rce-accounts-")),
    token = "account-settings-test-token-123456",
    dbPath = join(folder, "test.sqlite");
  let server = createApp({ token, dbPath });
  const startServer = async () => {
    await new Promise((r) => server.listen(0, "127.0.0.1", r));
    return "http://127.0.0.1:" + server.address().port;
  };
  let base = await startServer();
  const call = async (path, method = "GET", body) => {
    const r = await fetch(base + path, {
      method,
      headers: {
        Authorization: "Bearer " + token,
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    return { status: r.status, data: await r.json() };
  };
  try {
    const accounts = configuredAccounts({}).map((a) => ({
      ...a,
      capital:
        a.id === "isa"
          ? "13000000"
          : a.id === "general"
            ? "9000000"
            : "70000000",
    }));
    assert.equal(
      (await call("/api/positions/accounts", "PUT", { accounts })).status,
      200,
    );
    const initial = {
      type: "buy",
      accountId: "isa",
      actionId: "one",
      at: "2026-11-17T09:00:00Z",
      ticker: "계좌 API 검증",
      price: "8125",
      quantity: "100",
      stop: "7718.75",
      basis: { mode: "account-capital-v1", accountId: "isa", capital: "1" },
    };
    let saved = await call("/api/positions/isa-one/action", "POST", initial);
    assert.equal(saved.status, 200);
    assert.equal(saved.data.initialR, 162500);
    assert.equal(saved.data.e, 0.25);
    accounts[1].capital = "26000000";
    assert.equal(
      (await call("/api/positions/accounts", "PUT", { accounts })).status,
      200,
    );
    assert.equal((await call('/api/positions/stale/action','POST',{...initial,actionId:'stale',expectedCapital:'13000000'})).status,409);
    saved = await call("/api/positions/isa-one/action", "POST", initial);
    assert.equal(saved.status, 200);
    assert.equal(saved.data.initialR, 162500);
    const oldPlan = await call("/api/positions/unit-plan", "POST", {
      accountId: "isa",
      cycleId: "isa-one",
      price: "100000",
    });
    assert.equal(oldPlan.data.quantity, 8);
    const newPlan = await call("/api/positions/unit-plan", "POST", {
      accountId: "isa",
      price: "100000",
    });
    assert.equal(newPlan.data.quantity, 16);
    assert.equal(
      (
        await call("/api/positions/unit-plan", "POST", {
          accountId: "general",
          cycleId: "isa-one",
          price: "100000",
        })
      ).status,
      400,
    );
    saved = await call("/api/positions/isa-two/action", "POST", {
      ...initial,
      actionId: "two",
    });
    assert.equal(saved.data.initialR, 325000);
    await new Promise((r) => server.close(r));
    server = createApp({ token, dbPath });
    base = await startServer();
    const state = (await call("/api/positions")).data;
    assert.equal(state.accounts[1].capital, "26000000");
    assert.equal(state.cycles.find((c) => c.id === "isa-one").initialR, 162500);
    assert.equal(state.cycles.find((c) => c.id === "isa-two").initialR, 325000);
    assert.deepEqual((await call("/api/trades")).data, []);
  } finally {
    await new Promise((r) => server.close(r));
    rmSync(folder, { recursive: true, force: true });
  }
});
let serial = 0;
const act = (c, type, data = {}) =>
  apply(
    c,
    {
      actionId: "T_" + ++serial,
      version: c?.version ?? 0,
      type,
      at: "2026-11-16T09:00:00+09:00",
      ...data,
    },
    "cycle",
  );
const start = (data = {}) =>
  act(null, "buy", {
    ticker: "검증",
    code: "005930",
    price: "100000",
    quantity: "100",
    stop: "90000",
    ...data,
  });
test("book five stages: immutable R, independent lots, partial sales, final +5R", () => {
  let c = start();
  assert.deepEqual(
    [metrics(c).initialR, metrics(c).cr, metrics(c).e, metrics(c).unrealizedR],
    [1000000, 1, 1, 0],
  );
  const first = c.events[0].id;
  c = act(c, "mark", { price: "110000" });
  c = act(c, "stop", { lotId: first, stop: "100000" });
  assert.deepEqual(
    [metrics(c).unrealizedR, metrics(c).cr, metrics(c).e],
    [1, 0, 1],
  );
  assert.equal(metrics(c).givebackR, 1);
  c = act(c, "buy", { price: "120000", quantity: "100", stop: "110000" });
  const second = c.events.at(-1).id;
  assert.deepEqual(
    [
      metrics(c).e,
      metrics(c).cr,
      metrics(c).unrealizedR,
      metrics(c).protectedR,
    ],
    [2, 1, 2, -1],
  );
  assert.equal(metrics(c).givebackR, 3);
  assert.equal(metrics(c).givebackPercent, 150);
  c = act(c, "sell", {
    price: "140000",
    allocations: [
      { lotId: first, quantity: "50" },
      { lotId: second, quantity: "50" },
    ],
  });
  assert.deepEqual(
    [
      metrics(c).realizedR,
      metrics(c).unrealizedR,
      metrics(c).totalR,
      metrics(c).e,
    ],
    [3, 3, 6, 1],
  );
  c = act(c, "stop", { lotId: first, stop: "100000" });
  c = act(c, "stop", { lotId: second, stop: "120000" });
  assert.equal(metrics(c).cr, 0);
  assert.equal(metrics(c).protectedR, 3);
  c = act(c, "sell", {
    price: "130000",
    allocations: [
      { lotId: first, quantity: "50" },
      { lotId: second, quantity: "50" },
    ],
  });
  assert.deepEqual(
    [metrics(c).realizedR, metrics(c).e, metrics(c).cr, metrics(c).initialR],
    [5, 0, 0, 1000000],
  );
  assert.equal(metrics(c).totalR, 5);
  assert.equal(metrics(c).closed, true);
  assert.throws(() =>
    act(c, "buy", { price: "100000", quantity: "100", stop: "90000" }),
  );
  assert.equal(metrics(start()).initialR, 1000000);
});
test("stop above cost protects gains independently; half and full pyramid exposures", () => {
  let c = start();
  const id = c.events[0].id;
  c = act(c, "mark", { price: "120000" });
  c = act(c, "stop", { lotId: id, stop: "110000" });
  assert.equal(metrics(c).cr, 0);
  assert.equal(metrics(c).protectedR, 1);
  assert.equal(metrics(c).givebackR, 1);
  const half = act(c, "buy", {
    price: "120000",
    quantity: "50",
    stop: "110000",
  });
  assert.equal(metrics(half).e, 1.5);
  assert.equal(metrics(half).cr, 0.5);
  assert.equal(metrics(c).initialR, metrics(half).initialR);
});
test("missing and zero risk remain unknown, never inferred from historical loss", () => {
  for (const stop of ["", null, "100000"]) {
    const c = start({ stop });
    assert.equal(metrics(c).initialR, null);
    assert.equal(metrics(c).cr, null);
    assert.equal(metrics(c).realizedR, null);
    assert.equal(metrics(c).basisStatus, "기준 정보 부족");
  }
});
test("validate quantities, dates, duplicate orders and allocation over-selling", () => {
  assert.throws(() => start({ quantity: "0" }));
  assert.throws(() => start({ quantity: "-1" }));
  assert.throws(() => fixed("0.0000001"));
  assert.throws(() => start({ stop: "110000" }));
  assert.throws(() => start({ at: "bad" }));
  const c = start(),
    id = c.events[0].id;
  assert.throws(() =>
    act(c, "sell", {
      price: "110000",
      allocations: [{ lotId: id, quantity: "101" }],
    }),
  );
  assert.throws(() =>
    act(c, "sell", {
      price: "110000",
      allocations: [
        { lotId: id, quantity: "1" },
        { lotId: id, quantity: "1" },
      ],
    }),
  );
  const a = {
      actionId: "unique",
      version: c.version,
      type: "mark",
      at: "2026-11-16T10:00:00+09:00",
      price: "110000",
    },
    next = apply(c, a);
  assert.deepEqual(apply(next, a), next);
  assert.throws(() => apply(next, { ...a, price: "120000" }));
  assert.throws(
    () => apply(next, { ...a, actionId: "different" }),
    (e) => e.status === 409,
  );
  assert.throws(() =>
    act(next, "mark", { price: "120000", at: "2026-11-16T08:00:00+09:00" }),
  );
});
test("simulation is read-only with independent stops and reduced quantities", () => {
  let c = start();
  c = act(c, "mark", { price: "120000" });
  c = act(c, "stop", { lotId: c.events[0].id, stop: "100000" });
  const snapshot = JSON.stringify(c),
    s = simulate(
      c,
      { price: "120000", quantity: "100", stop: "110000" },
      rules,
    );
  assert.equal(JSON.stringify(c), snapshot);
  assert.deepEqual(
    [
      s.before.e,
      s.before.cr,
      s.after.e,
      s.after.cr,
      s.after.protectedR,
      s.after.givebackR,
    ],
    [1, 0, 2, 1, -1, 3],
  );
  assert.equal(s.reduced.e, 1.5);
  assert(s.after.warnings.includes("계획상 보호 수익 부족"));
});
test("fractional prices and quantities do not accumulate floating point money errors; fees counted once", () => {
  let c = start({ price: "0.3", quantity: "0.3", stop: "0.1", fee: "0.01" });
  c = act(c, "sell", {
    price: "0.4",
    fee: "0.01",
    allocations: [{ lotId: c.events[0].id, quantity: "0.3" }],
  });
  assert.equal(metrics(c).realized, 0.01);
  assert.equal(metrics(c).fees, 0.02);
});
test("simulator values all lots at scenario quote, rules are editable and can be disabled", () => {
  const c = start(),
    snapshot = JSON.stringify(c),
    a = simulate(
      c,
      {
        price: "120000",
        quantity: "100",
        stop: "110000",
        stops: [{ lotId: c.events[0].id, stop: "120000" }],
      },
      rules,
    );
  assert.equal(a.before.totalR, 2);
  assert.equal(a.after.protectedR, 1);
  assert.equal(a.after.cr, 1);
  assert.equal(JSON.stringify(c), snapshot);
  assert.equal(
    metrics(c, { ...rules, accountValue: "100000000" }).initialRiskPercent,
    1,
  );
  assert(
    metrics(c, { ...rules, accountValue: "100000000" }).warnings.includes(
      "지정한 초기 위험 한도 초과",
    ),
  );
  assert.deepEqual(
    metrics(c, { ...rules, enabled: false, accountValue: "100000000" })
      .warnings,
    [],
  );
  assert.throws(() => start({ at: "2026-02-30T10:00:00Z" }));
});
test("R performance excludes unknown basis, includes breakevens in denominator", () => {
  const end = (change, missing = false) => {
    let c = start({ stop: missing ? "" : "90000" });
    return act(c, "sell", {
      price: String(100000 + change),
      allocations: [{ lotId: c.events[0].id, quantity: "100" }],
    });
  };
  const s = riskStatistics([end(40000), end(-10000), end(0), end(1000, true)]);
  assert.equal(s.count, 3);
  assert.equal(s.totalR, 3);
  assert.equal(s.expectancy, 1);
  assert.equal(s.breakeven, 1);
  assert.equal(s.missingBasis, 1);
  assert.equal(s.averageWinR, 4);
  assert.equal(s.averageLossR, -1);
});
test("authenticated API persists positions and atomically projects one completed trade; journal preserves R", async () => {
  const token = "risk-test-owner-token-123456789",
    server = createApp({ token });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const call = async (p, method = "GET", body) => {
    const r = await fetch(base + p, {
      method,
      headers: {
        Authorization: "Bearer " + token,
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    return { status: r.status, body: await r.json() };
  };
  try {
    assert.equal((await fetch(base + "/api/positions")).status, 401);
    const a = {
      type: "buy",
      actionId: "first",
      version: 0,
      at: "2026-11-16T09:00:00Z",
      ticker: "R테스트",
      price: "100",
      quantity: "10",
      stop: "90",
    };
    assert.equal(
      (await call("/api/positions/cycle/action", "POST", a)).status,
      200,
    );
    const sale = {
      type: "sell",
      actionId: "last",
      version: 1,
      at: "2026-11-16T10:00:00Z",
      price: "120",
      allocations: [{ lotId: "first", quantity: "10" }],
    };
    assert.equal(
      (await call("/api/positions/cycle/action", "POST", sale)).status,
      200,
    );
    assert.equal(
      (await call("/api/positions/cycle/action", "POST", sale)).status,
      200,
    );
    const rows = (await call("/api/trades")).body;
    assert.equal(rows.length, 1);
    assert.equal(rows[0].final_r, 2);
    assert.equal(
      (await call("/api/trades/RISK_cycle", "PUT", rows[0])).status,
      409,
    );
    assert.equal((await call("/api/trades/RISK_cycle", "DELETE")).status, 409);
    const updated = await call("/api/trades/RISK_cycle/journal", "PATCH", {
      ...rows[0],
      memo: "복기",
      original: rows[0],
    });
    assert.equal(updated.status, 200);
    assert.equal(updated.body.final_r, 2);
    assert.equal(updated.body.memo, "복기");
    assert.equal((await call("/api/positions")).body.statistics.totalR, 2);
  } finally {
    await new Promise((r) => server.close(r));
  }
});
