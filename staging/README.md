# staging/

Per-scene presentation cues that are not text. Source of truth for the prototype's audio staging.

## bgm_cues_ch01-03.csv

One row per BGM cue for Ch.1-3 (plus the Ch.4 teaser paper).

| Column | Meaning |
| --- | --- |
| cue_id | Stable ID, `BGM_CHxx_nn` |
| chapter | Chapter number |
| start_id | Script line ID (`script_ch01-03.csv`) at which the cue fires, just before that line is shown. A scene heading ID (`..._L001`) means "when the scene starts". |
| bgm | Track ID (BGM01-BGM20, see 設計總覽 §十一), or `NONE` = fade to silence |
| fallback | Track to use while `bgm` is not delivered yet (`NONE` = silence). Empty = no fallback needed |
| fade | `cross` = 1.5 s crossfade; `cut` = 0.2 s fade-out, new track starts at full volume; `out` = 2.0 s fade-out to silence |
| note | Design intent |

Rules:

1. A cue lasts until the next cue fires. Every scene in Ch.1-3 starts with a cue, so nothing carries over by accident.
2. If the requested track is already playing, it keeps playing (no restart).
3. Cues on a branch line (`（分支）` rows such as `..._S06_L006 敗北`) fire only when that branch plays.
4. Inside debate scenes (Ch.1 S05, Ch.2 S05, Ch.3 S04 and S06) the cue only sets the opening track; after that the debate music rules in 設計總覽 §十一 take over (BGM07 → BGM08 → BGM09 / BGM10; Ch.1 stays BGM12; Ch.3 warm-up stays BGM07).
5. The clue board (BGM06) and other screens without script lines keep their moment default; when the flow returns to a script scene, that scene's cue fires again.
6. BGM18 (Wolfhart theme) is not delivered yet: the two Wolfhart cues use their fallback (Ch.2: silence, Ch.3: BGM03).
