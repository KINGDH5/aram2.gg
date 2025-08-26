# app.py — ARAM 대시보드 (진단 + 자동대체 + 탭형 UI, 캐시데코레이터 없음)
# ---------------------------------------------------------------------------------
# 파일 우선순위:
#   1) champion_master.csv
#   2) champion_master_plus.csv
#   3) (fallback) champion_summary.csv + champion_base_stats.csv 병합
# 보조 CSV(있으면 반영):
#   spell_summary.csv, item_summary.csv
#   timeline_kills.csv, timeline_item_purchases.csv
#   aram_participants_with_full_runes_merged.csv
# ---------------------------------------------------------------------------------

import os, io
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="ARAM.gg (Prototype)", layout="wide", initial_sidebar_state="collapsed")

# ===================== 스타일 =====================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif; }
.header{display:flex;align-items:center;gap:12px;margin:8px 0 16px}
.title{font-size:1.6rem;font-weight:800}
.section{font-weight:800;border-bottom:2px solid #f3f4f6;padding-bottom:6px;margin:14px 0 10px}
.empty{color:#9ca3af;background:#f8fafc;border:1px dashed #e5e7eb;border-radius:12px;padding:18px 12px;text-align:center}
.small{color:#6b7280;font-size:12px}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="header"><div class="title">ARAM.gg — 칼바람 대시보드</div></div>', unsafe_allow_html=True)

# ===================== 사이드바: 리셋/진단 =====================
with st.sidebar:
    if st.button("🔄 캐시/세션 초기화 & 재실행"):
        # 캐시/세션 완전 초기화 (혹시 남아있을지 모르는 상태 제거)
        try: st.cache_data.clear()
        except: pass
        try: st.cache_resource.clear()
        except: pass
        for k in list(st.session_state.keys()):
            try: del st.session_state[k]
            except: pass
        st.rerun()
    st.caption("이 앱은 레포의 CSV만 사용합니다 (Riot API 호출 없음)")

# ===================== 진단 블록 (현재 실행 컨텍스트 가시화) =====================
with st.expander("🔎 진단(실행 컨텍스트/파일 목록 보기)", expanded=True):
    st.write("**현재 실행 파일**:", __file__)
    st.write("**현재 작업 디렉토리(cwd)**:", os.getcwd())
    try:
        files = sorted(os.listdir("."))
        st.write("**레포 루트의 파일 목록 (상위 200개)**:", files[:200])
    except Exception as e:
        st.write("ls error:", e)

# ===================== 파일 로더 =====================
def exists(path: str) -> bool:
    try:
        return os.path.exists(path)
    except:
        return False

def load_master_dataframe() -> tuple[pd.DataFrame, str]:
    """
    1) champion_master.csv 사용
    2) 없으면 champion_master_plus.csv 사용
    3) 없으면 champion_summary.csv + champion_base_stats.csv 병합
    반환: (DataFrame, source_name)
    """
    if exists("champion_master.csv"):
        df = pd.read_csv("champion_master.csv")
        src = "champion_master.csv"
    elif exists("champion_master_plus.csv"):
        df = pd.read_csv("champion_master_plus.csv")
        src = "champion_master_plus.csv"
    elif exists("champion_summary.csv") and exists("champion_base_stats.csv"):
        s = pd.read_csv("champion_summary.csv")
        b = pd.read_csv("champion_base_stats.csv")
        df = s.merge(b, on="champion", how="left")
        # 파생치 보정
        if {"wins", "games"}.issubset(df.columns) and "winrate" not in df.columns:
            df["winrate"] = (df["wins"] / df["games"] * 100).round(2)
        src = "summary+base(merged)"
    else:
        st.error("❌ 필수 CSV가 없습니다.\n"
                 "- champion_master.csv 또는 champion_master_plus.csv\n"
                 "- 또는 champion_summary.csv + champion_base_stats.csv")
        st.stop()

    # 최소 컬럼 방어
    if "champion" not in df.columns:
        # 혹시 'name' 등에 저장되어 있으면 보정
        lower = [c.lower() for c in df.columns]
        if "name" in lower:
            df = df.rename(columns={df.columns[lower.index("name")]: "champion"})
        else:
            st.warning("champion 컬럼이 없어 임시 표시만 진행합니다.")
    if {"wins", "games"}.issubset(df.columns) and "winrate" not in df.columns:
        df["winrate"] = (df["wins"] / df["games"] * 100).round(2)
    return df, src

def safe_read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(name) if exists(name) else pd.DataFrame()

# ==== 마스터/보조 데이터 로드 ====
master, master_src = load_master_dataframe()
spell_summary = safe_read_csv("spell_summary.csv")
item_summary  = safe_read_csv("item_summary.csv")
tl_kills      = safe_read_csv("timeline_kills.csv")
tl_purchases  = safe_read_csv("timeline_item_purchases.csv")
raw           = safe_read_csv("aram_participants_with_full_runes_merged.csv")

# ===================== 상단: 개요 KPI =====================
st.markdown('<div class="section">📊 개요</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
c1.metric("챔피언 수", f"{master['champion'].nunique():,}" if "champion" in master.columns else "-")
if "games" in master.columns:
    c2.metric("총 경기 수(표본)", f"{int(master['games'].sum()):,}")
else:
    c2.metric("총 경기 수(표본)", "-")
if {"wins","games"}.issubset(master.columns):
    tot_games = master["games"].sum()
    wr = (master["wins"].sum() / tot_games * 100) if tot_games else 0
    c3.metric("전체 승률", f"{wr:.2f}%")
else:
    c3.metric("전체 승률", "-")
c4.metric("데이터 소스", master_src)

# ===================== 탭 =====================
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["챔피언 성과", "스펠 요약", "아이템 요약", "타임라인", "원자료(룬)"]
)

# ---------- 탭1: 챔피언 성과 ----------
with tab1:
    st.subheader("챔피언별 승률/피해/골드 요약")
    # 가벼운 필터
    champs = sorted(master["champion"].unique()) if "champion" in master.columns else []
    pick = st.multiselect("챔피언 필터", champs, default=[])

    dfv = master.copy()
    if pick and "champion" in dfv.columns:
        dfv = dfv[dfv["champion"].isin(pick)]

    show_cols = [c for c in ["champion","games","wins","winrate","avg_kills","avg_deaths","avg_assists","avg_damage","avg_gold","pickrate","kda"] if c in dfv.columns]
    if show_cols:
        st.dataframe(dfv[show_cols].sort_values(show_cols[1] if "winrate" not in show_cols else "winrate",
                                                ascending=False),
                     use_container_width=True, height=480)
        # 다운로드
        buf = io.StringIO(); dfv[show_cols].to_csv(buf, index=False, encoding="utf-8-sig")
        st.download_button("⬇️ 현재 표 CSV 다운로드", buf.getvalue().encode("utf-8-sig"), file_name="champion_overview.csv", mime="text/csv")
    else:
        st.markdown('<div class="empty">표시할 요약 컬럼이 없습니다. master CSV 컬럼을 확인하세요.</div>', unsafe_allow_html=True)

    # 차트
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

# ---------- 탭2: 스펠 요약 ----------
with tab2:
    st.subheader("스펠 조합 성과 요약")
    if spell_summary.empty:
        st.markdown('<div class="empty">spell_summary.csv 가 없습니다.</div>', unsafe_allow_html=True)
    else:
        st.dataframe(spell_summary.sort_values("games", ascending=False), use_container_width=True, height=480)
        buf = io.StringIO(); spell_summary.to_csv(buf, index=False, encoding="utf-8-sig")
        st.download_button("⬇️ 스펠 요약 CSV", buf.getvalue().encode("utf-8-sig"), file_name="spell_summary.csv", mime="text/csv")

# ---------- 탭3: 아이템 요약 ----------
with tab3:
    st.subheader("아이템 성과 요약")
    if item_summary.empty:
        st.markdown('<div class="empty">item_summary.csv 가 없습니다.</div>', unsafe_allow_html=True)
    else:
        st.dataframe(item_summary.sort_values("games", ascending=False), use_container_width=True, height=480)
        buf = io.StringIO(); item_summary.to_csv(buf, index=False, encoding="utf-8-sig")
        st.download_button("⬇️ 아이템 요약 CSV", buf.getvalue().encode("utf-8-sig"), file_name="item_summary.csv", mime="text/csv")

        if {"item","winrate"}.issubset(item_summary.columns):
            fig = px.bar(item_summary.sort_values("games", ascending=False).head(30),
                         x="item", y="winrate", title="아이템 승률 (Top30 by games)")
            fig.update_layout(height=360)
            st.plotly_chart(fig, use_container_width=True)

# ---------- 탭4: 타임라인 ----------
with tab4:
    st.subheader("타임라인 기반 간단 분석")
    has_any = False

    # 킬 히스토그램
    if not tl_kills.empty and "minute" in tl_kills.columns:
        has_any = True
        st.markdown("**킬 타임라인 분포**")
        fig = px.histogram(tl_kills, x="minute", nbins=40, title="킬 발생 분포(분 단위)")
        fig.update_layout(height=320)
        st.plotly_chart(fig, use_container_width=True)

    # 5분 이내 구매 아이템 상위
    if not tl_purchases.empty and {"minute","itemName"}.issubset(tl_purchases.columns):
        has_any = True
        st.markdown("**초반(≤5분) 구매 아이템 TOP**")
        early = tl_purchases[tl_purchases["minute"] <= 5].copy()
        if not early.empty:
            top = (early.groupby("itemName").size().reset_index(name="cnt")
                   .sort_values("cnt", ascending=False).head(15))
            st.dataframe(top, use_container_width=True)

    if not has_any:
        st.markdown('<div class="empty">timeline_kills.csv / timeline_item_purchases.csv 가 없습니다.</div>', unsafe_allow_html=True)

# ---------- 탭5: 원자료/룬 ----------
with tab5:
    st.subheader("원자료 + 룬 요약(있을 때)")
    if raw.empty:
        st.markdown('<div class="empty">aram_participants_with_full_runes_merged.csv 가 없습니다.</div>', unsafe_allow_html=True)
    else:
        # 챔피언×핵심룬 승률
        if {"champion","rune_core","matchId","win"}.issubset(raw.columns):
            rsum = (raw.groupby(["champion","rune_core"])
                      .agg(games=("matchId","count"), wins=("win","sum"))
                      .reset_index())
            rsum["winrate"] = (rsum["wins"]/rsum["games"]*100).round(2)
            st.markdown("**챔피언 × 핵심룬 요약**")
            st.dataframe(rsum.sort_values(["champion","games"], ascending=[True,False]),
                         use_container_width=True, height=420)
            buf = io.StringIO(); rsum.to_csv(buf, index=False, encoding="utf-8-sig")
            st.download_button("⬇️ 룬 요약 CSV", buf.getvalue().encode("utf-8-sig"), file_name="runes_by_champion.csv", mime="text/csv")

        # 원자료 미리보기
        show_cols = [c for c in ["matchId","summonerName","champion","teamId","win","kills","assists","deaths","gold",
                                 "spell1","spell2","rune_core","rune_sub"] if c in raw.columns]
        st.markdown("**원자료 미리보기**")
        st.dataframe(raw[show_cols].head(500), use_container_width=True, height=360)

st.caption("© ARAM.gg — CSV 기반. 레포의 CSV만 바꾸면 자동 반영됩니다.")
