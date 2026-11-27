"""
서울의 유령 버스 정류장 대시보드
실행: streamlit run app.py
필요 파일: stops_summary.csv (prep.py로 만든 정리 표)
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import streamlit as st

st.set_page_config(page_title="서울의 유령 버스 정류장", layout="wide")

# 색: 유령 두 종류만 색을 쓰고 나머지는 회색으로 둔다(산점도·지도에서 색은 3개까지만)
COLOR = {
    "정리 검토 후보": "#257de0",   # 유령 + 같은 노선 이웃 정류장이 가까움
    "지켜야 할 유령": "#f47230",   # 유령 + 이웃 정류장이 멂
    "일반 정류장": "#c4c4c4",
}
ORDER = list(COLOR.keys())


@st.cache_data
def load():
    df = pd.read_csv("stops_summary.csv", dtype={"NODE_ID": str, "ARS_ID": str})
    df["ARS_ID"] = df["ARS_ID"].str.zfill(5)
    return df


df = load()


@st.cache_data
def load_gu():
    with open("seoul_gu.geojson", encoding="utf-8") as f:
        return json.load(f)


GU = load_gu()

# ---------------- 사이드바: 조건 ----------------
st.sidebar.header("조건 바꾸기")
basis = st.sidebar.radio("어느 날 기준으로 볼까?", ["전체", "평일", "주말"], horizontal=True,
                         help="주말에는 10월 공휴일(10/3, 10/5, 10/9)도 들어 있어요.")
ghost_max = st.sidebar.slider("유령 기준: 하루 승하차가 몇 명 이하면 유령?", 1, 100, 20, step=1)
near_m = st.sidebar.slider("가깝다 기준: 같은 노선 앞뒤 정류장이 몇 m 안에 있으면?", 100, 600, 300, step=50)
gus = sorted(df["구"].unique().tolist())
gus = [g for g in gus if g != "서울 밖"]
pick_gu = st.sidebar.multiselect("구 고르기 (비우면 서울 전체)", gus)

with st.sidebar.expander("제외 기준 (기본: 모두 제외)"):
    ex_end = st.checkbox("기점·종점 빼기", True)
    ex_turn = st.checkbox("회차지·차고지·종점 이름 빼기", True)
    ex_tmp = st.checkbox("임시 정류장 빼기", True)
    ex_out = st.checkbox("서울 밖(경기도 구간) 빼기", True)

# ---------------- 계산 ----------------
d = df.copy()
mask = pd.Series(False, index=d.index)
if ex_end:
    mask |= d["제외_기종점"]
if ex_turn:
    mask |= d["제외_회차차고지"]
if ex_tmp:
    mask |= d["제외_임시"]
if ex_out:
    mask |= d["제외_서울밖"]
d = d[~mask]
if pick_gu:
    d = d[d["구"].isin(pick_gu)]

d["승차"] = d[f"{basis}_승차"]
d["하차"] = d[f"{basis}_하차"]
d["승하차"] = d["승차"] + d["하차"]
d["유령"] = d["승하차"] <= ghost_max
d["가까움"] = d["앞뒤최소거리_m"] <= near_m
d["분류"] = "일반 정류장"
d.loc[d["유령"] & d["가까움"], "분류"] = "정리 검토 후보"
d.loc[d["유령"] & ~d["가까움"], "분류"] = "지켜야 할 유령"

n_all = len(d)
n_ghost = int(d["유령"].sum())
n_cand = int((d["분류"] == "정리 검토 후보").sum())
n_keep = int((d["분류"] == "지켜야 할 유령").sum())

# ---------------- 머리말 ----------------
st.title("서울의 유령 버스 정류장")
st.markdown(
    "하루에 거의 아무도 타고 내리지 않는 정류장은 어디일까요? 그리고 그런 정류장을 **없애도 될까요?**  \n"
    "이 대시보드는 정류장을 없애라는 답을 주지 않아요. **현장을 먼저 살펴볼 정류장**을 고르는 데 쓰려고 만들었어요."
)
st.caption(f"자료: 서울시 버스노선별 정류장별 승하차 인원(2026년 10월, 10/27 누락으로 30일), "
           f"서울시 버스노선별 정류소 정보(2026.11.02 기준) · 기준: {basis}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("분석한 정류장", f"{n_all:,}개")
c2.metric(f"유령 정류장 (하루 {ghost_max}명 이하)", f"{n_ghost:,}개",
          help=f"분석한 정류장의 {n_ghost / n_all * 100:.1f}%" if n_all else None)
c3.metric(f"정리 검토 후보 ({near_m}m 안 대안 있음)", f"{n_cand:,}개")
c4.metric("지켜야 할 유령 (대안이 멂)", f"{n_keep:,}개")

tab1, tab2, tab3, tab4 = st.tabs(["① 유령 정류장은 어디에", "② 없애도 될까?", "③ 평일과 주말", "④ 데이터는 이렇게 만들었다"])

# ---------------- ① 지도 + 구별 막대 ----------------
with tab1:
    left, right = st.columns([3, 2])
    with left:
        st.subheader("지도")
        show_all = st.checkbox("일반 정류장도 회색으로 같이 보기", False)
        m = d if show_all else d[d["유령"]]
        m = m.sort_values("분류", key=lambda s: s.map({"일반 정류장": 0, "정리 검토 후보": 1, "지켜야 할 유령": 2}))
        fig = px.scatter_map(
            m, lat="Y좌표", lon="X좌표", color="분류", color_discrete_map=COLOR,
            category_orders={"분류": ORDER},
            hover_name="정류소명",
            hover_data={"구": True, "승차": ":.1f", "하차": ":.1f", "앞뒤최소거리_m": ":.0f",
                        "노선수": True, "ARS_ID": True, "X좌표": False, "Y좌표": False, "분류": False},
            labels={"승차": "하루 평균 승차", "하차": "하루 평균 하차", "앞뒤최소거리_m": "앞뒤 정류장까지(m)",
                    "노선수": "노선 수", "ARS_ID": "정류장 번호"},
            zoom=10, height=560, map_style="white-bg",
            center={"lat": 37.5636, "lon": 126.99},
        )
        fig.update_traces(marker=dict(size=9))
        # 바탕 지도 타일 대신 구 경계선만 그린다(외부 지도 서버 없이도 보이게)
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=1.02, title=None),
                          map_layers=[{"source": GU, "type": "fill", "color": "#f4f4f4", "below": "traces"},
                                      {"source": GU, "type": "line", "color": "#9c9c9c", "line": {"width": 1}, "below": "traces"}])
        st.plotly_chart(fig, width="stretch")
    with right:
        st.subheader("구별 유령 정류장 수")
        g = d[d["유령"]].groupby(["구", "분류"]).size().reset_index(name="정류장 수")
        tot = g.groupby("구")["정류장 수"].sum().sort_values()
        fig2 = px.bar(g, x="정류장 수", y="구", color="분류", orientation="h",
                      color_discrete_map=COLOR, category_orders={"분류": ORDER, "구": tot.index.tolist()},
                      height=560)
        fig2.update_traces(marker_line_color="white", marker_line_width=2)
        fig2.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=1.02, title=None),
                           yaxis_title=None, xaxis=dict(gridcolor="#eeeeee"), plot_bgcolor="white")
        st.plotly_chart(fig2, width="stretch")

# ---------------- ② 네 칸 산점도 + 확인 장면 ----------------
with tab2:
    st.subheader("이용은 얼마나 하나 × 대신 탈 정류장은 얼마나 가까운가")
    st.markdown("왼쪽(이용 적음)에 있으면서 아래(이웃 정류장이 가까움)에 있으면 **정리 검토 후보**, "
                "왼쪽 위(이웃이 멂)는 **지켜야 할 유령**이에요.")
    sc = d[d["앞뒤최소거리_m"].notna()].copy()
    sc["승하차_표시"] = sc["승하차"].clip(lower=0.1)
    fig3 = px.scatter(
        sc.sort_values("분류", key=lambda s: s.map({"일반 정류장": 0, "정리 검토 후보": 1, "지켜야 할 유령": 2})),
        x="승하차_표시", y="앞뒤최소거리_m", color="분류", color_discrete_map=COLOR,
        category_orders={"분류": ORDER}, log_x=True, hover_name="정류소명",
        hover_data={"구": True, "승하차": ":.1f", "앞뒤최소거리_m": ":.0f", "승하차_표시": False, "분류": False},
        labels={"승하차_표시": f"하루 평균 승하차 (명, {basis}, 로그 눈금)", "앞뒤최소거리_m": "같은 노선 앞뒤 정류장까지 가장 짧은 거리 (m)",
                "승하차": "하루 평균 승하차"},
        height=520,
    )
    fig3.update_traces(marker=dict(size=8, opacity=0.75, line=dict(color="white", width=1)))
    fig3.add_vline(x=ghost_max, line_dash="dash", line_color="#666666",
                   annotation_text=f"유령 기준 {ghost_max}명", annotation_position="top")
    fig3.add_hline(y=near_m, line_dash="dash", line_color="#666666",
                   annotation_text=f"가깝다 기준 {near_m}m", annotation_position="right")
    fig3.update_layout(plot_bgcolor="white", legend=dict(orientation="h", y=1.05, title=None),
                       xaxis=dict(gridcolor="#eeeeee"), yaxis=dict(gridcolor="#eeeeee", range=[0, min(1500, sc["앞뒤최소거리_m"].max() + 50)]),
                       margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig3, width="stretch")
    st.caption("앞뒤 거리가 1,500m를 넘는 정류장 몇 곳은 화면 위로 잘려요. 표(④ 탭)에서 볼 수 있어요.")

    st.subheader("확인: 유령 정류장은 이웃 정류장과 더 가까이 붙어 있을까?")
    st.markdown("서울 정류장은 원래 촘촘해요. 그래서 유령 정류장만 보지 않고 **일반 정류장과 나란히** 비교해요.")
    bins = [0, 100, 200, 300, 400, 500, 10_000]
    labels = ["100m 이하", "100~200m", "200~300m", "300~400m", "400~500m", "500m 초과"]
    sc["거리 구간"] = pd.cut(sc["앞뒤최소거리_m"], bins=bins, labels=labels, include_lowest=True)
    sc["그룹"] = sc["유령"].map({True: "유령 정류장", False: "일반 정류장"})
    share = (sc.groupby(["그룹", "거리 구간"], observed=False).size()
             .groupby(level=0).transform(lambda s: s / s.sum() * 100).reset_index(name="비율(%)"))
    fig4 = px.bar(share, x="거리 구간", y="비율(%)", color="그룹", barmode="group",
                  color_discrete_map={"유령 정류장": "#257de0", "일반 정류장": "#9c9c9c"},
                  category_orders={"거리 구간": labels, "그룹": ["유령 정류장", "일반 정류장"]}, height=380)
    fig4.update_traces(marker_line_color="white", marker_line_width=2, hovertemplate="%{x}<br>%{y:.1f}%")
    fig4.update_layout(plot_bgcolor="white", yaxis=dict(gridcolor="#eeeeee"), legend=dict(orientation="h", y=1.08, title=None),
                       xaxis_title="같은 노선 앞뒤 정류장까지 가장 짧은 거리", margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig4, width="stretch")

    gh = sc[sc["유령"]]
    ot = sc[~sc["유령"]]
    if len(gh) and len(ot):
        a = (gh["앞뒤최소거리_m"] <= near_m).mean() * 100
        b = (ot["앞뒤최소거리_m"] <= near_m).mean() * 100
        st.info(f"**{near_m}m 안에 대신 탈 정류장이 있는 비율**: 유령 정류장 {a:.1f}% vs 일반 정류장 {b:.1f}% "
                f"(차이 {a - b:+.1f}%p, 유령 {len(gh):,}개 / 일반 {len(ot):,}개)")

# ---------------- ③ 평일과 주말 ----------------
with tab3:
    st.subheader("평일에만 유령일까, 주말에만 유령일까?")
    st.markdown("같은 정류장이라도 평일과 주말 쓰임새가 달라요. 학교나 회사 앞은 주말에 비고, 공원이나 산 입구는 평일에 비어요.")
    w = d.copy()
    w["평일유령"] = (w["평일_승차"] + w["평일_하차"]) <= ghost_max
    w["주말유령"] = (w["주말_승차"] + w["주말_하차"]) <= ghost_max
    w["유형"] = "유령 아님"
    w.loc[w["평일유령"] & w["주말유령"], "유형"] = "평일·주말 모두 유령"
    w.loc[w["평일유령"] & ~w["주말유령"], "유형"] = "평일에만 유령"
    w.loc[~w["평일유령"] & w["주말유령"], "유형"] = "주말에만 유령"
    cnt = w[w["유형"] != "유령 아님"]["유형"].value_counts().reindex(
        ["평일·주말 모두 유령", "주말에만 유령", "평일에만 유령"], fill_value=0).reset_index()
    cnt.columns = ["유형", "정류장 수"]
    col_a, col_b = st.columns([2, 3])
    with col_a:
        fig5 = px.bar(cnt, x="정류장 수", y="유형", orientation="h", height=260,
                      color_discrete_sequence=["#257de0"], text="정류장 수")
        fig5.update_traces(marker_line_color="white", marker_line_width=2, textposition="outside")
        fig5.update_layout(plot_bgcolor="white", yaxis_title=None,
                           xaxis=dict(gridcolor="#eeeeee", range=[0, max(1, cnt["정류장 수"].max()) * 1.2]),
                           margin=dict(l=0, r=30, t=10, b=0))
        st.plotly_chart(fig5, width="stretch")
    with col_b:
        typ = st.radio("어떤 정류장을 볼까?", ["주말에만 유령", "평일에만 유령"], horizontal=True)
        show = w[w["유형"] == typ].copy()
        show["평일 승하차"] = show["평일_승차"] + show["평일_하차"]
        show["주말 승하차"] = show["주말_승차"] + show["주말_하차"]
        st.dataframe(show.sort_values("평일 승하차" if typ == "주말에만 유령" else "주말 승하차", ascending=False)
                     [["정류소명", "구", "평일 승하차", "주말 승하차", "노선수"]].head(15).round(1),
                     hide_index=True, width="stretch")

# ---------------- ④ 데이터 설명 ----------------
with tab4:
    st.subheader("데이터는 이렇게 만들었다")
    st.markdown(f"""
**자료**
- 서울 열린데이터광장 **서울시 버스노선별 정류장별 승하차 인원 정보** (OA-12912), 2026년 10월. 10월 27일 자료가 없어 30일(평일 19일, 주말·공휴일 11일)
- 서울 열린데이터광장 **서울시 버스 노선 정보 조회** (OA-1095)의 노선별 정류소 정보 파일(2026.11.02 기준): 노선별 정류장 순서와 좌표
- 서울 자치구 경계: 통계청 2013 경계(github.com/southkorea/seoul-maps)

**만든 순서**
1. 한 정류장에 여러 노선이 서서, 날짜와 정류장(표준버스정류장ID = NODE_ID)으로 승하차를 합쳤다. 승하차 줄의 99.6%가 노선 정보와 짝을 찾았다.
2. 아무도 안 탄 날은 기록이 없어서 0으로 채운 뒤 하루 평균을 냈다.
3. 버스가 지나가기만 하는 '(가상)' 경로점 112개를 뺐다. 빼지 않으면 유령 1~10위가 모두 '마포대교(가상)' 같은 점이었다.
4. 노선마다 정류장 순서대로 앞뒤 정류장까지 거리를 구하고, 노선이 여러 개면 가장 짧은 값을 썼다. = "이 정류장이 없어지면 같은 버스를 타러 최소 몇 m 걸어야 하나"
5. 기점·종점, 회차지·차고지, 임시 정류장, 서울 밖 구간은 표시해 두고 기본으로 뺐다(사이드바에서 켜고 끌 수 있음).

**한계**
- 내릴 때 카드를 찍지 않는 사람이 있어 하차는 실제보다 적게 잡힐 수 있다.
- 거리는 직선거리다. 실제로 걷는 길은 더 길 수 있다.
- 이용이 적어도 병원, 복지관, 학교 앞처럼 꼭 필요한 정류장일 수 있다. 그래서 결론은 '없앨 정류장'이 아니라 '먼저 살펴볼 정류장'이다.
- 한 달(2026년 10월) 자료라 계절에 따라 달라질 수 있다.
""")
    st.subheader("지금 조건의 정류장 표")
    out = d[["정류소명", "ARS_ID", "구", "분류", "승차", "하차", "승하차", "앞뒤최소거리_m", "노선수"]].sort_values("승하차")
    st.dataframe(out.round(1), hide_index=True, width="stretch", height=400)
    st.download_button("이 표를 CSV로 받기", out.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                       file_name="ghost_stops_filtered.csv", mime="text/csv")
