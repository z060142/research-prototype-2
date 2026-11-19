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
    s = {
        "n": n,
        "win": len(wins) / n,
        "rounds": sum(r.rounds for r in results) / n,
        "rounds_win": (sum(r.rounds for r in wins) / len(wins)) if wins else 0.0,
        "clean": sum(1 for r in results if r.kind == "clean") / n,
        "ronpa": sum(1 for r in results if r.ronpa) / n,
        "reversed_of_wins": (sum(1 for r in wins if r.reversed) / len(wins)) if wins else 0.0,
        "loss_after_ronpa": sum(1 for r in results if r.kind == "loss_after_ronpa") / n,
        "rev_ronpa": sum(1 for r in results if r.rev_ronpa) / n,
        "timeout": sum(1 for r in results if r.kind == "timeout") / n,
        "cross_p": sum(1 for r in results if r.crossed[0]) / n,
        "cross_g": sum(1 for r in results if r.crossed[1]) / n,
        "cross_a": sum(1 for r in results if r.crossed[2]) / n,
        "cracks": sum(r.cracks for r in results) / n,
        "truth": sum(r.truth for r in results) / n,
        "kinds": {},
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
    lines.append("| 策略 | 階段 | 勝率 | 平均回合 | 論破率 | 乾淨論破 | 勝場中被反擊 | 論破後論敗 | 被逆論破 | 壓力越線 | 罪惡感越線 | 怒氣越線 | 平均裂紋 | 真相度 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for pol in POLICY_ORDER:
        for stage in ("early", "mid", "late"):
            s = per_stage[(pol, stage)]
            lines.append(f"| {POLICY_ZH[pol]} | {stage} | {pct(s['win'])} | {s['rounds']:.1f} | {pct(s['ronpa'])} | "
                         f"{pct(s['clean'])} | {pct(s['reversed_of_wins'])} | {pct(s['loss_after_ronpa'])} | {pct(s['rev_ronpa'])} | "
                         f"{pct(s['cross_p'])} | {pct(s['cross_g'])} | {pct(s['cross_a'])} | {s['cracks']:.1f} | {pct(s['truth'])} |")
    lines.append("")
    lines.append("| 策略 | 對手 | 勝率 | 平均回合 | 乾淨論破 | 勝場中被反擊 | 論破後論敗 | 壓力越線 | 罪惡感越線 | 怒氣越線 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for pol in POLICY_ORDER:
        for opp in P.OPPONENTS:
            s = summarize(per_opp[(pol, opp)])
            lines.append(f"| {POLICY_ZH[pol]} | {P.OPPONENTS[opp]['name']} | {pct(s['win'])} | {s['rounds']:.1f} | {pct(s['clean'])} | "
                         f"{pct(s['reversed_of_wins'])} | {pct(s['loss_after_ronpa'])} | {pct(s['cross_p'])} | {pct(s['cross_g'])} | {pct(s['cross_a'])} |")
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
