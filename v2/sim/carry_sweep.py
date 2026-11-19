"""Carry-limit sweep for one debate: how tight can the carry limit be?

usage:  uv run python carry_sweep.py ../demo/debate_data.json --limits 11 10 9 8 7 --appraisals 2 1 [--per 12] [--md out.md]

For each (carry limit, appraisal limit):
  * check45 over every full loadout: failures, WEAK
  * careful / careless / psych win rate averaged over loadouts (`--per` games per
    loadout; loadouts are sampled down to --max-loadouts if there are more)
  * worst loadout for careful play: every loadout gets `--per` games, then the
    20 lowest are re-run with `--confirm` games each
  * share of loadouts where he holds 2 picked-up items
  * for failing / WEAK loadouts: which carried items they have in common, and
    which left-behind items are always among them (the likely cause)
"""
from __future__ import annotations

import argparse
import random
from collections import Counter

from check45 import check, load
from engine import Debate
from policies import POLICIES
from sim_data import NOTICE, base_overrides, loadout_overrides


def run_loadout(d, row, base, cards, claims, brk, pol, n, rng):
    o = loadout_overrides(d, row, base, cards, claims, brk)
    cut = o.pop("_cut")
    o["counter_p"] = (cut[0] * NOTICE[pol], cut[1] * NOTICE[pol])
    rs = [Debate(None, POLICIES[pol], rng, dict(o)).run() for _ in range(n)]
    return sum(r.win for r in rs) / n, sum(r.rounds for r in rs) / n, rs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--limits", type=int, nargs="+", default=[11, 10, 9, 8, 7])
    ap.add_argument("--appraisals", type=int, nargs="+", default=[2, 1])
    ap.add_argument("--per", type=int, default=12)
    ap.add_argument("--confirm", type=int, default=200)
    ap.add_argument("--max-loadouts", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--md", default=None)
    a = ap.parse_args()

    _, ev, cards, claims, appr, brk, _ = load(a.path)
    rng = random.Random(a.seed)
    lines = ["| 攜帶上限 | 鑑定 | 帶滿的帶法 | 失敗 | WEAK | 謹慎平均 | 粗心平均 | 心理牌平均 | 心理牌：對手放棄 | 謹慎最差帶法 | 謹慎平均回合 | 對手撿到 2 件 |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    details = []
    for lim in a.limits:
        for al in a.appraisals:
            d, need, rows, errs = check(a.path, override={"carry_limit": lim, "appraisal_limit": al})
            notes = []
            base = base_overrides(d, notes)
            fails = [r for r in rows if not r["ok"]]
            weak = [r for r in rows if r["ok"] and r["cuts"] == 0]
            two = sum(1 for r in rows if len(r["picked"]) >= 2) / len(rows)
            sample = rows if len(rows) <= a.max_loadouts else rng.sample(rows, a.max_loadouts)
            per_care = []
            for r in sample:
                w, rd, _ = run_loadout(d, r, base, cards, claims, brk, "careful", a.per, rng)
                per_care.append((w, rd, r))
            care_avg = sum(x[0] for x in per_care) / len(per_care)
            care_rd = sum(x[1] for x in per_care) / len(per_care)
            # confirm the worst ones
            per_care.sort(key=lambda x: x[0])
            confirmed = []
            for w, rd, r in per_care[:20]:
                w2, _, _ = run_loadout(d, r, base, cards, claims, brk, "careful", a.confirm, rng)
                confirmed.append((w2, r))
            confirmed.sort(key=lambda x: x[0])
            careless = sum(run_loadout(d, r, base, cards, claims, brk, "careless", a.per, rng)[0] for r in sample) / len(sample)
            psy_rows = [r for r in sample if any(ev[e].get("psych_card") for e in r["carry"])]
            psy_w = psy_s = 0.0
            if psy_rows:
                for r in psy_rows:
                    w, _, rs = run_loadout(d, r, base, cards, claims, brk, "psych", a.per, rng)
                    psy_w += w
                    psy_s += sum(x.surrendered for x in rs) / len(rs)
                psy_w /= len(psy_rows)
                psy_s /= len(psy_rows)
            pct = lambda x: f"{x * 100:.0f}%"
            lines.append(f"| {lim} | {al} | {len(rows)} | {len(fails)} | {len(weak)} | {pct(care_avg)} | {pct(careless)} | "
                         f"{pct(psy_w) if psy_rows else '—'} | {pct(psy_s) if psy_rows else '—'} | {pct(confirmed[0][0])} | {care_rd:.1f} | {pct(two)} |")
            print(lines[-1], flush=True)
            # causes
            all_items = [e["id"] for e in d["evidence"] if e.get("carriable", True)]
            det = [f"### 上限 {lim}、鑑定 {al}", ""]
            bad = fails + weak
            if bad:
                left = Counter()
                for r in bad:
                    for e in all_items:
                        if e not in r["carry"]:
                            left[e] += 1
                always_left = [e for e, c in left.items() if c == len(bad)]
                det.append(f"* 失敗＋WEAK {len(bad)} 種。每一種都沒帶的證物：{' '.join(always_left) or '（無共同項）'}；"
                           f"最常沒帶：{', '.join(f'{e}×{c}' for e, c in left.most_common(5))}")
                for r in bad[:8]:
                    tag = "FAIL" if not r["ok"] else "WEAK"
                    det.append(f"  * {tag}：沒帶 {' '.join(e for e in all_items if e not in r['carry'])}；鑑定 {' '.join(r['appraise']) or '—'}；"
                               f"他撿到 {' '.join(r['picked']) or '—'}；安全正論 {r['safe']}；能截斷 {r['cuts']}／{r['lies']}")
            det.append("* 謹慎最差的 3 種帶法（各 %d 場）：" % a.confirm)
            for w, r in confirmed[:3]:
                det.append(f"  * {pct(w)}：沒帶 {' '.join(e for e in all_items if e not in r['carry'])}；鑑定 {' '.join(r['appraise']) or '—'}；"
                           f"他撿到 {' '.join(r['picked']) or '—'}；安全正論 {r['safe']}；能截斷 {r['cuts']}／{r['lies']}")
            det.append("")
            details += det
    text = "\n".join(lines + [""] + details)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(text + "\n")
    print("\n".join(details))


if __name__ == "__main__":
    main()
