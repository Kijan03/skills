"""baseline.py — 타겟만 지정하면 '안전한 뼈대 모델'을 자동으로 돌려주는 도구.

매번 똑같이 짜야 하는데 느리고 실수(데이터 누수)가 나기 쉬운 부분을 자동화한다:
  - Train/Test 분리
  - 결측치 대체 (median) — ★ Train에서 계산해 Test에 적용 (누수 방지)
  - 범주형 원-핫 인코딩 (Train 기준 칼럼에 Test 정렬)
  - 분류/회귀 자동 판별 후 베이스라인 모델 1개 학습
  - 성능 지표 출력 (분류: accuracy·F1 / 회귀: RMSE·R²)

세부 모델 교체·튜닝은 아래 '빈칸'에서 Codex로 채운다.

사용법:
    python baseline.py data.csv target

sklearn이 필요하다 (없으면 설치 안내만 출력하고 종료).
"""

import sys

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

try:
    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LogisticRegression, LinearRegression
    from sklearn.metrics import (
        accuracy_score, f1_score, mean_squared_error, r2_score,
    )
except ImportError:
    print("scikit-learn이 필요합니다: pip install scikit-learn")
    sys.exit(1)


def read_csv_safe(path):
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"]
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise last_err if last_err else RuntimeError("인코딩 판별 실패")


def detect_problem_type(series):
    """숫자형이고 값 종류가 많으면 회귀, 아니면 분류."""
    if not is_numeric_dtype(series):
        return "분류"
    return "분류" if series.nunique(dropna=True) <= 20 else "회귀"


def run(path, target):
    print(f"# 베이스라인 모델 — {path} (타겟: {target})\n")

    try:
        df = read_csv_safe(path)
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {path}")
        return
    except Exception as e:
        print(f"❌ 파일을 읽는 중 오류: {e}")
        return

    if target not in df.columns:
        print(f"❌ 타겟 `{target}`이 칼럼에 없습니다. 칼럼: {list(df.columns)}")
        return

    # 타겟 결측 행은 학습에 쓸 수 없으므로 제거
    df = df.dropna(subset=[target])
    if len(df) < 10:
        print("❌ 학습에 쓸 행이 너무 적습니다 (10행 미만).")
        return

    y = df[target]
    X = df.drop(columns=[target])

    ptype = detect_problem_type(y)
    print(f"- 문제 유형: **{ptype}**")

    # 범주형 → 원-핫 인코딩 (문자형 피처를 숫자로)
    X = pd.get_dummies(X, dummy_na=False)

    # Train/Test 분리 (분류는 클래스 비율 유지)
    stratify = y if (ptype == "분류" and y.nunique() > 1) else None
    try:
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=stratify
        )
    except ValueError:
        # 클래스가 너무 적어 stratify 실패하면 그냥 분리
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

    # ★ 결측 대체: Train의 median을 계산해 Train·Test 모두에 적용 (데이터 누수 방지)
    medians = X_tr.median(numeric_only=True)
    X_tr = X_tr.fillna(medians)
    X_te = X_te.fillna(medians)
    # Test에만 있던 결측 칼럼이 남으면 0으로 정리
    X_te = X_te.reindex(columns=X_tr.columns, fill_value=0).fillna(0)

    print(f"- 학습 {len(X_tr):,}행 / 평가 {len(X_te):,}행, 피처 {X_tr.shape[1]}개\n")

    # 베이스라인 모델 학습 + 평가
    if ptype == "분류":
        model = LogisticRegression(max_iter=1000)
        model.fit(X_tr, y_tr)
        pred = model.predict(X_te)
        acc = accuracy_score(y_te, pred)
        f1 = f1_score(y_te, pred, average="macro")
        print("## 성능 (베이스라인: LogisticRegression)")
        print(f"- accuracy: **{acc:.3f}**")
        print(f"- F1(macro): **{f1:.3f}**  ← 불균형 데이터면 이 값을 신뢰")
    else:
        model = LinearRegression()
        model.fit(X_tr, y_tr)
        pred = model.predict(X_te)
        rmse = mean_squared_error(y_te, pred) ** 0.5
        r2 = r2_score(y_te, pred)
        print("## 성능 (베이스라인: LinearRegression)")
        print(f"- RMSE: **{rmse:.3g}**")
        print(f"- R²: **{r2:.3f}**")

    # --- AI 지시용 빈칸 ---
    # 여기서부터 Codex로 모델을 교체/개선한다. 예:
    # "위 베이스라인 구조를 유지하면서 모델만 RandomForest로 바꾸고,
    #  데이터 누수 없이 성능 지표를 다시 출력하는 코드 5줄만 짜줘."

    print("\n→ 이 수치가 '기준선'입니다. Codex에게 모델 교체·튜닝을 지시해 이 값을 넘기세요.")
    print("→ 전처리(결측·인코딩)는 Train 기준으로만 fit — 누수 방지가 뼈대에 내장돼 있습니다.")


def main():
    if len(sys.argv) < 3:
        print("사용법: python baseline.py <csv경로> <타겟칼럼>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
