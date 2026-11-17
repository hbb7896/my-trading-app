// Monetary products use 12 decimal places. Floating point is used only for display ratios.
import { validDate } from "./analysis.js";
import { isDeepStrictEqual } from "node:util";
const S = 1000000n,
  M = S * S;
export function fixed(value, { zero = false, max = 1000000000000n } = {}) {
  const s = String(value ?? "");
  if (!/^\d{1,13}(\.\d{1,6})?$/.test(s))
    throw Error("가격과 수량은 음수가 아닌 숫자, 소수점 6자리까지 입력하세요.");
  const [a, b = ""] = s.split(".");
  const n = BigInt(a) * S + BigInt(b.padEnd(6, "0"));
  if ((zero ? n < 0n : n <= 0n) || n > max * S)
    throw Error("가격 또는 수량 범위를 확인하세요.");
  return n;
}
const money = (n) => Number(n) / Number(M),
  quantity = (n) => Number(n) / Number(S),
  ratio = (n, d) => (d > 0n ? Number((n * 1000000000n) / d) / 1e9 : null);
const positive = (n) => (n > 0n ? n : 0n);
export const accountTypes = [
  { id: "dc", name: "DC 퇴직연금" },
  { id: "isa", name: "ISA" },
  { id: "general", name: "일반" },
];
export function capitalPlan(amount) {
  if (!/^\d{1,13}$/.test(String(amount)))
    throw Error("기준 자금은 원 단위 정수로 입력하세요.");
  const capital = fixed(amount) * S;
  return {
    capital: money(capital),
    oneE: money(capital / 4n),
    oneR: money(capital / 80n),
    unitBudget: money(capital / 16n),
    unitRisk: money(capital / 320n),
    stopPercent: 5,
    initialRiskPercent: 1.25,
    unitsPerE: 4,
  };
}
export function validateAccounts(input) {
  if (
    !Array.isArray(input) ||
    input.length !== 3 ||
    new Set(input.map((a) => a?.id)).size !== 3
  )
    throw Error("DC·ISA·일반 계좌를 각각 설정하세요.");
  return accountTypes.map((t) => {
    const a = input.find((a) => a?.id === t.id);
    if (!a || typeof a.capital !== "string")
      throw Error("계좌 자금을 확인하세요.");
    if (a.capital !== "") capitalPlan(a.capital);
    return { ...t, capital: a.capital };
  });
}
export function configuredAccounts(rules) {
  return validateAccounts(
    rules.accounts ?? accountTypes.map((t) => ({ ...t, capital: "" })),
  );
}
function accountBasis(basis) {
  if (!basis) return null;
  if (
    basis.mode !== "account-capital-v1" ||
    !accountTypes.some((a) => a.id === basis.accountId)
  )
    throw Error("계좌 기준을 확인하세요.");
  return {
    ...capitalPlan(basis.capital),
    accountId: basis.accountId,
    name: accountTypes.find((a) => a.id === basis.accountId).name,
    capitalText: basis.capital,
  };
}
export function unitOrder(amount, price) {
  const plan = capitalPlan(amount),
    p = fixed(price),
    budget = (fixed(amount) * S) / 16n;
  const shares = budget / (p * S);
  return {
    ...plan,
    quantity: Number(shares),
    stop: quantity((p * 95n) / 100n),
    buyAmount: money(p * shares * S),
    unusedBudget: money(budget - p * shares * S),
  };
}
export function accountOverview(cycles, rules) {
  let totalCapital = 0n,
    totalRisk = 0n,
    totalGiveback = 0n,
    totalMarket = 0n,
    unknown = 0;
  const accounts = configuredAccounts(rules).map((a) => {
    const plan = a.capital === "" ? null : capitalPlan(a.capital);
    if (plan) totalCapital += fixed(a.capital) * S;
    const owned = cycles.filter((c) => c.events[0].basis?.accountId === a.id);
    let risk = 0n,
      giveback = 0n,
      market = 0n,
      missing = false,
      active = 0;
    for (const c of owned) {
      const x = replay(c);
      if (x.closed) continue;
      active++;
      for (const lot of x.lots) {
        if (!lot.remaining) continue;
        market += x.mark * lot.remaining;
        if (lot.stop === null) {
          missing = true;
          unknown++;
          continue;
        }
        risk += positive(lot.price - lot.stop) * lot.remaining;
        giveback += (x.mark - lot.stop) * lot.remaining;
      }
    }
    totalRisk += risk;
    totalGiveback += giveback;
    totalMarket += market;
    return {
      ...a,
      plan,
      active,
      riskAmount: missing ? null : money(risk),
      givebackAmount: missing ? null : money(giveback),
      marketValue: money(market),
      statistics: riskStatistics(owned),
    };
  });
  return {
    accounts,
    totalCapital: money(totalCapital),
    totalRiskAmount: unknown ? null : money(totalRisk),
    knownRiskAmount: money(totalRisk),
    totalGivebackAmount: unknown ? null : money(totalGiveback),
    totalMarketValue: money(totalMarket),
    unknownStops: unknown,
    unassignedCycles: cycles.filter((c) => !c.events[0].basis).length,
  };
}
function text(v, max = 100) {
  if (typeof v !== "string" || !v.trim() || v.length > max)
    throw Error("종목명 또는 식별자를 확인하세요.");
  return v.trim();
}
function date(v) {
  if (
    typeof v !== "string" ||
    !/^\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d(\.\d{1,3})?)?(Z|[+-]\d\d:\d\d)$/.test(
      v,
    ) ||
    !validDate(v.slice(0, 10)) ||
    !Number.isFinite(Date.parse(v))
  )
    throw Error("체결 일시를 확인하세요.");
  return v;
}
export const defaultRiskRules = {
  maxE: "1.5",
  maxCR: "0.5",
  protectAtR: "2",
  minProtectedR: "1",
  initialRiskPercent: "0.5",
  accountValue: "",
  enabled: true,
};
export function validateRules(input) {
  const r = { ...defaultRiskRules, ...input };
  if (typeof r.enabled !== "boolean") throw Error("경고 설정을 확인하세요.");
  for (const k of [
    "maxE",
    "maxCR",
    "protectAtR",
    "minProtectedR",
    "initialRiskPercent",
  ]) {
    fixed(r[k], { zero: true });
    r[k] = String(r[k]);
  }
  if (r.accountValue !== "") fixed(r.accountValue);
  r.accounts = configuredAccounts(r);
  return r;
}
function replay(c) {
  const lots = new Map(),
    ids = new Set();
  let realized = 0n,
    buy = 0n,
    sell = 0n,
    fees = 0n,
    mark = null,
    peak = null,
    pyramidPeak = null,
    closed = false;
  let first = null,
    lastTime = -Infinity;
  for (const e of c.events) {
    if (closed) throw Error("청산된 사이클에는 체결을 추가할 수 없습니다.");
    text(e.id);
    if (ids.has(e.id)) throw Error("중복 주문 기록입니다.");
    ids.add(e.id);
    date(e.at);
    if (Date.parse(e.at) < lastTime)
      throw Error("이전 체결보다 빠른 일시는 입력할 수 없습니다.");
    lastTime = Date.parse(e.at);
    if (e.type === "buy") {
      const p = fixed(e.price),
        q = fixed(e.quantity, { max: 1000000000n }),
        stop =
          e.stop == null || e.stop === ""
            ? null
            : fixed(e.stop, { zero: true });
      if (stop !== null && stop > p)
        throw Error("신규 매수 손절가는 매수가 이하여야 합니다.");
      const fee = fixed(e.fee ?? "0", { zero: true }) * S;
      fees += fee;
      realized -= fee;
      buy += p * q;
      const l = {
        id: e.id,
        at: e.at,
        price: p,
        initial: q,
        remaining: q,
        stop,
        history: [],
        realized: 0n,
        memo: String(e.memo ?? "").slice(0, 10000),
      };
      if (!first) first = l;
      lots.set(e.id, l);
      mark = p;
      if (lots.size > 1) pyramidPeak = null;
    } else if (e.type === "stop") {
      const l = lots.get(e.lotId);
      if (!l || l.remaining === 0n)
        throw Error("보유 중인 매수 차수를 선택하세요.");
      const stop = fixed(e.stop, { zero: true });
      if (mark !== null && stop > mark)
        throw Error("손절가는 현재 입력 주가 이하여야 합니다.");
      l.history.push({
        at: e.at,
        from: l.stop === null ? null : quantity(l.stop),
        to: quantity(stop),
      });
      l.stop = stop;
    } else if (e.type === "sell") {
      const p = fixed(e.price),
        fee = fixed(e.fee ?? "0", { zero: true }) * S;
      let total = 0n;
      const allocated = new Set();
      if (!Array.isArray(e.allocations) || !e.allocations.length)
        throw Error("매도할 차수별 수량을 입력하세요.");
      for (const a of e.allocations) {
        if (allocated.has(a.lotId)) throw Error("차수 배분이 중복됐습니다.");
        allocated.add(a.lotId);
        const l = lots.get(a.lotId),
          q = fixed(a.quantity, { max: 1000000000n });
        if (!l || q > l.remaining)
          throw Error("매도 수량이 해당 차수의 잔여 수량을 초과합니다.");
        l.remaining -= q;
        l.realized += (p - l.price) * q;
        realized += (p - l.price) * q;
        total += q;
      }
      sell += p * total;
      fees += fee;
      realized -= fee;
      mark = p;
    } else if (e.type === "mark") {
      mark = fixed(e.price);
    } else throw Error("지원하지 않는 포지션 변경입니다.");
    let held = 0n,
      total = realized;
    for (const l of lots.values()) {
      held += l.remaining;
      total += (mark - l.price) * l.remaining;
    }
    peak = peak === null || total > peak ? total : peak;
    if (lots.size > 1)
      pyramidPeak =
        pyramidPeak === null || total > pyramidPeak ? total : pyramidPeak;
    closed = held === 0n;
  }
  if (!first) throw Error("최초 매수가 필요합니다.");
  // The first buy event is immutable. Its original stop fixes R forever.
  const firstEvent = c.events[0],
    initialStop =
      firstEvent.stop == null || firstEvent.stop === ""
        ? null
        : fixed(firstEvent.stop, { zero: true });
  const basis = accountBasis(firstEvent.basis);
  const initialR = basis
    ? (fixed(basis.capitalText) * S) / 80n
    : initialStop === null
      ? null
      : (first.price - initialStop) * first.initial;
  return {
    lots: [...lots.values()],
    realized,
    buy,
    sell,
    fees,
    mark,
    peak,
    pyramidPeak,
    closed,
    first,
    basis,
    initialR: initialR > 0n ? initialR : null,
  };
}
export function cycleMetrics(c, rules = defaultRiskRules) {
  const x = replay(c),
    { initialR: r } = x;
  let held = 0n,
    unrealized = 0n,
    risk = 0n,
    protectedPnl = x.realized,
    cost = 0n,
    missing = false;
  const lots = x.lots.map((l) => {
    held += l.remaining;
    cost += l.price * l.remaining;
    const u = (x.mark - l.price) * l.remaining;
    unrealized += u;
    if (l.remaining && l.stop === null) missing = true;
    const loss =
      l.stop === null ? null : positive(l.price - l.stop) * l.remaining;
    if (loss !== null) risk += loss;
    if (l.stop !== null) protectedPnl += (l.stop - l.price) * l.remaining;
    return {
      id: l.id,
      at: l.at,
      price: quantity(l.price),
      initialQuantity: quantity(l.initial),
      remaining: quantity(l.remaining),
      stop: l.stop === null ? null : quantity(l.stop),
      history: l.history,
      memo: l.memo,
      realized: money(l.realized),
      unrealized: money(u),
      cr: r && loss !== null ? ratio(loss, r) : null,
    };
  });
  const total = x.realized + unrealized,
    giveback = missing ? null : total - protectedPnl;
  const out = {
    id: c.id,
    ticker: c.ticker,
    code: c.code,
    version: c.version,
    events: c.events,
    lots,
    closed: x.closed,
    basisStatus: r ? "확정" : "기준 정보 부족",
    initialR: r ? money(r) : null,
    initialQuantity: quantity(x.first.initial),
    quantity: quantity(held),
    mark: quantity(x.mark),
    e: x.basis
      ? ratio(cost, (fixed(x.basis.capitalText) * S) / 4n)
      : ratio(held, x.first.initial),
    basisMode: x.basis ? "account-capital-v1" : "initial-entry",
    accountId: x.basis?.accountId ?? null,
    accountName: x.basis?.name ?? "기존 미분류",
    capitalPlan: x.basis,
    riskAmount: missing ? null : money(risk),
    cr: r && !missing ? ratio(risk, r) : null,
    realized: money(x.realized),
    unrealized: money(unrealized),
    total: money(total),
    realizedR: r ? ratio(x.realized, r) : null,
    unrealizedR: r ? ratio(unrealized, r) : null,
    totalR: r ? ratio(total, r) : null,
    protected: missing ? null : money(protectedPnl),
    protectedR: r && !missing ? ratio(protectedPnl, r) : null,
    giveback: giveback === null ? null : money(giveback),
    givebackR: r && giveback !== null ? ratio(giveback, r) : null,
    givebackPercent:
      total > 0n && giveback !== null ? ratio(giveback * 100n, total) : null,
    peak: money(x.peak),
    pyramidPeak: x.pyramidPeak === null ? null : money(x.pyramidPeak),
    peakGivebackPercent:
      x.peak > 0n ? ratio((x.peak - total) * 100n, x.peak) : null,
    marketValue: money(x.mark * held),
    remainingCost: money(cost),
    totalInvested: money(x.buy),
    fees: money(x.fees),
    pyramiding: x.lots.length > 1,
    missingStops: missing,
    warnings: [],
  };
  const settings = validateRules(rules);
  if (x.basis || settings.accountValue !== "") {
    const account = fixed(x.basis?.capitalText ?? settings.accountValue) * S;
    out.accountPercent = ratio(x.mark * held * 100n, account);
    out.initialRiskPercent = r ? ratio(r * 100n, account) : null;
  } else {
    out.accountPercent = null;
    out.initialRiskPercent = null;
  }
  if (settings.enabled) {
    if (out.e > (x.basis ? 1 : Number(settings.maxE)))
      out.warnings.push("E 한도 초과");
    if (out.cr !== null && out.cr > (x.basis ? 1 : Number(settings.maxCR)))
      out.warnings.push("CR 한도 초과");
    if (
      out.totalR !== null &&
      out.totalR >= Number(settings.protectAtR) &&
      out.protectedR !== null &&
      out.protectedR < Number(settings.minProtectedR)
    )
      out.warnings.push("계획상 보호 수익 부족");
    if (
      out.initialRiskPercent !== null &&
      out.initialRiskPercent >
        (x.basis ? 1.25 : Number(settings.initialRiskPercent))
    )
      out.warnings.push("지정한 초기 위험 한도 초과");
  }
  return out;
}
export function applyPositionAction(current, action, newId) {
  text(action.actionId);
  if (!/^[a-zA-Z0-9_-]{1,80}$/.test(action.actionId))
    throw Error("주문 ID는 영문·숫자·밑줄·하이픈 80자까지 입력하세요.");
  if (Object.hasOwn(action, "id"))
    throw Error("내부 차수 ID는 직접 지정할 수 없습니다.");
  date(action.at);
  if (action.basis) {
    accountBasis(action.basis);
    if (current && !current.events.some((e) => e.id === action.actionId))
      throw Error("시작한 사이클의 계좌 기준은 변경할 수 없습니다.");
  }
  let c;
  if (!current) {
    if (action.type !== "buy") throw Error("최초 매수부터 입력하세요.");
    c = {
      id: newId,
      ticker: text(action.ticker),
      code: action.code || "",
      version: 0,
      events: [],
    };
    if (c.code && !/^\d{6}$/.test(c.code))
      throw Error("종목코드는 6자리입니다.");
  } else {
    c = structuredClone(current);
    const existing = c.events.find((e) => e.id === action.actionId);
    if (existing) {
      const { actionId, version, ...data } = action;
      if (!isDeepStrictEqual(existing, { id: actionId, ...data }))
        throw Error("같은 주문 ID의 내용이 다릅니다.");
      return c;
    }
    if (action.version !== c.version)
      throw Object.assign(
        Error("다른 화면에서 변경됐습니다. 새로고침 후 다시 입력하세요."),
        { status: 409 },
      );
  }
  if (c.events.length >= 2000)
    throw Error("한 사이클에 최대 2,000개 이력을 기록할 수 있습니다.");
  if (action.type === "buy") {
    if (
      action.memo != null &&
      (typeof action.memo !== "string" || action.memo.length > 10000)
    )
      throw Error("메모는 10,000자까지 입력할 수 있습니다.");
    if (
      action.tags != null &&
      (!Array.isArray(action.tags) ||
        action.tags.length > 30 ||
        action.tags.some((t) => typeof t !== "string" || t.length > 100))
    )
      throw Error("태그를 확인하세요.");
    for (const key of ["emotion", "discipline"])
      if (
        action[key] != null &&
        (typeof action[key] !== "string" || action[key].length > 2048)
      )
        throw Error("복기 정보를 확인하세요.");
  }
  const { actionId, version, ...data } = action;
  c.events.push({ id: actionId, ...data });
  c.version++;
  const checked = replay(c);
  if (
    checked.buy > 1000000000000000n * M ||
    checked.sell > 1000000000000000n * M
  )
    throw Error("누적 거래금액은 1,000조 원 이하로 입력하세요.");
  return c;
}
export function simulatePosition(c, input, rules) {
  const quoted = structuredClone(c);
  quoted.events.push({
    id: "SIM_QUOTE",
    type: "mark",
    at: quoted.events.at(-1).at,
    price: input.price,
  });
  const before = cycleMetrics(quoted, rules);
  if (before.closed) throw Error("청산된 거래는 시뮬레이션할 수 없습니다.");
  const run = (qty) => {
    const next = structuredClone(quoted),
      at = next.events.at(-1).at;
    for (const [i, s] of (input.stops || []).entries())
      next.events.push({
        id: "SIM_STOP_" + i,
        type: "stop",
        at,
        lotId: s.lotId,
        stop: s.stop,
      });
    next.events.push({
      id: "SIM_BUY",
      type: "buy",
      at,
      price: input.price,
      quantity: qty,
      stop: input.stop,
      fee: input.fee || "0",
    });
    next.events.push({ id: "SIM_MARK", type: "mark", at, price: input.price });
    return cycleMetrics(next, rules);
  };
  const after = run(input.quantity),
    half = fixed(input.quantity, { max: 1000000000n }) / 2n;
  if (
    rules.enabled &&
    after.totalR !== null &&
    after.totalR >= Number(rules.protectAtR) &&
    after.protectedR !== null &&
    after.protectedR < Number(rules.minProtectedR) &&
    !after.warnings.includes("계획상 보호 수익 부족")
  )
    after.warnings.push("계획상 보호 수익 부족");
  return {
    before,
    after,
    reduced: half > 0n ? run((Number(half) / Number(S)).toFixed(6)) : null,
  };
}
export function closedTrade(c) {
  const x = replay(c);
  if (!x.closed) return null;
  const m = cycleMetrics(c);
  return {
    ticker: c.ticker,
    code: c.code,
    entry: new Date(Date.parse(c.events[0].at) + 9 * 3600000)
      .toISOString()
      .slice(0, 10),
    exit: new Date(Date.parse(c.events.at(-1).at) + 9 * 3600000)
      .toISOString()
      .slice(0, 10),
    buy: money(x.buy),
    sell: money(x.sell - x.fees),
    memo: x.first.memo || "R·CR·E 포지션 사이클에서 자동 연결",
    tags: c.events[0].tags || [],
    emotion: c.events[0].emotion || "",
    discipline: c.events[0].discipline || "",
    chart_link: "",
    pnl: money(x.realized),
    roi: ratio(x.realized * 100n, x.buy),
    risk_cycle_id: c.id,
    initial_r: m.initialR,
    final_r: m.realizedR,
    account_id: m.accountId,
    account_name: m.accountName,
  };
}
export function riskStatistics(cycles) {
  const all = cycles.map((c) => ({ display: cycleMetrics(c), raw: replay(c) })),
    closed = all.filter((m) => m.raw.closed && m.raw.initialR);
  const gcd = (a, b) => {
    while (b) {
      [a, b] = [b, a % b];
    }
    return a < 0n ? -a : a;
  };
  const sum = (rows) => {
    let n = 0n,
      d = 1n;
    for (const m of rows) {
      const r = m.raw.initialR;
      n = n * r + m.raw.realized * d;
      d *= r;
      const g = gcd(n, d);
      n /= g;
      d /= g;
    }
    return [n, d];
  };
  const average = (rows) => {
    if (!rows.length) return null;
    const [n, d] = sum(rows);
    return ratio(n, d * BigInt(rows.length));
  };
  const summarize = (rows) => {
    const wins = rows.filter((m) => m.raw.realized > 0n),
      losses = rows.filter((m) => m.raw.realized < 0n),
      n = rows.length,
      [total, denom] = sum(rows);
    return {
      count: n,
      totalR: n ? ratio(total, denom) : null,
      averageWinR: average(wins),
      averageLossR: average(losses),
      averageR: average(rows),
      winRate: n ? (wins.length / n) * 100 : null,
      lossRate: n ? (losses.length / n) * 100 : null,
      breakeven: n - wins.length - losses.length,
      expectancy: average(rows),
    };
  };
  return {
    ...summarize(closed),
    missingBasis: all.filter((m) => !m.raw.initialR).length,
    rows: closed.map((m) => ({
      id: m.display.id,
      ticker: m.display.ticker,
      realizedR: m.display.realizedR,
      pyramiding: m.display.pyramiding,
    })),
    pyramiding: summarize(closed.filter((m) => m.display.pyramiding)),
    single: summarize(closed.filter((m) => !m.display.pyramiding)),
  };
}
