import io

import streamlit as st
import pandas as pd
# import joblib  # 모델 로드 시 주석 해제

# [기본 세팅] 오버엔지니어링 방지용 심플 UI
st.set_page_config(page_title="현업 데이터 분석 대시보드", layout="wide")
st.title("📊 현업 데이터 분석 대시보드 (MVP)")
st.markdown("현장 오퍼레이터가 데이터를 업로드하면 즉시 핵심 지표를 확인하는 툴입니다.")


# [데이터 로더] 인코딩 방어 + 캐싱 (리렌더링 시 재읽기 방지)
@st.cache_data(show_spinner=False)
def load_csv(file_bytes):
    encodings = ["utf-8-sig", "cp949", "euc-kr", "latin-1"]
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(io.BytesIO(file_bytes), encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise last_err if last_err else UnicodeDecodeError(
        "unknown", b"", 0, 1, "인코딩 판별 실패"
    )


# [사이드바] 데이터 업로드 구역
with st.sidebar:
    st.header("1. 데이터 업로드")
    uploaded_file = st.file_uploader("CSV 파일을 업로드하세요", type=["csv"])

if uploaded_file is not None:
    # 데이터 로드 (인코딩/포맷 오류 방어)
    try:
        df = load_csv(uploaded_file.getvalue())
    except UnicodeDecodeError:
        st.error("❌ 인코딩을 판별할 수 없습니다 (utf-8/cp949/euc-kr 모두 실패).")
        st.stop()
    except pd.errors.EmptyDataError:
        st.error("❌ 비어 있거나 읽을 데이터가 없는 파일입니다.")
        st.stop()
    except pd.errors.ParserError:
        st.error("❌ CSV 형식이 올바르지 않습니다 (파싱 실패).")
        st.stop()
    except Exception as e:
        st.error(f"❌ 파일을 읽는 중 오류가 발생했습니다: {e}")
        st.stop()

    st.success("데이터 로드 완료!")
    st.write(df.head(3))

    st.divider()

    # 화면 2분할 (차트 영역 / 분석 결과 영역)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 데이터 시각화")
        # --- AI 지시용 빈칸 1 ---
        # "여기에 df의 특정 변수 분포를 보여주는 가장 가벼운 Bar Chart 코드 3줄만 짜줘"
        st.info("여기에 시각화 차트가 들어갑니다.")

    with col2:
        st.subheader("🤖 모델 예측 결과")
        if st.button("분석 실행"):
            with st.spinner("분석 중입니다..."):
                # --- AI 지시용 빈칸 2 ---
                # "여기에 best_model.pkl을 불러와 df를 예측하고 결과를 텍스트로 출력하는 코드 5줄만 짜줘"
                st.warning("분석 로직이 아직 연결되지 않았습니다.")
else:
    st.info("👈 좌측 사이드바에서 CSV 파일을 업로드해 주세요.")
