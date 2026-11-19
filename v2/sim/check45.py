"""Rule 4.5 checker: every legal loadout must have a sophistry-free winning route.

usage:  uv run python check45.py data/ch02_fitch.json [--all-sizes] [--md out.md] [--verbose]

Data format: see README.md「論戰資料格式」.

A loadout = which evidence is carried (exactly carry_limit items, or fewer with
--all-sizes) × which appraisals are done (any subset of the carried, appraisable
evidence, up to appraisal_limit; doing fewer is legal because knowing more can
turn a 正論 into a 詭辯).

For each loadout:
  known      = always_known + carried evidence ids + their `grants` + appraisal ids done
  available  = claims whose evidence is carried and whose `unlock` items are all known
  proper     = available, not a psych card, and no `conflicts` item is known
               ("said:..." items are lines the opponent may say in the debate;
               unknown at the start, so they never count here)
  picked     = up to max_pickup left-behind evidence that has `opponent_use`, in
               pickup_priority order
  safe       = proper, and no `opp_refute.via` the opponent holds (a picked-up
               evidence id, or one of his fav/unfav card ids)

Sophistry-free route (PASS) = there is a set of safe claims, pairwise not
`exclusive`, of size >= ronpa_len, covering >= 2 issues. 破防 can always be
reached without sophistry by baiting a rebuttal with 打迷糊仗 (6.3), and 接話
claims are a bonus, so neither is required.

WEAK = a route exists, but no safe claim breaks any of his lies. Rule 4.5
(0.4, a8e4305) requires at least one such 正論 cut, so WEAK is a failure.

Also reported (how pretty the route can be; not part of PASS/FAIL):
  clean     grade 1 possible: PASS and nothing picked up
  cut_key   a safe claim breaks the keystone lie (抓漏洞)
  cuts      number of his lies (incl. picked-up lies) a safe claim can break
  counter   a proper claim breaks his last card (殘局截斷)
  pick_lie  picked-up lies no proper claim can break (he can only be beaten by 詭辯 there)
  truth_max 100 − 10 × key evidence left behind (9); gold clue needs >= 70
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys

RONPA_LEN = {"early": 3, "mid": 4, "late": 4}


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    errs = []
    ev = {e["id"]: e for e in d["evidence"]}
    cards = {c["id"]: c for c in d["opponent"]["cards"]}
    issues = {i["id"] for i in d["issues"]}
    claims = {c["id"]: c for c in d["claims"]}
    appr = {a["id"]: a for a in d.get("appraisals", [])}
    for c in d["claims"]:
        if c["evidence"] not in ev:
            errs.append(f"claim {c['id']}: unknown evidence {c['evidence']}")
        if c["issue"] not in issues:
            errs.append(f"claim {c['id']}: unknown issue {c['issue']}")
        for x in c.get("exclusive", []):
            if x not in claims:
                errs.append(f"claim {c['id']}: exclusive -> unknown claim {x}")
        for x in c.get("breaks", []):
            if x not in cards:
                errs.append(f"claim {c['id']}: breaks -> unknown card {x}")
    for e in d["evidence"]:
        u = e.get("opponent_use")
        if u and u not in cards:
            errs.append(f"evidence {e['id']}: opponent_use -> unknown card {u}")
        a = e.get("appraisal")
        if a and a not in appr:
            errs.append(f"evidence {e['id']}: unknown appraisal {a}")
    for c in d["opponent"]["cards"]:
        for x in c.get("breakable_by", []):
            if x not in claims:
                errs.append(f"card {c['id']}: breakable_by -> unknown claim {x}")
    # breaks / breakable_by are the same relation written from both sides: merge
    brk = {cid: set(c.get("breaks", [])) for cid, c in claims.items()}
    for card in d["opponent"]["cards"]:
        for x in card.get("breakable_by", []):
            if x in brk:
                brk[x].add(card["id"])
    for cid, c in claims.items():
        for cardid in list(brk[cid]):
            card = cards.get(cardid)
            if card is not None and cid not in card.get("breakable_by", []) and "breakable_by" in card:
                errs.append(f"note: {cid} breaks {cardid} but {cardid}.breakable_by does not list it (merged)")
    for cid, c in claims.items():
        for x in c.get("exclusive", []):
            if x in claims and cid not in claims[x].get("exclusive", []):
                errs.append(f"note: exclusive {cid} -> {x} is one-way (treated as mutual)")
    return d, ev, cards, claims, appr, brk, errs


def refute_vias(c):
    r = c.get("opp_refute") or []
    if isinstance(r, dict):
        r = [r]
    return [x["via"] if isinstance(x, dict) else x for x in r]


def has_route(safe, claims, need):
    """Exists a pairwise non-exclusive subset of `safe`, size >= need, >= 2 issues."""
    ids = sorted(safe)
    excl = {i: set(claims[i].get("exclusive", [])) for i in ids}
    for i in ids:
        for x in list(excl[i]):
            if x in excl:
                excl[x].add(i)
    best = []

    def grow(chosen, rest):
        nonlocal best
        if len(chosen) >= need and len({claims[i]["issue"] for i in chosen}) >= 2:
            best = list(chosen)
            return True
        for k, i in enumerate(rest):
            if any(i in excl[j] for j in chosen):
                continue
            if grow(chosen + [i], rest[k + 1:]):
                return True
        return False

    grow([], ids)
    return best


def check(path, all_sizes=False):
    d, ev, cards, claims, appr, brk, errs = load(path)
    need = d.get("ronpa_len", RONPA_LEN[d.get("stage", "mid")])
    carriable = [e["id"] for e in d["evidence"] if e.get("carriable", True)]
    limit = min(d["carry_limit"], len(carriable)) if d.get("carry_limit") is not None else len(carriable)
    alim = d.get("appraisal_limit", len(appr))
    maxp = d.get("max_pickup", 2)
    prio = d["opponent"].get("pickup_priority") or [e["id"] for e in d["evidence"] if e.get("opponent_use")]
    always = set(d.get("always_known", []))
    own_facts = {c["id"] for c in d["opponent"]["cards"] if c["kind"] in ("fav", "unfav")}
    lies = [c["id"] for c in d["opponent"]["cards"] if c["kind"] == "lie"]
    keystone = [c["id"] for c in d["opponent"]["cards"] if c.get("keystone")]
    last = [c["id"] for c in d["opponent"]["cards"] if c["kind"] == "last"]
    keyev = {e["id"] for e in d["evidence"] if e.get("key")}

    sizes = range(1, limit + 1) if all_sizes else [limit]
    rows = []
    for n in sizes:
        for carry in itertools.combinations(carriable, n):
            cset = set(carry)
            appraisable = [ev[e]["appraisal"] for e in carry if ev[e].get("appraisal")]
            left = [e for e in carriable if e not in cset]
            picked = [e for e in prio if e in left and ev[e].get("opponent_use")][:maxp]
            held_cards = [ev[e]["opponent_use"] for e in picked]
            held = set(picked) | own_facts
            for k in range(0, min(alim, len(appraisable)) + 1):
                for done in itertools.combinations(appraisable, k):
                    known = always | cset | set(done)
                    for e in carry:
                        known |= set(ev[e].get("grants", []))
                    avail = [c for c in claims.values()
                             if c["evidence"] in cset and all(u in known for u in c.get("unlock", []))]
                    proper = [c["id"] for c in avail if not c.get("psych_card")
                              and not any(x in known for x in c.get("conflicts", []) if not x.startswith("said:"))]
                    safe = [i for i in proper if not any(v in held for v in refute_vias(claims[i]))]
                    route = has_route(safe, claims, need)
                    his_lies = lies + [c for c in held_cards if cards[c].get("as") == "lie"]
                    cuts = [l for l in his_lies if any(l in brk[i] for i in safe)]
                    pick_lie = [c for c in held_cards if cards[c].get("as") == "lie" and c not in cuts]
                    rows.append(dict(
                        carry=list(carry), appraise=list(done), picked=held_cards,
                        ok=bool(route), route=route,
                        safe=len(safe), proper=len(proper),
                        clean=bool(route) and not picked,
                        cut_key=any(k2 in cuts for k2 in keystone),
                        cuts=len(cuts), lies=len(his_lies),
                        counter=any(any(l in brk[i] for i in proper) for l in last) if last else None,
                        pick_lie=pick_lie,
                        truth_max=100 - 10 * len(keyev - cset),
                        safe_ids=safe, proper_ids=proper, held=held_cards,
                    ))
    return d, need, rows, errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--all-sizes", action="store_true", help="also loadouts that carry fewer than carry_limit")
    ap.add_argument("--md", default=None)
    ap.add_argument("--verbose", action="store_true", help="list every loadout")
    a = ap.parse_args()
    d, need, rows, errs = check(a.path, a.all_sizes)
    fails = [r for r in rows if not r["ok"]]
    weak = [r for r in rows if r["ok"] and r["cuts"] == 0]
    bad = fails + weak
    out = [f"# 4.5 檢查：{d.get('id', a.path)}", "",
           f"* 論破門檻 {need}；攜帶上限 {d.get('carry_limit')}；鑑定上限 {d.get('appraisal_limit')}；對手最多撿 {d.get('max_pickup', 2)} 件",
           f"* 帶法 × 鑑定組合：{len(rows)}；**沒有不靠詭辯的獲勝路線：{len(fails)}**；"
           f"有路線但沒有任何正論能截斷他的謊言（WEAK，也算失敗）：{len(weak)}",
           f"* 可能乾淨論破（等級一）：{sum(r['clean'] for r in rows)}；能截斷要害：{sum(r['cut_key'] for r in rows)}；"
           f"能截斷最後一張牌：{sum(1 for r in rows if r['counter'])}；黃金線索可能（真相度上限 ≥ 70）：{sum(r['truth_max'] >= 70 for r in rows)}", ""]
    if errs:
        out += ["## 資料警告", ""] + [f"* {e}" for e in errs] + [""]
    show = rows if a.verbose else fails + weak
    title = "全部組合" if a.verbose else "失敗與 WEAK 的組合"
    out += [f"## {title}", ""]
    if show:
        out += ["| 結果 | 帶走 | 鑑定 | 對手撿到 | 安全正論數 | 範例路線 | 乾淨 | 截要害 | 截最後一張牌 | 只能詭辯打的撿來謊言 | 真相度上限 |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in show:
            tag = "FAIL" if not r["ok"] else ("WEAK" if r["cuts"] == 0 else "PASS")
            out.append(f"| {tag} | {' '.join(r['carry'])} | {' '.join(r['appraise']) or '—'} | "
                       f"{' '.join(r['picked']) or '—'} | {r['safe']} | {' '.join(r['route']) or '—'} | "
                       f"{'是' if r['clean'] else ''} | {'是' if r['cut_key'] else ''} | {'是' if r['counter'] else ''} | "
                       f"{' '.join(r['pick_lie']) or ''} | {r['truth_max']}% |")
    else:
        out.append("（無）")
    text = "\n".join(out)
    print(text)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(text + "\n")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
