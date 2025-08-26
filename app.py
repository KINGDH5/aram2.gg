# app.py  — ARAM 대시보드 (CSV만 사용)
# ---------------------------------------------------------
# 깃허브 레포 루트에 올려둔 CSV들을 읽어 간단한 칼바람 통계 UI를 제공합니다.
# 파일명:
#  - champion_master.csv (있으면 최우선) 또는 champion_master_plus.csv
#  - 없을 경우 champion_summary.csv + champion_base_stats.csv 를 병합해 사용
#  - 보조: spell_summary.csv, item_summary.csv
#  - 타임라인(있으면 자동 반영): timeline_kills.csv, timeline_item_purchases.csv
#  - 원자료(있으면 일부 기능 강화): aram_participants_with_full_runes_merged.csv
# ---------------------------------------------------------

import os, io
from typing import List, Tuple
import pandas as pd
import streamlit as st
import plotly.express as px

# ===================== UI 기본 스타일 =====================
st.set_page_config(page_title="ARAM.gg (Prototype)", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif; }
.header{display:flex;align-items:center;gap:12px;margin:8px 0 16px}
.title{font-size:1.6rem;font-weight:800}
.section{font-weight:800;border-bottom:2px solid #f3f4f6;padding-bottom:6px;margin:14px 0 10px}
.empty{color:#9ca3af;background:#f8fafc;border:1px dashed #e5e7eb;border-radius:12px;padding:18px 12px;text-align:center}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="header"><div class="title">ARAM.gg — 칼바람 개인 프로젝트 대시보드</div></div>', unsafe_allow_html=True)

# ===================== 사이드바 =====================
with st.sidebar:
    if st.button("🔄 캐시/세션 초기화"):
        try: st.cache_data.clear()
        except: pass
        try: st.cache_resource.clear()
        except: pass
        for k in list(st.session_state.keys()):
            try: del st.session_state[k]
            except: pass
        st.rerun()
    st.caption("이 앱은 로컬/레포 **CSV 파일**만 사용합니다 (Riot API 호출 없음).")

# ===================== 파일 로딩 유틸 =====================
def exists(path: str) -> bool:
    try: 
        return os.path.exists(path)
    except: 
        return False

def load_master() -> pd.DataFrame:
    """
    1) champion_master.csv (또는 champion_master_plus.csv) 사용
    2) 없으면 champion_summary.csv + champion_base_stats.csv 병합
    반환: 최소한 ['champion','games','wins','winrate'] 가 있는 DF
    """
    cand = ["champion_master.csv", "champion_master_plus.csv"]
    used = None
    for f in cand:
        if exists(f):
            used = f
            break

    if used:
        st.success(f"챔피언 마스터 테이블 사용: **{used}**")
        df = pd.read_csv(used)
        # 컬럼 최소 보정
        cols = [c.lower() for c in df.columns]
        # champion 컬럼명 보정
        if "champion" not in df.columns:
            # 혹시 'name' 등으로 저장된 경우
            if "champion" not in cols and "name" in cols:
                df = df.rename(columns={df.columns[cols.index("name")]: "champion"})
        # winrate 없으면 계산
        if {"wins","games"}.issubset(set(df.columns)) and "winrate" not in df.columns:
            df["winrate"] = (df["wins"]/df["games"]*100).round(2)
        return df

    # fallback: summary + base
    need = ["champion_summary.csv", "champion_base_stats.csv"]
    if all(exists(f) for f in need):
        st.warning("master csv 없음 → **summary + base** 병합하여 사용합니다.")
        s = pd.read_csv("champion_summary.csv")
        b = pd.read_csv("champion_base_stats.csv")
        df = s.merge(b, on="champion", how="left")
        if {"wins","games"}.issubset(df.columns) and "winrate" not in df.columns:
            df["winrate"] = (df["wins"]/df["games"]*100).round(2)
        return df

    st.error("필수 CSV가 없습니다. (champion_master.csv 또는 summary+base 조합)")
    st.stop()

@st.cache_data
def load_all():
    master = load_master()

    spell = pd.read_csv("spell_summary.csv") if exists("spell_summary.csv") else pd.DataFrame()
    item  = pd.read_csv("item_summary.csv")  if exists("item_summary.csv")  else pd.DataFrame()

    tl_kill = pd.read_csv("timeline_kills.csv") if exists("timeline_kills.csv") else pd.DataFrame()
    tl_buy  = pd.read_csv("timeline_item_purchases.csv") if exists("timeline_item_purchases.csv") else pd.DataFrame()

    raw = pd.read_csv("aram_participants_with_full_runes_merged.csv") if exists("aram_participants_with_full_runes_merged.csv") else pd.DataFrame()

    return master, spell, item, tl_kill, tl_buy, raw

master, spell_summary, item_summary, tl_kills, tl_purchases, raw = load_all()

# ===================== 헬퍼: 다운로드 버튼 =====================
def df_download_button(df: pd.DataFrame, label="CSV 다운로드", filename="data.csv"):
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    st.download_button(label, buf.getvalue().encode("utf-8-sig"), file_name=filename, mime="text/csv")

# ===================== 상단: 개요 =====================
st.markdown('<div class="section">📊 개요</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
c1.metric("챔피언 수", f"{master['champion'].nunique():,}")
if "games" in master.columns:
    c2.metric("총 경기 수(표본)", f"{int(master['games'].sum()):,}")
else:
    c2.metric("총 경기 수(표본)", "-")
if "wins" in master.columns and "games" in master.columns:
    wr = (master["wins"].sum() / master["games"].sum() * 100) if master["games"].sum() else 0
    c3.metric("전체 승률", f"{wr:.2f}%")
else:
    c3.metric("전체 승률", "-")
c4.metric("타임라인(킬) 레코드", f"{len(tl_kills):,}" if not tl_kills.empty else "0")

# ===================== 탭 =====================
tab_overview, tab_spell, tab_item, tab_timeline, tab_raw = st.tabs(
    ["챔피언 성과", "스펠 요약", "아이템 요약", "타임라인 분석", "원자료/룬"]
)

# ---------- 챔피언 성과 ----------
with tab_overview:
    st.subheader("챔피언별 승률/피해/골드 요약")

    # 가벼운 필터
    champs = sorted(master["champion"].unique().tolist())
    pick = st.multiselect("챔피언 필터", champs, default=[])

    dfv = master.copy()
    if pick:
        dfv = dfv[dfv["champion"].isin(pick)]

    # 표시는 꼭 존재하는 컬럼만
    show_cols = [c for c in ["champion","games","wins","winrate","avg_kills","avg_deaths","avg_assists","avg_damage","avg_gold"] if c in dfv.columns]
    if not show_cols:
        st.warning("표시할 요약 컬럼이 없습니다. master CSV 컬럼을 확인하세요.")
    else:
        st.dataframe(dfv[show_cols].sort_values("winrate", ascending=False), use_container_width=True, height=480)
        df_download_button(dfv[show_cols], "표시 데이터 다운로드", "champion_overview.csv")

    # 간단한 차트 (winrate / games)
    cc1, cc2 = st.columns(2)
    if {"champion","winrate"}.issubset(dfv.columns):
        fig = px.bar(dfv.sort_values("winrate", ascending=False).head(20),
                     x="champion", y="winrate", title="상위 승률(Top20)")
        fig.update_layout(height=360)
        cc1.plotly_chart(fig, use_container_width=True)
    if {"champion","games"}.issubset(dfv.columns):
        fig = px.bar(dfv.sort_values("games", ascending=False).head(20),
                     x="champion", y="games", title="등장 경기수(Top20)")
        fig.update_layout(height=360)
        cc2.plotly_chart(fig, use_container_width=True)

# ---------- 스펠 요약 ----------
with tab_spell:
    st.subheader("스펠 조합 성과 요약")
    if spell_summary.empty:
        st.markdown('<div class="empty">spell_summary.csv 가 없습니다.</div>', unsafe_allow_html=True)
    else:
        st.dataframe(spell_summary.sort_values("games", ascending=False), use_container_width=True, height=480)
        df_download_button(spell_summary, "CSV 다운로드", "spell_summary.csv")

# ---------- 아이템 요약 ----------
with tab_item:
    st.subheader("아이템 성과 요약")
    if item_summary.empty:
        st.markdown('<div class="empty">item_summary.csv 가 없습니다.</div>', unsafe_allow_html=True)
    else:
        st.dataframe(item_summary.sort_values("games", ascending=False), use_container_width=True, height=480)
        df_download_button(item_summary, "CSV 다운로드", "item_summary.csv")

        # 상위 아이템 승률 차트
        if {"item","winrate"}.issubset(item_summary.columns):
            fig = px.bar(item_summary.sort_values("games", ascending=False).head(30),
                         x="item", y="winrate", title="아이템 승률 (Top30 by games)")
            fig.update_layout(height=360)
            st.plotly_chart(fig, use_container_width=True)

# ---------- 타임라인 ----------
with tab_timeline:
    st.subheader("타임라인 기반 간단 분석")
    if tl_kills.empty and tl_purchases.empty:
        st.markdown('<div class="empty">timeline_kills.csv / timeline_item_purchases.csv 가 없습니다.</div>', unsafe_allow_html=True)
    else:
        if not tl_kills.empty:
            st.markdown("**킬 타임라인**")
            # minute 기준 히스토그램 (0.5분 bin)
            t = tl_kills.copy()
            if "minute" in t.columns:
                fig = px.histogram(t, x="minute", nbins=40, title="킬 발생 분포")
                fig.update_layout(height=320)
                st.plotly_chart(fig, use_container_width=True)

        if not tl_purchases.empty:
            st.markdown("**아이템 구매 타임라인 (초기 5분)**")
            p = tl_purchases.copy()
            p = p[p["minute"] <= 5] if "minute" in p.columns else p.head(0)
            if not p.empty and {"minute","itemName"}.issubset(p.columns):
                # 자주 산 시작 아이템 상위
                top = (p.groupby("itemName").size().reset_index(name="cnt")
                       .sort_values("cnt", ascending=False).head(15))
                st.dataframe(top, use_container_width=True)

# ---------- 원자료/룬 ----------
with tab_raw:
    st.subheader("원자료 + 룬 요약(있을 때)")
    if raw.empty:
        st.markdown('<div class="empty">aram_participants_with_full_runes_merged.csv 가 없습니다.</div>', unsafe_allow_html=True)
    else:
        # 챔피언/핵심룬 기준 요약
        if {"champion","rune_core"}.issubset(raw.columns):
            rsum = (raw.groupby(["champion","rune_core"])
                      .agg(games=("matchId","count"),
                           wins=("win","sum"))
                      .reset_index())
            rsum["winrate"] = (rsum["wins"]/rsum["games"]*100).round(2)
            st.markdown("**챔피언 × 핵심룬 요약**")
            st.dataframe(rsum.sort_values(["champion","games"], ascending=[True,False]),
                         use_container_width=True, height=420)
            df_download_button(rsum, "룬 요약 CSV", "runes_by_champion.csv")

        # 원자료 미리보기(가벼운 컬럼)
        show_cols = [c for c in ["matchId","summonerName","champion","teamId","win","kills","assists","deaths","gold",
                                 "spell1","spell2","rune_core","rune_sub"] if c in raw.columns]
        st.markdown("**원자료 미리보기**")
        st.dataframe(raw[show_cols].head(500), use_container_width=True, height=360)
