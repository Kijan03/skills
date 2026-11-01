"""table_merge.py — 여러 CSV를 조인하거나 그룹 집계해 '슬림 결과'로 저장하는 도구.

큰 원본을 반복해서 읽지 않도록, 필요한 열만(usecols) 읽어서
조인/집계한 뒤 작은 결과 파일로 저장하고, 화면에는 요약만 출력한다.
이후 단계는 이 작은 결과 파일만 입력으로 쓰면 되므로 원본 재방문이 사라진다.

두 가지 모드:
  (1) 조인(JOIN)  : 2개 이상 CSV를 공통 키로 합친다.
  (2) 집계(GROUP) : 1개 CSV를 특정 열로 묶어 개수/합계 등을 센다.

사용 예:
    # 조인 — 공통 키 id 로 합치고, 필요한 열만 남겨 저장
    python table_merge.py left.csv right.csv --on id --cols id,shift,stop_id --out slim.csv

    # 집계 — stop_id 별 행 개수(인원 수)를 세어 저장
    python table_merge.py member_stop.csv --group stop_id --agg count --out demand.csv

    # 집계 — date,shift,stop_id 조합별 행 개수
    python table_merge.py rec.csv --group date,shift,stop_id --agg count --out demand.csv

    # 집계 — 합계/평균 등은 --value 로 대상 열 지정
    python table_merge.py rec.csv --group stop_id --agg sum --value people --out sum.csv

입력 형식 요약(AI/사용자 참고):
  - 조인: 모든 파일에 --on 키 열이 있어야 한다. 없으면 어떤 열이 있는지 알려주고 멈춘다.
  - 집계: --group 에 적은 열이 파일에 있어야 한다.
          count 외(sum/mean/min/max)는 --value 로 집계 대상 열을 지정한다.

pandas 가 필요하다.
"""

import argparse
import csv as _csv
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import pandas as pd
except ImportError:
    print("[의존성 오류] pandas 가 필요합니다. 먼저 설치하세요:")
    print("    pip install pandas")
    sys.exit(1)

ENCODINGS = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"]


def read_header(path):
    """파일 첫 줄만 읽어 열 이름 목록을 저렴하게 얻는다(인코딩 방어)."""
    for enc in ENCODINGS:
        try:
            with open(path, encoding=enc, newline="") as f:
                first = f.readline()
            if not first:
                return []
            return next(_csv.reader([first]))
        except UnicodeDecodeError:
            continue
    return []


def safe_read_csv(path, usecols=None):
    """pandas 로 CSV 를 인코딩 방어하며 읽는다. usecols 지정 시 그 열만 읽는다."""
    last_err = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, usecols=usecols, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise last_err if last_err else RuntimeError("인코딩 판별 실패")


def needed_cols(path, wanted):
    """원하는 열 중 실제로 파일에 있는 것만 골라 usecols 로 쓴다(없으면 None=전부)."""
    if not wanted:
        return None
    header = set(read_header(path))
    use = [c for c in wanted if c in header]
    return use or None


def print_summary(df, out_path):
    """결과를 요약만 출력하고(원본 전체 X) 파일로 저장한다."""
    print(f"✅ 결과: {len(df):,}행 × {len(df.columns)}열")
    nulls = df.isna().sum()
    nulls = nulls[nulls > 0]
    if len(nulls):
        parts = [f"{c} {int(n)}건" for c, n in nulls.items()]
        print("결측: " + ", ".join(parts))
    else:
        print("결측: 없음")
    print("미리보기(앞 5행):")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(df.head().to_string(index=False))
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"→ 저장: {out_path}  (이후 단계는 이 파일만 입력으로 쓰세요)")


def do_join(files, on, how, cols, out_path):
    if not on:
        print("[입력 오류] 2개 이상 파일을 조인하려면 --on <공통키> 가 필요합니다.")
        for f in files:
            print(f"  {f} 의 열: {read_header(f)}")
        sys.exit(1)

    # 조인 키 + 남길 열 + value 를 usecols 후보로
    wanted = set(cols or [])
    for k in on:
        wanted.add(k)

    frames = []
    for f in files:
        use = needed_cols(f, wanted) if cols else None
        # 조인 키는 반드시 읽어야 하므로, cols 를 줬다면 키 포함 여부 확인
        if use is not None:
            for k in on:
                if k not in use:
                    header = read_header(f)
                    if k in header:
                        use.append(k)
        df = safe_read_csv(f, usecols=use)
        for k in on:
            if k not in df.columns:
                print(f"[입력 오류] '{f}' 에 조인 키 '{k}' 가 없습니다.")
                print(f"  이 파일의 열: {list(df.columns)}")
                sys.exit(1)
        frames.append(df)

    merged = frames[0]
    for df in frames[1:]:
        merged = merged.merge(df, on=on, how=how)

    if cols:
        keep = [c for c in cols if c in merged.columns]
        if keep:
            merged = merged[keep]

    print(f"[조인] {len(files)}개 파일 · 키={on} · 방식={how}")
    print_summary(merged, out_path)


def do_group(path, group, agg, value, out_path):
    header = set(read_header(path))
    missing = [g for g in group if g not in header]
    if missing:
        print(f"[입력 오류] '{path}' 에 그룹 열이 없습니다: {missing}")
        print(f"  이 파일의 열: {read_header(path)}")
        sys.exit(1)

    # 필요한 열만 읽기: 그룹 열 (+ count 외엔 value 열)
    wanted = list(group)
    if agg != "count":
        if not value:
            print(f"[입력 오류] --agg {agg} 는 --value <대상 열> 이 필요합니다.")
            sys.exit(1)
        if value not in header:
            print(f"[입력 오류] '{path}' 에 집계 대상 열 '{value}' 가 없습니다.")
            print(f"  이 파일의 열: {read_header(path)}")
            sys.exit(1)
        wanted.append(value)

    df = safe_read_csv(path, usecols=wanted)

    if agg == "count":
        result = df.groupby(group, dropna=False).size().reset_index(name="count")
    else:
        grouped = df.groupby(group, dropna=False)[value]
        result = getattr(grouped, agg)().reset_index()

    print(f"[집계] 파일={path} · 그룹={group} · 집계={agg}"
          + (f"({value})" if agg != "count" else ""))
    print_summary(result, out_path)


def build_parser():
    p = argparse.ArgumentParser(
        description="여러 CSV를 조인하거나 그룹 집계해 슬림 결과 파일로 저장한다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("files", nargs="+", help="입력 CSV. 1개=집계 모드, 2개 이상=조인 모드")
    p.add_argument("--on", help="조인 공통 키(쉼표로 여러 개)")
    p.add_argument("--how", default="inner",
                   choices=["inner", "left", "right", "outer"], help="조인 방식")
    p.add_argument("--cols", help="결과에 남길 열(쉼표). 읽기 단계에서 usecols 로도 쓰임")
    p.add_argument("--group", help="집계할 그룹 열(쉼표). 지정 시 집계 모드")
    p.add_argument("--agg", default="count",
                   choices=["count", "sum", "mean", "min", "max"],
                   help="집계 함수(기본 count=행 개수)")
    p.add_argument("--value", help="count 외 집계의 대상 열")
    p.add_argument("--out", help="결과 저장 경로(기본: 자동 생성)")
    return p


def main():
    args = build_parser().parse_args()
    on = [s.strip() for s in args.on.split(",")] if args.on else None
    cols = [s.strip() for s in args.cols.split(",")] if args.cols else None
    group = [s.strip() for s in args.group.split(",")] if args.group else None

    if group:
        out = args.out or "grouped.csv"
        do_group(args.files[0], group, args.agg, args.value, out)
    elif len(args.files) >= 2:
        out = args.out or "merged.csv"
        do_join(args.files, on, args.how, cols, out)
    else:
        print("[사용 오류] 파일이 1개면 --group 으로 집계하거나, 2개 이상 주고 --on 으로 조인하세요.")
        print(f"  '{args.files[0]}' 의 열: {read_header(args.files[0])}")
        sys.exit(1)


if __name__ == "__main__":
    main()
