import sys

# Windows 한글 콘솔(cp949)에서 이모지/유니코드 출력 시 UnicodeEncodeError 방지
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# [의존성 방어] LangChain이 없는 환경이면 순수 파이썬 fallback 사용
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False


def simple_chunk(text, chunk_size=500, chunk_overlap=50):
    """LangChain 없이 동작하는 경량 문자열 청킹 (overlap 지원 슬라이딩 윈도우).

    문단/줄 경계를 가볍게 존중하되, 외부 라이브러리는 전혀 쓰지 않는다.
    """
    text = text.strip()
    if not text:
        return []
    if chunk_overlap >= chunk_size:
        chunk_overlap = chunk_size // 5  # 비정상 입력 방어

    step = chunk_size - chunk_overlap
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = start + chunk_size
        piece = text[start:end]
        # 중간에서 자른 경우, 가까운 공백/줄바꿈 경계로 살짝 당겨 가독성 확보
        if end < n:
            for sep in ("\n\n", "\n", " "):
                cut = piece.rfind(sep)
                if cut > step:  # 너무 앞쪽이면 무시
                    piece = piece[: cut + len(sep)]
                    break
        piece = piece.strip()
        if piece:
            chunks.append(piece)
        start += max(len(piece) - chunk_overlap, step) if piece else step
    return chunks


def read_text_safe(file_path):
    """한국어 현업 문서용 인코딩 방어 읽기 (utf-8 / cp949 등 혼용 대비)."""
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"]
    last_err = None
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise last_err if last_err else UnicodeDecodeError(
        "unknown", b"", 0, 1, "인코딩 판별 실패"
    )


def safe_chunk_text(file_path, chunk_size=500, chunk_overlap=50):
    try:
        text_data = read_text_safe(file_path)
    except FileNotFoundError:
        print(f"❌ 오류: '{file_path}' 파일을 찾을 수 없습니다.")
        return
    except PermissionError:
        print(f"❌ 오류: '{file_path}' 파일에 접근할 수 없습니다 (권한 문제).")
        return
    except UnicodeDecodeError:
        print("❌ 오류: 파일 인코딩을 판별할 수 없습니다 (utf-8/cp949/euc-kr 모두 실패).")
        return
    except Exception as e:
        print(f"❌ 파일 읽기 중 오류 발생: {e}")
        return

    if not text_data.strip():
        print(f"❌ 오류: '{file_path}' 는 비어 있는 문서입니다.")
        return

    print(f"📄 문서 로드 완료: 총 {len(text_data):,} 글자")

    # 분할 (LangChain 있으면 사용, 없으면 순수 파이썬 fallback)
    engine = "LangChain(Recursive)" if HAS_LANGCHAIN else "Pure-Python(fallback)"
    if HAS_LANGCHAIN:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )
        chunks = splitter.split_text(text_data)
    else:
        chunks = simple_chunk(text_data, chunk_size, chunk_overlap)

    print("### 🧩 RAG Chunking 요약 리포트 (프롬프트 복붙용) ###")
    print(f"- 분할 엔진: {engine}")
    print(f"- 설정값: Chunk Size={chunk_size}, Overlap={chunk_overlap}")
    print(f"- 분할 결과: 총 {len(chunks)}개의 청크(Chunk) 생성")

    if chunks:
        lengths = [len(c) for c in chunks]
        print(f"- 청크 글자 수: 평균 {sum(lengths) // len(lengths)}자 "
              f"(최소 {min(lengths)} ~ 최대 {max(lengths)})")
        print(f"- 첫 번째 청크 미리보기:\n{chunks[0][:100]}...\n")

    # --- AI 지시용 빈칸 ---
    # "이 chunks 리스트를 입력받아 BM25나 TF-IDF로 가장 가볍게 검색(Retriever)하는 함수 1개만 추가해 줘.
    # 무거운 VectorDB나 임베딩 모델(OpenAI/HuggingFace) 연결은 절대 금지."


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python rag_chunking_safe.py <텍스트파일명.txt>")
        sys.exit(1)

    file_name = sys.argv[1]
    safe_chunk_text(file_name)
