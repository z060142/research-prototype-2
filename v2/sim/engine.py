"""One debate under the v2 rules (v2/00_core_rules.md, draft 0.1).

Abstraction level: evidence and statements are not modelled one by one. The
player holds a pool of 正論 statements spread over the 3 issues (some of them
sincerely wrong), can always produce a 詭辯 statement on any issue, and holds a
refuting 正論 for each opponent lie with probability `coverage`. Places where
the rules text had to be interpreted are tagged ASSUMPTION-xx; the list is in
v2/01_numbers.md §7.

Player choices are dicts:
  {"kind": "argue", "soph": bool, "issue": int, "stmt": Stmt|None, "mult": float, "contra": bool}
  {"kind": "catch"}                       抓住他的話
  {"kind": "psych", "issue": int}         心理牌（一律詭辯）
  {"kind": "intercept", "soph": bool}     反駁・截斷
  {"kind": "dismantle", "node": Node, "soph": bool}   反駁・拆台
  {"kind": "stall"}                       打迷糊仗
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import params as P

ATTACK, FORCE, REBUT, PARRY = "attack", "force", "rebut", "parry"   # 立論 強辯 反駁 周旋
CLASS = {ATTACK: "attack", FORCE: "attack", REBUT: "rebut", PARRY: "parry"}
PV, GV, AV = 0, 1, 2   # pressure, guilt, anger


@dataclass(eq=False)
class Card:
    kind: str              # lie / fav / unfav / picked
    issue: int
    key: bool = False      # 要害論點
    covered: bool = False  # player holds a refuting 正論


@dataclass(eq=False)
class Node:
    issue: int
    soph: bool = False
    cracked: bool = False
    false: bool = False    # sincerely wrong 正論 (truth hidden)
    card: Card | None = None


@dataclass(eq=False)
class Stmt:
    issue: int
    false: bool
    oppknows: bool = False   # opponent holds the conflicting info (can 駁倒 it)
    standing: bool = False
    voided: bool = False


@dataclass
class Side:
    hp: float
    max_hp: float
    chain: list = field(default_factory=list)
    combo: int = 0


@dataclass
class Result:
    win: bool
    kind: str        # clean / surrender / countered / reversed_win / grind / confession / loss / loss_after_ronpa / timeout
    rounds: int
    ronpa: bool
    reversed: bool   # a last card was played against the player
    cracks: int
    denials: int
    crossed: tuple   # (P, G, A) crossed at least once
    stalls: int
    psych_card: bool
    truth: float
    rev_ronpa: bool  # player was 逆論破'd at least once


class Debate:
    def __init__(self, opp_key: str, policy, rng: random.Random, overrides: dict | None = None):
        self.rng = rng
        self.policy = policy
        o = dict(P.OPPONENTS[opp_key])
        if overrides:
            o.update(overrides)
        a = P.ARCHETYPES[o["arch"]]
        st = P.STAGES[o["stage"]]
        self.opp_key = opp_key
        self.stage = o["stage"]
        self.skill = P.SKILL[policy.name]
        self.ronpa_len = st["ronpa_len"]
        self.opp_base = o.get("opp_base", st["opp_base"])
        clar = o.get("clarity", st["clarity"])
        if not o.get("disguise", False):
            c, v, d = clar
            clar = (c + d / 2, v + d / 2, 0.0)
        self.clarity = clar
        self.thr = o.get("thr", a["thr"])
        self.scale = o.get("scale", a["scale"])
        self.override = a["override"]
        self.decay = a["decay"]
        self.weights = o.get("weights", a["weights"])
        self.rage = a["rage"]
        self.weakness = o["weakness"]
        self.lock = o.get("lock", False) and P.USE_LOCK_FLAGS   # 論破前可信度不會低於 1（提案）
        self.sore = o.get("sore", 0.0)       # chance a 正論 touches his 心結 (scripted, 8.2)

        self.player = Side(st["player_hp"], st["player_hp"])
        self.opp = Side(o["hp"], o["hp"])
        self.psy = list(o.get("start", a["start"]))
        self.over = [False, False, False]
        self.crossed = [False, False, False]

        # opponent hand (5.2)
        hand = o.get("hand", st["hand"])
        cov = self.skill["coverage"][self.stage]
        self.hand: list[Card] = []
        for k in ("lie", "fav", "unfav"):
            for _ in range(hand[k]):
                self.hand.append(Card(k, rng.randrange(3)))
        lies = [c for c in self.hand if c.kind == "lie"]
        for c in lies:
            c.covered = rng.random() < cov
        if o["key_lie"] and lies:
            lies[0].key = True
            lies[0].covered = rng.random() < self.skill["key_cover"]
        n_picked = 0
        if not o.get("no_pickup", False):
            lam = self.skill["picked"]
            n_picked = min(2, sum(1 for _ in range(4) if rng.random() < lam / 4))
        self.picked_reserved = n_picked > 0       # one picked item kept as last card (ASSUMPTION-09)
        for _ in range(max(0, n_picked - 1)):
            self.hand.append(Card("picked", rng.randrange(3)))
        self.scripted_last = o["last_card"]
        self.refuted: list[Card] = []

        # player statements
        n = P.PROPER_POOL[self.stage]
        self.stmts = [Stmt(i % 3, rng.random() < st["false_share"]) for i in range(n)]
        for s in self.stmts:
            s.oppknows = s.false and rng.random() < st["refute_hidden"]

        # state
        self.rnd = 0
        self.broken = 0              # opponent 破防: rounds remaining incl. current
        self.force_clear = False     # next tell is 明示
        self.no_intercept = False    # after a whiffed 截斷 vs 周旋
        self.shisshu = False         # player 失守 active this round
        self.shisshu_next = False
        self.hachiku = 0
        self.rec_cracks = 0          # cracks from sophistic rebuttals / psych card / contradictions
        self.denials = 0
        self.stall_streak = 0
        self.stalls = 0
        self.catch_issue = None
        self.catch_next = None
        self.last_player_soph = False
        self.opp_lost_node = False
        self.few_fired = False
        self.ronpa_done = False
        self.reversed = False
        self.endgame = False
        self.opp_lastcard_used = False
        self.player_locked = False
        self.player_comeback_used = False
        self.psych_card_used = False
        self.next_unfav = False
        self.rev_ronpa = False

    # ------------------------------------------------------------ helpers
    def ev(self, name):
        base = P.EVENTS[name]
        m = self.override.get(name, self.scale)
        if name in self.override:
            m = tuple(self.scale[i] * m[i] for i in range(3))
        for i in range(3):
            self.psy[i] = max(0.0, min(100.0, self.psy[i] + base[i] * m[i]))

    def playable(self):
        return [c for c in self.hand if c.kind in ("lie", "fav", "picked")]

    def any_over(self):
        return any(self.over)

    def crack_count(self):
        return sum(1 for n in self.player.chain if n.soph or n.cracked) + self.rec_cracks

    def player_dmg(self, base_kind, issue, mult=1.0):
        combo = min(self.player.combo, P.COMBO_CAP)
        d = P.BASE[base_kind] * (1 + P.COMBO_STEP * (combo - 1)) * mult
        prev = self.player.chain[-2] if len(self.player.chain) >= 2 else None
        if prev is not None and prev.issue == issue:
            d *= P.CONTINUATION
        d *= 1 + P.HACHIKU_STEP * self.hachiku
        if self.broken > 0:
            d *= 1 + P.BROKEN_BONUS
        return d

    def opp_dmg(self, act, issue):
        combo = min(self.opp.combo, P.COMBO_CAP)
        d = self.opp_base * (1 + P.COMBO_STEP * (combo - 1))
        prev = self.opp.chain[-2] if len(self.opp.chain) >= 2 else None
        if prev is not None and prev.issue == issue:
            d *= P.CONTINUATION
        if act == FORCE:
            d *= P.FORCE_MULT
            if self.over[AV]:
                d *= P.RAGE_FORCE_MULT
        if self.shisshu:
            d *= 1 + P.SHISSHU_TAKEN
        return d

    def heal_opp(self):
        if not self.over[PV]:          # 8.3: pressure over disables recovery
            self.opp.hp = min(self.opp.max_hp, self.opp.hp + P.HEAL)

    def parry_reraise(self):
        """周旋：把一張被打掉的謊言改口重提（玩家可能失去對應的反駁材料）。"""
        if self.refuted:
            c = self.refuted.pop(0)
            c.covered = c.covered and self.rng.random() < 0.7
            self.hand.append(c)

    # ------------------------------------------------------------ opponent AI (6.2, 8.3)
    def opp_choose(self):
        r = self.rng
        cards = self.playable()
        unfav = [c for c in self.hand if c.kind == "unfav"]
        can_unfav = self.any_over() or not cards       # 8.3: good state never plays unfav
        avail = cards + (unfav if can_unfav else [])
        if self.over[AV]:
            act = FORCE if (avail and r.random() < self.rage) else REBUT
        else:
            w = list(self.weights)
            if self.last_player_soph:
                w[2] *= 2.5                     # 被詭辯過 → 傾向反駁
            if self.opp_lost_node:
                w[3] *= 2.0                     # 掉節 → 傾向周旋
            if not avail:
                w[0] = w[1] = 0
            act = r.choices([ATTACK, FORCE, REBUT, PARRY], weights=w)[0]
        card = None
        if act in (ATTACK, FORCE):
            if (self.next_unfav or self.over[PV]) and unfav:
                card = r.choice(unfav)
                self.next_unfav = False
            elif cards:
                card = r.choices(cards, weights=[2 if c.kind == "lie" else 1 for c in cards])[0]
            elif unfav:
                card = r.choice(unfav)
            else:
                act = REBUT
        return act, card

    def tell(self, act):
        """Return (perceived class, clarity index)."""
        r = self.rng
        true_cls = CLASS[act]
        if self.force_clear or self.over[PV] or self.over[AV]:
            clarity = 0
        else:
            clarity = r.choices([0, 1, 2], weights=self.clarity)[0]
        self.force_clear = False
        if r.random() < self.skill["read"][clarity]:
            return true_cls, clarity
        return r.choice([c for c in ("attack", "rebut", "parry") if c != true_cls]), clarity

    # ------------------------------------------------------------ player statements
    def free_stmt(self, need_new_issue=False, prefer_issue=None):
        have = {n.issue for n in self.player.chain}
        cands = [s for s in self.stmts if not s.standing and not s.voided]
        if not cands:
            v = [s for s in self.stmts if s.voided]
            return (v[0], P.RERAISE) if v else (None, 0.0)
        if need_new_issue:
            c2 = [s for s in cands if s.issue not in have]
            if c2:
                return c2[0], 1.0
        if prefer_issue is not None:
            c2 = [s for s in cands if s.issue == prefer_issue]
            if c2:
                return c2[0], 1.0
        return cands[0], 1.0

    def chain_issues(self):
        return {n.issue for n in self.player.chain}

    # ------------------------------------------------------------ main loop
    def run(self) -> Result:
        while True:
            self.rnd += 1
            if self.rnd > P.MAX_ROUNDS:
                return self.finish(False, "timeout")
            res = self.round()
            if res is not None:
                return res

    def finish(self, win, kind):
        truth = 1.0 - 0.15 * sum(1 for n in self.player.chain if n.false or n.soph) - 0.20 * self.denials
        return Result(win, kind, self.rnd, self.ronpa_done, self.reversed, self.crack_count(),
                      self.denials, tuple(self.crossed), self.stalls, self.psych_card_used,
                      max(0.0, truth), self.rev_ronpa)

    def round(self):
        r = self.rng
        pl, op = self.player, self.opp
        self.shisshu, self.shisshu_next = self.shisshu_next, False
        self.catch_issue, self.catch_next = self.catch_next, None
        self.opp_lost_node = False

        # ---------------- 7.5 player's own last card
        if self.player_locked:
            self.player_locked = False
            lies = [n for n in op.chain if n.card and n.card.kind == "lie" and n.card.covered]
            if lies and not self.player_comeback_used and r.random() < self.policy.comeback_read(self):
                self.player_comeback_used = True
                del op.chain[op.chain.index(lies[0]):]
                op.combo = 0
                pl.hp = P.PLAYER_COMEBACK_HP * pl.max_hp
                return None
            return self.finish(False, "loss")

        # ---------------- 7.4 opponent's last card
        if self.endgame:
            self.endgame = False
            self.opp_lastcard_used = True
            uses_picked = self.picked_reserved and not self.scripted_last
            counter_p = self.skill["counter"] * (0.4 if uses_picked else 1.0)
            if r.random() < counter_p and self.policy.counter_last(self):
                return self.finish(True, "countered")
            c = self.crack_count()
            self.reversed = True
            pl.chain = [n for n in pl.chain if not (n.soph or n.cracked)]
            pl.combo = 0
            if c == 0:
                pl.hp -= P.LASTCARD_ZERO_C_DMG
                op.hp = op.max_hp * P.LASTCARD_HEAL_PER_CRACK
            else:
                pl.hp -= P.LASTCARD_PER_CRACK * c + (P.LASTCARD_PICKED_EXTRA if uses_picked else 0)
                op.hp = op.max_hp * min(P.LASTCARD_HEAL_CAP, P.LASTCARD_HEAL_PER_CRACK * c)
            self.rec_cracks = 0             # ASSUMPTION-10: cracks are spent by the last card
            self.broken = 0
            self.hachiku = 0
            if pl.hp <= 0:
                return self.finish(False, "loss_after_ronpa")
            return None

        # ---------------- 1-2 tell and choice
        act, card = self.opp_choose()
        seen, _ = self.tell(act)
        ch = self.policy.choose(self, seen, card if seen == "attack" else None)
        kind = ch["kind"]

        p_dmg = o_dmg = 0.0
        p_attached = o_attached = False
        read_ok = read_bad = False
        key_hit = False
        events = []
        used_soph = kind == "psych" or bool(ch.get("soph"))

        def opp_attach():
            nonlocal o_attached, o_dmg
            if card is None:
                return
            if card in self.hand:
                self.hand.remove(card)
            op.chain.append(Node(card.issue, card=card))
            op.combo += 1
            o_attached = True
            if card.kind == "unfav":
                self.catch_next = card.issue        # 6.5
                return                               # ASSUMPTION-03: an admission deals no damage
            d = self.opp_dmg(act, card.issue)
            pl.hp -= d
            o_dmg = d
            events.append("hit_player")

        def player_attach(node, base_kind, mult=1.0):
            nonlocal p_attached, p_dmg
            pl.chain.append(node)
            pl.combo += 1
            p_attached = True
            d = self.player_dmg(base_kind, node.issue, mult)
            op.hp -= d
            p_dmg = d

        if kind == "stall":
            self.stalls += 1
            self.stall_streak += 1
        else:
            self.stall_streak = 0

        # ---------------- 3 resolve (6.3, 6.4)
        if kind in ("argue", "catch", "psych"):
            stmt = None
            if kind == "catch":
                node, bk, mult, soph = Node(self.catch_issue), "catch", 1.0, False
            elif kind == "psych":
                node, bk, mult, soph = Node(ch["issue"], soph=True, cracked=True), "soph", 1.0, True
            elif ch["soph"]:
                node, bk, mult, soph = Node(ch["issue"], soph=True, cracked=True), "soph", 1.0, True
            else:
                stmt, mult = ch["stmt"], ch["mult"]
                node, bk, soph = Node(stmt.issue, false=stmt.false), "proper", False
            if ch.get("contra"):
                # 3.4 red crack: −10, the old contradicting node falls, the new node is cracked
                pl.hp -= P.CONTRADICTION
                node.cracked = True
                proper_nodes = [n for n in pl.chain if not n.soph]
                if proper_nodes:
                    pl.chain.remove(proper_nodes[0])
            if act == REBUT:
                if soph:                                       # 被拆穿
                    pl.hp -= P.EXPOSED
                    pl.combo = 0
                    self.rec_cracks += 1
                    self.shisshu_next = True
                    events.append("hit_player")
                elif stmt is not None and stmt.oppknows:      # 被駁倒
                    pl.hp -= P.REFUTED
                    stmt.voided = True
                    self.shisshu_next = True                   # ASSUMPTION-02
                    events.append("hit_player")
                read_bad = True                                # blocked: no node, combo kept
            else:
                if stmt is not None:
                    stmt.standing = True
                player_attach(node, bk, mult)
                if not soph and r.random() < self.sore:
                    events.append("sore_spot")
                if kind == "psych":
                    self.psych_card_used = True
                    for i in range(3):
                        self.psy[i] = min(100.0, self.psy[i] + self.weakness[i])
                if act in (ATTACK, FORCE):
                    opp_attach()            # clash: both attach
                else:
                    read_ok = True
                    self.heal_opp()
                    self.parry_reraise()
        elif kind == "intercept":
            soph = ch["soph"]
            if act in (ATTACK, FORCE) and card is not None and not self.no_intercept:
                if card.kind == "lie":
                    ok = soph or card.covered               # 詭辯: same issue suffices (ASSUMPTION-05)
                else:
                    ok = soph
                if ok:
                    base = P.SOPH_INTERCEPT_DMG if soph else P.INTERCEPT_DMG
                    d = base + (P.INTERCEPT_FORCE_EXTRA if act == FORCE else 0)
                    if self.broken > 0:
                        d *= 1 + P.BROKEN_BONUS             # ASSUMPTION-07
                    op.hp -= d
                    p_dmg = d
                    op.combo = 0
                    if card in self.hand:
                        self.hand.remove(card)
                    if not soph or P.SOPH_INTERCEPT_BREAKS:
                        self.broken = 2
                    read_ok = True
                    events.append("intercepted")
                    if card.kind == "lie":
                        self.refuted.append(card)
                        events.append("lie_down_soph" if soph else "lie_down_proper")
                    else:
                        events.append("fact_down_soph")
                        self.denials += 1
                    if soph:
                        self.rec_cracks += 1
                    if card.key:
                        key_hit = True                       # 抓漏洞 (ASSUMPTION-06)
                else:
                    pl.hp -= P.PROPER_MISS
                    read_bad = True
                    opp_attach()                             # ASSUMPTION-04
            else:
                read_bad = True
                if act == REBUT:                             # 互相落空
                    pl.hp -= P.WHIFF
                    op.hp -= P.WHIFF
                    events.append("own_rebut_whiff")
                elif act == PARRY:
                    pl.hp -= P.WHIFF
                    self.no_intercept = True
                    self.heal_opp()
                    self.parry_reraise()
                else:                                        # attack, but 截斷 disabled this round
                    pl.hp -= P.WHIFF
                    opp_attach()
            if act in (ATTACK, FORCE):
                self.no_intercept = False
        elif kind == "dismantle":
            soph, target = ch["soph"], ch["node"]
            if target in op.chain:
                tc = target.card
                ok = (tc.kind == "lie" and (tc.covered or soph)) or (tc.kind != "lie" and soph)
                if ok:
                    op.chain.remove(target)
                    op.hp -= P.DISMANTLE_DMG
                    p_dmg = P.DISMANTLE_DMG
                    self.opp_lost_node = True
                    if tc.kind == "lie":
                        self.refuted.append(tc)
                        events.append("lie_down_soph" if soph else "lie_down_proper")
                    else:
                        events.append("fact_down_soph")
                        self.denials += 1
                    if soph:
                        self.rec_cracks += 1
                    read_ok = True
                else:
                    pl.hp -= P.PROPER_MISS
                    read_bad = True
            if act in (ATTACK, FORCE):
                opp_attach()
            elif act == REBUT:
                op.hp -= P.WHIFF
                events.append("own_rebut_whiff")
            else:
                self.heal_opp()
                self.parry_reraise()
        elif kind == "stall":
            repeat = self.stall_streak >= 2                 # 6.3 note
            events.append("stalled")
            if act in (ATTACK, FORCE):
                pre = pl.hp
                opp_attach()
                if not repeat:
                    pl.hp += (pre - pl.hp) / 2
            elif act == REBUT:
                op.hp -= P.WHIFF                            # ASSUMPTION-08: the whiff itself still costs him
                events.append("own_rebut_whiff")
                if not repeat:
                    self.broken = 2
                    self.force_clear = True
                    read_ok = True
            else:
                pl.hp -= P.STALEMATE
                op.hp -= P.STALEMATE
            if repeat:
                pl.hp -= P.STALL_REPEAT_EXTRA

        self.last_player_soph = used_soph
        if o_attached is False and act in (ATTACK, FORCE) and kind != "intercept":
            pass
        if p_attached:
            read_ok = True                  # 7.2: 接上 counts as a correct read, clash included
        if read_ok:
            self.hachiku = min(P.HACHIKU_MAX, self.hachiku + 1)
        elif read_bad:
            self.hachiku = 0
        if self.shisshu_next:
            self.hachiku = 0

        # ---------------- 4 psych update (8.2, 8.3)
        for e in events:
            self.ev(e)
        if not self.few_fired and len(self.playable()) <= P.FEW_OPTIONS_AT:
            self.few_fired = True
            self.ev("few_options")
        for i in range(3):
            self.psy[i] = max(0.0, self.psy[i] - P.DECAY[i] * self.decay[i])
            now = self.psy[i] >= self.thr[i]
            if now and not self.over[i]:
                self.crossed[i] = True
                if i == PV:
                    self.broken = max(self.broken, 1)    # crossing round counts as 破防
                    self.next_unfav = True
            self.over[i] = now
        if self.psy[GV] >= 100:
            return self.finish(True, "confession")

        # ---------------- 5 stance check (7.3)
        ronpa = key_hit
        if not ronpa and self.broken > 0 and p_attached:
            if len(pl.chain) >= self.ronpa_len and len(self.chain_issues()) >= 2:
                ronpa = True
        rev = False
        if self.shisshu and o_attached and card is not None and card.kind != "unfav":
            if len(op.chain) >= self.ronpa_len and len({n.issue for n in op.chain}) >= 2:
                rev = True
        if ronpa and rev:
            if p_dmg >= o_dmg:
                rev = False
            else:
                ronpa = False
        if self.broken > 0:
            self.broken -= 1

        if rev:
            pl.hp = 1
            pl.combo = 0
            self.rev_ronpa = True
            self.player_locked = True
            return None
        if pl.hp <= 0:
            return self.finish(False, "loss")
        if ronpa:
            return self.on_ronpa()
        if op.hp <= 0:
            if (P.GRIND_LOCK or self.lock) and not self.ronpa_done:
                op.hp = 1.0                      # proposed fix: no win without 論破
                return None
            return self.finish(True, "reversed_win" if self.reversed else "grind")
        return None

    def on_ronpa(self):
        op = self.opp
        op.chain.clear()
        op.combo = 0
        if self.ronpa_done:                  # second 論破: no last card left
            return self.finish(True, "reversed_win" if self.reversed else "clean")
        self.ronpa_done = True
        op.hp = 1
        c = self.crack_count()
        if self.over[GV]:
            return self.finish(True, "surrender" if c > 0 else "clean")
        if c == 0 and not (self.scripted_last or self.picked_reserved):
            return self.finish(True, "clean")
        self.endgame = True
        return None
