# v2 論戰模擬

依 `v2/00_core_rules.md`（草案 0.1）模擬一場論戰，用來定 `v2/01_numbers.md` 的數值。

## 安裝與執行

需要 [uv](https://docs.astral.sh/uv/)（沒有第三方套件）。

```bash
# 安裝 uv（擇一）
#   Windows:  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
#   macOS / Linux:  curl -LsSf https://astral.sh/uv/install.sh | sh
cd v2/sim
uv run python run.py --n 4000 --md results_lock.md --json results_lock.json
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
| `results_lock.md` | 採用提案「論破前鎖 1」（`USE_LOCK_FLAGS = True`）的結果 |
| `results_as_written.md` | 規則照字面（`USE_LOCK_FLAGS = False`）的結果 |

## 開關

| `params.py` | 預設 | 意義 |
| --- | --- | --- |
| `USE_LOCK_FLAGS` | True | 提案：對手偵探、後期對手與 Wolfhart 在被論破前可信度不會低於 1（v1 已有此設定）。設為 False 即規則原文 |
| `GRIND_LOCK` | False | 所有對手都論破前鎖 1 |
| `SOPH_INTERCEPT_DMG` | 20 | 詭辯截斷的傷害（規則原文與正論截斷相同） |
| `SOPH_INTERCEPT_BREAKS` | True | 詭辯截斷是否造成破防（規則原文：是） |

規則詮釋（ASSUMPTION-xx）的完整清單見 `v2/01_numbers.md` 第 7 節。
