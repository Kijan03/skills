# data-prep-tools

데이터 분석·개발 작업을 빠르게 시작하기 위한 **범용 경량 파이썬 유틸리티** 모음.
무거운 의존성 없이, 데이터·작업 공간·에러를 먼저 **요약**해 주고 반복되는 뼈대 코드를
**미리 깔아** 주는 데 목표를 둔다. 자세한 사용법은 [USAGE.md](USAGE.md) 참고.

## 설치

```bash
git clone <this-repo-url>
cd data-prep-tools
pip install -r requirements.txt   # pandas (필수) 등
```

## 구성

| 파일 | 용도 | 의존성 |
|---|---|---|
| `repo_scan.py` | 작업 폴더의 구조·파일을 한 덩어리로 요약 | (표준 라이브러리) |
| `data_advisor.py` | CSV 진단 + 문제 유형·전처리·지표 추천 | pandas |
| `eda_scanner_big.py` | 초대용량 CSV를 chunk 스트리밍으로 메모리 안전하게 요약 | pandas |
| `baseline.py` | 타겟 지정 시 학습/평가 분리된 뼈대 예측 모델 자동 실행 | scikit-learn, pandas |
| `streamlit_mvp_base.py` | 로그인·DB 없는 초경량 대시보드 뼈대 (빈칸형) | streamlit, pandas |
| `rag_chunking_safe.py` | 텍스트 청킹 유틸 (LangChain 없으면 순수 파이썬 fallback) | (선택) langchain |
| `err_triage.py` | 에러 로그에서 원인 유형을 분류하고 정돈된 질문 생성 | (표준 라이브러리) |

> 모든 스크립트는 인코딩 자동 판별(utf-8/cp949/euc-kr/latin-1)과
> Windows 한글 콘솔(cp949) 출력 크래시 방지를 공통 적용한다.

## 사용법 (요약)

```bash
# 1) 작업 폴더 요약
python repo_scan.py .

# 2) CSV 진단·추천 (타겟 칼럼 지정 시 불균형 진단)
python data_advisor.py data.csv label

# 3) 초대용량 CSV 요약
python eda_scanner_big.py big.csv label

# 4) 뼈대 예측 모델
python baseline.py data.csv label

# 5) 대시보드 뼈대 실행
streamlit run streamlit_mvp_base.py

# 6) 텍스트 청킹 요약
python rag_chunking_safe.py document.txt

# 7) 에러 원인 분류
python err_triage.py "ValueError: shapes ..."
```

자세한 입력·출력 예시와 상황별 선택 가이드는 [USAGE.md](USAGE.md)에 정리돼 있다.

## 설계 원칙

- **요약 먼저**: 원본을 통째로 다루기 전에 요약본을 만들어 가볍게 시작한다.
- **경량 우선**: 시각화·무거운 라이브러리를 기본 포함하지 않는다.
- **뼈대 + 빈칸**: `baseline.py`·`streamlit_mvp_base.py`·`rag_chunking_safe.py`는 핵심 로직을
  의도적으로 비워 두어, 사용자가 상황에 맞는 구현을 직접 채워 넣도록 한다.
- **방어적 I/O**: 파일 입출력은 인코딩·빈 파일·포맷 오류를 모두 예외 처리한다.
- **학습/평가 분리**: 예측 모델은 전처리를 학습 데이터 기준으로만 맞춰 혼용을 피한다.

## 라이선스

MIT
