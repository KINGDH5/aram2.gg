import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="칼바람 챔피언 대시보드", layout="wide")

MASTER_CANDS = ["champion_master_plus.csv", "champion_master.csv"]
FALLBACKS = {
    "champion_summary": "champion_summary.csv",
    "base_stats": "champion_base_stats.csv"
}

@st.cache_data
def load_master() -> pd.DataFrame:
    # 1) master(+/기본) 우선 로드
    for name in MASTER_CANDS:
        if os.path.exists(name):
            df = pd.read_csv(name)
            df["champion"] = df["champion"].astype(str)
            df["winrate"] = df.get("winrate", np.nan)
            return df, name

    # 2) 없으면 최소 합성 (champion_summary + base_stats)
    if not (os.path.exists(FALLBACKS["champion_summary"]) and os.path.exists(FALLBACKS["base_stats"])):
        missing = []
        if not os.path.exists(FALLBACKS["champion_summary"]): missing.append("champion_summary.csv")
        if not os.path.exists(FALLBACKS["base_stats"]): missing.append("champion_base_stats.csv")
        raise FileNotFoundError(f"필수 CSV가 없습니다: {', '.join(missing)}")

    cs = pd.read_csv(FALLBACKS["champion_summary"])
    bs = pd.read_csv(FALLBACKS["base_stats"])
    df = cs.merge(bs, on="champion", how="left")
    total_games = df["games"].sum()
    df["pickrate"] = (df["games"]/total_games*100).round(2)
    df["kda"] = ((df["avg_kills"]+df["avg_assists"])/df["avg_deaths"].clip(lower=1)).round(2)
    df["champion"] = df["champion"].astype(str)
    df["winrate"] = df.get("winrate", np.nan)
    return df, "fallback(champion_summary+base_stats)"

try:
    df, source_name = load_master()
except Exception as e:
    st.error(f"❌ 데이터 로드 실패: {e}")
    st.stop()

# -----------------------------
# UI
# -----------------------------
st.title("칼바람 챔피언 통계 대시보드")
st.caption(f"데이터 소스: {source_name}")

# 사이드바
champs = sorted(df["champion"].unique())
search = st.sidebar.text_input("챔피언 검색")
if search.strip():
    champs = [c for c in champs if search.lower() in c.lower()]
champ = st.sidebar.selectbox("챔피언", champs) if champs else None
if not champ:
    st.warning("표시할 챔피언이 없습니다.")
    st.stop()

row = df[df["champion"] == champ].iloc[0]

# KPI
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("승률", f"{row.get('winrate', np.nan):.2f}%")
k2.metric("픽률", f"{row.get('pickrate', np.nan):.2f}%")
k3.metric("게임수", f"{int(row.get('games', 0)):,}")
k4.metric("KDA", f"{row.get('kda', np.nan):.2f}")
k5.metric("DPM", f"{row.get('avg_dpm', np.nan):.0f}")
k6.metric("GPM", f"{row.get('avg_gpm', np.nan):.0f}")
if "delta_winrate" in row and not pd.isna(row["delta_winrate"]):
    st.info(f"📈 최근 메타 변화: {row['delta_winrate']:+.2f}%p")

st.divider()

# 좌/우 레이아웃
left, right = st.columns([1.1, 1])

with left:
    st.subheader("추천 빌드")
    st.markdown(f"**추천 룬**: {row.get('best_rune','—')}")
    st.markdown(f"**추천 스펠**: {row.get('best_spell_combo', row.get('best_spells','—'))}")
    st.markdown(f"**시작템**: {row.get('best_start','—')}")
    st.markdown(f"**신발**: {row.get('best_boots','—')}")
    st.markdown(f"**코어3**: {row.get('best_core3','—')}")

    st.subheader("시너지 & 카운터")
    syn, synwr = row.get("synergy_top1","—"), row.get("synergy_wr", np.nan)
    hard, hardwr = row.get("enemy_hard_top1","—"), row.get("enemy_wr", np.nan)
    if isinstance(syn, str) and syn.strip():
        st.markdown(f"**같이하면 좋은 챔피언**: {syn} — {synwr if pd.isna(synwr) else f'{synwr:.2f}%'}")
    if isinstance(hard, str) and hard.strip():
        st.markdown(f"**상대하기 어려운 챔피언**: {hard} — {hardwr if pd.isna(hardwr) else f'{hardwr:.2f}%'}")

with right:
    st.subheader("페이즈별 DPM")
    if any(c in df.columns for c in ["dpm_early","dpm_mid","dpm_late"]):
        plot_df = pd.DataFrame({
            "phase":["0–8분","8–16분","16+분"],
            "dpm":[row.get("dpm_early", np.nan),
                   row.get("dpm_mid", np.nan),
                   row.get("dpm_late", np.nan)]
        })
        fig = px.bar(plot_df, x="phase", y="dpm", text="dpm", title=None, height=300)
        fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
        fig.update_layout(yaxis_title=None, xaxis_title=None, margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("페이즈별 DPM 데이터가 없습니다.")

st.divider()

# 기본 스탯
st.subheader("기본 스탯")
base_cols = [
    ("체력","hp"),("레벨당 체력","hpperlevel"),
    ("마나","mp"),("레벨당 마나","mpperlevel"),
    ("방어력","armor"),("레벨당 방어력","armorperlevel"),
    ("마법저항","spellblock"),("레벨당 마저","spellblockperlevel"),
    ("공격력","attackdamage"),("레벨당 공격력","attackdamageperlevel"),
    ("공속","attackspeed"),("레벨당 공속","attackspeedperlevel"),
    ("이동속도","movespeed"),("사거리","attackrange")
]
cols = st.columns(5)
i = 0
for label, key in base_cols:
    if key in df.columns and not pd.isna(row.get(key, np.nan)):
        cols[i % 5].metric(label, f"{row[key]:.2f}")
        i += 1

st.divider()

# 승률 TOP10 (전체)
st.subheader("승률 TOP 10 챔피언")
top10 = df[df["winrate"].notna()].sort_values("winrate", ascending=False).head(10)
if not top10.empty:
    fig = px.bar(top10, x="champion", y="winrate", text="winrate")
    fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("승률 데이터가 부족합니다.")

st.caption("© ARAM 대시보드 — CSV 기반. 레포의 CSV만 바꾸면 자동 업데이트됩니다.")
