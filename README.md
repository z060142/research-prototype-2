# 狐耳摩斯（Sherefox）第一作：設計資料包

蒸氣龐克偵探 AVG《狐耳摩斯》的完整遊戲設計文件（GDD）、在地化字串與美術素材。

主文件（線上、持續更新）：https://claude.ai/artifact/LQDVV6KG7qX32iaqWw4Pv2
`docs/` 是主文件各分頁的 Markdown 匯出快照；兩者有出入時，以線上主文件為準。

## 目錄

| 路徑 | 內容 |
| --- | --- |
| `docs/` | GDD 各分頁匯出：設計總覽、美術風格、系統規格、數值總表、各章設計（Ch.1-12）、完整劇本（Ch.1-12） |
| `gdd_parts/systems.md` | 系統規格的本地鏡像，與線上「系統規格」分頁同步 |
| `gdd_parts/numbers.md` | 數值總表的工作稿 |
| `gdd_parts/consistency_report.md` | 早期跨章一致性審查（歷史紀錄，所列問題已在主文件處理） |
| `localization/` | Ch.1-3 原型的中英對照表（zh-TW ↔ en）與 `strings.json`；說明見 `localization/README.md` |
| `images/` | 去背角色立繪、論戰對手、書法字 cut-in（論破／破竹／困獸／失守）、報紙美術風格樣張 |
| `gdd.md` | 初版 GDD 草稿 v1.0（歷史紀錄，已由主文件取代） |
| `遊戲流程-已定設計.md`、`狐耳摩斯流程藍圖.md` | 原始企劃材料 |
| `Final_Sherefox_Character_Profile.json`、`persona-wolfhart.json` | 原始角色設定 |

## 資料優先順序

1. 數值總表
2. 系統規格（規則、UI 流程）；美術風格（外觀、配色、字體、美術資產命名）
3. 各章設計
4. 劇本
5. 設計總覽（摘要層）

## 在地化原則

* 字串 ID 在 CSV 與 `strings.json` 中一一對應。
* 論戰的書法大字（論破、破竹、困獸、失守等）在中英兩種語言下都維持中文。

## 遊戲原型（Ch.1～3 可玩）

本 repo 同時是遊戲專案：以 [XTAtrium](https://github.com/z060142/XTAtrium) 執行遊戲邏輯（Atrium Script 流程圖、資料表），全部畫面用 XTFrame UI。

| 路徑 | 內容 |
| --- | --- |
| `game.json` | 專案根（XTAtrium 0.4） |
| `flows/` | 流程圖（由 `tools/gen_flows.py`、`tools/gen_debui.py`、`tools/gen_debate.py` 產生，不要手改） |
| `data/`、`strings/` | 資料表與遊戲字串（由 `tools/build_data.py` 產生） |
| `ui/boards/` → `ui/project/` | UI 原稿（.dc.html）與 XTFrame UI 專案；`ui/bundle/` 為打包產物，不進版控 |
| `ref/` | 論戰規則的 Python 參考模型（黃金軌跡） |
| `tests/` | 錄製重播與比對檢查 |
| `docs/architecture.md`、`docs/flows.md`、`docs/debate-engine.md`、`docs/ui-contracts.md`、`docs/data-schema.md`、`docs/rulings.md` | 實作文件 |

執行（需先用 XTAtrium 的 `tools/install-sdk.ps1` 建好 SDK）：

```
xtatrium pack --game .
xtatrium play --game .
xtatrium publish --game . --out <輸出目錄>
```

資料與檢查：`uv run tools/build_data.py`、`uv run tests/check_playthrough.py` 等，見 `tests/README.md`。
