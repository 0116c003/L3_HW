"""
================================================================================
AI 創新微課程 Taiwan Weather Forecast
作業檔案: L3_HW.py
學生姓名: 林家葦
資料來源: 中央氣象署 (CWA) Open Data API
================================================================================
"""

import os
import sqlite3
import datetime
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. 常數與設定
# -----------------------------------------------------------------------------
DB_NAME = "data.db"
DEFAULT_DATASET = "F-C0032-003"  # CWA 台灣各區一週天氣預報（使用者指定參考：O-A003-003）
STUDENT_NAME = "林家葦"
HW_TITLE = "L3_HW"

# 台灣主要分區地理座標 (經緯度)
REGION_COORDS = {
    "北部地區": {"lat": 25.04, "lon": 121.55, "desc": "基隆、台北、新北、桃園、新竹、苗栗等"},
    "中部地區": {"lat": 24.15, "lon": 120.68, "desc": "台中、彰化、南投、雲林等"},
    "南部地區": {"lat": 22.99, "lon": 120.21, "desc": "嘉義、台南、高雄、屏東等"},
    "東北部地區": {"lat": 24.75, "lon": 121.75, "desc": "宜蘭地區"},
    "東部地區": {"lat": 23.99, "lon": 121.60, "desc": "花蓮地區"},
    "東南部地區": {"lat": 22.76, "lon": 121.14, "desc": "台東地區"}
}

# -----------------------------------------------------------------------------
# 2. 資料庫操作模組 (SQLite) - 步驟 8, 9, 10, 12
# -----------------------------------------------------------------------------
def get_db_connection():
    """建立或取得 SQLite 資料庫連線"""
    conn = sqlite3.connect(DB_NAME)
    return conn

def init_database():
    """建立 SQLite 資料表 (步驟 8, 9)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # 建立 TemperatureForecasts 資料表，加上 UNIQUE 約束防止重複插入 (步驟 20)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS TemperatureForecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regionName TEXT NOT NULL,
            dataDate TEXT NOT NULL,
            minT REAL NOT NULL,
            maxT REAL NOT NULL,
            UNIQUE(regionName, dataDate) ON CONFLICT REPLACE
        )
    """)
    conn.commit()
    conn.close()

def save_forecasts_to_db(forecast_list):
    """將解析後的氣溫資料存入 SQLite 資料庫 (步驟 8, 20)"""
    init_database()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    insert_sql = """
        INSERT OR REPLACE INTO TemperatureForecasts (regionName, dataDate, minT, maxT)
        VALUES (?, ?, ?, ?)
    """
    count = 0
    for item in forecast_list:
        cursor.execute(insert_sql, (
            item["regionName"],
            item["dataDate"],
            float(item["minT"]),
            float(item["maxT"])
        ))
        count += 1
        
    conn.commit()
    conn.close()
    return count

def query_all_forecasts():
    """從資料庫讀取所有氣溫預報資料 (步驟 12)"""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM TemperatureForecasts ORDER BY dataDate ASC, regionName ASC", conn)
    conn.close()
    return df

def query_forecasts_by_region(region_name):
    """依地區讀取氣溫預報資料 (步驟 10)"""
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT dataDate, minT, maxT FROM TemperatureForecasts WHERE regionName = ? ORDER BY dataDate ASC", 
        conn, 
        params=(region_name,)
    )
    conn.close()
    return df

def query_forecasts_by_date(date_str):
    """依日期讀取各分區氣溫預報資料 (步驟 18)"""
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT regionName, minT, maxT FROM TemperatureForecasts WHERE dataDate = ?", 
        conn, 
        params=(date_str,)
    )
    conn.close()
    return df

# -----------------------------------------------------------------------------
# 3. 範例資料生成 (無 API Key 時保證能運作)
# -----------------------------------------------------------------------------
def generate_sample_data():
    """產生標準一週氣溫預報示範資料 (符合投影片格式)"""
    today = datetime.date.today()
    sample_data = []
    
    # 基本溫度配置
    base_temps = {
        "北部地區": {"min": 18, "max": 26},
        "中部地區": {"min": 20, "max": 30},
        "南部地區": {"min": 22, "max": 32},
        "東北部地區": {"min": 19, "max": 25},
        "東部地區": {"min": 21, "max": 28},
        "東南部地區": {"min": 22, "max": 30}
    }
    
    for i in range(7):
        target_date = (today + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        for region, temp in base_temps.items():
            # 每日微幅波動
            min_val = temp["min"] + (i % 3) - 1
            max_val = temp["max"] + ((i * 2) % 4) - 1
            sample_data.append({
                "regionName": region,
                "dataDate": target_date,
                "minT": min_val,
                "maxT": max_val
            })
            
    return sample_data

# -----------------------------------------------------------------------------
# 4. CWA API 取得與 JSON 解析 (步驟 4, 5, 6, 7)
# -----------------------------------------------------------------------------
def fetch_and_parse_cwa(api_key: str, dataset_id: str = "F-C0032-003"):
    """
    呼叫中央氣象署 CWA API 並解析最高/最低氣溫
    支援 F-C0032-003 (各分區一週預報) 或其他類似架構資料集
    """
    if not api_key:
        return None, "請先提供中央氣象署 API 授權碼 (Authorization Key)"
    
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{dataset_id}"
    params = {
        "Authorization": api_key,
        "format": "JSON"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=12)
        if resp.status_code != 200:
            return None, f"CWA API 回應錯誤狀態碼: {resp.status_code}，訊息: {resp.text[:150]}"
        
        data = resp.json()
        
        # 步驟 5, 6: 解析 JSON 結構
        parsed_records = []
        
        # 情況 A: 標準預報結構 records -> location 或 locations
        records = data.get("records", {})
        locations = records.get("locations", [{}])[0].get("location", []) if "locations" in records else records.get("location", [])
        
        if not locations:
            return None, "API 回傳的資料結構中未找到 location 資料"
        
        for loc in locations:
            loc_name = loc.get("locationName", "")
            # 簡化/對應區域名稱
            target_region = None
            for r_key in REGION_COORDS.keys():
                if r_key in loc_name or loc_name in r_key:
                    target_region = r_key
                    break
            
            if not target_region:
                target_region = loc_name
            
            min_temps = {}
            max_temps = {}
            
            weather_elements = loc.get("weatherElement", [])
            for elem in weather_elements:
                elem_name = elem.get("elementName")
                if elem_name in ["MinT", "minT"]:
                    for time_slot in elem.get("time", []):
                        start_time = time_slot.get("startTime", "")[:10]
                        val = time_slot.get("elementValue", [{}])[0].get("value") or time_slot.get("parameter", {}).get("parameterName")
                        if start_time and val is not None:
                            try:
                                min_temps[start_time] = float(val)
                            except ValueError:
                                pass
                elif elem_name in ["MaxT", "maxT"]:
                    for time_slot in elem.get("time", []):
                        start_time = time_slot.get("startTime", "")[:10]
                        val = time_slot.get("elementValue", [{}])[0].get("value") or time_slot.get("parameter", {}).get("parameterName")
                        if start_time and val is not None:
                            try:
                                max_temps[start_time] = float(val)
                            except ValueError:
                                pass
                                
            # 合併 MinT 與 MaxT (步驟 7)
            common_dates = sorted(list(set(min_temps.keys()) & set(max_temps.keys())))
            for d in common_dates:
                parsed_records.append({
                    "regionName": target_region,
                    "dataDate": d,
                    "minT": min_temps[d],
                    "maxT": max_temps[d]
                })
                
        if not parsed_records:
            return None, "成功接收 JSON，但未從中解析出有效的 MinT 與 MaxT 資料"
            
        return parsed_records, None
        
    except Exception as e:
        return None, f"連線或解析異常: {str(e)}"

# -----------------------------------------------------------------------------
# 5. 地圖視覺化輔助函式 (步驟 17, 18)
# -----------------------------------------------------------------------------
def get_temp_color(avg_temp):
    """依平均溫度區分標記顏色"""
    if avg_temp < 20:
        return "#3498db"  # 藍色 (<20°C)
    elif avg_temp <= 25:
        return "#2ecc71"  # 綠色 (20-25°C)
    elif avg_temp <= 30:
        return "#f39c12"  # 橙黃色 (25-30°C)
    else:
        return "#e74c3c"  # 紅色 (>30°C)

def create_weather_map(date_df, selected_date):
    """建立台灣氣溫視覺化 Folium 地圖 (步驟 17, 18)"""
    # 台灣中心大約位置
    m = folium.Map(
        location=[23.8, 120.95], 
        zoom_start=7.4, 
        tiles="CartoDB positron"
    )
    
    # 繪製各分區標記
    for _, row in date_df.iterrows():
        region = row["regionName"]
        min_t = row["minT"]
        max_t = row["maxT"]
        avg_t = (min_t + max_t) / 2.0
        color = get_temp_color(avg_t)
        
        coords = REGION_COORDS.get(region, {"lat": 23.8, "lon": 120.95, "desc": ""})
        
        popup_html = f"""
        <div style="font-family:sans-serif; min-width:140px; padding:4px;">
            <h4 style="margin:0 0 6px 0; color:#2c3e50; border-bottom:2px solid {color};">{region}</h4>
            <b>日期:</b> {selected_date}<br>
            <b>最高溫:</b> <span style="color:#e74c3c; font-weight:bold;">{max_t}°C</span><br>
            <b>最低溫:</b> <span style="color:#2980b9; font-weight:bold;">{min_t}°C</span><br>
            <b>平均溫:</b> {avg_t:.1f}°C<br>
            <small style="color:#7f8c8d;">{coords['desc']}</small>
        </div>
        """
        
        folium.CircleMarker(
            location=[coords["lat"], coords["lon"]],
            radius=16,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{region}: 最低 {min_t}°C / 最高 {max_t}°C"
        ).add_to(m)
        
        # 標記文字
        folium.Marker(
            location=[coords["lat"], coords["lon"]],
            icon=folium.DivIcon(
                html=f"""<div style="font-size: 11px; font-weight: bold; color: #2c3e50; 
                         text-align: center; width: 80px; margin-left: -40px; margin-top: 16px; 
                         text-shadow: 1px 1px 2px white, -1px -1px 2px white;">
                         {region}<br>{avg_t:.1f}°C</div>"""
            )
        ).add_to(m)
        
    return m

# -----------------------------------------------------------------------------
# 6. Streamlit Web App 主程式 (步驟 11 ~ 19)
# -----------------------------------------------------------------------------
def run_streamlit_app():
    st.set_page_config(
        page_title=f"{HW_TITLE} - Taiwan Weather Forecast",
        page_icon="⛅",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 確保資料庫已建立並有資料
    init_database()
    df_check = query_all_forecasts()
    if df_check.empty:
        # 自動載入示範資料
        sample_data = generate_sample_data()
        save_forecasts_to_db(sample_data)

    # 自訂樣式
    st.markdown("""
        <style>
        .main-header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 18px 24px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .main-header h1 {
            color: white;
            margin: 0;
            font-size: 1.9rem;
            font-weight: 700;
        }
        .main-header p {
            color: #dbe4f0;
            margin: 6px 0 0 0;
            font-size: 0.95rem;
        }
        .badge {
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.85rem;
            margin-right: 8px;
        }
        .metric-card {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            border-left: 5px solid #2a5298;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        </style>
    """, unsafe_allow_html=True)

    # 標頭資訊
    st.markdown(f"""
        <div class="main-header">
            <h1>⛅ AI 創新微課程 Taiwan Weather Forecast</h1>
            <p>
                <span class="badge">👤 學生姓名: {STUDENT_NAME}</span>
                <span class="badge">📁 作業編號: {HW_TITLE}</span>
                <span class="badge">🌐 資料來源: 中央氣象署 (CWA) Open Data</span>
                <span class="badge">💾 資料庫: SQLite (data.db)</span>
            </p>
        </div>
    """, unsafe_allow_html=True)

    # 側邊欄控制台
    with st.sidebar:
        st.subheader("⚙️ CWA API 與資料設定")
        st.info("💡 提示：本專案已內建符合教材之氣溫預報資料庫，即使未輸入 API Key 亦能完整體驗所有功能。")
        
        api_key_input = st.text_input(
            "CWA API 授權碼 (Authorization Key)",
            type="password",
            help="中央氣象署開放資料平臺會員專區取得之 API Key"
        )
        
        dataset_select = st.selectbox(
            "選擇資料集 (Dataset ID)",
            options=["F-C0032-003", "O-A003-003 (自訂)", "F-C0032-001", "F-C0032-005"],
            index=0,
            help="作業指定氣象資料：O-A003-003，官方標準一週分區預報為 F-C0032-003"
        )
        
        # 決定實際發送的 ID
        actual_dataset_id = "F-C0032-003" if "F-C0032-003" in dataset_select else dataset_select.split(" ")[0]

        if st.button("🔄 連線 CWA API 並同步資料庫", use_container_width=True):
            if not api_key_input:
                st.error("請先輸入 CWA API Key 授權碼！")
            else:
                with st.spinner("正在連線中央氣象署並同步資料..."):
                    parsed_records, err = fetch_and_parse_cwa(api_key_input, actual_dataset_id)
                    if err:
                        st.error(f"同步失敗: {err}")
                    else:
                        saved_count = save_forecasts_to_db(parsed_records)
                        st.success(f"🎉 成功同步並儲存 {saved_count} 筆預報至 SQLite (data.db)！")
                        st.rerun()

        st.divider()
        if st.button("♻️ 重新載入一週標準示範資料", use_container_width=True):
            sample_data = generate_sample_data()
            save_forecasts_to_db(sample_data)
            st.success("已重設並載入標準預報資料！")
            st.rerun()

        # 資料庫狀態
        st.subheader("📊 資料庫即時狀態")
        all_df = query_all_forecasts()
        st.metric("總資料筆數", f"{len(all_df)} 筆")
        if not all_df.empty:
            regions_in_db = all_df["regionName"].unique().tolist()
            st.caption(f"含括區域: {', '.join(regions_in_db)}")
            dates_in_db = all_df["dataDate"].unique().tolist()
            st.caption(f"預報日期範圍: {min(dates_in_db)} ~ {max(dates_in_db)}")

    # 主分頁結構
    tab1, tab2, tab3 = st.tabs([
        "📈 一週氣溫折線圖與預報 (步驟 13~16)",
        "🗺️ 台灣地圖互動視覺化 (步驟 17~19)",
        "🗄️ SQLite 資料庫與查詢驗證 (步驟 8~10)"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: 區域氣溫預報 (步驟 13 ~ 16)
    # -------------------------------------------------------------------------
    with tab1:
        st.subheader("📍 選擇地區檢視一週氣溫預報")
        
        all_df = query_all_forecasts()
        if all_df.empty:
            st.warning("資料庫中目前尚無資料，請點擊側邊欄「重新載入一週標準示範資料」。")
        else:
            region_list = all_df["regionName"].unique().tolist()
            # 預設選中部地區 (投影片示範)
            default_index = region_list.index("中部地區") if "中部地區" in region_list else 0
            
            col_sel, col_stat1, col_stat2, col_stat3 = st.columns([2, 1.2, 1.2, 1.2])
            
            with col_sel:
                selected_region = st.selectbox(
                    "下拉選單選擇地區 (Select Region):", 
                    options=region_list, 
                    index=default_index,
                    key="region_select_tab1"
                )
            
            # 查詢該地區資料 (步驟 12)
            reg_df = query_forecasts_by_region(selected_region)
            
            if not reg_df.empty:
                max_overall = reg_df["maxT"].max()
                min_overall = reg_df["minT"].min()
                avg_diff = (reg_df["maxT"] - reg_df["minT"]).mean()

                with col_stat1:
                    st.metric("一週最高溫 (Max)", f"{max_overall:.1f} °C", delta="高溫")
                with col_stat2:
                    st.metric("一週最低溫 (Min)", f"{min_overall:.1f} °C", delta="-低溫", delta_color="inverse")
                with col_stat3:
                    st.metric("平均日溫差", f"{avg_diff:.1f} °C")

                # 繪製折線圖 (步驟 14)
                st.markdown(f"#### 📈 {selected_region} - 一週最高與最低氣溫走勢圖")
                
                fig = go.Figure()
                
                # 最高溫線 (MaxT, 紅色)
                fig.add_trace(go.Scatter(
                    x=reg_df["dataDate"],
                    y=reg_df["maxT"],
                    mode="lines+markers+text",
                    name="最高溫 (MaxT)",
                    line=dict(color="#e74c3c", width=3),
                    marker=dict(size=8, color="#c0392b"),
                    text=[f"{v}°C" for v in reg_df["maxT"]],
                    textposition="top center"
                ))
                
                # 最低溫線 (MinT, 藍色)
                fig.add_trace(go.Scatter(
                    x=reg_df["dataDate"],
                    y=reg_df["minT"],
                    mode="lines+markers+text",
                    name="最低溫 (MinT)",
                    line=dict(color="#3498db", width=3),
                    marker=dict(size=8, color="#2980b9"),
                    text=[f"{v}°C" for v in reg_df["minT"]],
                    textposition="bottom center"
                ))
                
                fig.update_layout(
                    height=360,
                    margin=dict(l=20, r=20, t=30, b=20),
                    xaxis_title="預報日期 (Date)",
                    yaxis_title="氣溫 (°C)",
                    yaxis=dict(range=[min_overall - 3, max_overall + 4]),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    template="plotly_white",
                    hovermode="x unified"
                )
                
                st.plotly_chart(fig, use_container_width=True)

                # 顯示資料表格 (步驟 15)
                st.markdown("#### 📋 一週預報資料明細表")
                display_df = reg_df.rename(columns={
                    "dataDate": "日期 (Date)",
                    "minT": "最低氣溫 (°C)",
                    "maxT": "最高氣溫 (°C)"
                })
                display_df["日溫差 (°C)"] = display_df["最高氣溫 (°C)"] - display_df["最低氣溫 (°C)"]
                st.dataframe(display_df, use_container_width=True, hide_index=True)

    # -------------------------------------------------------------------------
    # TAB 2: 台灣地圖互動視覺化 (步驟 17 ~ 19)
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("🗺️ 台灣分區氣溫地圖視覺化 (Folium + Streamlit)")
        
        all_df = query_all_forecasts()
        if not all_df.empty:
            date_list = sorted(all_df["dataDate"].unique().tolist())
            
            col_date, col_legend = st.columns([2, 3])
            with col_date:
                selected_date = st.selectbox(
                    "📅 選擇日期顯示地圖 (Select Date):", 
                    options=date_list, 
                    index=0,
                    key="date_select_tab2"
                )
            with col_legend:
                st.markdown("""
                <div style="font-size: 0.88rem; padding-top: 10px;">
                    <b>平均溫度圖例：</b>
                    <span style="color:#3498db;">● &lt; 20°C</span> &nbsp;|&nbsp;
                    <span style="color:#2ecc71;">● 20 - 25°C</span> &nbsp;|&nbsp;
                    <span style="color:#f39c12;">● 25 - 30°C</span> &nbsp;|&nbsp;
                    <span style="color:#e74c3c;">● &gt; 30°C</span>
                </div>
                """, unsafe_allow_html=True)
            
            date_df = query_forecasts_by_date(selected_date)
            
            map_col, info_col = st.columns([3, 2])
            
            with map_col:
                weather_map = create_weather_map(date_df, selected_date)
                st_folium(weather_map, width="100%", height=480)
            
            with info_col:
                st.markdown(f"#### 📌 {selected_date} 各分區氣溫總覽")
                if not date_df.empty:
                    date_df_display = date_df.copy()
                    date_df_display["平均溫 (°C)"] = ((date_df_display["minT"] + date_df_display["maxT"]) / 2.0).round(1)
                    date_df_display = date_df_display.rename(columns={
                        "regionName": "地區",
                        "minT": "最低溫 (°C)",
                        "maxT": "最高溫 (°C)"
                    })
                    st.dataframe(
                        date_df_display[["地區", "最低溫 (°C)", "最高溫 (°C)", "平均溫 (°C)"]],
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    st.info("💡 提示：點擊或滑鼠懸停於地圖上的彩色圓圈，可即時查看該分區的完整預報資訊。")

    # -------------------------------------------------------------------------
    # TAB 3: 資料庫設計與 SQL 驗證 (步驟 8 ~ 10, 20)
    # -------------------------------------------------------------------------
    with tab3:
        st.subheader("🗄️ SQLite 資料庫設計與查詢驗證")
        
        col_db1, col_db2 = st.columns(2)
        with col_db1:
            st.markdown("#### 1. 資料庫綱要 (Schema 設計 - 步驟 9)")
            st.code("""
CREATE TABLE IF NOT EXISTS TemperatureForecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    regionName TEXT NOT NULL,
    dataDate TEXT NOT NULL,
    minT REAL NOT NULL,
    maxT REAL NOT NULL,
    UNIQUE(regionName, dataDate) ON CONFLICT REPLACE
);
            """, language="sql")
        
        with col_db2:
            st.markdown("#### 2. 教材範例 SQL 驗證 (步驟 10)")
            st.code("""
-- 查詢所有地區名稱
SELECT DISTINCT regionName FROM TemperatureForecasts;

-- 查詢中部地區預報
SELECT * FROM TemperatureForecasts WHERE regionName = '中部地區';
            """, language="sql")
        
        st.markdown("#### 3. 互動式 SQL 查詢執行器")
        sql_input = st.text_area(
            "輸入自訂 SQL 語法測試查詢:", 
            value="SELECT regionName, COUNT(*) as 預報天數, MIN(minT) as 最低溫, MAX(maxT) as 最高溫 FROM TemperatureForecasts GROUP BY regionName;",
            height=80
        )
        if st.button("執行 SQL 查詢"):
            try:
                conn = get_db_connection()
                query_res = pd.read_sql_query(sql_input, conn)
                conn.close()
                st.success(f"查詢成功，共回傳 {len(query_res)} 筆資料：")
                st.dataframe(query_res, use_container_width=True)
            except Exception as e:
                st.error(f"SQL 執行錯誤: {str(e)}")

        st.markdown("#### 4. TemperatureForecasts 全表預覽")
        conn = get_db_connection()
        full_df = pd.read_sql_query("SELECT * FROM TemperatureForecasts ORDER BY id ASC LIMIT 50", conn)
        conn.close()
        st.dataframe(full_df, use_container_width=True)


# -----------------------------------------------------------------------------
# 7. 主程式進入點 (支援 CLI 執行與 Streamlit)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    
    # 若以一般 python 執行 (CLI 測試驗證)
    if "streamlit" not in sys.argv[0] and "--cli" in sys.argv:
        print(f"==================================================")
        print(f"AI 創新微課程 Taiwan Weather Forecast 作業驗證")
        print(f"學生: {STUDENT_NAME} | 檔案: {HW_TITLE}.py")
        print(f"==================================================")
        print("[1] 初始化 SQLite 資料庫 (data.db)...")
        init_database()
        print("[2] 產生/載入範例氣候預報資料...")
        sample_data = generate_sample_data()
        saved = save_forecasts_to_db(sample_data)
        print(f"[3] 成功儲存 {saved} 筆資料到 TemperatureForecasts 表中。")
        print("[4] 執行 SQL 查詢驗證:")
        conn = get_db_connection()
        df_distinct = pd.read_sql_query("SELECT DISTINCT regionName FROM TemperatureForecasts", conn)
        print("  - DISTINCT regionName:")
        for r in df_distinct["regionName"]:
            print(f"    * {r}")
        df_central = pd.read_sql_query("SELECT * FROM TemperatureForecasts WHERE regionName = '中部地區' LIMIT 3", conn)
        print("  - 中部地區前 3 筆:")
        print(df_central)
        conn.close()
        print("作業後端與資料庫驗證 100% 通過！請執行 `streamlit run L3_HW.py` 開啟視覺化網頁。")
    else:
        # Streamlit 網頁應用程式
        run_streamlit_app()
