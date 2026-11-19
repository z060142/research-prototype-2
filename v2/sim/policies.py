"""Player policies.

careful   讀招準、不用詭辯
careless  隨手亂打（讀招差、常出錯、偶爾詭辯）
sophist   讀招準，但大量依賴詭辯與詭辯反駁
staller   濫用打迷糊仗
psych     如 careful，但開場就用心理牌（個人弱點）
"""
from __future__ import annotations

import random


class Policy:
    name = "base"

    # how the policy plays its own last card (7.5) / the endgame counter (7.4)
    def comeback_read(self, d) -> float:
        return 0.9

    def counter_last(self, d) -> bool:
        return True

    # helpers ---------------------------------------------------------
    @staticmethod
    def argue_proper(d, contra=False):
        need_new = len(d.chain_issues()) < 2
        prev = d.player.chain[-1].issue if d.player.chain else None
        stmt, mult = d.free_stmt(need_new_issue=need_new, prefer_issue=prev)
        if stmt is None:
            return None
        return {"kind": "argue", "soph": False, "stmt": stmt, "issue": stmt.issue, "mult": mult, "contra": contra}

    @staticmethod
    def argue_soph(d):
        have = d.chain_issues()
        prev = d.player.chain[-1].issue if d.player.chain else None
        if len(have) < 2:
            issue = next(i for i in range(3) if i not in have)
        else:
            issue = prev if prev is not None else 0
        return {"kind": "argue", "soph": True, "issue": issue}

    @staticmethod
    def covered_opp_lie(d):
        for n in d.opp.chain:
            if n.card and n.card.kind == "lie" and n.card.covered:
                return n
        return None

    def judge_truth(self, d, card) -> str:
        """What the player believes the claim is: 'lie_covered', 'lie', 'fav', 'unfav'."""
        if card.kind == "lie" and card.covered:
            return "lie_covered" if d.rng.random() < 0.95 else "lie"
        right = d.rng.random() < d.skill["truth"]
        if right:
            return {"lie": "lie", "fav": "fav", "picked": "fav", "unfav": "unfav"}[card.kind]
        return d.rng.choice([k for k in ("lie_covered", "fav", "unfav") if k != card.kind])


class Careful(Policy):
    name = "careful"
    soph_share = 0.0

    def attack_response(self, d, card):
        belief = self.judge_truth(d, card)
        if belief == "lie_covered":
            return {"kind": "intercept", "soph": False}
        if belief == "unfav":
            return self.argue_proper(d) or {"kind": "stall"}   # let him say it, catch it next round
        return self.argue_proper(d) or {"kind": "stall"}       # clash

    def choose(self, d, seen, card):
        r = d.rng
        if r.random() < d.skill["noise"]:
            seen = r.choice(["attack", "rebut", "parry"])
        if seen == "rebut":
            if d.stall_streak >= 1:
                n = self.covered_opp_lie(d)
                if n is not None:
                    return {"kind": "dismantle", "node": n, "soph": False}
                return self.argue_proper(d) or {"kind": "stall"}
            return {"kind": "stall"}
        if d.catch_issue is not None:
            return {"kind": "catch"}
        if seen == "attack" and card is not None:
            return self.attack_response(d, card)
        # parry (or attack tell without a visible claim)
        return self.argue_proper(d) or {"kind": "stall"}


class Careless(Policy):
    name = "careless"

    def comeback_read(self, d):
        return 0.5

    def counter_last(self, d):
        return d.rng.random() < 0.6

    def choose(self, d, seen, card):
        r = d.rng
        if r.random() < d.skill["noise"]:
            k = r.choice(["argue", "argue", "soph", "intercept", "stall"])
            if k == "argue":
                return self.argue_proper(d, contra=r.random() < 0.1) or {"kind": "stall"}
            if k == "soph":
                return self.argue_soph(d)
            if k == "intercept":
                return {"kind": "intercept", "soph": r.random() < 0.3}
            return {"kind": "stall"}
        if seen == "rebut":
            return {"kind": "stall"} if d.stall_streak == 0 else (self.argue_proper(d) or {"kind": "stall"})
        if d.catch_issue is not None and r.random() < 0.6:
            return {"kind": "catch"}
        if seen == "attack" and card is not None:
            belief = self.judge_truth(d, card)
            if belief == "lie_covered" or (belief == "lie" and r.random() < 0.5):
                return {"kind": "intercept", "soph": belief != "lie_covered" and r.random() < 0.5}
            if r.random() < 0.25:
                return self.argue_soph(d)
            return self.argue_proper(d, contra=r.random() < 0.1) or {"kind": "stall"}
        if r.random() < 0.25:
            return self.argue_soph(d)
        return self.argue_proper(d, contra=r.random() < 0.1) or {"kind": "stall"}


class Sophist(Careful):
    """Reads well, but takes the sophistic option whenever it is stronger."""
    name = "sophist"
    soph_argue = 0.75       # share of attaches done with 詭辯

    def attack_response(self, d, card):
        belief = self.judge_truth(d, card)
        if belief == "lie_covered":
            return {"kind": "intercept", "soph": False}
        if belief == "unfav":
            return self.argue_soph(d) if d.rng.random() < self.soph_argue else (self.argue_proper(d) or {"kind": "stall"})
        # lie without coverage, or a fact: knock it down with a sophistic rebuttal
        return {"kind": "intercept", "soph": True}

    def choose(self, d, seen, card):
        r = d.rng
        if r.random() < d.skill["noise"]:
            seen = r.choice(["attack", "rebut", "parry"])
        if seen == "rebut":
            if d.stall_streak >= 1:
                n = d.opp.chain[-1] if d.opp.chain else None
                if n is not None:
                    return {"kind": "dismantle", "node": n, "soph": not (n.card.kind == "lie" and n.card.covered)}
                return self.argue_proper(d) or {"kind": "stall"}
            return {"kind": "stall"}
        if d.catch_issue is not None:
            return {"kind": "catch"}
        if seen == "attack" and card is not None:
            return self.attack_response(d, card)
        if r.random() < self.soph_argue:
            return self.argue_soph(d)
        return self.argue_proper(d) or self.argue_soph(d)


class Staller(Careless):
    name = "staller"
    stall_share = 0.7

    def choose(self, d, seen, card):
        if d.rng.random() < self.stall_share:
            return {"kind": "stall"}
        return super().choose(d, seen, card)


class Psych(Careful):
    name = "psych"

    def choose(self, d, seen, card):
        if not d.psych_card_used and seen != "rebut" and d.rnd <= 3:
            have = d.chain_issues()
            issue = next((i for i in range(3) if i not in have), 0)
            return {"kind": "psych", "issue": issue}
        return super().choose(d, seen, card)


POLICIES = {p.name: p for p in (Careful(), Careless(), Sophist(), Staller(), Psych())}
