# app.py  — ARAM 대시보드 (CSV 자동 감지/대체 버전)
# 사용 가능한 파일(있으면 사용, 없으면 건너뜀):
# - champion_master.csv / champion_master_plus.csv
# - champion_summary.csv, champion_base_stats.csv
# - spell_summary.csv, item_summary.csv
# - timeline_* (kills, first_deaths, first_towers, game_end, item_purchases, gold_diff)

import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="칼바람 대시보드", layout="wide")

# -------------------------------
# 유틸
# -------------------------------
def exists(path: str) -> bool:
    return os.path.exists(path)

def list_if_has(cols, df):
    return [c for c in cols if c in df.columns]

def metric_if(col, row, fmt="{:.2f}", label=None):
    if col in row.index and pd.notna(row[col]):
        return (label or col), fmt.format(row[col])
    return None

@st.cache_data
def read_csv_safe(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

# -------------------------------
# 데이터 로딩 (최대한 관대하게)
# -------------------------------
FILES = {
    "master_plus": "champion_master_plus.csv",
    "master":      "champion_master.csv",
    "summary":     "champion_summary.csv",
    "base":        "champion_base_stats.csv",
    "spell":       "spell_summary.csv",
    "item":        "item_summary.csv",
    # 타임라인 (옵션)
    "tl_kills":         "timeline_kills.csv",
    "tl_first_deaths":  "timeline_first_deaths.csv",
    "tl_first_towers":  "timeline_first_towers.csv",
    "tl_game_end":      "timeline_game_end.csv",
    "tl_item":          "timeline_item_purchases.csv",
    "tl_gold":          "timeline_gold_diff.csv",
}

# 디버그용: 현재 폴더 파일 보여주기 (사이드바)
with st.sidebar:
    st.caption("📁 레포 루트 파일 목록")
    try:
        st.code("\n".join(sorted(os.listdir("."))[:200]), language="bash")
    except Exception:
        pass

# 1) 마스터 DF 선택: master_plus > master > (summary+base 합성)
master_src = None
df_master = None

if exists(FILES["master_plus"]):
    df_master = read_csv_safe(FILES["master_plus"])
    master_src = FILES["master_plus"]
elif exists(FILES["master"]):
    df_master = read_csv_safe(FILES["master"])
    master_src = FILES["master"]
elif exists(FILES["summary"]) and exists(FILES["base"]):
    df_sum  = read_csv_safe(FILES["summary"])
    df_base = read_csv_safe(FILES["base"])
    df_master = df_sum.merge(df_base, on="champion", how="left")
    # 기본 파생치 채우기
    total_games = df_master["games"].sum() if "games" in df_master.columns else np.nan
    if "pickrate" not in df_master.columns and "games" in df_master.columns and total_games > 0:
        df_master["pickrate"] = (df_master["games"]/total_games*100).round(2)
    if "kda" not in df_master.columns and set(["avg_kills","avg_deaths","avg_assists"]).issubset(df_master.columns):
        df_master["kda"] = ((df_master["avg_kills"]+df_master["avg_assists"])
                            / df_master["avg_deaths"].clip(lower=1)).round(2)
    if "winrate" not in df_master.columns and set(["wins","games"]).issubset(df_master.columns):
        df_master["winrate"] = (df_master["wins"]/df_master["games"]*100).round(2)
    master_src = "summary+base(merged)"
else:
    st.error("❌ 핵심 CSV가 없습니다. 다음 중 하나가 필요합니다:\n"
             "- champion_master_plus.csv\n- champion_master.csv\n- (champion_summary.csv + champion_base_stats.csv)")
    st.stop()

# 정리
df_master["champion"] = df_master["champion"].astype(str)
if "winrate" in df_master.columns:
    df_master["winrate"] = pd.to_numeric(df_master["winrate"], errors="coerce")

# 2) 서브 데이터(있으면 로드)
def load_optional(name):
    if exists(FILES[name]):
        try:
            return read_csv_safe(FILES[name])
        except Exception:
            return None
    return None

df_spell = load_optional("spell")
df_item  = load_optional("item")
df_tlk   = load_optional("tl_kills")
df_tld   = load_optional("tl_first_deaths")
df_tlt   = load_optional("tl_first_towers")
df_tle   = load_optional("tl_game_end")
df_tli   = load_optional("tl_item")
df_tlg   = load_optional("tl_gold")

# -------------------------------
# UI — 탭 구성
# -------------------------------
st.title("칼바람 챔피언 대시보드")
st.caption(f"데이터 소스: **{master_src}**  |  CSV 기반으로 구동")

tab_overview, tab_champ, tab_tables = st.tabs(["📊 개요", "🧩 챔피언 상세", "📄 테이블/다운로드"])

# -------------------------------
# 탭 1: 개요
# -------------------------------
with tab_overview:
    # 상단 KPI
    total_games = int(df_master["games"].sum()) if "games" in df_master.columns else None
    avg_wr = df_master["winrate"].mean() if "winrate" in df_master.columns else None
    cols = st.columns(4)
    cols[0].metric("챔피언 수", f"{df_master['champion'].nunique():,}")
    if total_games: cols[1].metric("총 게임수(표본)", f"{total_games:,}")
    if avg_wr: cols[2].metric("평균 승률", f"{avg_wr:.2f}%")
    if "pickrate" in df_master.columns:
        cols[3].metric("평균 픽률", f"{df_master['pickrate'].mean():.2f}%")

    st.divider()

    # 승률 TOP10
    if "winrate" in df_master.columns:
        st.subheader("승률 TOP 10")
        top10 = df_master.dropna(subset=["winrate"]).sort_values("winrate", ascending=False).head(10)
        if not top10.empty:
            fig = px.bar(top10, x="champion", y="winrate", text="winrate", height=380)
            fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("승률 데이터가 부족합니다.")

    # 픽률 TOP10
    if "pickrate" in df_master.columns:
        st.subheader("픽률 TOP 10")
        top10p = df_master.dropna(subset=["pickrate"]).sort_values("pickrate", ascending=False).head(10)
        fig = px.bar(top10p, x="champion", y="pickrate", text="pickrate", height=360)
        fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

# -------------------------------
# 탭 2: 챔피언 상세
# -------------------------------
with tab_champ:
    champs = sorted(df_master["champion"].unique())
    c1, c2 = st.columns([1.2, 2])
    sel = c1.selectbox("챔피언 선택", champs, index=0)
    row = df_master[df_master["champion"] == sel].iloc[0]

    # KPI 보드
    k = st.columns(6)
    if "winrate" in row.index: k[0].metric("승률", f"{row['winrate']:.2f}%")
    if "pickrate" in row.index and pd.notna(row["pickrate"]): k[1].metric("픽률", f"{row['pickrate']:.2f}%")
    if "games" in row.index: k[2].metric("게임수", f"{int(row['games']):,}")
    if "kda" in row.index and pd.notna(row["kda"]): k[3].metric("KDA", f"{row['kda']:.2f}")
    if "avg_dpm" in row.index and pd.notna(row["avg_dpm"]): k[4].metric("DPM", f"{row['avg_dpm']:.0f}")
    if "avg_gpm" in row.index and pd.notna(row['avg_gpm']): k[5].metric("GPM", f"{row['avg_gpm']:.0f}")

    # 메타 변화(있으면)
    if "delta_winrate" in row.index and pd.notna(row["delta_winrate"]):
        st.info(f"📈 최근 승률 변화: {row['delta_winrate']:+.2f}%p")

    # 좌/우
    left, right = st.columns([1.1, 1])

    with left:
        st.subheader("추천 빌드 / 룬 / 스펠 (있을 때만 표시)")
        fields = [
            ("best_rune", "추천 룬"),
            ("best_spell_combo", "추천 스펠"),
            ("best_start", "시작템"),
            ("best_boots", "신발"),
            ("best_core3", "코어 3"),
            ("synergy_top1", "같이하면 좋은 챔피언"),
            ("enemy_hard_top1", "상대하기 어려운 챔피언")
        ]
        for col, label in fields:
            if col in row.index and isinstance(row[col], (str, int, float)) and str(row[col]).strip():
                st.markdown(f"- **{label}**: {row[col]}")

        # 기본 스탯(있으면)
        base_cols = [
            ("체력", "hp"), ("레벨당 체력", "hpperlevel"),
            ("마나", "mp"), ("레벨당 마나", "mpperlevel"),
            ("방어력", "armor"), ("레벨당 방어력", "armorperlevel"),
            ("마법저항", "spellblock"), ("레벨당 마저", "spellblockperlevel"),
            ("공격력", "attackdamage"), ("레벨당 공격력", "attackdamageperlevel"),
            ("공속", "attackspeed"), ("레벨당 공속", "attackspeedperlevel"),
            ("이동속도", "movespeed"), ("사거리", "attackrange"),
        ]
        st.subheader("기본 스탯")
        cols = st.columns(5)
        i=0
        for label, key in base_cols:
            if key in row.index and pd.notna(row[key]):
                cols[i%5].metric(label, f"{row[key]:.2f}")
                i+=1

    with right:
        st.subheader("페이즈별 DPM (있을 때만)")
        if any(c in df_master.columns for c in ["dpm_early","dpm_mid","dpm_late"]):
            plot_df = pd.DataFrame({
                "phase": ["0–8분","8–16분","16+분"],
                "dpm": [
                    row.get("dpm_early", np.nan),
                    row.get("dpm_mid", np.nan),
                    row.get("dpm_late", np.nan),
                ]
            })
            fig = px.bar(plot_df, x="phase", y="dpm", text="dpm", height=300)
            fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
            fig.update_layout(yaxis_title=None, xaxis_title=None, margin=dict(t=10,b=10,l=10,r=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("페이즈별 DPM 컬럼이 없습니다.")

# -------------------------------
# 탭 3: 테이블 & 다운로드
# -------------------------------
with tab_tables:
    st.subheader("원본/요약 테이블")

    def show_tbl(name, df):
        if df is None or df.empty:
            st.warning(f"{name} 없음")
            return
        st.markdown(f"#### {name}")
        st.dataframe(df, use_container_width=True, height=320)
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(f"⬇️ {name} 다운로드", data=csv, file_name=f"{name}.csv", mime="text/csv")

    show_tbl("champion_master(표시 중)", df_master)

    show_tbl("spell_summary", df_spell)
    show_tbl("item_summary",  df_item)

    show_tbl("timeline_kills",         df_tlk)
    show_tbl("timeline_first_deaths",  df_tld)
    show_tbl("timeline_first_towers",  df_tlt)
    show_tbl("timeline_game_end",      df_tle)
    show_tbl("timeline_item_purchases",df_tli)
    show_tbl("timeline_gold_diff",     df_tlg)

st.caption("© ARAM 대시보드 — 레포의 CSV만 바꿔도 자동 반영됩니다.")

