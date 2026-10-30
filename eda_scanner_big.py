import sys

# Windows 한글 콘솔(cp949)에서 이모지/유니코드 출력 시 UnicodeEncodeError 방지
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import pandas as pd
    from pandas.api.types import is_numeric_dtype
except ImportError:
    print("❌ 오류: pandas가 설치되어 있지 않습니다. 'pip install pandas' 후 다시 실행하세요.")
    sys.exit(1)

CHUNK_SIZE = 100_000  # 한 번에 읽을 행 수 (메모리 상한 조절)


def fmt_list(items, limit=5):
    if not items:
        return "(없음)"
    head = ", ".join(str(c) for c in items[:limit])
    return f"{head} ..." if len(items) > limit else head


def open_reader(file_path):
    """인코딩을 순차 시도하여 chunk 단위 TextFileReader를 연다."""
    encodings = ["utf-8-sig", "cp949", "euc-kr", "latin-1"]
    last_err = None
    for enc in encodings:
        try:
            reader = pd.read_csv(
                file_path, encoding=enc, chunksize=CHUNK_SIZE, low_memory=False
            )
            # 첫 chunk를 미리 당겨 인코딩 유효성 확인 후 다시 사용할 수 있게 보관
            first = next(reader)
            return reader, first
        except StopIteration:
            # 헤더만 있고 데이터가 없는 경우 (빈 chunk)
            return None, pd.DataFrame()
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise last_err if last_err else UnicodeDecodeError(
        "unknown", b"", 0, 1, "인코딩을 판별할 수 없습니다."
    )


def scan_data(file_path, target_col=None):
    try:
        reader, first = open_reader(file_path)
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
    except Exception as e:
        print(f"❌ 분석 중 예기치 못한 오류 발생: {e}")
        return

    columns = list(first.columns)

    # 헤더만 존재하고 데이터 행이 없는 경우
    if first.shape[0] == 0 and reader is None:
        print("### 📊 Data Scanner 요약 리포트 (대용량/스트리밍) ###")
        print(f"- 데이터 형태: 0행, {len(columns)}열 (헤더만 존재, 데이터 없음)")
        return

    # --- 누적 집계용 상태 ---
    total_rows = 0
    missing_counts = pd.Series(0, index=columns, dtype="int64")
    # 각 칼럼이 지금까지 모든 chunk에서 숫자형이었는지 추적
    all_numeric = {c: True for c in columns}
    target_counts = None
    target_na = 0

    def consume(chunk):
        nonlocal total_rows, missing_counts, target_counts, target_na
        total_rows += len(chunk)
        missing_counts = missing_counts.add(chunk.isnull().sum(), fill_value=0)
        for c in columns:
            if c in chunk.columns and not is_numeric_dtype(chunk[c]):
                all_numeric[c] = False
        if target_col and target_col in chunk.columns:
            target_na += int(chunk[target_col].isnull().sum())
            vc = chunk[target_col].value_counts(dropna=True)
            target_counts = vc if target_counts is None else target_counts.add(
                vc, fill_value=0
            )

    try:
        consume(first)
        if reader is not None:
            for chunk in reader:
                consume(chunk)
    except (pd.errors.ParserError, UnicodeDecodeError) as e:
        print(f"❌ 오류: 파일 중간에서 읽기 실패: {e}")
        return
    except MemoryError:
        print("❌ 오류: 메모리 부족. CHUNK_SIZE를 더 작게 조정하세요.")
        return
    except Exception as e:
        print(f"❌ 분석 중 예기치 못한 오류 발생: {e}")
        return

    # --- 리포트 출력 ---
    print("### 📊 Data Scanner 요약 리포트 (대용량/스트리밍) ###")
    print(f"- 데이터 형태: 총 {total_rows:,}행, {len(columns)}열 (chunk={CHUNK_SIZE:,}행 단위 처리)")

    missing = missing_counts[missing_counts > 0].astype("int64")
    if len(missing) > 0:
        detail = ", ".join(f"{col}({int(cnt):,})" for col, cnt in missing.items())
        print(f"- 결측치 존재 칼럼 ({len(missing)}개): {detail}")
    else:
        print("- 결측치: 없음")

    num_cols = [c for c in columns if all_numeric[c]]
    cat_cols = [c for c in columns if not all_numeric[c]]
    print(f"- 숫자형 칼럼 ({len(num_cols)}개): {fmt_list(num_cols)}")
    print(f"- 범주형 칼럼 ({len(cat_cols)}개): {fmt_list(cat_cols)}")

    if target_col:
        if target_col not in columns:
            print(f"\n❌ 오류: 타겟 칼럼 '{target_col}' 이(가) 존재하지 않습니다.")
            print(f"   사용 가능한 칼럼: {fmt_list(columns, limit=20)}")
            return

        print(f"\n[Target 변수('{target_col}') 클래스 비율]")
        if target_na > 0:
            print(f" - (결측치: {target_na:,}개는 비율 계산에서 제외)")

        if target_counts is None or target_counts.sum() == 0:
            print(" - 유효한 값이 없어 비율을 계산할 수 없습니다.")
            return

        dist = (target_counts / target_counts.sum() * 100).sort_values(ascending=False)
        n_unique = len(dist)
        if n_unique > 50:
            print(f" ⚠️ 고유값이 {n_unique:,}개로 많습니다. 분류 타겟이 맞는지 확인하세요 (상위 10개만 표시).")
            dist = dist.head(10)

        for val, pct in dist.items():
            print(f" - {val}: {pct:.2f}%")

        if dist.max() >= 80:
            print(" ⚠️ [경고] 극심한 클래스 불균형 감지! 전처리 시 SMOTE 등 리샘플링 검토 필요.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python eda_scanner_big.py <파일명.csv> [타겟칼럼명]")
        sys.exit(1)

    file_name = sys.argv[1]
    target_name = sys.argv[2] if len(sys.argv) > 2 else None
    scan_data(file_name, target_name)
