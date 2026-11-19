"""Policy simulation on one real debate (sherefox-debate/1 data).

usage:  uv run python sim_data.py data/ch02_fitch.json [--n 4000] [--per 60] [--md out.md]

For every full loadout (check45.py) the opponent's actual cards and the
player's actual claims are fed into engine.Debate:
  hand      = his lies / facts / unfavourable facts + the picked-up items for
              that loadout (one picked item is held back as his last card when
              last_card_priority puts pickups first)
  covered   = a safe 正論 in this loadout breaks that card
  claims    = every 正論 available in this loadout, with its truth, whether he
              can 駁倒 it (opp_refute), and its own 心理作用
  last card = the player can cut it if a proper claim breaks it
Policies choose loadouts like players would:
  careful / sophist / psych  the best quarter of loadouts (psych: with the psych card)
  careless / staller         any full loadout, uniformly
Values the data file does not give (HP, damage, personality) come from
params.py for the debate's stage and the opponent's archetype.
"""
from __future__ import annotations

import argparse
import random
import statistics

import params as P
from check45 import check, load
from engine import Debate
from policies import POLICIES
from run import POLICY_ORDER, POLICY_ZH, summarize

STAGE_HP = {"early": 130, "mid": 190, "late": 260}
NOTICE = {"careful": 0.9, "sophist": 0.9, "psych": 0.9, "careless": 0.5, "staller": 0.5}
ARCH_ALIASES = {"一般人": "ordinary", "心虛的初犯": "nervous", "老練的慣犯": "veteran",
                "自信的專家": "expert", "易怒的權貴": "noble", "冷靜的主謀": "mastermind"}
EVENT_ALIASES = {"謊言被正論打掉": "lie_down_proper", "謊言被詭辯打掉": "lie_down_soph",
                 "事實被詭辯打掉": "fact_down_soph", "自己的反駁落空": "own_rebut_whiff",
                 "被打迷糊仗": "stalled", "成功打中玩家": "hit_player", "選項所剩無幾": "few_options",
                 "無辜者被牽連": "innocent", "說法觸及他的心結": "sore_spot", "說法觸及心結": "sore_spot",
                 "玩家公開他的私事": "private", "公開私事": "private"}


def pga(d, default=(0, 0, 0)):
    if d is None:
        return default
    if isinstance(d, (list, tuple)):
        return tuple(d)
    return (d.get("P", 0), d.get("G", 0), d.get("A", 0))


def base_overrides(d, notes):
    opp = d["opponent"]
    per = opp.get("personality") or {}
    beh = opp.get("behavior") or {}
    arch = per.get("archetype") or opp.get("archetype") or "ordinary"
    arch = ARCH_ALIASES.get(arch, arch)
    if arch not in P.ARCHETYPES:
        notes.append(f"unknown archetype {arch!r}; using ordinary")
        arch = "ordinary"
    stage = d.get("stage", "mid")
    o = dict(stage=stage, arch=arch, hp=opp.get("hp", STAGE_HP[stage]), key_lie=False,
             last_card=any(c["kind"] == "last" for c in opp["cards"]), sore=0.0)
    if "base_damage" in opp:
        o["opp_base"] = opp["base_damage"]
    if d.get("max_rounds"):
        o["max_rounds"] = d["max_rounds"]
    if "start" in per:
        o["start"] = pga(per["start"])
    if "threshold" in per:
        o["thr"] = pga(per["threshold"])
    if "decay" in per:
        o["decay"] = pga(per["decay"], (1, 1, 1))
    em = per.get("event_mult") or {}
    if em:
        ov = dict(P.ARCHETYPES[arch]["override"])
        for k, v in em.items():
            key = EVENT_ALIASES.get(k, k)
            if key in P.EVENTS:
                ov[key] = pga(v, (1, 1, 1))
            else:
                notes.append(f"event_mult {k!r} not recognised; ignored")
        o["override"] = ov
    if "rage_force_share" in per:
        o["rage"] = per["rage_force_share"]
    w = beh.get("weights")
    if isinstance(w, dict):
        o["weights"] = (w.get("attack", 0), w.get("force", 0), w.get("rebut", 0), w.get("parry", 0))
    tc = beh.get("tell_clarity")
    if isinstance(tc, dict):
        clar = (tc.get("clear", 0), tc.get("vague", 0), tc.get("disguise", 0))
        tot = sum(clar) or 1
        o["clarity"] = tuple(x / tot for x in clar)
        o["disguise"] = clar[2] > 0
    return o


def loadout_overrides(d, row, base, cards, claims, brk):
    issues = [i["id"] for i in d["issues"]]
    ix = {k: n for n, k in enumerate(issues)}
    safe = set(row["safe_ids"])
    proper = row["proper_ids"]
    opp = d["opponent"]
    prio = opp.get("last_card_priority") or ["pickup", "last"]
    held = list(row["held"])
    picked_last = bool(held) and prio and prio[0] == "pickup"
    reserve = held[0] if picked_last else None

    def covered(cid):
        return any(cid in brk[c] for c in safe)

    hand = []
    for c in opp["cards"]:
        if c["kind"] in ("lie", "fav", "unfav"):
            hand.append((c["kind"], ix.get(c.get("issue"), 0), bool(c.get("keystone")), covered(c["id"])))
    for cid in held:
        if cid == reserve:
            continue
        c = cards[cid]
        kind = "picked_lie" if c.get("as") == "lie" else "picked_fav"
        hand.append((kind, ix.get(c.get("issue"), 0), False, covered(cid)))
    # one row per proper claim; 駁倒-able ones are those not in the safe list
    stmts = []
    for cid in proper:
        c = claims[cid]
        ps = pga(c.get("psych")) if c.get("psych") else None
        stmts.append((ix.get(c["issue"], 0), not c.get("true", True), cid not in safe, ps))
    last = [c["id"] for c in opp["cards"] if c["kind"] == "last"]
    cut_last = any(any(l in brk[i] for i in proper) for l in last)
    cut_pick = reserve is not None and any(reserve in brk[i] for i in proper)
    o = dict(base, hand_cards=hand, stmts=stmts, picked_last=picked_last,
             key_lie=any(h[2] for h in hand))
    o["_cut"] = (1.0 if cut_last else 0.0, 1.0 if cut_pick else 0.0)
    psy = [pga(claims[c].get("psych")) for c in claims
           if claims[c].get("psych_card") and claims[c]["evidence"] in row["carry"]]
    o["weakness"] = max(psy, key=sum) if psy else None
    return o


def score(row):
    return (row["ok"], row["cuts"], bool(row["counter"]), row["clean"], row["safe"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--n", type=int, default=4000, help="games per policy")
    ap.add_argument("--per", type=int, default=60, help="careful games per loadout (loadout spread)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--md", default=None)
    a = ap.parse_args()

    d, need, rows, errs = check(a.path)
    _, ev, cards, claims, appr, brk, _ = load(a.path)
    notes = []
    base = base_overrides(d, notes)
    psych_ev = {e["id"] for e in d["evidence"] if e.get("psych_card")}
    ranked = sorted(rows, key=score, reverse=True)
    top = ranked[:max(1, len(ranked) // 4)]
    with_psych = [r for r in ranked if psych_ev & set(r["carry"])]
    pools = {
        "careful": [r for r in top if not psych_ev & set(r["carry"])] or top,
        "sophist": [r for r in top if not psych_ev & set(r["carry"])] or top,
        "psych": with_psych[:max(1, len(with_psych) // 4)] or top,
        "careless": rows, "staller": rows,
    }
    rng = random.Random(a.seed)
    out_rows = []
    for pol in POLICY_ORDER:
        res = []
        pool = pools[pol]
        for _ in range(a.n):
            row = rng.choice(pool)
            o = loadout_overrides(d, row, base, cards, claims, brk)
            cut = o.pop("_cut")
            o["counter_p"] = (cut[0] * NOTICE[pol], cut[1] * NOTICE[pol])
            res.append(Debate(None, POLICIES[pol], rng, o).run())
        out_rows.append((pol, summarize(res)))

    # careful win rate per loadout (does any full loadout leave a careful player stuck?)
    spread = []
    for row in rows:
        o = loadout_overrides(d, row, base, cards, claims, brk)
        cut = o.pop("_cut")
        o["counter_p"] = (cut[0] * NOTICE["careful"], cut[1] * NOTICE["careful"])
        rs = [Debate(None, POLICIES["careful"], rng, dict(o)).run() for _ in range(a.per)]
        spread.append((sum(r.win for r in rs) / len(rs), row))
    spread.sort(key=lambda x: x[0])
    wr = [w for w, _ in spread]

    pct = lambda x: f"{x * 100:.0f}%"
    L = [f"# 策略模擬：{d.get('id', a.path)}", "",
         f"* 階段 {d.get('stage')}；論破門檻 {need}；對手原型 {base['arch']}；可信度 {base['hp']}；"
         f"每次立論論證 {base.get('opp_base', P.STAGES[base['stage']]['opp_base'])}",
         f"* 帶滿的帶法 {len(rows)} 種；每種策略 {a.n} 場（謹慎／詭辯／心理牌從最好的 1/4 帶法中抽，粗心／拖延從全部帶法中抽）",
         ""]
    if notes or errs:
        L += ["## 資料提示", ""] + [f"* {x}" for x in notes + errs] + [""]
    L += ["## 各策略", "",
          "| 策略 | 勝率 | 平均回合 | 論破率 | 等級一 | 等級二 | 等級三 | 等級四 | 勝場中被反擊 | 論破後論敗 | 被逆論破 | 接話 | 說溜嘴 | 壓力越線 | 罪惡感越線 | 怒氣越線 | 真相度 |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for pol, s in out_rows:
        L.append(f"| {POLICY_ZH[pol]} | {pct(s['win'])} | {s['rounds']:.1f} | {pct(s['ronpa'])} | {pct(s['g1'])} | {pct(s['g2'])} | "
                 f"{pct(s['g3'])} | {pct(s['g4'])} | {pct(s['reversed_of_wins'])} | {pct(s['loss_after_ronpa'])} | {pct(s['rev_ronpa'])} | "
                 f"{pct(s['catch'])} | {pct(s['slip'])} | {pct(s['cross_p'])} | {pct(s['cross_g'])} | {pct(s['cross_a'])} | {pct(s['truth'])} |")
    ps = dict(out_rows)["psych"]
    L += ["", "## 心理牌路線（心理牌策略）", "",
          f"* 打出心理牌：{pct(ps['psych_used'])}；罪惡感越線：{pct(ps['cross_g'])}；"
          f"對手因罪惡感放棄或自白：{pct(ps['surrender'])}；勝率 {pct(ps['win'])}（謹慎 {pct(dict(out_rows)['careful']['win'])}）",
          f"* 對照謹慎策略：罪惡感越線 {pct(dict(out_rows)['careful']['cross_g'])}；放棄或自白 {pct(dict(out_rows)['careful']['surrender'])}"]
    L += ["", "## 謹慎玩家在每種帶法下的勝率", "",
          f"每種帶法 {a.per} 場。最低 {pct(wr[0])}、中位數 {pct(statistics.median(wr))}、最高 {pct(wr[-1])}。", "",
          "最差的 5 種帶法：", "",
          "| 勝率 | 帶走 | 鑑定 | 對手撿到 | 安全正論數 | 能截斷的謊言 |", "| --- | --- | --- | --- | --- | --- |"]
    for w, row in spread[:5]:
        L.append(f"| {pct(w)} | {' '.join(row['carry'])} | {' '.join(row['appraise']) or '—'} | {' '.join(row['picked']) or '—'} | "
                 f"{row['safe']} | {row['cuts']}／{row['lies']} |")
    text = "\n".join(L)
    print(text)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
