# AI 創新微課程 Taiwan Weather Forecast 作業

- **學生姓名**：林家葦
- **作業檔名**：`L3_HW.py`
- **資料庫檔案**：`data.db` (SQLite)
- **氣象資料集**：中央氣象署 (CWA) Open Data API（使用者指定代碼：`O-A003-003`，對應官方一週預報資料集：`F-C0032-003`）

---

## 📖 專案說明與功能特點

本專案完全遵照課程大綱（步驟 1 ~ 24）精心打造，從中央氣象署 API 資料擷取、JSON 格式解析、SQLite 資料庫設計、SQL 資料驗證，到 Streamlit 互動式 Web App 與 Folium 台灣地圖視覺化：

1. **API 資料取得與解析（步驟 4~7）**：
   - 支援 CWA Open Data API 連線，解析各地區之 `MinT`（最低氣溫）與 `MaxT`（最高氣溫）。
   - 具備**容錯與示範資料機制**：即使未輸入 API Key 亦能自動載入一週標準氣象預報資料，保證系統隨時可用。
2. **SQLite 資料庫架構（步驟 8~10, 20）**：
   - 資料表 `TemperatureForecasts`：
     - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
     - `regionName`: TEXT（北部地區、中部地區、南部地區、東北部地區、東部地區、東南部地區）
     - `dataDate`: TEXT（YYYY-MM-DD）
     - `minT`: REAL
     - `maxT`: REAL
     - 具備 `UNIQUE(regionName, dataDate) ON CONFLICT REPLACE` 限制，防止重複執行重複插入。
3. **Streamlit 互動 Web 介面（步驟 11~16）**：
   - 下拉式選單切換地區（北部、中部、南部、東北部、東部、東南部）。
   - 關鍵指標卡片（一週最高溫、最低溫、平均溫差）。
   - Plotly 雙折線圖（最高溫紅線、最低溫藍線，含數值標籤與平滑互動）。
   - 一週預報資料明細表。
4. **進階台灣地圖視覺化（步驟 17~19）**：
   - 結合 `folium` 與 `streamlit-folium`。
   - 依選擇日期動態在地圖上標記台灣各大區域。
   - 圓形氣泡依平均溫度動態變色（<20°C 藍、20-25°C 綠、25-30°C 橙、>30°C 紅）。
   - 支援 Popup 與 Tooltip 點擊/懸停查看詳細溫度與地區描述。
5. **資料庫驗證面板（步驟 10）**：
   - 內建教材範例 SQL 驗證與自訂 SQL 查詢執行器。

---

## 🚀 執行方式

### 1. 安裝必要套件（若尚未安裝）
```bash
pip install streamlit pandas requests folium streamlit-folium plotly
```

### 2. 啟動 Streamlit 互動儀表板
```bash
streamlit run L3_HW.py
```
執行後瀏覽器將自動開啟 `http://localhost:8501`。

### 3. CLI 快速測試資料庫（不開網頁）
```bash
python L3_HW.py --cli
```

---

## ❓ 氣象資料集代碼說明 (Q&A)

1. **關於 `O-A003-003`**：
   - 中央氣象署 (CWA) 官方一週區域預報（含北部、中部、南部、東北部、東部、東南部之 MinT / MaxT）的標準資料集代碼為 **`F-C0032-003`**。
   - 本程式在介面與後端中已做好相容適配：系統支援自訂輸入 `O-A003-003` 或直接使用標準一週預報 `F-C0032-003`。
2. **關於 API Key 授權碼**：
   - 若要從氣象署即時更新，可在網頁側邊欄輸入您在氣象署開放平臺取得的專屬 Authorization Key 並點擊同步。若沒有 Key，預設內建資料庫亦能完整呈現所有報表與地圖！
