"""All tunable numbers for the v2 debate simulation.

Every value here is mirrored in v2/01_numbers.md. Section numbers refer to
v2/00_core_rules.md.
"""

# ---------------------------------------------------------------- 7.1 damage
BASE = {"proper": 12.0, "soph": 16.0, "catch": 18.0}   # 正論／詭辯／抓住他的話
COMBO_STEP = 0.25            # 連擊倍率 = 1 + 0.25 × (combo − 1)
COMBO_CAP = 5                # 最多算到 5（×2.0）
CONTINUATION = 1.2           # 同爭點／承接
HACHIKU_STEP = 0.10          # 破竹每層
HACHIKU_MAX = 3
BROKEN_BONUS = 0.25          # 對手破防中受到的論證 +25%
RERAISE = 0.5                # 被打掉的說法重提 ×0.5

# ---------------------------------------------------------------- 6.3 clash
INTERCEPT_DMG = 20.0         # 截斷成功，對手受
INTERCEPT_FORCE_EXTRA = 10.0 # 截斷強辯時多受
DISMANTLE_DMG = 10.0         # 拆台成功，對手受
WHIFF = 5.0                  # 反駁落空的自損
PROPER_MISS = 10.0           # 正論反駁打不掉事實／不在可破解清單
EXPOSED = 25.0               # 詭辯被拆穿
REFUTED = 15.0               # 正論被駁倒（對手持有玩家不知道的資訊）
STALEMATE = 3.0              # 打迷糊仗 × 周旋，雙方各
STALL_REPEAT_EXTRA = 3.0     # 連續第 2 次打迷糊仗起的額外自損
CONTRADICTION = 10.0         # 3.4 紅色裂紋
FORCE_MULT = 1.25            # 強辯
RAGE_FORCE_MULT = 1.25       # 怒氣失常中的強辯再 ×1.25
SHISSHU_TAKEN = 0.25         # 玩家失守：下一回合受到的傷害 +25%
HEAL = 5.0                   # 周旋回復

# ---------------------------------------------------------------- 7.3–7.5
LASTCARD_PER_CRACK = 15.0    # 最後一張牌：玩家受 15 × c
LASTCARD_PICKED_EXTRA = 10.0 # 用玩家留下的證物時再 +20
LASTCARD_HEAL_PER_CRACK = 0.12
LASTCARD_HEAL_CAP = 0.45
LASTCARD_ZERO_C_DMG = 20.0   # c = 0 但有牌可出
PLAYER_COMEBACK_HP = 0.30    # 7.5 玩家最後一張牌成功後回復到 30%

MAX_ROUNDS = 20              # 超過即判玩家論敗（旁觀者散場）
SOPH_INTERCEPT_DMG = 20.0    # 詭辯截斷的傷害（規則：與正論截斷相同）
SOPH_INTERCEPT_BREAKS = True # 詭辯截斷也造成破防（規則：是）
DYING_DMG = 10.0             # 垂死反撲打中（c = 0、對手沒撿到證物，R-14）
LASTCARD_BAD_CUT = 5.0       # 殘局截斷用錯說法，視同承受再 −5
LASTCARD_ZERO_C_HEAL = 0.10  # c = 0 但用撿來的證物反擊：對手回復 10%
PICKED_COUNTER = 0.4         # 玩家握有能截斷「撿來的證物」的說法的機率，相對於劇本殺手鐧
PICKED_LIE_SHARE = 0.5       # 撿來的證物被當謊言用的比例（其餘當事實）
SOPH_POOL = 6                # 真相度：詭辯說法最多算 6 個不同的說法（每個爭點 2 個）

# ---------------------------------------------------------------- 8.2 events
# (pressure, guilt, anger) at multiplier 1
EVENTS = {
    "lie_down_proper": (20, 10, 0),
    "lie_down_soph": (12, 0, 12),
    "fact_down_soph": (5, 0, 20),
    "intercepted": (12, 0, 8),
    "own_rebut_whiff": (8, 0, 12),
    "stalled": (0, 0, 10),
    "hit_player": (-10, 0, -8),
    "few_options": (20, 0, 0),
    "innocent": (0, 20, 0),
    "sore_spot": (5, 15, 0),
    "private": (10, 0, 15),
}
DECAY = (3, 1, 5)            # 每回合自然回落
FEW_OPTIONS_AT = 2           # 選項所剩無幾：可用選項 ≤ 2
FLOAT_BAND = 15              # 浮動段：門檻 − 15 以上（R-18）
SLIP_CHANCE = 0.30           # 浮動段中每次立論改打不利事實的機率

# ---------------------------------------------------------------- 5 / 7.3 stages
STAGES = {
    #           player HP, ronpa threshold, opp base dmg, tell clarity (clear, vague, disguise)
    "early": dict(player_hp=100, ronpa_len=3, opp_base=20.0, clarity=(0.60, 0.40, 0.00),
                  hand=dict(lie=3, fav=2, unfav=1), false_share=0.15, refute_hidden=0.6),
    "mid":   dict(player_hp=140, ronpa_len=4, opp_base=14.0, clarity=(0.45, 0.45, 0.10),
                  hand=dict(lie=4, fav=2, unfav=2), false_share=0.20, refute_hidden=0.7),
    "late":  dict(player_hp=150, ronpa_len=4, opp_base=22.0, clarity=(0.30, 0.45, 0.25),
                  hand=dict(lie=5, fav=3, unfav=2), false_share=0.25, refute_hidden=0.8),
}
PROPER_POOL = {"early": 5, "mid": 6, "late": 7}   # 玩家可用的正論說法數（3 個爭點平均分）

# ---------------------------------------------------------------- 8.4 archetypes
# start / threshold: (P, G, A); decay: multiplier on DECAY; scale: per-value
# multiplier applied to every event; override: {event: (mP, mG, mA)} replacing scale;
# weights: 立論, 強辯, 反駁, 周旋; rage: share of 強辯 when anger is over (rest 反駁)
ARCHETYPES = {
    "ordinary": dict(name="一般人", start=(10, 10, 5), thr=(60, 60, 60), decay=(1, 1, 1),
                     scale=(1.0, 1.0, 1.0), override={},
                     weights=(50, 10, 20, 20), rage=0.6),
    "nervous": dict(name="心虛的初犯", start=(20, 20, 5), thr=(55, 55, 70), decay=(1, 1, 1),
                    scale=(1.2, 1.3, 0.8), override={},
                    weights=(45, 10, 20, 25), rage=0.5),
    "veteran": dict(name="老練的慣犯", start=(5, 0, 5), thr=(55, 85, 60), decay=(1.3, 1, 1),
                    scale=(0.8, 0.4, 1.0), override={"hit_player": (1.2, 0, 1.0)},
                    weights=(40, 15, 25, 20), rage=0.6),
    "expert": dict(name="自信的專家", start=(0, 5, 10), thr=(55, 75, 50), decay=(1, 1, 0.8),
                   scale=(0.7, 0.6, 1.2), override={"few_options": (-0.5, 0, 0.5)},
                   weights=(35, 10, 35, 20), rage=0.4),
    "noble": dict(name="易怒的權貴", start=(5, 5, 20), thr=(50, 70, 45), decay=(1, 1, 0.7),
                  scale=(0.9, 0.7, 1.4), override={"stalled": (0, 0, 1.6)},
                  weights=(40, 25, 20, 15), rage=0.7),
    "mastermind": dict(name="冷靜的主謀", start=(0, 0, 0), thr=(85, 95, 85), decay=(2, 2, 2),
                       scale=(0.4, 0.3, 0.4), override={"few_options": (0, 0, 0)},
                       weights=(40, 15, 25, 20), rage=0.5),
}

# ---------------------------------------------------------------- opponents
# weakness: psych effect of the psych card (通靈板-type, always 詭辯)
# last_card: scripted killer card (True/False); key_lie: has a 要害論點
OPPONENTS = {
    "arthur":   dict(name="亞瑟（Ch.1）", stage="early", arch="ordinary", hp=80, sore=0.35,
                     start=(10, 25, 0), thr=(55, 50, 70), scale=(1.0, 1.4, 0.6),
                     weights=(55, 0, 15, 30), weakness=(5, 30, 0), last_card=False, key_lie=True,
                     hand=dict(lie=2, fav=1, unfav=1), opp_base=6.0, no_pickup=True, max_rounds=8),
    "fitch":    dict(name="費奇（Ch.2）", stage="early", arch="nervous", hp=130, sore=0.25,
                     weakness=(25, 10, 0), last_card=False, key_lie=True),
    "pierce":   dict(name="皮爾斯（Ch.3）", stage="early", arch="veteran", hp=140, sore=0.10,
                     weakness=(10, 20, 5), last_card=False, key_lie=True),
    "mid_expert":  dict(name="中期：自信的專家", stage="mid", arch="expert", hp=190, sore=0.06, disguise=True,
                        weakness=(15, 5, 15), last_card=True, key_lie=True),
    "mid_noble":   dict(name="中期：易怒的權貴", stage="mid", arch="noble", hp=190, sore=0.10,
                        weakness=(10, 5, 25), last_card=False, key_lie=True),
    "mid_veteran": dict(name="中期：老練的慣犯", stage="mid", arch="veteran", hp=190, sore=0.08,
                        weakness=(15, 15, 5), last_card=True, key_lie=True),
    "late_noble":  dict(name="後期：易怒的權貴", stage="late", arch="noble", hp=260, sore=0.08,
                        weakness=(10, 5, 20), last_card=True, key_lie=True),
    "wolfhart": dict(name="Wolfhart（終局）", stage="late", arch="mastermind", hp=230, sore=0.03, disguise=True,
                     clarity=(0.30, 0.45, 0.25),
                     weakness=(5, 5, 0), last_card=True, key_lie=False),
}
STAGE_SCENARIOS = {
    "early": ["fitch", "pierce"],
    "mid": ["mid_expert", "mid_noble", "mid_veteran"],
    "late": ["late_noble", "wolfhart"],
}

# ---------------------------------------------------------------- player skill
# read: chance to read a tell correctly (clear, vague, disguise)
# truth: chance to judge a claim's truth correctly when no refuting statement is held
# coverage: chance to hold a refuting 正論 for a given opponent lie, per stage
# picked: expected number of evidence items the opponent picks up (Poisson-ish)
SKILL = {
    "careful":  dict(read=(1.0, 0.75, 0.65), truth=0.80, coverage=dict(early=0.75, mid=0.65, late=0.65),
                     key_cover=0.85, counter=0.55, picked=0.3, noise=0.03),
    "careless": dict(read=(0.90, 0.60, 0.25), truth=0.65, coverage=dict(early=0.60, mid=0.55, late=0.50),
                     key_cover=0.60, counter=0.25, picked=1.2, noise=0.20),
    "sophist":  dict(read=(1.0, 0.75, 0.65), truth=0.80, coverage=dict(early=0.75, mid=0.65, late=0.65),
                     key_cover=0.85, counter=0.55, picked=0.3, noise=0.03),
    "staller":  dict(read=(0.80, 0.50, 0.15), truth=0.55, coverage=dict(early=0.55, mid=0.45, late=0.40),
                     key_cover=0.55, counter=0.25, picked=1.2, noise=0.10),
    "psych":    dict(read=(1.0, 0.75, 0.65), truth=0.80, coverage=dict(early=0.75, mid=0.65, late=0.65),
                     key_cover=0.85, counter=0.55, picked=0.5, noise=0.03),
}
