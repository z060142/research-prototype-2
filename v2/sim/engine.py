"""One debate under the v2 rules (v2/00_core_rules.md, draft 0.3).

Abstraction level: evidence and statements are not modelled one by one. The
player holds a pool of 正論 statements spread over the 3 issues (some of them
sincerely wrong), can always produce a 詭辯 statement on any issue, and holds a
refuting 正論 for each opponent lie with probability `coverage`. Places where
the rules text had to be interpreted are tagged ASSUMPTION-xx; the list is in
v2/01_numbers.md §7. (For data-driven checks of one real debate see check45.py.)

Player choices are dicts:
  {"kind": "argue", "soph": bool, "issue": int, "stmt": Stmt|None, "mult": float, "contra": bool}
  {"kind": "catch"}                       抓住他的話
  {"kind": "psych", "issue": int}         心理牌（照詭辯結算，不計裂紋）
  {"kind": "intercept", "soph": bool}     反駁・截斷
  {"kind": "dismantle", "node": Node, "soph": bool}   反駁・拆台
  {"kind": "stall"}                       打迷糊仗
Any choice may carry "guard": True (援護, once per debate, 5.3).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import params as P

ATTACK, FORCE, REBUT, PARRY = "attack", "force", "rebut", "parry"   # 立論 強辯 反駁 周旋
CLASS = {ATTACK: "attack", FORCE: "attack", REBUT: "rebut", PARRY: "parry"}
PV, GV, AV = 0, 1, 2   # pressure, guilt, anger

# win grades (7.6)
GRADE = {"clean": 1, "hold": 2, "reversed_win": 3, "grind": 4}


@dataclass(eq=False)
class Card:
    kind: str              # lie / fav / unfav / picked_lie / picked_fav
    issue: int
    key: bool = False      # 要害論點
    covered: bool = False  # player holds a refuting 正論

    @property
    def is_lie(self):
        return self.kind in ("lie", "picked_lie")

    @property
    def is_fact(self):
        return self.kind in ("fav", "unfav", "picked_fav")


@dataclass(eq=False)
class Node:
    issue: int
    soph: bool = False
    psych: bool = False
    cracked: bool = False
    false: bool = False
    card: Card | None = None


@dataclass(eq=False)
class Stmt:
    issue: int
    false: bool
    oppknows: bool = False   # opponent can 駁倒 it
    standing: bool = False
    voided: bool = False
    said: bool = False


@dataclass
class Side:
    hp: float
    max_hp: float
    chain: list = field(default_factory=list)
    combo: int = 0


@dataclass
class Result:
    win: bool
    kind: str        # clean / hold / reversed_win / grind / confession / loss / loss_after_ronpa / timeout
    grade: int       # 1-4 for wins, 5 for losses
    rounds: int
    ronpa: bool
    reversed: bool   # a last card hit the player
    cracks: int
    denials: int
    crossed: tuple   # (P, G, A) crossed at least once
    stalls: int
    psych_card: bool
    truth: float
    rev_ronpa: bool  # player was 逆論破'd at least once
    comeback: bool   # 7.5 succeeded
    catches: int     # 抓住他的話 used
    slips: int       # unfavourable facts he played
    guard_saved: bool
    dying: bool      # 垂死反撲 beat happened


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
        self.max_rounds = o.get("max_rounds", P.MAX_ROUNDS)
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
        self.sore = o.get("sore", 0.0)

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
            if rng.random() < P.PICKED_LIE_SHARE:
                self.hand.append(Card("picked_lie", rng.randrange(3), covered=rng.random() < cov * 0.6))
            else:
                self.hand.append(Card("picked_fav", rng.randrange(3)))
        self.scripted_last = o["last_card"]
        self.refuted: list[Card] = []

        # player statements
        n = P.PROPER_POOL[self.stage]
        self.stmts = [Stmt(i % 3, rng.random() < st["false_share"]) for i in range(n)]
        for s in self.stmts:
            s.oppknows = s.false and rng.random() < st["refute_hidden"]

        # state
        self.rnd = 0
        self.broken = 0
        self.force_clear = False
        self.no_intercept = False
        self.shisshu = False
        self.shisshu_next = False
        self.hachiku = 0
        self.cracks = 0              # c (7.4, R-16): crack events on the public record
        self.denials = 0
        self.soph_said = 0           # sophistic statements said (truth score)
        self.stall_streak = 0
        self.stalls = 0
        self.catch_issue = None
        self.catch_next = None
        self.catches = 0
        self.slips = 0
        self.last_player_soph = False
        self.opp_lost_node = False
        self.few_fired = False
        self.ronpa_done = False
        self.reversed = False
        self.endgame = None          # None / "ronpa" / "zero"
        self.endgame_used = False    # the opponent already had his endgame
        self.player_locked = False
        self.comeback = False
        self.psych_card_used = False
        self.next_unfav = False
        self.rev_ronpa = False
        self.guard_used = False
        self.guard_saved = False
        self.dying = False
        self.both_zero = False

    # ------------------------------------------------------------ helpers
    def ev(self, name):
        base = P.EVENTS[name]
        m = self.scale
        if name in self.override:
            m = tuple(self.scale[i] * self.override[name][i] for i in range(3))
        for i in range(3):
            self.psy[i] = max(0.0, min(100.0, self.psy[i] + base[i] * m[i]))

    def playable(self):
        return [c for c in self.hand if c.kind in ("lie", "fav", "picked_lie", "picked_fav")]

    def any_over(self):
        return any(self.over)

    def floating(self):
        return any(self.psy[i] >= self.thr[i] - P.FLOAT_BAND for i in range(3))

    def player_dmg(self, base_kind, issue, mult=1.0):
        combo = min(self.player.combo, P.COMBO_CAP)
        d = P.BASE[base_kind] * (1 + P.COMBO_STEP * (combo - 1)) * mult
        prev = self.player.chain[-2] if len(self.player.chain) >= 2 else None
        if prev is not None and prev.issue == issue:
            d *= P.CONTINUATION
        d *= 1 + P.HACHIKU_STEP * self.hachiku
        if self.broken_at_start:
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
        if not self.over[PV]:
            self.opp.hp = min(self.opp.max_hp, self.opp.hp + P.HEAL)

    def parry_reraise(self):
        """周旋：把一張被打掉的謊言改口重提，沿用原牌的可破解清單（R-27）。"""
        if self.refuted:
            self.hand.append(self.refuted.pop(0))

    # ------------------------------------------------------------ opponent AI (6.2, 8.3)
    def opp_choose(self):
        r = self.rng
        cards = self.playable()
        unfav = [c for c in self.hand if c.kind == "unfav"]
        can_unfav = self.any_over() or not cards or self.floating()
        avail = cards + (unfav if can_unfav else [])
        if self.over[AV]:
            act = FORCE if (avail and r.random() < self.rage) else REBUT
        else:
            w = list(self.weights)
            if self.last_player_soph:
                w[2] *= 2.5
            if self.opp_lost_node:
                w[3] *= 2.0
            if not avail:
                w[0] = w[1] = 0
            act = r.choices([ATTACK, FORCE, REBUT, PARRY], weights=w)[0]
        card = None
        if act in (ATTACK, FORCE):
            slip = unfav and (self.next_unfav or self.over[PV]
                              or (self.floating() and r.random() < P.SLIP_CHANCE))
            if slip:
                card = r.choice(unfav)
                self.next_unfav = False
            elif cards:
                if self.over[GV]:      # 8.3: guilt over → no framing cards
                    cards = [c for c in cards if c.kind != "picked_lie"] or cards
                card = r.choices(cards, weights=[2 if c.is_lie else 1 for c in cards])[0]
            elif unfav:
                card = r.choice(unfav)
            else:
                act = REBUT
        return act, card

    def tell(self, act):
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
            return None, 0.0
        if need_new_issue:
            c2 = [s for s in cands if s.issue not in have]
            if c2:
                return c2[0], 1.0
        if prefer_issue is not None:
            c2 = [s for s in cands if s.issue == prefer_issue]
            if c2:
                return c2[0], 1.0
        s = cands[0]
        return s, (P.RERAISE if s.said else 1.0)

    def chain_issues(self):
        return {n.issue for n in self.player.chain}

    # ------------------------------------------------------------ main loop
    def run(self) -> Result:
        while True:
            self.rnd += 1
            if self.rnd > self.max_rounds:
                return self.finish(False, "timeout")
            res = self.round()
            if res is not None:
                return res

    def finish(self, win, kind):
        false_said = sum(1 for s in self.stmts if s.said and s.false)
        false_said += min(self.soph_said, P.SOPH_POOL) + (1 if self.psych_card_used else 0)
        truth = 1.0 - 0.15 * false_said - 0.20 * self.denials
        if kind == "confession":
            grade = 1 if self.cracks == 0 else 2
        else:
            grade = GRADE.get(kind, 5) if win else 5
        if win and self.both_zero:
            grade = min(4, grade + 1)
        return Result(win, kind, grade, self.rnd, self.ronpa_done, self.reversed, self.cracks,
                      self.denials, tuple(self.crossed), self.stalls, self.psych_card_used,
                      max(0.0, truth), self.rev_ronpa, self.comeback, self.catches, self.slips,
                      self.guard_saved, self.dying)

    # ------------------------------------------------------------ endgame (7.4)
    def opp_endgame(self):
        """Resolve the opponent's endgame. Returns a Result or None (debate continues)."""
        r = self.rng
        pl, op = self.player, self.opp
        kind_win = "clean" if self.ronpa_done else "grind"
        trigger = self.endgame
        self.endgame = None
        self.endgame_used = True
        c = self.cracks
        if self.over[GV]:
            return self.finish(True, ("clean" if c == 0 else "hold") if trigger == "ronpa" else "grind")
        if c == 0 and not self.picked_reserved:
            if self.scripted_last:                      # 垂死反撲 (R-14)
                self.dying = True
                has = r.random() < self.skill["counter"]
                if not self.policy.counter_last(self, has):
                    pl.hp -= P.DYING_DMG
                    if pl.hp <= 0:
                        return self.finish(False, "loss_after_ronpa")
            return self.finish(True, kind_win)
        # he plays his last card: picked-up evidence first, then the scripted one (R-03)
        uses_picked = self.picked_reserved
        has = r.random() < self.skill["counter"] * (P.PICKED_COUNTER if uses_picked else 1.0)
        attempt = self.policy.counter_last(self, has)
        if attempt and has:
            if trigger == "ronpa":
                return self.finish(True, "clean" if c == 0 else "hold")
            return self.finish(True, "grind")
        if attempt:
            pl.hp -= P.LASTCARD_BAD_CUT
        self.reversed = True
        pl.chain = [n for n in pl.chain if not (n.soph or n.cracked)]
        pl.combo = 0
        extra = P.LASTCARD_PICKED_EXTRA if uses_picked else 0.0
        if c == 0:
            pl.hp -= P.LASTCARD_ZERO_C_DMG + extra
            op.hp = op.max_hp * P.LASTCARD_ZERO_C_HEAL
        else:
            pl.hp -= P.LASTCARD_PER_CRACK * c + extra
            op.hp = op.max_hp * min(P.LASTCARD_HEAL_CAP, P.LASTCARD_HEAL_PER_CRACK * c)
        self.cracks = 0                  # ASSUMPTION-10: spent by the last card
        self.broken = 0
        self.hachiku = 0
        if pl.hp <= 0:
            return self.finish(False, "loss_after_ronpa")
        return None

    def enter_endgame(self, trigger):
        op = self.opp
        op.chain.clear()
        op.combo = 0
        op.hp = 1.0
        if trigger == "ronpa":
            self.ronpa_done = True
        if self.endgame_used:            # no last card left: this ends it
            if self.ronpa_done and trigger == "ronpa":
                return self.finish(True, "reversed_win" if self.reversed else "clean")
            return self.finish(True, "reversed_win" if (self.reversed and self.ronpa_done) else "grind")
        self.endgame = trigger
        # 罪惡感 / clean cases resolve at once; a real last card takes next round's tell
        c = self.cracks
        if self.over[GV] or (c == 0 and not self.picked_reserved):
            return self.opp_endgame()
        return None

    # ------------------------------------------------------------ one round
    def round(self):
        r = self.rng
        pl, op = self.player, self.opp
        # R-11: natural decay at the start of the round
        if self.rnd > 1:
            for i in range(3):
                self.psy[i] = max(0.0, self.psy[i] - P.DECAY[i] * self.decay[i])
                self.over[i] = self.psy[i] >= self.thr[i]
        if self.shisshu_next:                 # 7.2 (0.4): 失守 lasts until the next correct read
            self.shisshu = True
            self.shisshu_next = False
        self.catch_issue, self.catch_next = self.catch_next, None
        self.opp_lost_node = False
        self.broken_at_start = self.broken > 0
        hp_at_start_opp = op.hp

        # ---------------- 7.5 player's own last card (scripted round, he does not act)
        if self.player_locked:
            self.player_locked = False
            lies = [n for n in op.chain if n.card and n.card.is_lie and n.card.covered]
            if lies and r.random() < self.policy.comeback_read(self):
                self.comeback = True
                del op.chain[op.chain.index(lies[0]):]
                op.combo = 0
                pl.hp = P.PLAYER_COMEBACK_HP * pl.max_hp
                return None
            return self.finish(False, "loss")

        # ---------------- 7.4 opponent's last card
        if self.endgame:
            return self.opp_endgame()

        # ---------------- 1-2 tell and choice
        act, card = self.opp_choose()
        seen, clarity = self.tell(act)
        self.last_clarity = clarity
        ch = self.policy.decide(self, seen, card if seen == "attack" else None)
        kind = ch["kind"]
        guard = bool(ch.get("guard")) and not self.guard_used
        if guard:
            self.guard_used = True
        pl_hp0 = pl.hp

        p_dmg = o_dmg = 0.0
        p_attached = o_attached = False
        read_ok = read_bad = False
        hurt = False                      # he hurt the player this round (R-09)
        guard_trigger = False
        key_hit = False
        p_events, o_events = [], []       # R-10: one event per action

        def opp_attach(damage=True):
            nonlocal o_attached, o_dmg, hurt
            if card is None:
                return
            if card in self.hand:
                self.hand.remove(card)
            op.chain.append(Node(card.issue, card=card))
            op.combo += 1
            o_attached = True
            if card.kind == "unfav":
                self.slips += 1
                self.catch_next = card.issue        # 6.5
                return                               # ASSUMPTION-03
            if damage:
                d = self.opp_dmg(act, card.issue)
                pl.hp -= d
                o_dmg = d
                hurt = True
                o_events.append("hit_player")

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
                self.catches += 1
                node, bk, mult, soph = Node(self.catch_issue), "catch", 1.0, False
            elif kind == "psych":
                node, bk, mult, soph = Node(ch["issue"], psych=True), "soph", 1.0, True
            elif ch["soph"]:
                node, bk, mult, soph = Node(ch["issue"], soph=True), "soph", 1.0, True
                self.soph_said += 1
            else:
                stmt, mult = ch["stmt"], ch["mult"]
                stmt.said = True
                node, bk, soph = Node(stmt.issue, false=stmt.false), "proper", False
            if ch.get("contra"):
                pl.hp -= P.CONTRADICTION                       # 3.4
                node.cracked = True
                old = [n for n in pl.chain if not n.soph and not n.psych]
                if old:
                    pl.chain.remove(old[0])
            if act == REBUT:
                read_bad = True
                if soph:                                       # 被拆穿
                    pl.hp -= P.EXPOSED
                    pl.combo = 0
                    if kind != "psych":
                        self.cracks += 1                       # psych card: no crack (3.2, ASSUMPTION-27)
                    self.shisshu_next = True
                    hurt = True
                    guard_trigger = True
                    o_events.append("hit_player")
                elif stmt is not None and stmt.oppknows:      # 被駁倒 (R-05, R-08)
                    pl.hp -= P.REFUTED
                    pl.combo = 0
                    stmt.voided = True
                    self.shisshu_next = True
                    hurt = True
                    guard_trigger = True
                    o_events.append("hit_player")
                elif ch.get("contra"):
                    self.cracks += 1
                # else: blocked; combo kept
            else:
                if stmt is not None:
                    stmt.standing = True
                if node.soph or node.cracked:
                    self.cracks += 1                           # one crack per node (R-16)
                player_attach(node, bk, mult)
                if kind == "psych":
                    self.psych_card_used = True
                    for i in range(3):
                        self.psy[i] = min(100.0, self.psy[i] + self.weakness[i])
                elif not soph and kind != "catch" and r.random() < self.sore:
                    p_events.append("sore_spot")
                if act in (ATTACK, FORCE):
                    opp_attach()                               # both attach; layers kept, no gain
                else:
                    read_ok = True
                    self.heal_opp()
                    self.parry_reraise()
        elif kind == "intercept":
            soph = ch["soph"]
            if act in (ATTACK, FORCE) and card is not None and not self.no_intercept:
                ok = soph or (card.is_lie and card.covered)
                if ok:
                    base = P.SOPH_INTERCEPT_DMG if soph else P.INTERCEPT_DMG
                    d = base + (P.INTERCEPT_FORCE_EXTRA if act == FORCE else 0)   # R-26: fixed damage
                    op.hp -= d
                    p_dmg = d
                    op.combo = 0
                    if card in self.hand:
                        self.hand.remove(card)
                    if not soph or P.SOPH_INTERCEPT_BREAKS:
                        self.broken = 2
                    read_ok = True
                    if soph:
                        self.cracks += 1
                        self.soph_said += 1
                    if card.is_lie:
                        self.refuted.append(card)
                        p_events.append("lie_down_soph" if soph else "lie_down_proper")
                    else:
                        self.denials += 1
                        p_events.append("fact_down_soph")      # ASSUMPTION-14
                    if card.key and (self.broken_at_start or hp_at_start_opp <= 0.5 * op.max_hp):
                        key_hit = True                          # R-19
                elif card.is_lie:                               # wrong claim (R-04)
                    pl.hp -= P.WHIFF
                    read_bad = guard_trigger = True
                    opp_attach()
                else:                                           # a fact: −10, his node lands, no damage
                    pl.hp -= P.PROPER_MISS
                    read_bad = guard_trigger = True
                    opp_attach(damage=False)
                    if card.kind == "unfav":
                        self.catch_next = None                  # 錯過接話
            else:
                read_bad = guard_trigger = True
                if act == REBUT:
                    pl.hp -= P.WHIFF
                    op.hp -= P.WHIFF
                    o_events.append("own_rebut_whiff")
                elif act == PARRY:
                    pl.hp -= P.WHIFF
                    self.no_intercept = True
                    self.heal_opp()
                    self.parry_reraise()
                else:
                    pl.hp -= P.WHIFF
                    opp_attach()
            if act in (ATTACK, FORCE):
                self.no_intercept = False
        elif kind == "dismantle":
            soph, target = ch["soph"], ch["node"]
            if target in op.chain:
                tc = target.card
                ok = soph or (tc.is_lie and tc.covered)
                if ok:
                    op.chain.remove(target)
                    op.hp -= P.DISMANTLE_DMG
                    p_dmg = P.DISMANTLE_DMG
                    op.combo = 0                                # R-02
                    self.opp_lost_node = True
                    if soph:
                        self.cracks += 1
                        self.soph_said += 1
                    if tc.is_lie:
                        self.refuted.append(tc)
                        p_events.append("lie_down_soph" if soph else "lie_down_proper")
                    else:
                        self.denials += 1
                        p_events.append("fact_down_soph")
                    read_ok = True
                else:
                    pl.hp -= P.PROPER_MISS if tc.is_fact else P.WHIFF
                    read_bad = guard_trigger = True
            if act in (ATTACK, FORCE):
                opp_attach()
            elif act == REBUT:
                op.hp -= P.WHIFF
                o_events.append("own_rebut_whiff")
            else:
                self.heal_opp()
                self.parry_reraise()
        elif kind == "stall":
            repeat = self.stall_streak >= 2
            if act in (ATTACK, FORCE):
                pre = pl.hp
                opp_attach()
                if not repeat:
                    pl.hp += (pre - pl.hp) / 2
                read_bad = True                                  # ASSUMPTION-11
                p_events.append("stalled")
            elif act == REBUT:
                op.hp -= P.WHIFF                                # ASSUMPTION-08
                o_events.append("own_rebut_whiff")              # R-10: his whiff, not 被打迷糊仗
                if not repeat:
                    self.broken = 2
                    self.force_clear = True
                    read_ok = True
            else:
                pl.hp -= P.STALEMATE
                op.hp -= P.STALEMATE
                p_events.append("stalled")
            if repeat:
                pl.hp -= P.STALL_REPEAT_EXTRA
        if act == REBUT and kind in ("intercept", "dismantle", "stall"):
            self.broken = max(self.broken, 2)                   # 7.2: his rebut missed → 破防

        # 援護 (5.3)
        if guard and guard_trigger:
            pl.hp = max(pl.hp, pl_hp0)
            self.shisshu_next = False
            self.guard_saved = True

        self.last_player_soph = kind == "psych" or bool(ch.get("soph"))
        # 破竹 (R-09)
        if read_ok and not hurt:
            self.hachiku = min(P.HACHIKU_MAX, self.hachiku + 1)
        elif read_bad:
            self.hachiku = 0

        # ---------------- 4 psych update: events, then threshold check (R-11)
        for e in p_events[:1] + o_events[:1]:
            self.ev(e)
        if not self.few_fired and len(self.playable()) <= P.FEW_OPTIONS_AT:
            self.few_fired = True
            self.ev("few_options")
        for i in range(3):
            now = self.psy[i] >= self.thr[i]
            if now and not self.over[i]:
                self.crossed[i] = True
                self.broken = max(self.broken, 1)
                if i == PV:
                    self.next_unfav = True
            self.over[i] = now
        if self.psy[GV] >= 100:
            return self.finish(True, "confession")

        # ---------------- 5 stance check: 論破 → 歸零 (5.3)
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
        if read_ok and self.shisshu and P.SHISSHU_UNTIL_READ:
            self.shisshu = False                # ASSUMPTION-37: correct read = the 破竹 list
        elif not P.SHISSHU_UNTIL_READ:
            self.shisshu = False

        if rev:
            pl.hp = 1
            pl.combo = 0
            self.rev_ronpa = True
            self.player_locked = True
            return None
        if pl.hp <= 0 and op.hp <= 0:
            self.both_zero = True                               # 6.3: player wins, one grade lower
            pl.hp = 1
        if pl.hp <= 0:
            return self.finish(False, "loss")
        if ronpa:
            return self.enter_endgame("ronpa")
        if op.hp <= 0:
            return self.enter_endgame("zero")                   # R-13
        return None
