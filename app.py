"""
서울의 유령 버스 정류장 대시보드
실행: streamlit run app.py
필요 파일: stops_summary.csv (prep.py로 만든 정리 표), seoul_gu.geojson (구 경계)
"""
import json
import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

st.set_page_config(page_title="서울의 유령 버스 정류장", page_icon="🚏", layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------- 색과 차트 기본값 ----------------
NAVY, YELLOW, INK, MUTED, GRID = "#1d3f7a", "#ffc93c", "#1f2733", "#5b6573", "#e7e7e7"
BLUE, ORANGE, AQUA, AMBER, GRAY = "#257de0", "#f47230", "#00b894", "#f2a600", "#c9ced6"

# 유형 4개: 색은 늘 이 순서로 고정(필터가 바뀌어도 같은 유형은 같은 색)
TYPE_ORDER = ["늘 비고, 가까이 대안 있음", "늘 비고, 대안이 멂", "주말에만 빔", "평일에만 빔"]
TYPE_COLOR = dict(zip(TYPE_ORDER, [BLUE, ORANGE, AQUA, AMBER]))
WALK_M_PER_MIN = 80  # 사람 걷는 속도: 분당 약 80m

pio.templates["bus"] = go.layout.Template(layout=dict(
    font=dict(family="Pretendard, Noto Sans KR, sans-serif", size=13, color=INK),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(gridcolor=GRID, zeroline=False, linecolor=GRID),
    yaxis=dict(gridcolor=GRID, zeroline=False, linecolor=GRID),
    hoverlabel=dict(bgcolor=NAVY, bordercolor=NAVY, font=dict(color="white", family="Pretendard, Noto Sans KR, sans-serif")),
    legend=dict(orientation="h", y=1.08, x=0, title=None),
    margin=dict(l=0, r=10, t=20, b=0),
))
pio.templates.default = "plotly_white+bus"
CHART_CFG = {"displayModeBar": False}


@st.cache_data
def load():
    df = pd.read_csv("stops_summary.csv", dtype={"NODE_ID": str, "ARS_ID": str})
    df["ARS_ID"] = df["ARS_ID"].str.zfill(5)
    df["걷는시간_분"] = df["앞뒤최소거리_m"] / WALK_M_PER_MIN
    return df


@st.cache_data
def load_gu():
    with open("seoul_gu.geojson", encoding="utf-8") as f:
        return json.load(f)


df = load()
GU = load_gu()

# ---------------- 디자인(CSS) ----------------
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
html, body, [class*="css"], .stMarkdown, button, input, textarea, label {font-family:"Pretendard", -apple-system, "Noto Sans KR", sans-serif !important;}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none;}
.block-container {padding-top:2.2rem; max-width:1250px;}

/* 정류장 표지판 */
.stop-sign {display:flex; gap:22px; align-items:center; background:#1d3f7a; color:#fff; border-radius:16px; padding:24px 28px;}
.stop-sign .num {display:inline-block; background:#ffc93c; color:#1d3f7a; font-weight:800; border-radius:6px; padding:2px 10px; font-size:0.82rem; letter-spacing:0.06em;}
.stop-sign h1 {color:#fff !important; margin:8px 0 6px 0; padding:0; font-size:2.35rem; line-height:1.2; font-weight:800;}
.stop-sign .sub {color:#dbe4f3; font-size:0.98rem; margin:0; line-height:1.6;}
.route-band {display:flex; height:7px; border-radius:0 0 8px 8px; overflow:hidden; margin:0 16px 20px 16px;}
.route-band span {flex:1;}

/* 버스 도착 안내 전광판 */
.led-board {background:#121212; border-radius:12px 12px 0 0; padding:14px 18px 10px 18px; border:3px solid #2b2b2b; border-bottom:none;
  display:grid; grid-template-columns:repeat(4, 1fr); gap:10px;}
.led-cell {border-left:1px dashed #3a3a3a; padding:4px 14px;}
.led-cell:first-child {border-left:none;}
.led-label {color:#9fb3c8; font-size:0.82rem; margin-bottom:4px;}
.led-value {color:#ffb300; font-family:"DejaVu Sans Mono", Menlo, Consolas, monospace; font-weight:700; font-size:2rem; letter-spacing:0.03em; text-shadow:0 0 6px rgba(255,179,0,0.5);}
.led-value small {font-size:0.95rem; margin-left:3px;}
.led-value.blue {color:#6fb1ff; text-shadow:0 0 6px rgba(111,177,255,0.5);}
.led-value.orange {color:#ff8a4c; text-shadow:0 0 6px rgba(255,138,76,0.5);}
.led-foot {color:#7d8a99; font-size:0.76rem; margin-top:2px;}
.ticker {background:#121212; border-radius:0 0 12px 12px; overflow:hidden; white-space:nowrap; border:3px solid #2b2b2b; border-top:1px dashed #3a3a3a; margin-bottom:6px;}
.ticker .run {display:inline-block; padding:8px 0; color:#ffb300; font-family:"DejaVu Sans Mono", Menlo, monospace; font-size:0.9rem; animation:run 45s linear infinite; padding-left:100%;}
.ticker .run b {color:#6fb1ff;}
@keyframes run {from {transform:translateX(0);} to {transform:translateX(-100%);}}
@media (prefers-reduced-motion: reduce) {.ticker .run {animation:none; padding-left:12px;}}
@media (max-width: 900px) {.led-board {grid-template-columns:repeat(2, 1fr);}}

/* 조건 줄: 전체 조건(진한 테두리), 그래프 조건(연한 바탕) */
.st-key-global_bar {background:#eef3fb; border:2px solid #1d3f7a; border-radius:14px; padding:12px 18px 4px 18px; margin:14px 0 8px 0;}
[class*="st-key-chart_bar"] {background:#f4f6fa; border-radius:10px; padding:8px 14px 0 14px; margin-bottom:4px;}
.bar-title {font-weight:800; color:#1d3f7a; font-size:0.92rem; margin-bottom:2px;}
.bar-title .chip {background:#ffc93c; color:#1d3f7a; border-radius:5px; padding:1px 7px; margin-right:6px; font-size:0.78rem;}
.small-label {font-size:0.8rem; color:#5b6573; font-weight:700; margin-bottom:-6px;}

/* 탭 = 노선도 */
[role="tablist"] {gap:0 !important; position:relative; padding-top:26px !important; border-bottom:none !important; margin-top:8px;}
[role="tablist"]::before {content:""; position:absolute; top:33px; left:12.5%; right:12.5%; height:6px; background:#3b6fc4; border-radius:3px; z-index:0;}
[role="tab"] {flex:1 1 0 !important; position:relative; padding-top:28px !important; background:transparent !important; justify-content:center; text-align:center; z-index:1;}
[role="tab"]::before {content:""; position:absolute; top:0; left:50%; transform:translateX(-50%); width:20px; height:20px; border-radius:50%; background:#fff; border:4px solid #3b6fc4; box-sizing:border-box;}
[role="tab"][aria-selected="true"]::before {background:#ffc93c; border-color:#1d3f7a; width:28px; height:28px; top:-4px; box-shadow:0 0 0 5px rgba(255,201,60,0.35);}
[role="tab"] p {font-size:1rem !important; font-weight:600; color:#5b6573;}
[role="tab"][aria-selected="true"] p {color:#1d3f7a !important; font-weight:800;}
.react-aria-SelectionIndicator, div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {display:none !important;}

/* 그래프 제목 = 정류장 안내판 */
.sec {display:flex; align-items:center; gap:12px; margin:22px 0 4px 0;}
.sec .no {background:#1d3f7a; color:#ffc93c; font-weight:800; border-radius:8px; padding:4px 11px; font-family:"DejaVu Sans Mono", Menlo, monospace; font-size:0.95rem; white-space:nowrap;}
.sec .tt {font-size:1.3rem; font-weight:800; color:#1f2733; line-height:1.35;}
.sec-sub {color:#5b6573; margin:2px 0 10px 0; font-size:0.95rem;}

/* 안내 방송 카드, 예시 카드 */
.announce {display:flex; gap:14px; align-items:flex-start; background:#fff8e1; border:2px solid #ffc93c; border-radius:12px; padding:14px 16px; margin:10px 0;}
.announce .ic {font-size:1.5rem; line-height:1;}
.announce .hd {font-weight:800; color:#1d3f7a; margin-bottom:2px;}
.announce .big {font-family:"DejaVu Sans Mono", Menlo, monospace; font-weight:800; font-size:1.12rem;}
.cards {display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; margin:6px 0 4px 0;}
.card {border-radius:12px; padding:12px 14px; background:#fff; border:1px solid #e3e7ee; border-top:6px solid var(--c);}
.card .t {font-weight:800; color:#1f2733; font-size:0.92rem;}
.card .n {font-family:"DejaVu Sans Mono", Menlo, monospace; font-weight:800; font-size:1.6rem; color:#1f2733;}
.card .n small {font-size:0.85rem; color:#5b6573; margin-left:2px;}
.card .e {color:#5b6573; font-size:0.83rem; line-height:1.45; margin-top:2px;}
@media (max-width: 900px) {.cards {grid-template-columns:repeat(2, 1fr);}}
.foot {color:#8a93a0; font-size:0.8rem; margin-top:-4px;}
</style>
""", unsafe_allow_html=True)


def section(no, title, sub=None):
    st.markdown(f'<div class="sec"><span class="no">{no}</span><span class="tt">{title}</span></div>'
                + (f'<p class="sec-sub">{sub}</p>' if sub else ""), unsafe_allow_html=True)


def bar_title(text):
    st.markdown(f'<div class="bar-title"><span class="chip">조건</span>{text}</div>', unsafe_allow_html=True)


# ---------------- 머리말: 정류장 표지판 ----------------
BUS_SVG = """<svg width="66" height="66" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<rect x="8" y="6" width="48" height="44" rx="9" fill="#fff"/><rect x="13" y="13" width="38" height="17" rx="3" fill="#1d3f7a"/>
<rect x="13" y="34" width="9" height="5" rx="2" fill="#ffc93c"/><rect x="42" y="34" width="9" height="5" rx="2" fill="#ffc93c"/>
<rect x="24" y="9" width="16" height="2.5" rx="1.2" fill="#1d3f7a"/><rect x="12" y="49" width="10" height="8" rx="3" fill="#fff"/>
<rect x="42" y="49" width="10" height="8" rx="3" fill="#fff"/></svg>"""
st.markdown(f"""
<div class="stop-sign"><div>{BUS_SVG}</div><div>
  <span class="num">서울 시내버스 · 2026년 10월</span>
  <h1>서울의 유령 버스 정류장</h1>
  <p class="sub">하루에 거의 아무도 타고 내리지 않는 정류장은 어디일까요? 그런 정류장을 <b>없애도 될까요?</b><br>
  이 대시보드는 없앨 정류장을 정해 주지 않아요. <b>현장을 먼저 살펴볼 정류장</b>을 고르는 데 써요.</p>
</div></div>
<div class="route-band"><span style="background:#3b6fc4"></span><span style="background:#5bb025"></span><span style="background:#f2b705"></span><span style="background:#e6443a"></span></div>
""", unsafe_allow_html=True)

# ---------------- 전체 조건 (모든 그래프와 전광판에 걸림) ----------------
GU_LIST = sorted(g for g in df["구"].unique() if g != "서울 밖")
with st.container(key="global_bar"):
    bar_title("모든 그래프에 같이 걸리는 조건")
    g1, g2, g3, g4 = st.columns([1, 1.2, 1.2, 1.2])
    basis = g1.selectbox("어느 날 기준?", ["전체", "평일", "주말"],
                         help="주말에는 10월 공휴일(10/3, 10/5 대체공휴일, 10/9)도 들어 있어요.")
    ghost_max = g2.selectbox("유령 기준 (하루 승하차)", [5, 10, 20, 30, 50, 100], index=2,
                             format_func=lambda v: f"{v}명 이하")
    walk_max = g3.selectbox("대안이 가깝다 (걸어서)", [2, 3, 4, 5, 6], index=2,
                            format_func=lambda v: f"{v}분 이내 (약 {v * WALK_M_PER_MIN}m)")
    pick_gu = g4.selectbox("구", ["서울 전체"] + GU_LIST)

# 제외 기준은 ④ 탭에서 바꾼다. 위에서 먼저 계산해야 하므로 session_state에서 읽는다.
EXCLUDE = {"ex_end": ("제외_기종점", "기점·종점 빼기"), "ex_turn": ("제외_회차차고지", "회차지·차고지·종점 이름 빼기"),
           "ex_tmp": ("제외_임시", "임시 정류장 빼기"), "ex_out": ("제외_서울밖", "서울 밖(경기도 구간) 빼기")}
base = df.copy()
for key, (col, _) in EXCLUDE.items():
    if st.session_state.get(key, True):
        base = base[~base[col]]

# 기준일에 맞춘 이용량과 유령 여부
base["승차"], base["하차"] = base[f"{basis}_승차"], base[f"{basis}_하차"]
base["승하차"] = base["승차"] + base["하차"]
base["평일승하차"] = base["평일_승차"] + base["평일_하차"]
base["주말승하차"] = base["주말_승차"] + base["주말_하차"]
base["유령"] = base["승하차"] <= ghost_max
base["대안가까움"] = base["걷는시간_분"] <= walk_max

# 유형: 평일과 주말을 따로 본다
wd_g, we_g = base["평일승하차"] <= ghost_max, base["주말승하차"] <= ghost_max
base["유형"] = None
base.loc[wd_g & we_g & base["대안가까움"], "유형"] = TYPE_ORDER[0]
base.loc[wd_g & we_g & ~base["대안가까움"], "유형"] = TYPE_ORDER[1]
base.loc[~wd_g & we_g, "유형"] = TYPE_ORDER[2]
base.loc[wd_g & ~we_g, "유형"] = TYPE_ORDER[3]

d = base if pick_gu == "서울 전체" else base[base["구"] == pick_gu]
ghosts = d[d["유령"]]
n_all, n_ghost = len(d), len(ghosts)
n_cand = int(ghosts["대안가까움"].sum())
n_keep = n_ghost - n_cand
where = "서울" if pick_gu == "서울 전체" else pick_gu

# ---------------- 전광판 + 흐르는 글자 ----------------
pct = f"{n_ghost / n_all * 100:.1f}" if n_all else "0"
st.markdown(f"""
<div class="led-board" role="group" aria-label="지금 조건의 요약 숫자">
  <div class="led-cell"><div class="led-label">{where} 정류장</div><div class="led-value">{n_all:,}<small>곳</small></div><div class="led-foot">기준: {basis} · 2026년 10월</div></div>
  <div class="led-cell"><div class="led-label">유령 정류장</div><div class="led-value">{n_ghost:,}<small>곳</small></div><div class="led-foot">하루 {ghost_max}명 이하 · 전체의 {pct}%</div></div>
  <div class="led-cell"><div class="led-label">정리 검토 후보</div><div class="led-value blue">{n_cand:,}<small>곳</small></div><div class="led-foot">걸어서 {walk_max}분 안에 대안 있음</div></div>
  <div class="led-cell"><div class="led-label">지켜야 할 유령</div><div class="led-value orange">{n_keep:,}<small>곳</small></div><div class="led-foot">대안까지 {walk_max}분 넘게 걸림</div></div>
</div>""", unsafe_allow_html=True)
low5 = d.nsmallest(5, "승하차")
items = " &nbsp;·&nbsp; ".join(f"<b>{r.정류소명}</b>({r.구}) 하루 {r.승하차:.1f}명" for r in low5.itertuples())
st.markdown(f'<div class="ticker"><span class="run">이번 정류장은 … 아무도 기다리지 않는 정류장입니다 ▶ {items}</span></div>',
            unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["어디에 있나", "왜 비었을까", "없애도 될까", "데이터는 이렇게"])

# ======================= 탭 1: 어디에 있나 =======================
with tab1:
    # ---- 그래프 1: 지도 ----
    section("01", f"{where} 정류장 {n_all:,}곳 중 {n_ghost:,}곳은 하루 {ghost_max}명도 안 탄다",
            "회색 점은 모든 정류장, 파란 점은 유령 정류장이에요. 점에 마우스를 올리면 이름과 이용객 수가 나와요.")
    with st.container(key="chart_bar_map"):
        bar_title("이 지도에만 걸리는 조건")
        m1, m2, _ = st.columns([1, 1, 2])
        show_all = m1.toggle("일반 정류장도 회색으로 보기", True)
        dot = m2.selectbox("유령 점 크기", ["보통", "크게"], index=1)
    fig = go.Figure()
    if show_all:
        others = d[~d["유령"]]
        fig.add_trace(go.Scattermap(lat=others["Y좌표"], lon=others["X좌표"], mode="markers", name="일반 정류장",
                                    marker=dict(size=4, color=GRAY, opacity=0.55), hoverinfo="skip"))
    fig.add_trace(go.Scattermap(
        lat=ghosts["Y좌표"], lon=ghosts["X좌표"], mode="markers", name=f"유령 정류장 (하루 {ghost_max}명 이하)",
        marker=dict(size=11 if dot == "크게" else 8, color=BLUE),
        customdata=ghosts[["정류소명", "구", "승하차", "걷는시간_분"]].values,
        hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>하루 %{customdata[2]:.1f}명<br>"
                      "대안 정류장까지 걸어서 %{customdata[3]:.1f}분<extra></extra>"))
    center = {"lat": d["Y좌표"].mean(), "lon": d["X좌표"].mean()} if n_all else {"lat": 37.56, "lon": 126.99}
    fig.update_layout(map=dict(style="white-bg", center=center, zoom=10 if pick_gu == "서울 전체" else 12,
                               layers=[{"source": GU, "type": "fill", "color": "#f3f5f9", "below": "traces"},
                                       {"source": GU, "type": "line", "color": "#9aa4b2", "line": {"width": 1}, "below": "traces"}]),
                      height=560, margin=dict(l=0, r=0, t=0, b=0), legend=dict(y=0.99, x=0.01, bgcolor="rgba(255,255,255,0.85)"))
    st.plotly_chart(fig, width="stretch", config=CHART_CFG)

    # ---- 그래프 2: 구별 막대 ----
    gu = base.groupby("구").agg(전체=("유령", "size"), 유령=("유령", "sum")).drop("서울 밖", errors="ignore").reset_index()
    gu["비율"] = gu["유령"] / gu["전체"] * 100
    corr = gu["전체"].corr(gu["유령"]) if len(gu) > 2 else float("nan")
    top_ratio = gu.sort_values("비율", ascending=False).iloc[0]
    zero = gu[gu["유령"] == 0]["구"].tolist()
    section("02", "정류장이 많다고 유령도 많은 건 아니다",
            f"막대는 유령 정류장 수, 글자는 그 구의 전체 정류장 중 몇 곳인지예요. "
            f"정류장 수와 유령 수의 상관계수는 {corr:.2f}로 딱 비례하지는 않아요. "
            f"비율이 가장 높은 곳은 {top_ratio['구']}({top_ratio['비율']:.1f}%)"
            + (f", 유령이 한 곳도 없는 구는 {', '.join(zero)}예요." if zero else "예요."))
    with st.container(key="chart_bar_gu"):
        bar_title("이 그래프에만 걸리는 조건")
        s1, _ = st.columns([1, 3])
        sort_by = s1.selectbox("정렬", ["유령 정류장 많은 순", "유령 비율 높은 순", "전체 정류장 많은 순"])
    key = {"유령 정류장 많은 순": "유령", "유령 비율 높은 순": "비율", "전체 정류장 많은 순": "전체"}[sort_by]
    gu = gu.sort_values(key)
    colors = [NAVY if g == pick_gu else BLUE for g in gu["구"]]
    if pick_gu != "서울 전체":
        colors = [NAVY if g == pick_gu else "#9dc8f7" for g in gu["구"]]
    fig2 = go.Figure(go.Bar(
        x=gu["유령"], y=gu["구"], orientation="h", marker=dict(color=colors, line=dict(color="white", width=2)),
        text=[f"  전체 {t:,}곳 중 {g}곳 ({r:.1f}%)" for t, g, r in zip(gu["전체"], gu["유령"], gu["비율"])],
        textposition="outside", textfont=dict(size=12, color=MUTED), cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>유령 %{x}곳<extra></extra>", name="유령 정류장 수"))
    fig2.update_layout(height=max(420, 26 * len(gu)), xaxis=dict(title="유령 정류장 수 (곳)", range=[0, gu["유령"].max() * 1.6 + 1]),
                       yaxis=dict(title=None), showlegend=False)
    st.plotly_chart(fig2, width="stretch", config=CHART_CFG)
    if pick_gu != "서울 전체":
        st.markdown(f'<p class="foot">진한 막대가 고른 구({pick_gu})예요. 이 그래프는 비교를 위해 늘 서울 전체 구를 보여 줘요.</p>',
                    unsafe_allow_html=True)

# ======================= 탭 2: 왜 비었을까 =======================
with tab2:
    typed = d[d["유형"].notna()]
    cnt = typed["유형"].value_counts().reindex(TYPE_ORDER, fill_value=0)
    biggest = cnt.idxmax() if cnt.sum() else TYPE_ORDER[0]
    section("03", "유령 정류장이라고 다 같은 유령은 아니다",
            f"평일과 주말을 따로 보면 이유가 보여요. 평일 또는 주말 하루 {ghost_max}명 이하인 정류장 {int(cnt.sum()):,}곳 중 "
            f"가장 많은 유형은 <b>{biggest}</b>({cnt[biggest]:,}곳)이에요.")

    def example(t):
        x = typed[typed["유형"] == t]
        if x.empty:
            return "해당 정류장 없음"
        if t == TYPE_ORDER[2]:
            r = x.loc[x["평일승하차"].idxmax()]
            return f"예: {r.정류소명}({r.구})<br>평일 {r.평일승하차:.0f}명 · 주말 {r.주말승하차:.0f}명"
        if t == TYPE_ORDER[3]:
            r = x.loc[x["주말승하차"].idxmax()]
            return f"예: {r.정류소명}({r.구})<br>평일 {r.평일승하차:.0f}명 · 주말 {r.주말승하차:.0f}명"
        if t == TYPE_ORDER[0]:
            r = x.loc[x["앞뒤최소거리_m"].idxmin()]
            return f"예: {r.정류소명}({r.구})<br>{r.앞뒤최소거리_m:.0f}m 옆에 같은 노선 정류장"
        r = x.loc[x["앞뒤최소거리_m"].idxmax()]
        return f"예: {r.정류소명}({r.구})<br>대안까지 걸어서 {r.걷는시간_분:.0f}분"

    DESC = {TYPE_ORDER[0]: "평일·주말 모두 비고, 걸어서 몇 분 안에 같은 노선 정류장이 있어요.",
            TYPE_ORDER[1]: "평일·주말 모두 비지만, 없어지면 한참 걸어야 해요.",
            TYPE_ORDER[2]: "평일엔 사람이 있어요. 회사·학교 앞처럼 쓰임새가 분명한 곳이에요.",
            TYPE_ORDER[3]: "주말엔 사람이 있어요. 공원·산·경기장 입구 같은 곳이에요."}
    cards = "".join(f'<div class="card" style="--c:{TYPE_COLOR[t]}"><div class="t">{t}</div>'
                    f'<div class="n">{cnt[t]:,}<small>곳</small></div><div class="e">{DESC[t]}</div>'
                    f'<div class="e" style="margin-top:6px;color:#1f2733">{example(t)}</div></div>' for t in TYPE_ORDER)
    st.markdown(f'<div class="cards">{cards}</div>', unsafe_allow_html=True)

    fig3 = go.Figure(go.Bar(
        x=cnt.values, y=cnt.index, orientation="h",
        marker=dict(color=[TYPE_COLOR[t] for t in cnt.index], line=dict(color="white", width=2)),
        text=[f"  {v:,}곳" for v in cnt.values], textposition="outside", textfont=dict(color=INK, size=13), cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>%{x}곳<extra></extra>"))
    fig3.update_layout(height=260, yaxis=dict(autorange="reversed", title=None),
                       xaxis=dict(title="정류장 수 (곳)", range=[0, max(1, cnt.max()) * 1.18]), showlegend=False)
    st.plotly_chart(fig3, width="stretch", config=CHART_CFG)

    with st.container(key="chart_bar_type"):
        bar_title("아래 목록에만 걸리는 조건")
        t1, _ = st.columns([1.3, 2.7])
        pick_type = t1.selectbox("어떤 유형의 정류장을 볼까?", TYPE_ORDER, index=2)
    lst = typed[typed["유형"] == pick_type].copy()
    sort_col = {TYPE_ORDER[0]: ("앞뒤최소거리_m", True), TYPE_ORDER[1]: ("앞뒤최소거리_m", False),
                TYPE_ORDER[2]: ("평일승하차", False), TYPE_ORDER[3]: ("주말승하차", False)}[pick_type]
    lst = lst.sort_values(sort_col[0], ascending=sort_col[1])
    st.dataframe(lst[["정류소명", "구", "평일승하차", "주말승하차", "걷는시간_분", "노선수"]].rename(columns={
        "정류소명": "정류장", "평일승하차": "평일 하루 승하차", "주말승하차": "주말 하루 승하차",
        "걷는시간_분": "대안까지 걷는 시간(분)", "노선수": "노선 수"}).round(1),
        hide_index=True, width="stretch", height=300)

# ======================= 탭 3: 없애도 될까 =======================
with tab3:
    walk = ghosts["걷는시간_분"].dropna()
    edges = [0, 1, 2, 3, 4, 5, 6, 8, 10_000]
    labels = ["1분 이내", "1~2분", "2~3분", "3~4분", "4~5분", "5~6분", "6~8분", "8분 넘음"]
    binned = pd.cut(walk, edges, labels=labels, include_lowest=True).value_counts().reindex(labels, fill_value=0)
    upper = [edges[i + 1] for i in range(len(labels))]
    in_near = int(sum(v for v, u in zip(binned.values, upper) if u <= walk_max))
    section("04", f"유령 정류장 {len(walk):,}곳 중 {in_near:,}곳은 걸어서 {walk_max}분 안에 같은 버스를 탈 수 있다",
            f"정류장이 없어지면 같은 노선의 앞 또는 뒤 정류장까지 걸어가야 해요. 그 거리를 분당 {WALK_M_PER_MIN}m로 걸었을 때의 시간이에요. "
            f"파랑은 {walk_max}분 이내(정리 검토 후보), 주황은 {walk_max}분 넘게 걸리는 곳(지켜야 할 유령)이에요.")
    with st.container(key="chart_bar_walk"):
        bar_title("이 그래프에만 걸리는 조건")
        w1, _ = st.columns([1.3, 2.7])
        show_names = w1.toggle("막대 위에 정류장 수 보기", True)
    bar_colors = [BLUE if u <= walk_max else ORANGE for u in upper]
    fig4 = go.Figure(go.Bar(
        x=labels, y=binned.values, marker=dict(color=bar_colors, line=dict(color="white", width=2)),
        text=[f"{v:,}곳" for v in binned.values] if show_names else None, textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>%{y}곳<extra></extra>"))
    fig4.add_trace(go.Bar(x=[None], y=[None], marker_color=BLUE, name=f"정리 검토 후보 ({walk_max}분 이내)"))
    fig4.add_trace(go.Bar(x=[None], y=[None], marker_color=ORANGE, name=f"지켜야 할 유령 ({walk_max}분 넘음)"))
    fig4.data[0].showlegend = False
    fig4.update_layout(height=400, xaxis=dict(title="대안 정류장까지 걷는 시간", type="category"),
                       yaxis=dict(title="유령 정류장 수 (곳)", range=[0, max(1, binned.max()) * 1.2]), bargap=0.25)
    st.plotly_chart(fig4, width="stretch", config=CHART_CFG)

    # ---- 확인: 유령 정류장은 정말 더 붙어 있나 ----
    others = d[~d["유령"]]
    if len(ghosts) and len(others):
        a = (ghosts["걷는시간_분"] <= walk_max).mean() * 100
        b = (others["걷는시간_분"] <= walk_max).mean() * 100
        section("05", "확인: 유령 정류장은 다른 정류장보다 대안과 더 가까이 붙어 있을까?",
                "서울 정류장은 원래 촘촘해요. 그래서 유령 정류장만 보지 않고 일반 정류장과 나란히 비교해요.")
        st.markdown(f"""<div class="announce"><div class="ic">📢</div><div>
<div class="hd">안내 말씀 드립니다</div>
<div>걸어서 {walk_max}분 안에 대안 정류장이 있는 비율은 유령 정류장 <span class="big">{a:.1f}%</span>,
일반 정류장 <span class="big">{b:.1f}%</span>예요. 차이는 <b>{a - b:+.1f}%p</b>
(유령 {len(ghosts):,}곳, 일반 {len(others):,}곳).<br>
{"유령 정류장이 조금 더 촘촘하게 붙어 있어서, 정리해도 걷는 부담이 크지 않은 곳이 많아요." if a > b else
 "유령 정류장이 특별히 더 붙어 있지는 않아요. 정리하면 걷는 부담이 생길 수 있어요."}</div></div></div>""",
                    unsafe_allow_html=True)

# ======================= 탭 4: 데이터는 이렇게 =======================
with tab4:
    section("06", "데이터는 이렇게 만들었다")
    st.markdown("""
**자료**
- 서울 열린데이터광장 **서울시 버스노선별 정류장별 승하차 인원 정보** (OA-12912), 2026년 10월. 10월 27일 자료가 없어 30일(평일 19일, 주말·공휴일 11일)
- 서울 열린데이터광장 **서울시 버스 노선 정보 조회** (OA-1095)의 노선별 정류소 정보 파일(2026.11.02 기준): 노선별 정류장 순서와 좌표
- 서울 자치구 경계: 통계청 2013 경계(github.com/southkorea/seoul-maps)

**만든 순서**
1. 한 정류장에 여러 노선이 서서, 날짜와 정류장(표준버스정류장ID = NODE_ID)으로 승하차를 합쳤다. 승하차 줄의 99.6%가 노선 정보와 짝을 찾았다.
2. 아무도 안 탄 날은 기록이 없어서 0으로 채운 뒤 하루 평균을 냈다.
3. 버스가 지나가기만 하는 '(가상)' 경로점 112개를 뺐다. 빼지 않으면 유령 1~10위가 모두 '마포대교(가상)' 같은 점이었다.
4. 노선마다 정류장 순서대로 앞뒤 정류장까지 직선거리를 구하고, 노선이 여러 개면 가장 짧은 값을 썼다. 이 거리를 분당 80m로 나눠 걷는 시간으로 바꿨다.
5. 기점·종점, 회차지·차고지, 임시 정류장, 서울 밖 구간은 기본으로 뺐다(아래에서 바꿀 수 있음).

**한계**
- 내릴 때 카드를 찍지 않는 사람이 있어 하차는 실제보다 적게 잡힐 수 있다.
- 거리는 직선거리라 실제로 걷는 길은 더 길 수 있다.
- 이용이 적어도 병원, 복지관, 학교 앞처럼 꼭 필요한 정류장일 수 있다. 그래서 결론은 '없앨 정류장'이 아니라 '먼저 살펴볼 정류장'이다.
- 한 달(2026년 10월) 자료라 계절에 따라 달라질 수 있다.
""")
    with st.container(key="chart_bar_exclude"):
        bar_title("제외 기준 (바꾸면 모든 그래프가 다시 계산돼요)")
        cols = st.columns(4)
        for c, (k, (_, label)) in zip(cols, EXCLUDE.items()):
            c.checkbox(label, value=st.session_state.get(k, True), key=k)

    with st.expander("자세히 보기: 정류장 전체 산점도 (이용객 수 × 대안까지 걷는 시간)"):
        sc = d[d["걷는시간_분"].notna()].copy()
        sc["표시"] = sc["승하차"].clip(lower=0.1)
        sc["그룹"] = sc["유령"].map({True: "유령 정류장", False: "일반 정류장"})
        fig5 = px.scatter(sc.sort_values("유령"), x="표시", y="걷는시간_분", color="그룹", log_x=True,
                          color_discrete_map={"유령 정류장": BLUE, "일반 정류장": GRAY}, hover_name="정류소명",
                          labels={"표시": f"하루 평균 승하차 (명, {basis}, 로그 눈금)", "걷는시간_분": "대안까지 걷는 시간 (분)"},
                          height=460)
        fig5.update_traces(marker=dict(size=6, opacity=0.7))
        fig5.add_vline(x=ghost_max, line_dash="dash", line_color=MUTED)
        fig5.add_hline(y=walk_max, line_dash="dash", line_color=MUTED)
        fig5.update_layout(yaxis=dict(range=[0, 15]),
                           xaxis=dict(range=[-1, math.log10(max(10, sc["표시"].max() * 1.5))]))
        st.plotly_chart(fig5, width="stretch", config=CHART_CFG)
        st.caption("가로축은 0.1, 1, 10, 100처럼 열 배씩 늘어나는 눈금이에요. 걷는 시간 15분이 넘는 몇 곳은 화면 위로 잘려요.")

    section("07", "지금 조건의 정류장 표")
    out = d[["정류소명", "ARS_ID", "구", "승차", "하차", "승하차", "걷는시간_분", "노선수", "유형"]].sort_values("승하차")
    st.dataframe(out.round(1), hide_index=True, width="stretch", height=380)
    st.download_button("이 표를 CSV로 받기", out.to_csv(index=False).encode("utf-8-sig"),
                       file_name="ghost_stops_filtered.csv", mime="text/csv")
