import sys

# Windows 한글 콘솔(cp949)에서 이모지/유니코드 출력 시 UnicodeEncodeError 방지
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import pandas as pd
except ImportError:
    print("❌ 오류: pandas가 설치되어 있지 않습니다. 'pip install pandas' 후 다시 실행하세요.")
    sys.exit(1)


def read_csv_safe(file_path):
    """인코딩 문제에 견고하게 CSV를 읽는다. 여러 인코딩을 순차 시도."""
    encodings = ["utf-8-sig", "cp949", "euc-kr", "latin-1"]
    last_err = None
    for enc in encodings:
        try:
            # low_memory=False: 혼합 타입 칼럼 경고/오탐 방지 (메모리 급증 아님)
            return pd.read_csv(file_path, encoding=enc, low_memory=False)
        except UnicodeDecodeError as e:
            last_err = e
            continue
    # 모든 인코딩 실패 시 마지막 에러 전달
    raise last_err if last_err else UnicodeDecodeError(
        "unknown", b"", 0, 1, "인코딩을 판별할 수 없습니다."
    )


def fmt_list(items, limit=5):
    """칼럼 목록을 보기 좋게 출력. limit 초과 시에만 '...' 표시."""
    if not items:
        return "(없음)"
    head = ", ".join(str(c) for c in items[:limit])
    return f"{head} ..." if len(items) > limit else head


def scan_data(file_path, target_col=None):
    try:
        df = read_csv_safe(file_path)
    except FileNotFoundError:
        print(f"❌ 오류: '{file_path}' 파일을 찾을 수 없습니다.")
        return
    except PermissionError:
        print(f"❌ 오류: '{file_path}' 파일에 접근할 수 없습니다 (권한 문제).")
        return
    except pd.errors.EmptyDataError:
        print(f"❌ 오류: '{file_path}' 는 비어 있거나 읽을 데이터가 없습니다.")
        return
    except pd.errors.ParserError as e:
        print(f"❌ 오류: CSV 파싱 실패 (형식이 올바르지 않음): {e}")
        return
    except UnicodeDecodeError:
        print("❌ 오류: 파일 인코딩을 판별할 수 없습니다 (utf-8/cp949/euc-kr/latin-1 모두 실패).")
        return
    except MemoryError:
        print("❌ 오류: 파일이 너무 커서 메모리에 로드할 수 없습니다 (MemoryError).")
        return
    except Exception as e:
        print(f"❌ 분석 중 예기치 못한 오류 발생: {e}")
        return

    # 로드 성공했으나 행이 0인 경우 (헤더만 존재)
    if df.shape[0] == 0:
        print("### 📊 Data Scanner 요약 리포트 (프롬프트 복붙용) ###")
        print(f"- 데이터 형태: 0행, {df.shape[1]}열 (헤더만 존재, 데이터 없음)")
        return

    print("### 📊 Data Scanner 요약 리포트 (프롬프트 복붙용) ###")
    print(f"- 데이터 형태: 총 {df.shape[0]:,}행, {df.shape[1]}열")

    missing = df.isnull().sum()
    missing = missing[missing > 0]
    if len(missing) > 0:
        detail = ", ".join(f"{col}({cnt:,})" for col, cnt in missing.items())
        print(f"- 결측치 존재 칼럼 ({len(missing)}개): {detail}")
    else:
        print("- 결측치: 없음")

    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    cat_cols = df.select_dtypes(exclude=["number"]).columns.tolist()
    print(f"- 숫자형 칼럼 ({len(num_cols)}개): {fmt_list(num_cols)}")
    print(f"- 범주형 칼럼 ({len(cat_cols)}개): {fmt_list(cat_cols)}")

    if target_col:
        if target_col not in df.columns:
            print(f"\n❌ 오류: 타겟 칼럼 '{target_col}' 이(가) 존재하지 않습니다.")
            print(f"   사용 가능한 칼럼: {fmt_list(df.columns.tolist(), limit=20)}")
            return

        print(f"\n[Target 변수('{target_col}') 클래스 비율]")
        series = df[target_col]
        n_missing = int(series.isnull().sum())
        if n_missing > 0:
            print(f" - (결측치: {n_missing:,}개는 비율 계산에서 제외)")

        dist = series.value_counts(normalize=True, dropna=True) * 100
        if dist.empty:
            print(" - 유효한 값이 없어 비율을 계산할 수 없습니다.")
            return

        n_unique = series.nunique(dropna=True)
        # 고유값이 너무 많으면 타겟이 아니라 연속형/식별자일 가능성 경고
        if n_unique > 50:
            print(f" ⚠️ 고유값이 {n_unique:,}개로 많습니다. 분류 타겟이 맞는지 확인하세요 (상위 10개만 표시).")
            dist = dist.head(10)

        for val, pct in dist.items():
            print(f" - {val}: {pct:.2f}%")

        if dist.max() >= 80:
            print(" ⚠️ [경고] 극심한 클래스 불균형 감지! 전처리 시 SMOTE 등 리샘플링 검토 필요.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python eda_scanner.py <파일명.csv> [타겟칼럼명]")
        sys.exit(1)

    file_name = sys.argv[1]
    target_name = sys.argv[2] if len(sys.argv) > 2 else None
    scan_data(file_name, target_name)
