"""Batch runner: every policy × every opponent, aggregated per stage.

usage:  uv run python run.py [--n 4000] [--seed 1] [--md results.md] [--json results.json]
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict

import params as P
from engine import Debate
from policies import POLICIES

POLICY_ORDER = ["careful", "careless", "sophist", "staller", "psych"]
POLICY_ZH = {"careful": "謹慎", "careless": "粗心", "sophist": "詭辯", "staller": "拖延", "psych": "心理牌"}


def run_one(opp, pol, n, seed):
    rng = random.Random(seed)
    return [Debate(opp, POLICIES[pol], rng).run() for _ in range(n)]


def summarize(results):
    n = len(results)
    wins = [r for r in results if r.win]

    def pct(f):
        return sum(1 for r in results if f(r)) / n

    s = {
        "n": n,
        "win": len(wins) / n,
        "rounds": sum(r.rounds for r in results) / n,
        "ronpa": pct(lambda r: r.ronpa),
        "g1": pct(lambda r: r.win and r.grade == 1),
        "g2": pct(lambda r: r.win and r.grade == 2),
        "g3": pct(lambda r: r.win and r.grade == 3),
        "g4": pct(lambda r: r.win and r.grade == 4),
        "reversed_of_wins": (sum(1 for r in wins if r.reversed) / len(wins)) if wins else 0.0,
        "loss_after_ronpa": pct(lambda r: r.kind == "loss_after_ronpa"),
        "rev_ronpa": pct(lambda r: r.rev_ronpa),
        "comeback": pct(lambda r: r.comeback),
        "catch": pct(lambda r: r.catches > 0),
        "catches": sum(r.catches for r in results) / n,
        "slip": pct(lambda r: r.slips > 0),
        "guard_saved": pct(lambda r: r.guard_saved),
        "dying": pct(lambda r: r.dying),
        "surrender": pct(lambda r: r.surrendered),
        "psych_used": pct(lambda r: r.psych_card),
        "timeout": pct(lambda r: r.kind == "timeout"),
        "cross_p": pct(lambda r: r.crossed[0]),
        "cross_g": pct(lambda r: r.crossed[1]),
        "cross_a": pct(lambda r: r.crossed[2]),
        "cracks": sum(r.cracks for r in results) / n,
        "truth": sum(r.truth for r in results) / n,
    }
    kinds = defaultdict(int)
    for r in results:
        kinds[r.kind] += 1
    s["kinds"] = {k: v / n for k, v in sorted(kinds.items())}
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--md", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    per_opp = {}
    per_stage = {}
    for pi, pol in enumerate(POLICY_ORDER):
        for oi, opp in enumerate(P.OPPONENTS):
            per_opp[(pol, opp)] = run_one(opp, pol, a.n, a.seed * 1000 + pi * 37 + oi)
        for stage, opps in P.STAGE_SCENARIOS.items():
            allr = [r for o in opps for r in per_opp[(pol, o)]]
            per_stage[(pol, stage)] = summarize(allr)

    lines = []
    pct = lambda x: f"{x * 100:.0f}%"
    lines.append(f"模擬次數：每個「玩家策略 × 對手」各 {a.n} 場（seed {a.seed}）。階段數字是該階段各對手的平均。\n")
    lines.append("| 策略 | 階段 | 勝率 | 平均回合 | 論破率 | 等級一 | 等級二 | 等級三 | 等級四 | 勝場中被反擊 | 論破後論敗 | 被逆論破 | 反擊論破成功 | 接話 | 說溜嘴 | 壓力越線 | 罪惡感越線 | 怒氣越線 | 真相度 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for pol in POLICY_ORDER:
        for stage in ("early", "mid", "late"):
            s = per_stage[(pol, stage)]
            lines.append(f"| {POLICY_ZH[pol]} | {stage} | {pct(s['win'])} | {s['rounds']:.1f} | {pct(s['ronpa'])} | "
                         f"{pct(s['g1'])} | {pct(s['g2'])} | {pct(s['g3'])} | {pct(s['g4'])} | {pct(s['reversed_of_wins'])} | "
                         f"{pct(s['loss_after_ronpa'])} | {pct(s['rev_ronpa'])} | {pct(s['comeback'])} | {pct(s['catch'])} | {pct(s['slip'])} | "
                         f"{pct(s['cross_p'])} | {pct(s['cross_g'])} | {pct(s['cross_a'])} | {pct(s['truth'])} |")
    lines.append("")
    lines.append("| 策略 | 對手 | 勝率 | 平均回合 | 等級一 | 勝場中被反擊 | 論破後論敗 | 被逆論破 | 接話 | 壓力越線 | 罪惡感越線 | 怒氣越線 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for pol in POLICY_ORDER:
        for opp in P.OPPONENTS:
            s = summarize(per_opp[(pol, opp)])
            lines.append(f"| {POLICY_ZH[pol]} | {P.OPPONENTS[opp]['name']} | {pct(s['win'])} | {s['rounds']:.1f} | {pct(s['g1'])} | "
                         f"{pct(s['reversed_of_wins'])} | {pct(s['loss_after_ronpa'])} | {pct(s['rev_ronpa'])} | {pct(s['catch'])} | "
                         f"{pct(s['cross_p'])} | {pct(s['cross_g'])} | {pct(s['cross_a'])} |")
    text = "\n".join(lines)
    print(text)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(text + "\n")
    if a.json:
        out = {f"{p}|{s}": v for (p, s), v in per_stage.items()}
        out.update({f"{p}|{o}": summarize(v) for (p, o), v in per_opp.items()})
        json.dump(out, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
