# data-prep-tools

CSV 탐색·대시보드 뼈대·텍스트 청킹을 위한 **범용 경량 파이썬 유틸리티** 모음.
무거운 의존성 없이 데이터 전처리 초기 단계를 빠르게 돕는 것을 목표로 한다.

## 설치

```bash
git clone <this-repo-url>
cd data-prep-tools
pip install -r requirements.txt   # pandas (필수), streamlit (3번만)
```

## 구성

| 파일 | 용도 | 의존성 |
|---|---|---|
| `eda_scanner.py` | CSV 메타데이터(행·열·결측치·타입·타겟 분포) 요약 출력 | pandas |
| `eda_scanner_big.py` | 초대용량 CSV를 chunk 스트리밍으로 메모리 안전하게 요약 | pandas |
| `streamlit_mvp_base.py` | 로그인·DB 없는 초경량 대시보드 뼈대 (빈칸형) | streamlit, pandas |
| `rag_chunking_safe.py` | 텍스트 청킹 유틸 (LangChain 없으면 순수 파이썬 fallback) | (선택) langchain |

> 모든 스크립트는 인코딩 자동 판별(utf-8/cp949/euc-kr/latin-1)과
> Windows 한글 콘솔(cp949) 출력 크래시 방지를 공통 적용한다.

## 사용법

```bash
# 1) CSV 요약 (타겟 칼럼 지정 시 클래스 불균형 진단)
python eda_scanner.py data.csv target

# 2) 초대용량 CSV
python eda_scanner_big.py data.csv target

# 3) 대시보드 뼈대 실행
streamlit run streamlit_mvp_base.py

# 4) 텍스트 청킹 요약
python rag_chunking_safe.py document.txt
```

## 설계 원칙

- **경량 우선**: 시각화·무거운 라이브러리를 기본 포함하지 않는다.
- **뼈대 + 빈칸**: `streamlit_mvp_base.py`와 `rag_chunking_safe.py`는 핵심 로직을
  의도적으로 비워 두어, 사용자가 상황에 맞는 구현을 직접 채워 넣도록 한다.
- **방어적 I/O**: 파일 입출력은 인코딩·빈 파일·포맷 오류를 모두 예외 처리한다.

## 라이선스

MIT
