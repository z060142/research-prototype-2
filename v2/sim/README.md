# v2 論戰模擬

依 `v2/00_core_rules.md`（草案 0.4）模擬一場論戰，用來定 `v2/01_numbers.md` 的數值。

## 安裝與執行

需要 [uv](https://docs.astral.sh/uv/)（沒有第三方套件）。

```bash
# 安裝 uv（擇一）
#   Windows:  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
#   macOS / Linux:  curl -LsSf https://astral.sh/uv/install.sh | sh
cd v2/sim
uv run python run.py --n 4000 --md results.md --json results.json
```

或直接執行 `start.bat`（Windows）／`start.sh`。

`--n` 是每個「玩家策略 × 對手」的場數。4000 場約需 2～4 分鐘。

## 檔案

| 檔案 | 內容 |
| --- | --- |
| `params.py` | 所有數值（與 `01_numbers.md` 一致）。改數值只改這裡 |
| `engine.py` | 一場論戰的規則實作：對決表 6.3、兩層反駁 6.4、接話 6.5、論證與態勢 7.1～7.2、論破與殘局 7.3～7.5、心理數值 8 |
| `policies.py` | 五種玩家策略：謹慎、粗心、詭辯、拖延、心理牌 |
| `run.py` | 批次執行並輸出 Markdown／JSON 結果 |
| `results.md`／`results.json` | 最近一次 4000 場的結果（`01_numbers.md` 第 5 節引用） |
| `check45.py` | 4.5 防卡關檢查（見下） |
| `sim_data.py` | 用一場真實論戰的資料跑五種策略（見下） |
| `carry_sweep.py` | 一場論戰在不同攜帶上限下的 4.5 檢查與勝率（見下） |
| `results_demo.md`／`results_demo_carry.md` | 示範章（`v2/demo/debate_data.json`）的策略模擬與攜帶上限掃描 |
| `data/` | 論戰資料（`sherefox-debate/1` 格式） |

## 開關

| `params.py` | 預設 | 意義 |
| --- | --- | --- |
| `SOPH_INTERCEPT_DMG` | 20 | 詭辯截斷的傷害（規則：與正論截斷相同） |
| `SOPH_INTERCEPT_BREAKS` | True | 詭辯截斷是否造成破防（規則：是） |
| `MAX_ROUNDS` | 20 | 回合上限（Ch.1 亞瑟另設 8） |
| `SHISSHU_UNTIL_READ` | True | 失守持續到下一次讀對（0.4）；False ＝ 只持續一回合（0.3） |

規則詮釋（ASSUMPTION-xx）的完整清單見 `v2/01_numbers.md` 第 7 節。

## 4.5 檢查（防卡關）

```bash
uv run python check45.py data/ch02_fitch.json            # 只看帶滿上限的帶法
uv run python check45.py data/ch02_fitch.json --all-sizes # 也檢查少帶的帶法
uv run python check45.py data/ch02_fitch.json --verbose --md out.md   # 列出每一種組合
```

列舉所有合法的「帶法 × 鑑定」組合，回報沒有「不靠詭辯的獲勝路線」的組合與 WEAK 的組合。有任一種時結束碼為 1，可以放進批次檢查。判定方式寫在 `check45.py` 開頭的說明；摘要：

* 已知＝`always_known`＋帶走的證物＋其 `grants`＋做過的鑑定。
* 安全正論＝證物有帶、解鎖條件都已知、衝突清單沒有已知項（`said:` 開頭的項目是對手在論戰中才會說的話，開場時不算已知）、不是心理牌，且對手手上沒有能駁倒它的東西（撿到的證物或他自己的事實牌）。
* 對手撿證物：被留下且有 `opponent_use` 的證物，依 `pickup_priority` 撿，最多 `max_pickup` 件。
* **通過**＝存在一組兩兩不互斥的安全正論，數量 ≥ 論破門檻，涵蓋 ≥ 2 個爭點。破防一定能不靠詭辯達成（打迷糊仗騙反駁落空），接話只算加分，所以不列入條件。
* 另外回報漂亮程度：能否乾淨論破、能否截斷要害、能否截斷最後一張牌、只能用詭辯打掉的撿來謊言、真相度上限。

* **WEAK（也算失敗）**：有路線，但這套帶法沒有任何安全正論能截斷他的謊言。4.5（0.4 版，a8e4305）要求每套帶滿的帶法至少有一個能截斷他謊言的正論。

## 真實論戰的策略模擬

```bash
uv run python sim_data.py data/ch02_fitch.json --n 4000 --per 60 --md out.md
```

把一份論戰資料的每一種帶滿的帶法，換成實際的手牌與說法，交給 `engine.py` 跑五種策略：

* 對手手牌＝資料裡的謊言、有利／不利的事實，加上這套帶法下他撿到的證物（`last_card_priority` 把撿來的放第一時，留一件當最後一張牌）。
* 「能截斷」＝這套帶法裡有安全正論能破解那張牌；說法清單＝這套帶法裡所有正論，含真偽、能否被駁倒（`opp_refute`）、說法自己的心理作用。
* 謹慎／詭辯／心理牌從最好的 1/4 帶法裡抽（心理牌限有帶心理牌的帶法），粗心／拖延從全部帶法裡抽。
* 另外對每一種帶法跑謹慎玩家 `--per` 場，列出勝率最低的 5 種：用來找「規則上有路，實際上很難贏」的帶法。
* 資料沒給的數值（可信度、論證、性格）依 `stage` 與 `opponent.personality.archetype`（原型名稱，中文或 `params.py` 的代號皆可）取 `params.py` 的值。

## 攜帶上限掃描

```bash
uv run python carry_sweep.py ../demo/debate_data.json --limits 11 10 9 8 7 --appraisals 2 1 --md out.md
```

對每個「攜帶上限 × 鑑定上限」：4.5 檢查（失敗、WEAK）、謹慎／粗心／心理牌在各帶法的平均勝率、謹慎玩家最差帶法的勝率、對手撿到 2 件的比例，以及失敗帶法共同沒帶的證物（通常就是原因）。`sim_data.py` 也可用 `--carry`、`--appraisals`、`--hp`、`--dmg`、`--tendency`（行為表傾向規則的機率）、`--lastcard`（最後一張牌每道裂紋的傷害）覆寫數值做試算。示範章的數值凍結在章節 0.1（最後一張牌 15 × c），跑示範章時要加 `--lastcard 15`。

## 論戰資料格式（`sherefox-debate/1`）

一場論戰一個 JSON 檔（UTF-8）。範例：`data/ch02_fitch.json`（`v2/02_sample_debate_ch02.md` 的 Ch.2 費奇）。所有 ID 沿用 .md 表格裡的 ID；爭點用 `issues[].id` 參照。

### 頂層

| 欄位 | 必填 | 內容 |
| --- | --- | --- |
| `format` | 是 | 固定 `"sherefox-debate/1"` |
| `id` | 是 | 論戰代號，例 `"ch02_fitch"` |
| `stage` | 是 | `early`／`mid`／`late`（決定論破門檻 3／4／4） |
| `ronpa_len` | 否 | 覆寫論破門檻 |
| `carry_limit` | 是 | 攜帶上限（4.1）；`null` ＝不設限 |
| `appraisal_limit` | 是 | 鑑定次數上限（4.3） |
| `max_pickup` | 否 | 對手最多撿幾件，預設 2 |
| `issues` | 是 | `[{id, name}]`，3 個 |
| `always_known` | 否 | 不佔名額、一定拿得到的觀察與人物筆記 ID（例 `O12`、`PN1`） |
| `optional_known` | 否 | 不佔名額、但玩家可能錯過的筆記：`[{id, hotspots}]`。`check45.py` 預設檢查每一種「錯過哪幾條」的組合（`--notes all`）；`--notes known`／`missed` 只看全拿到／全錯過。`sim_data.py`、`carry_sweep.py` 預設全拿到 |
| `evidence` | 是 | 見下 |
| `appraisals` | 否 | 見下 |
| `claims` | 是 | 每個說法一筆，見下 |
| `opponent` | 是 | 見下 |

### `evidence[]`

| 欄位 | 必填 | 內容 |
| --- | --- | --- |
| `id`、`name` | 是 | |
| `carriable` | 否 | 預設 true；劇情證物填 false（不列入帶法） |
| `appraisal` | 否 | 這件證物可做的鑑定 ID |
| `grants` | 否 | 帶走時一併得到的觀察 ID（例 E02\_03 → `O03`） |
| `opponent_use` | 否 | 被留下時對手用它打出的牌 ID（對應 `opponent.cards` 中 `kind: "pickup"` 的牌） |
| `key` | 否 | 與真相有關的關鍵證物（9：沒帶走真相度 −10%） |
| `psych_card` | 否 | 心理牌（佔名額，說法一律詭辯、不計裂紋） |

### `appraisals[]`

`{id, target, unlocks[]}`。`target` 是證物 ID。鑑定 ID 本身就是「已知」項目，說法的 `unlock`／`conflicts` 直接寫鑑定 ID。`unlocks` 只是方便閱讀，判定以說法的 `unlock` 為準。可加 `reveals`（結果文字）。

### `claims[]`（說法，3.1）

| 欄位 | 必填 | 內容 |
| --- | --- | --- |
| `id`、`evidence`、`issue` | 是 | |
| `unlock` | 是 | 解鎖條件：已知項目 ID 清單（鑑定、觀察、人物筆記、證物）；空 ＝一律出現 |
| `conflicts` | 是 | 衝突清單：任一項已知 → 顯示為詭辯。對手在論戰中才說的話寫成 `"said:<簡述或台詞 ID>"` |
| `true` | 是 | 真偽 |
| `exclusive` | 是 | 互斥的說法 ID（寫一邊即可，視為雙向） |
| `breaks` | 是 | 能破解的對手牌 ID（謊言、撿來的謊言、最後一張牌）。和牌上的 `breakable_by` 是同一個關係，兩邊擇一寫或都寫，程式會合併 |
| `opp_refute` | 否 | 對手能駁倒它的方式：`[{via, line_id}]`；`via` 是撿來的證物 ID 或他的事實牌 ID，`line_id` 是駁倒台詞 ID。單一物件也接受 |
| `psych` | 否 | 心理作用：`{P, G, A}`（缺的當 0） |
| `private` | 否 | 是否公開私事 |
| `psych_card` | 否 | 心理牌的說法 |
| `text` | 否 | 主張台詞（程式不讀） |

### `opponent`

| 欄位 | 必填 | 內容 |
| --- | --- | --- |
| `cards[]` | 是 | `{id, kind, issue, breakable_by[], keystone, frames, as, source}`。`kind`：`lie`／`fav`／`unfav`／`pickup`／`last`。`pickup` 另填 `as`（`lie`／`fav`，4.2「當謊言還是事實用」）與 `source`（證物 ID）。`keystone` ＝要害論點；`frames` ＝栽贓類（罪惡感越線時不用） |
| `pickup_priority` | 否 | 撿證物的順序（證物 ID）；省略則依 `evidence` 的順序 |
| `last_card_priority` | 否 | 例 `["pickup", "last"]` |
| `hp`、`base_damage` | 否 | 覆寫數值表（模擬用） |
| `personality` | 否 | 8.4 性格表：`{start:{P,G,A}, threshold:{P,G,A}, decay:{P,G,A}, event_mult:{<事件>:{P,G,A}}, weakness:[...], rage_force_share}` |
| `behavior` | 否 | 行為表：`{weights:{attack,force,rebut,parry}, rules:[...], play_order:[...], tell_clarity:{clear,vague,disguise}}` |

`personality`、`behavior`、`hp`、`base_damage`：`check45.py` 不讀；`sim_data.py` 會讀。`sim_data.py` 認得的欄位：`personality.archetype`（可加「（改）」）、`start`、`threshold`、`decay`（每回合回落量 `{P,G,A}`）、`mult`（數值倍率）、`event_mult`（倍率）、`exceptions`（該事件的實際增量，例 `options_low`、`fooled`）、`rage_force_share`／`rage_strong_ratio`；`behavior.weights`（`attack`／`force`／`rebut`／`parry` 或 `立論`／`強辯`／`反駁`／`周旋`）、`behavior.tell_clarity`（`clear`／`vague`／`disguise` 或 `explicit`／`vague`／`disguised`）。說法自己的 `psych` 每場只生效一次（8.1）；頂層 `max_rounds`。其他欄位照樣保留給人讀。未列出的欄位一律忽略，可以自由加註解欄位（例 `note`）。
