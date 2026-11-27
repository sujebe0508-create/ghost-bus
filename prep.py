"""
2단계 전처리: 정류장 하나당 한 줄짜리 정리 표(stops_summary.csv)를 만든다.

입력 (data 폴더)
  - BUS_STATION_BOARDING_MONTH_YYYYMM.csv : 서울시 버스노선별 정류장별 승하차 인원 (OA-12912)
  - route_stops.xlsx                    : 서울시 버스노선별 정류소 정보 (OA-1095), 순번과 좌표 포함
  - seoul_gu.geojson                    : 서울 자치구 경계 (통계청 2013, github.com/southkorea/seoul-maps)

출력
  - stops_summary.csv : 정류장별 하루 평균 승하차, 같은 노선 앞뒤 정류장까지 거리, 구, 제외 표시

사용법
  python prep.py data/BUS_STATION_BOARDING_MONTH_202610.csv data/route_stops.xlsx data/seoul_gu.geojson
"""
import sys
import json
import numpy as np
import pandas as pd

# 2026년 10월 공휴일: 개천절(10/3), 대체공휴일(10/5), 한글날(10/9). 공휴일은 주말로 친다.
HOLIDAYS = {"20261003", "20261005", "20261009"}


def haversine_m(lat1, lon1, lat2, lon2):
    """위경도 두 점 사이 거리(m)."""
    r = 6371000
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def load_boarding(path):
    b = pd.read_csv(path, encoding="cp949",
                    dtype={"표준버스정류장ID": str, "버스정류장ARS번호": str, "노선번호": str, "사용일자": str})
    b["승차"] = pd.to_numeric(b["승차총승객수"], errors="coerce").fillna(0)
    b["하차"] = pd.to_numeric(b["하차총승객수"], errors="coerce").fillna(0)
    return b


def daily_average(b):
    """정류장별로 하루 승차·하차를 구한다.
    한 정류장에 여러 노선이 서므로 먼저 (날짜, 정류장)으로 합친다.
    아무도 안 탄 날은 기록이 없으므로 0으로 채운 뒤 평균을 낸다(채우지 않으면 평균이 부풀려진다)."""
    days = sorted(b["사용일자"].unique())
    daily = b.groupby(["표준버스정류장ID", "사용일자"])[["승차", "하차"]].sum()
    full_idx = pd.MultiIndex.from_product([daily.index.levels[0], days], names=daily.index.names)
    daily = daily.reindex(full_idx, fill_value=0).reset_index()

    dow = pd.to_datetime(daily["사용일자"]).dt.dayofweek
    daily["주말"] = (dow >= 5) | daily["사용일자"].isin(HOLIDAYS)

    out = daily.groupby("표준버스정류장ID").agg(전체_승차=("승차", "mean"), 전체_하차=("하차", "mean"))
    wk = daily[~daily["주말"]].groupby("표준버스정류장ID")[["승차", "하차"]].mean().add_prefix("평일_")
    we = daily[daily["주말"]].groupby("표준버스정류장ID")[["승차", "하차"]].mean().add_prefix("주말_")
    out = out.join(wk).join(we).round(1)
    out["전체_승하차"] = out["전체_승차"] + out["전체_하차"]

    info = {"분석일수": len(days), "평일수": int((~daily.drop_duplicates("사용일자")["주말"]).sum()),
            "주말·공휴일수": int(daily.drop_duplicates("사용일자")["주말"].sum())}
    return out, info


def neighbor_distance(r):
    """노선마다 순번대로 정렬해 앞 정류장, 뒤 정류장까지 거리를 구한다.
    한 정류장에 노선이 여러 개면 그중 가장 짧은 거리를 쓴다
    = '이 정류장이 없어지면 같은 버스를 타러 최소 몇 m 걸어야 하나'."""
    r = r.copy()
    # '(가상)' 정류장은 버스가 지나가기만 하는 경로 표시점이라 실제로 탈 수 없다.
    # 앞뒤 이웃 계산에서 빼야 '가장 가까운 진짜 정류장'까지 거리가 나온다.
    virtual = r["정류소명"].str.contains("가상", na=False)
    print(f"   '(가상)' 경로점 {r.loc[virtual, 'NODE_ID'].nunique()}개 제외")
    r = r[~virtual]
    r["순번"] = pd.to_numeric(r["순번"])
    r["X좌표"] = pd.to_numeric(r["X좌표"])
    r["Y좌표"] = pd.to_numeric(r["Y좌표"])
    r = r.sort_values(["ROUTE_ID", "순번"])
    g = r.groupby("ROUTE_ID")
    for side, shift in (("앞", 1), ("뒤", -1)):
        r[f"{side}_x"] = g["X좌표"].shift(shift)
        r[f"{side}_y"] = g["Y좌표"].shift(shift)
        r[f"{side}_거리"] = haversine_m(r["Y좌표"], r["X좌표"], r[f"{side}_y"], r[f"{side}_x"])
    # 같은 정류장이 연달아 나오는 경우(거리 0)는 이웃으로 치지 않는다
    for side in ("앞", "뒤"):
        r.loc[r[f"{side}_거리"] < 1, f"{side}_거리"] = np.nan
    r["이웃최소거리"] = r[["앞_거리", "뒤_거리"]].min(axis=1)

    # 노선의 처음·끝 순번 = 기점·종점
    first = g["순번"].transform("min")
    last = g["순번"].transform("max")
    r["기종점"] = (r["순번"] == first) | (r["순번"] == last)

    s = r.groupby("NODE_ID").agg(
        ARS_ID=("ARS_ID", "first"),
        정류소명=("정류소명", "first"),
        X좌표=("X좌표", "first"),
        Y좌표=("Y좌표", "first"),
        노선수=("ROUTE_ID", "nunique"),
        앞뒤최소거리_m=("이웃최소거리", "min"),
        기종점노선수=("기종점", "sum"),
    )
    s["앞뒤최소거리_m"] = s["앞뒤최소거리_m"].round(0)
    return s


def assign_gu(s, geojson_path):
    from shapely.geometry import shape, Point
    from shapely.strtree import STRtree
    with open(geojson_path, encoding="utf-8") as f:
        feats = json.load(f)["features"]
    polys = [shape(ft["geometry"]) for ft in feats]
    names = [ft["properties"]["name"] for ft in feats]
    tree = STRtree(polys)
    gu = []
    for x, y in zip(s["X좌표"], s["Y좌표"]):
        p = Point(x, y)
        hit = [i for i in tree.query(p) if polys[i].contains(p)]
        gu.append(names[hit[0]] if hit else "서울 밖")
    s["구"] = gu
    return s


def main(board_path, route_path, geo_path):
    print("1) 승하차 읽기")
    b = load_boarding(board_path)
    avg, info = daily_average(b)
    print(f"   정류장 {len(avg):,}개, {info}")

    print("2) 노선별 정류장 순서로 앞뒤 거리 계산")
    r = pd.read_excel(route_path, dtype=str)
    nb = neighbor_distance(r)
    print(f"   노선 {r['ROUTE_ID'].nunique():,}개, 정류장 {len(nb):,}개")

    print("3) 합치기 (표준버스정류장ID = NODE_ID)")
    s = nb.join(avg, how="inner")
    only_board = len(avg.index.difference(nb.index))
    print(f"   합쳐진 정류장 {len(s):,}개 / 승하차에만 있고 노선 정보에 없는 정류장 {only_board}개(제외)")

    print("4) 구 붙이기")
    s = assign_gu(s, geo_path)

    print("5) 제외 표시 (지우지 않고 표시만 해서 대시보드에서 켜고 끌 수 있게)")
    name = s["정류소명"].fillna("")
    s["제외_기종점"] = s["기종점노선수"] > 0
    s["제외_임시"] = name.str.contains("임시")
    s["제외_회차차고지"] = name.str.contains("회차|차고지|종점")
    s["제외_서울밖"] = s["구"] == "서울 밖"
    s["제외"] = s[["제외_기종점", "제외_임시", "제외_회차차고지", "제외_서울밖"]].any(axis=1)

    s = s.reset_index().rename(columns={"index": "NODE_ID"})
    s.to_csv("stops_summary.csv", index=False, encoding="utf-8-sig")

    kept = s[~s["제외"]]
    print("\n=== 결과 ===")
    print(f"전체 {len(s):,}개 중 제외 {s['제외'].sum():,}개 → 분석 대상 {len(kept):,}개")
    for c in ["제외_기종점", "제외_임시", "제외_회차차고지", "제외_서울밖"]:
        print(f"  {c}: {s[c].sum():,}개")
    print("\n분석 대상 하루 평균 승하차 분포:")
    print(kept["전체_승하차"].describe().round(1).to_string())
    print("\n앞뒤 정류장 최소 거리(m) 분포:")
    print(kept["앞뒤최소거리_m"].describe().round(0).to_string())
    print("\n저장: stops_summary.csv")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    main(*sys.argv[1:])
