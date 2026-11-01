"""optimize_route.py — 지점 할당과 경로 개선을 위한 경량 최적화 도구.

특정 소재를 모르는 범용 유틸이다.
다루는 추상 개념은 점(node)·비용(cost)·출발지(depot)·정원(capacity) 뿐이라,
"지점들을 가까운 곳에 배정하고, 가장 짧게 돌아보는" 문제라면 어디든 쓴다.

두 가지 모드:
  (1) 할당(--match) : 좌표 두 그룹을 받아 하버사인 거리로 가장 가까운 짝을 찾는다.
                      (예: 지점→최근접 거점, 주문→최근접 센터, 작업자→최근접 구역)
  (2) 경로(--route) : 점 목록 + 점 사이 소요시간 행렬을 받아,
                      그리디(최근접 이웃) 초기 순서 → 2-opt 로 더 짧은 방문 순서를 만든다.
                      개선 전/후 총비용과 개선율을 함께 출력한다.

사용 예:
    python optimize_route.py --match homes.csv stops.csv --out assign.csv
    python optimize_route.py --route nodes.csv --matrix times.csv --depot D0

좌표 열은 이름으로 자동 감지한다(lat/latitude/위도, lon/lng/longitude/경도).
안 맞으면 --lat / --lon / --id 로 직접 지정한다.

소요시간 행렬(--matrix)은 'from,to,minutes' 형식의 엣지 목록을 기대한다
(열 이름이 달라도 앞 3개 열을 from,to,cost 로 해석한다).

표준 라이브러리만 사용한다(pandas 불필요).
"""

import argparse
import csv
import math
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ENCODINGS = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"]

LAT_HINTS = ("lat", "latitude", "위도")
LON_HINTS = ("lon", "lng", "longitude", "경도")


def read_rows(path):
    """CSV 를 dict 리스트로 인코딩 방어하며 읽는다."""
    last_err = None
    for enc in ENCODINGS:
        try:
            with open(path, encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                return list(reader), (reader.fieldnames or [])
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise last_err if last_err else RuntimeError("인코딩 판별 실패")


def pick_col(fields, hints, override=None):
    """힌트 단어를 포함하는 열 이름을 자동 감지한다(override 있으면 그것)."""
    if override:
        return override
    for f in fields:
        low = f.lower()
        if any(h in low for h in hints):
            return f
    return None


def pick_id(fields, override=None):
    if override:
        return override
    for f in fields:
        if "id" in f.lower():
            return f
    return fields[0] if fields else None


def haversine(lat1, lon1, lat2, lon2):
    """두 위경도 사이 거리(미터). 경도 왜곡을 보정한 정확한 지표 거리."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ----------------------------------------------------------------------------
# 할당 모드
# ----------------------------------------------------------------------------
def run_match(src_path, cand_path, out_path, max_dist, args):
    src, sf = read_rows(src_path)
    cand, cf = read_rows(cand_path)

    s_lat = pick_col(sf, LAT_HINTS, args.lat)
    s_lon = pick_col(sf, LON_HINTS, args.lon)
    c_lat = pick_col(cf, LAT_HINTS, args.lat)
    c_lon = pick_col(cf, LON_HINTS, args.lon)
    s_id = pick_id(sf, args.id)
    c_id = pick_id(cf, args.id)

    for name, col, path in [("좌표(lat)", s_lat, src_path), ("좌표(lon)", s_lon, src_path),
                            ("좌표(lat)", c_lat, cand_path), ("좌표(lon)", c_lon, cand_path)]:
        if not col:
            print(f"[입력 오류] '{path}' 에서 {name} 열을 못 찾았습니다. --lat/--lon 로 지정하세요.")
            print(f"  이 파일의 열: {sf if path == src_path else cf}")
            sys.exit(1)

    print(f"[할당] 대상={src_path} ({len(src):,}행, id={s_id}, 좌표={s_lat}/{s_lon})")
    print(f"       후보={cand_path} ({len(cand):,}행, id={c_id}, 좌표={c_lat}/{c_lon})")

    # 후보 좌표 미리 파싱
    cand_pts = []
    for c in cand:
        try:
            cand_pts.append((c[c_id], float(c[c_lat]), float(c[c_lon])))
        except (ValueError, TypeError):
            continue
    if not cand_pts:
        print("[입력 오류] 후보 파일에서 유효한 좌표를 읽지 못했습니다.")
        sys.exit(1)

    results = []
    bad = 0
    beyond = 0
    for s in src:
        try:
            la, lo = float(s[s_lat]), float(s[s_lon])
        except (ValueError, TypeError):
            bad += 1
            continue
        best_id, best_d = None, float("inf")
        for cid, cla, clo in cand_pts:
            d = haversine(la, lo, cla, clo)
            if d < best_d:
                best_id, best_d = cid, d
        if max_dist and best_d > max_dist:
            beyond += 1
        results.append((s[s_id], best_id, round(best_d, 1)))

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([s_id, "nearest_" + str(c_id), "distance_m"])
        w.writerows(results)

    print(f"✅ 최근접 할당 완료: {len(results):,}건")
    if bad:
        print(f"⚠ 좌표 불량으로 건너뜀: {bad}건")
    if max_dist:
        print(f"⚠ 거리 {max_dist:.0f}m 초과: {beyond}건 (도보 가능성 별도 검토)")
    print("미리보기(앞 5건):")
    for row in results[:5]:
        print(f"  {row[0]} → {row[1]}  ({row[2]}m)")
    print(f"→ 저장: {out_path}")


# ----------------------------------------------------------------------------
# 경로 모드
# ----------------------------------------------------------------------------
def load_matrix(path):
    """'from,to,minutes' 엣지 목록을 cost dict 로 읽는다(앞 3열 사용)."""
    rows, fields = read_rows(path)
    if len(fields) < 3:
        print(f"[입력 오류] 행렬 '{path}' 는 from,to,minutes 3개 열이 필요합니다. 열: {fields}")
        sys.exit(1)
    fcol, tcol, ccol = fields[0], fields[1], fields[2]
    cost = {}
    for r in rows:
        try:
            cost[(r[fcol], r[tcol])] = float(r[ccol])
        except (ValueError, TypeError):
            continue
    return cost, (fcol, tcol, ccol)


def make_cost_fn(cost):
    """양방향 보완 + 미싱 엣지 추적이 되는 비용 함수를 만든다."""
    missing = set()

    def c(a, b):
        if a == b:
            return 0.0
        if (a, b) in cost:
            return cost[(a, b)]
        if (b, a) in cost:
            return cost[(b, a)]
        missing.add((a, b))
        return 1e9  # 미싱: 사실상 금지(아주 큰 비용)
    return c, missing


def route_cost(order, c):
    return sum(c(order[i], order[i + 1]) for i in range(len(order) - 1))


def nearest_neighbor(nodes, c, start):
    unvisited = set(nodes)
    order = [start]
    unvisited.discard(start)
    cur = start
    while unvisited:
        nxt = min(unvisited, key=lambda n: c(cur, n))
        order.append(nxt)
        unvisited.discard(nxt)
        cur = nxt
    return order


def two_opt(order, c, fix_start):
    """방문 순서를 2-opt 로 개선한다. fix_start=True 면 첫 점(출발지)을 고정."""
    best = order[:]
    start_i = 1 if fix_start else 0
    improved = True
    while improved:
        improved = False
        n = len(best)
        for i in range(start_i, n - 1):
            for j in range(i + 1, n):
                new = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                if route_cost(new, c) < route_cost(best, c) - 1e-9:
                    best = new
                    improved = True
    return best


def run_route(nodes_path, matrix_path, depot, out_path, args):
    rows, fields = read_rows(nodes_path)
    nid = pick_id(fields, args.id)
    nodes = [r[nid] for r in rows if r.get(nid)]
    nodes = list(dict.fromkeys(nodes))  # 중복 제거, 순서 유지
    if len(nodes) < 2:
        print(f"[입력 오류] 노드가 2개 미만입니다(파일={nodes_path}, id열={nid}).")
        sys.exit(1)

    cost, mcols = load_matrix(matrix_path)
    c, missing = make_cost_fn(cost)

    if depot and depot not in nodes:
        nodes = [depot] + nodes  # 출발지가 노드 목록에 없으면 추가
    start = depot if depot else nodes[0]

    print(f"[경로] 노드={len(nodes)}개 (id열={nid}) · 행렬={matrix_path} "
          f"(열 {mcols[0]},{mcols[1]},{mcols[2]}) · 출발지={start}")

    init = nearest_neighbor(nodes, c, start)
    init_cost = route_cost(init, c)
    improved = two_opt(init, c, fix_start=bool(depot))
    imp_cost = route_cost(improved, c)

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seq", "node"])
        for i, n in enumerate(improved):
            w.writerow([i, n])

    print(f"초기(그리디) 총비용: {init_cost:,.1f}")
    print(f"2-opt 개선 후   : {imp_cost:,.1f}", end="")
    if init_cost > 0:
        print(f"  (↓ {(init_cost - imp_cost) / init_cost * 100:.1f}%)")
    else:
        print()
    if missing:
        print(f"⚠ 행렬에 없는 구간 {len(missing)}개 — 결과 신뢰도 확인 필요"
              f" (예: {list(missing)[:3]})")
    print("개선된 순서: " + " → ".join(str(x) for x in improved[:12])
          + (" ..." if len(improved) > 12 else ""))
    print(f"→ 저장: {out_path}")

    # --- AI 지시용 빈칸 ---
    # 여기에 이 문제만의 제약을 넣는다. 예시 지시(RSMC):
    #   "이 순서(improved)를 돌 때, 누적 인원이 [정원]을 넘거나
    #    누적 소요시간이 [상한]을 넘으면 거기서 경로를 끊고 출발지에서 다시 시작하는
    #    함수 하나만 추가해 줘. 시간창(도착 20분 전 등) 계산은 별도 입력으로 받고,
    #    기존 2-opt 결과 순서는 바꾸지 마."


def build_parser():
    p = argparse.ArgumentParser(
        description="지점 할당(하버사인 최근접)과 경로 개선(그리디→2-opt) 범용 도구.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--match", nargs=2, metavar=("SRC", "CAND"),
                   help="할당 모드: 대상 좌표파일 후보 좌표파일")
    p.add_argument("--route", metavar="NODES", help="경로 모드: 점 목록 파일")
    p.add_argument("--matrix", help="경로 모드의 소요시간 엣지 목록(from,to,minutes)")
    p.add_argument("--depot", help="경로의 출발지 노드 id(있으면 거기서 시작·고정)")
    p.add_argument("--max-dist", type=float,
                   help="할당 모드: 이 거리(m) 초과 짝은 경고로 표시")
    p.add_argument("--lat", help="위도 열 이름(자동 감지 실패 시)")
    p.add_argument("--lon", help="경도 열 이름(자동 감지 실패 시)")
    p.add_argument("--id", help="id 열 이름(자동 감지 실패 시)")
    p.add_argument("--out", help="결과 저장 경로(기본: 자동)")
    return p


def main():
    args = build_parser().parse_args()

    if args.match:
        out = args.out or "assignment.csv"
        run_match(args.match[0], args.match[1], out, args.max_dist, args)
    elif args.route:
        if not args.matrix:
            print("[사용 오류] --route 는 --matrix <소요시간파일> 이 필요합니다.")
            sys.exit(1)
        out = args.out or "route.csv"
        run_route(args.route, args.matrix, args.depot, out, args)
    else:
        print("[사용 오류] --match SRC CAND  또는  --route NODES --matrix TIMES 를 쓰세요.")
        print("자세한 사용법: python optimize_route.py --help")
        sys.exit(1)


if __name__ == "__main__":
    main()
