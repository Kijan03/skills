"""err_triage.py — 에러 로그를 주면 '원인 유형'을 먼저 분류해 주는 도구.

에러가 나면 로그만 보며 헤매기 쉽다. 이 도구는 로그에서 신호를 찾아
가장 가능성 높은 원인(차원 불일치 / 메모리 / 인코딩 / 타입 등)을 짚고,
Codex에 그대로 붙일 수 있는 '정돈된 질문'을 만들어 준다.

사용법:
    python err_triage.py error.log          # 로그 파일에서 읽기
    python err_triage.py "ValueError: shapes (3,) and (4,)..."   # 직접 전달
    (인자가 없으면 표준입력으로 붙여넣기 가능)

표준 라이브러리만 사용한다.
"""

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# (신호 키워드, 원인 이름, 설명, 최소 수정 방향) — 위에서부터 우선 매칭
RULES = [
    (
        ["memoryerror", "out of memory", "oom", "killed", "cannot allocate"],
        "메모리 초과 (OOM)",
        "데이터/모델이 메모리보다 큼. 대회 환경에서 OOM은 구제 대상이 아님.",
        "데이터를 chunksize로 나눠 읽거나(eda_scanner_big 참고), 필요한 칼럼만 로드하거나, dtype을 축소(float64→float32)하는 방향",
    ),
    (
        ["unicodedecodeerror", "codec can't decode", "cp949", "euc-kr", "0x"],
        "인코딩 문제",
        "파일 인코딩이 코드가 가정한 것과 다름 (한글 CSV에서 흔함).",
        "read_csv에 encoding을 utf-8-sig→cp949→euc-kr 순으로 시도(read_csv_safe 패턴)하는 방향",
    ),
    (
        ["shapes", "dimension mismatch", "could not broadcast",
         "shape mismatch", "found array with", "inconsistent numbers of samples"],
        "차원/형상 불일치 (shape mismatch)",
        "배열·행렬의 크기가 서로 안 맞음 (X와 y 행 수, 피처 수 불일치 등).",
        "연산 직전 X.shape / y.shape를 출력해 어디서 어긋나는지 확인하고, Train 기준 칼럼에 Test를 reindex로 맞추는 방향",
    ),
    (
        ["could not convert string to float", "invalid literal",
         "valueerror: could not"],
        "타입 변환 실패",
        "숫자로 기대한 칼럼에 문자/빈값이 섞여 있음.",
        "해당 칼럼을 pd.to_numeric(errors='coerce')로 변환하고 결측 처리하는 방향",
    ),
    (
        ["keyerror"],
        "존재하지 않는 키/칼럼 (KeyError)",
        "DataFrame에 없는 칼럼명이나 딕셔너리 키를 참조함 (오타·대소문자 포함).",
        "df.columns를 출력해 실제 칼럼명과 철자를 대조하는 방향",
    ),
    (
        ["modulenotfounderror", "no module named"],
        "모듈 없음",
        "import하려는 라이브러리가 설치돼 있지 않음.",
        "pip install로 설치하거나, 꼭 필요한지 자문하고 표준 라이브러리로 대체하는 방향(오버엔지니어링 점검)",
    ),
    (
        ["filenotfounderror", "no such file"],
        "파일 경로 문제",
        "지정한 파일이 그 경로에 없음.",
        "현재 작업 폴더(os.getcwd())와 실제 파일 위치를 확인하고 경로를 맞추는 방향",
    ),
    (
        ["typeerror"],
        "타입 오류 (TypeError)",
        "함수에 기대와 다른 타입을 넘김 (None, 리스트 vs 배열 등).",
        "문제가 된 변수의 type()을 출력해 어떤 값이 들어왔는지 확인하는 방향",
    ),
    (
        ["indexerror", "index out of range", "out of bounds"],
        "인덱스 범위 초과",
        "리스트/배열의 범위를 벗어난 위치를 참조함.",
        "반복 범위와 실제 길이(len)를 대조하는 방향",
    ),
]


def classify(log):
    low = log.lower()
    for keys, name, desc, fix in RULES:
        if any(k in low for k in keys):
            return name, desc, fix
    return None, None, None


def last_line(log):
    """로그에서 핵심인 마지막 비어있지 않은 줄 (보통 예외 메시지)."""
    lines = [ln.strip() for ln in log.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else log.strip()


def triage(log):
    print("# 에러 분류 리포트\n")
    name, desc, fix = classify(log)
    key_line = last_line(log)

    if name:
        print(f"## 가장 가능성 높은 원인: **{name}**")
        print(f"- 무엇: {desc}")
        print(f"- 수정 방향(가설): {fix}")
    else:
        print("## 자동 분류 실패 — 아래 핵심 줄로 직접 판단하세요.")

    print(f"\n- 핵심 메시지: `{key_line}`")

    # Codex에 바로 붙일 수 있는 정돈된 질문
    print("\n## Codex에 붙일 질문 (복사용)")
    print("-" * 50)
    print(
        "터미널 에러가 났어:\n"
        f"{key_line}\n\n"
        "이게 차원 불일치 / 메모리(OOM) / 타입·인코딩 중 무엇 때문인지 "
        "원인부터 한 줄로 진단해줘. 그다음 기존 비즈니스 로직을 해치지 않는 선에서 "
        "가장 간단한 수정 1개만 제시해. 전체 리팩터링은 하지 마."
    )
    print("-" * 50)


def read_input():
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        # 파일 경로면 파일 내용을, 아니면 인자 자체를 로그로 취급
        if os.path.isfile(arg):
            for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
                try:
                    with open(arg, encoding=enc) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            return ""
        return " ".join(sys.argv[1:])
    # 인자가 없으면 표준입력
    if not sys.stdin.isatty():
        return sys.stdin.read()
    print("사용법: python err_triage.py <로그파일 또는 에러메시지>")
    sys.exit(1)


def main():
    log = read_input()
    if not log.strip():
        print("읽을 에러 내용이 없습니다.")
        sys.exit(1)
    triage(log)


if __name__ == "__main__":
    main()
