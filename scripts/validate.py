#!/usr/bin/env python3
"""Checks data.json (and optionally index.html) before they are published.

Usage: python3 scripts/validate.py data.json [--prev OLD.json] [--page index.html]
Exit code 1 means at least one error: do not publish. Warnings do not fail the check.
"""
import json, re, sys

SEG = {"exchange", "em_exchange", "post_trade", "data_index"}
CAT = {"results", "volumes", "m_and_a", "regulation", "product", "technology", "strategy", "leadership", "other"}
MAT = {"high", "medium", "low"}
POOLS = {"trading_cash", "trading_derivatives", "trading_other", "clearing", "custody", "nii", "listings", "data", "technology", "other"}
STORY = {"data_compounder", "diversified_fmi", "volume_play", "em_growth_yield", "consolidator", "post_trade_utility", "reset"}
TSTATUS = {"on_track", "ahead", "met", "behind", "missed", "withdrawn", "replaced", "new"}
CTYPE = {"results", "investor_day", "agm", "dividend", "volumes", "other"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
REQUIRED = ["companies", "news", "events", "series", "tech", "mix"]
OPTIONAL = ["story", "volumes", "calendar", "instruments"]
ICLASS = {"listed_companies", "etfs", "funds", "reits", "bonds", "structured"}
DCLASS = {"equity", "rates", "fx", "commodity", "other"}
PAGE_MARKERS = ["<title>Exchange Sector Monitor</title>", 'claude?.use?.("db")', 'fetch("data.json"']

errors, warnings = [], []
err = lambda m: errors.append(m)
warn = lambda m: warnings.append(m)
isnum = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)


def check(d):
    for k in REQUIRED:
        if not isinstance(d.get(k), dict):
            err(f"missing or malformed collection: {k}")
    if errors:
        return
    for k in OPTIONAL:
        if k in d and not isinstance(d[k], dict):
            err(f"collection {k} is not an object")
    if not DATE.match(str(d.get("exported_at", ""))):
        err("exported_at is not YYYY-MM-DD")
    if not isinstance(d.get("status"), dict):
        err("status is missing")
    co = d["companies"]
    if len(co) < 40:
        err(f"only {len(co)} companies (expected about 48)")
    for k, c in co.items():
        if not c.get("name"):
            err(f"companies/{k}: no name")
        if c.get("segment") not in SEG:
            err(f"companies/{k}: bad segment {c.get('segment')!r}")
        m = c.get("metrics") or {}
        for f in ("revenue", "net_income", "market_cap", "revenue_yoy", "ebitda_margin"):
            if m.get(f) not in (None, "") and not isnum(m[f]):
                warn(f"companies/{k}: metrics.{f} is not a number")

    def ids(x):
        return x.get("companies") or [x.get("company")]

    for k, n in d["news"].items():
        if not DATE.match(str(n.get("date", ""))):
            err(f"news/{k}: bad date")
        if any(c not in co for c in ids(n)):
            err(f"news/{k}: unknown company {ids(n)}")
        if n.get("category") not in CAT:
            err(f"news/{k}: bad category {n.get('category')!r}")
        if n.get("materiality") not in MAT:
            err(f"news/{k}: bad materiality {n.get('materiality')!r}")
        if not n.get("headline"):
            err(f"news/{k}: no headline")
        if n.get("url") and not str(n["url"]).startswith("http"):
            err(f"news/{k}: url is not a link")
    seen = {}
    for k, e in d["events"].items():
        if not DATE.match(str(e.get("date", ""))):
            err(f"events/{k}: bad date")
        if any(c not in co for c in ids(e)):
            err(f"events/{k}: unknown company {ids(e)}")
        if not e.get("title"):
            err(f"events/{k}: no title")
        key = (e.get("date"), e.get("company"), e.get("category"))
        if key in seen:
            warn(f"events/{k}: same date, company and category as events/{seen[key]} (possible duplicate)")
        seen[key] = k
    for coll in ("series", "mix", "tech", "story", "volumes", "instruments"):
        for k in d.get(coll, {}):
            if k not in co:
                err(f"{coll}/{k}: no such company")
    for k, s in d["series"].items():
        for r in s.get("annual") or []:
            if not isinstance(r.get("year"), int):
                err(f"series/{k}: annual row without a numeric year")
            if r.get("revenue") is not None and not isnum(r["revenue"]):
                err(f"series/{k}: {r.get('year')} revenue is not a number")
        qs = [r.get("period") for r in s.get("quarterly") or []]
        if len(qs) != len(set(qs)):
            err(f"series/{k}: duplicate quarter")
    for k, m in d["mix"].items():
        rev = {r.get("year"): r.get("revenue") for r in (d["series"].get(k, {}).get("annual") or [])}
        for y in m.get("years") or []:
            p = y.get("pools") or {}
            if set(p) - POOLS:
                err(f"mix/{k}: {y.get('year')} unknown pools {sorted(set(p) - POOLS)}")
            tot = sum(v for v in p.values() if isnum(v))
            r = rev.get(y.get("year"))
            if isnum(r) and r and abs(tot - r) / r > 0.08:
                warn(f"mix/{k}: {y.get('year')} pools add up to {tot / r:.2f}x of series revenue")
    for k, s in d.get("story", {}).items():
        if s.get("archetype") not in STORY:
            err(f"story/{k}: bad archetype {s.get('archetype')!r}")
        if not s.get("thesis"):
            err(f"story/{k}: no thesis")
        for t in s.get("targets") or []:
            if not t.get("metric") or not t.get("target"):
                err(f"story/{k}: target without metric or target")
            if t.get("status") is not None and t["status"] not in TSTATUS:
                err(f"story/{k}: bad target status {t['status']!r}")
    for k, v in d.get("volumes", {}).items():
        keys = {m.get("key") for m in v.get("metrics") or []}
        if not keys or None in keys:
            err(f"volumes/{k}: metrics need a key")
        for mth, vals in (v.get("months") or {}).items():
            if not MONTH.match(mth):
                err(f"volumes/{k}: bad month {mth!r}")
            for kk, val in (vals or {}).items():
                if kk not in keys:
                    err(f"volumes/{k}: {mth} has unknown metric {kk!r}")
                if not isnum(val) or val < 0:
                    err(f"volumes/{k}: {mth} {kk} is not a positive number")
    for k, t in d.get("instruments", {}).items():
        for c, x in (t.get("counts") or {}).items():
            if c not in ICLASS:
                err(f"instruments/{k}: unknown class {c!r}")
            elif not isinstance(x, dict) or not isnum(x.get("count")) or x["count"] < 0:
                err(f"instruments/{k}: {c} needs a non-negative count")
        for g, v in (t.get("derivatives") or {}).items():
            if g not in DCLASS:
                err(f"instruments/{k}: unknown derivatives class {g!r}")
            elif not isinstance(v, dict) or set(v) - {"futures", "options"}:
                err(f"instruments/{k}: derivatives.{g} must hold futures and/or options")
            elif any(x is not None and (not isnum(x) or x < 0) for x in v.values()):
                err(f"instruments/{k}: derivatives.{g} volumes must be positive numbers or null")
        for e in t.get("extra") or []:
            if not e.get("label"):
                err(f"instruments/{k}: extra entry without a label")
    for k, e in d.get("calendar", {}).items():
        if not DATE.match(str(e.get("date", ""))):
            err(f"calendar/{k}: bad date")
        if any(c not in co for c in ids(e)):
            err(f"calendar/{k}: unknown company {ids(e)}")
        if e.get("type") not in CTYPE:
            err(f"calendar/{k}: bad type {e.get('type')!r}")
        if not e.get("title"):
            err(f"calendar/{k}: no title")
    fx = d.get("fx")
    if fx is not None:
        rates = fx.get("rates") if isinstance(fx, dict) else None
        if not isinstance(rates, dict) or any(not isnum(v) or v <= 0 for v in rates.values()):
            err("fx: rates must be positive numbers")
        else:
            need = {c.get("metrics", {}).get("currency") for c in co.values()} - {None, "USD"}
            miss = sorted(x for x in need if x not in rates)
            if miss:
                warn(f"fx: no rate for {miss}")


def check_prev(d, prev):
    """A run should add to the knowledge base, not shrink it."""
    limits = {"instruments": 0.0, "companies": 0.0, "events": 0.02, "series": 0.0, "tech": 0.0, "mix": 0.0, "story": 0.0, "volumes": 0.0, "news": 0.2}
    for k, tol in limits.items():
        a, b = len(prev.get(k) or {}), len(d.get(k) or {})
        if a and b < a * (1 - tol):
            err(f"{k} shrank from {a} to {b} documents")


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    path, prev, page = argv[0], None, None
    for flag, val in zip(argv[1::2], argv[2::2]):
        if flag == "--prev":
            prev = val
        elif flag == "--page":
            page = val
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"ERROR {path} is not valid JSON: {e}")
        return 1
    check(d)
    if prev and not errors:
        try:
            check_prev(d, json.load(open(prev, encoding="utf-8")))
        except Exception as e:
            warn(f"could not compare with {prev}: {e}")
    if page:
        try:
            html = open(page, encoding="utf-8").read()
            for mk in PAGE_MARKERS:
                if mk not in html:
                    err(f"{page}: missing {mk!r}")
        except Exception as e:
            err(f"{page}: cannot read ({e})")
    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("ERROR:", e)
    counts = ", ".join(f"{k} {len(d.get(k) or {})}" for k in REQUIRED + OPTIONAL if isinstance(d.get(k), dict))
    print(f"{'FAILED' if errors else 'OK'}: {len(errors)} errors, {len(warnings)} warnings ({counts})")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
