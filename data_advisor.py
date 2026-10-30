"""data_advisor.py — 데이터를 주면 '무엇을 해야 할지' 알려주는 진단·추천 도구.

eda_scanner가 '데이터가 어떻게 생겼나'를 보여준다면,
이 도구는 거기서 한 걸음 더 나아가 '그래서 뭘 해야 하나'를 추천한다.
  - 문제 유형(분류 / 회귀) 자동 판별
  - 타겟(정답) 칼럼 후보 추천
  - 추천 전처리(결측 대체 / 인코딩 / 스케일링)
  - 추천 평가지표(불균형이면 F1·recall 등)

사용법:
    python data_advisor.py data.csv          # 타겟 자동 추측
    python data_advisor.py data.csv defect   # 타겟 칼럼 직접 지정

무거운 라이브러리 없이 pandas만 사용한다.
"""

import sys

# 한글 Windows 콘솔(cp949)에서 이모지/기호 출력 시 크래시 방지
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import pandas as pd
    from pandas.api.types import is_numeric_dtype
except ImportError:
    print("pandas가 필요합니다: pip install pandas")
    sys.exit(1)


# 타겟(정답) 칼럼으로 자주 쓰이는 이름들 (소문자 비교)
TARGET_HINTS = [
    "target", "label", "class", "y", "result", "output",
    "defect", "fault", "fail", "pass", "pred", "answer",
    "불량", "양불", "정답", "결과", "분류", "수율", "판정",
]


def read_csv_safe(path):
    """인코딩을 순서대로 시도해 안전하게 CSV를 읽는다."""
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"]
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise last_err if last_err else RuntimeError("인코딩 판별 실패")


def guess_target(df):
    """타겟 칼럼 후보를 추측한다. (이름 힌트 우선, 없으면 마지막 칼럼)"""
    cols_lower = {c.lower(): c for c in df.columns}
    for hint in TARGET_HINTS:
        for low, orig in cols_lower.items():
            if hint in low:
                return orig, f"이름에 '{hint}'가 들어가 타겟일 가능성이 높음"
    # 힌트가 없으면 관례상 마지막 칼럼을 후보로
    return df.columns[-1], "이름 힌트가 없어 관례상 마지막 칼럼을 후보로 제시"


def detect_problem_type(series):
    """타겟 칼럼을 보고 분류/회귀를 판별한다."""
    n_unique = series.nunique(dropna=True)
    if not is_numeric_dtype(series):
        return "분류", f"타겟이 문자형이고 값이 {n_unique}종류 → 분류 문제"
    # 숫자형이라도 값 종류가 적으면 분류로 본다
    if n_unique <= 20:
        return "분류", f"타겟이 숫자형이지만 값이 {n_unique}종류뿐 → 분류 문제로 판단"
    return "회귀", f"타겟이 숫자형이고 값이 {n_unique}종류로 연속적 → 회귀 문제"


def fmt_list(items, limit=10):
    items = list(items)
    if not items:
        return "없음"
    shown = ", ".join(str(x) for x in items[:limit])
    if len(items) > limit:
        shown += f" ... (외 {len(items) - limit}개)"
    return shown


def advise(path, target=None):
    print(f"# 데이터 진단 리포트 — {path}\n")

    try:
        df = read_csv_safe(path)
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {path}")
        return
    except PermissionError:
        print(f"❌ 파일 접근 권한이 없습니다: {path}")
        return
    except pd.errors.EmptyDataError:
        print("❌ 비어 있거나 읽을 데이터가 없는 파일입니다.")
        return
    except pd.errors.ParserError:
        print("❌ CSV 형식이 올바르지 않습니다 (파싱 실패).")
        return
    except Exception as e:
        print(f"❌ 파일을 읽는 중 오류: {e}")
        return

    n_rows, n_cols = df.shape
    print(f"- 크기: **{n_rows:,}행 × {n_cols}열**")

    # 1) 타겟 결정
    reason = ""
    if target is None:
        target, reason = guess_target(df)
        print(f"- 추천 타겟: **`{target}`** ({reason})")
    elif target not in df.columns:
        print(f"⚠️ 지정한 타겟 `{target}`이 칼럼에 없습니다. 자동 추측으로 대체합니다.")
        target, reason = guess_target(df)
        print(f"- 추천 타겟: **`{target}`** ({reason})")
    else:
        print(f"- 타겟: **`{target}`** (사용자 지정)")

    # 2) 문제 유형 판별
    ptype, preason = detect_problem_type(df[target])
    print(f"\n## 문제 유형: **{ptype}**")
    print(f"- 근거: {preason}")

    # 3) 분류면 클래스 분포 / 불균형 + 지표 추천
    if ptype == "분류":
        vc = df[target].value_counts(dropna=False)
        print("\n### 클래스 분포")
        for val, cnt in vc.items():
            print(f"  - {val}: {cnt:,} ({cnt / n_rows * 100:.1f}%)")
        top_ratio = vc.iloc[0] / n_rows
        if top_ratio >= 0.8:
            print(f"\n⚠️ **클래스 불균형** (최다 클래스 {top_ratio*100:.0f}%)")
            print("  - 추천 지표: **F1 / recall** (accuracy는 신뢰하지 말 것)")
            print("  - 추천 처리: 소수 클래스 오버샘플링(SMOTE 등)은 **Train에만** 적용")
        else:
            print("\n- 비교적 균형 → accuracy도 참고 가능하나 F1 병행 권장")
    else:
        desc = df[target].describe()
        print("\n### 타겟 분포(요약)")
        print(f"  - 최소 {desc['min']:.3g} / 평균 {desc['mean']:.3g} / 최대 {desc['max']:.3g}")
        print("- 추천 지표: **RMSE / MAE / R²**")

    # 4) 전처리 추천
    print("\n## 추천 전처리")
    features = [c for c in df.columns if c != target]

    # 결측
    miss = df[features].isnull().sum()
    miss = miss[miss > 0]
    if len(miss) > 0:
        print("- 결측치 있는 칼럼 → **대체 필요**:")
        for col, cnt in miss.items():
            kind = "median" if is_numeric_dtype(df[col]) else "최빈값/'미상'"
            print(f"    - `{col}`: {cnt:,}개 결측 → {kind} 대체 권장")
    else:
        print("- 결측치: 없음 ✅")

    # 범주형 인코딩
    cat_cols = [c for c in features if not is_numeric_dtype(df[c])]
    if cat_cols:
        print(f"- 범주형 칼럼 → **인코딩 필요** (원-핫/라벨): {fmt_list(cat_cols)}")
    else:
        print("- 범주형 칼럼: 없음 (모두 숫자형)")

    # 스케일 차이
    num_cols = [c for c in features if is_numeric_dtype(df[c])]
    if len(num_cols) >= 2:
        ranges = {}
        for c in num_cols:
            col = df[c].dropna()
            if len(col) > 0:
                ranges[c] = col.max() - col.min()
        ranges = {k: v for k, v in ranges.items() if v and v > 0}
        if ranges and max(ranges.values()) / min(ranges.values()) >= 100:
            print("- 숫자 칼럼 간 **스케일 차이 큼** → 정규화/표준화 권장 "
                  "(거리·선형 모델 사용 시). 스케일러 `fit`은 **Train에만**.")
        else:
            print("- 숫자 칼럼 스케일: 큰 차이 없음")

    # 5) 다음 단계
    print("\n## 다음 단계")
    print(f"→ `python baseline.py {path} {target}` 로 **뼈대 모델**을 먼저 돌려 성능 기준선을 잡으세요.")
    print("→ 위 진단 내용을 그대로 Codex에 붙여 \"이 진단대로 전처리 코드를 N줄로 짜줘\"처럼 범위를 좁혀 지시하세요.")


def main():
    if len(sys.argv) < 2:
        print("사용법: python data_advisor.py <csv경로> [타겟칼럼]")
        sys.exit(1)
    path = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) >= 3 else None
    advise(path, target)


if __name__ == "__main__":
    main()
