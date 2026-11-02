"""repo_scan.py — 작업 폴더를 '한 덩어리 요약'으로 압축해 AI에 먹이는 도구.

과제를 시작하면 코딩 에이전트는 보통 파일을 하나씩 열어보며 탐색한다.
그 탐색 자체가 토큰을 먹는다. 이 도구로 작업 공간을 미리 요약해
첫 메시지에 한 번 붙여 주면, AI가 탐색 없이 바로 작업에 들어갈 수 있다.

출력:
  - 디렉토리 트리 (노이즈 폴더 제외)
  - .py  : 모듈 첫 줄 설명 + def/class 시그니처만
  - .md/.txt/.json : 앞부분 몇 줄
  - .csv : 헤더 + 행 수 (내용은 붙이지 않음 → 데이터는 data_advisor로)
  - 그 외/바이너리 : 이름만

사용법:
    python repo_scan.py           # 현재 폴더
    python repo_scan.py ./src     # 특정 폴더

표준 라이브러리만 사용한다.
"""

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 탐색에서 건너뛸 폴더 (노이즈)
SKIP_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "env", "node_modules",
    ".idea", ".vscode", ".pytest_cache", ".mypy_cache", "dist", "build",
}
# 내용을 붙이지 않고 이름만 보일 확장자 (바이너리/대용량)
BINARY_EXT = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pkl", ".joblib", ".h5", ".pt", ".pth", ".bin", ".zip", ".gz",
    ".tar", ".xlsx", ".parquet", ".db", ".sqlite", ".exe", ".dll",
}

MAX_FILES = 60          # 요약할 최대 파일 수
MAX_DEPTH = 4           # 트리 최대 깊이
HEAD_LINES = 10         # 텍스트 파일에서 보여줄 앞부분 줄 수
MAX_READ_BYTES = 200_000  # 이보다 큰 파일은 내용 생략


def read_head(path, n):
    """파일 앞부분 n줄을 인코딩 방어하며 읽는다."""
    for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= n:
                        break
                    lines.append(line.rstrip("\n"))
                return lines
        except UnicodeDecodeError:
            continue
        except Exception:
            return None
    return None


def py_signatures(path):
    """.py 파일에서 모듈 설명 첫 줄과 def/class 시그니처만 뽑는다."""
    out = []
    lines = read_head(path, 2000)
    if lines is None:
        return out
    # 모듈 docstring 첫 줄
    for ln in lines[:5]:
        s = ln.strip().strip('"').strip("'")
        if s:
            out.append(f'    """ {s[:80]}')
            break
    for ln in lines:
        s = ln.strip()
        if s.startswith("def ") or s.startswith("class ") \
                or s.startswith("async def "):
            out.append("    " + s.rstrip(":"))
    return out


def build_tree(root):
    """노이즈를 제외한 파일 목록과 트리 문자열을 만든다."""
    tree_lines = []
    files = []
    root = os.path.abspath(root)
    base = os.path.basename(root) or root
    tree_lines.append(base + "/")

    for dirpath, dirnames, filenames in os.walk(root):
        # 노이즈 폴더 제거 (in-place로 걸러야 os.walk가 안 들어감)
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS
                             and not d.startswith("."))
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > MAX_DEPTH:
            dirnames[:] = []
            continue
        indent = "  " * depth
        if rel != ".":
            tree_lines.append(f"{indent}{os.path.basename(dirpath)}/")
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            tree_lines.append(f"{indent}  {fn}")
            files.append(os.path.join(dirpath, fn))

    return tree_lines, files, root


def summarize_file(path, root):
    rel = os.path.relpath(path, root)
    ext = os.path.splitext(path)[1].lower()
    print(f"\n### {rel}")

    try:
        size = os.path.getsize(path)
    except OSError:
        print("  (읽을 수 없음)")
        return

    if ext in BINARY_EXT:
        print(f"  (바이너리/대용량, {size:,}바이트 — 이름만)")
        return

    # CSV는 크기와 무관하게 헤더+행 수를 보여준다.
    # 열 이름은 '첫 줄' 한 줄에만 있으므로, 파일이 아무리 커도 읽는 비용이 거의 없다.
    # (크기 가드보다 먼저 처리해, 큰 과제 데이터도 열 구조는 항상 드러나게 한다.)
    if ext == ".csv":
        head = read_head(path, 1)
        header = head[0] if head else "(헤더 없음)"
        # 행 수는 저렴하게 센다(값 파싱 없이 줄 개수만)
        try:
            with open(path, "rb") as f:
                n = sum(1 for _ in f)
        except Exception:
            n = -1
        big = "  ※대용량" if size > MAX_READ_BYTES else ""
        print(f"  헤더: {header[:120]}")
        print(f"  행 수: 약 {n:,}{big} (데이터 내용은 data_advisor.py로 요약)")
        return

    if size > MAX_READ_BYTES:
        print(f"  (큰 파일 {size:,}바이트 — 내용 생략)")
        return

    if ext == ".py":
        sigs = py_signatures(path)
        if sigs:
            print("\n".join(sigs))
        else:
            print("  (함수/클래스 없음)")
    else:
        head = read_head(path, HEAD_LINES)
        if head:
            for ln in head:
                print("  " + ln[:120])
        else:
            print("  (내용 없음)")


def scan(root):
    tree_lines, files, root = build_tree(root)

    print(f"# 작업 공간 요약 — {root}\n")
    print("## 디렉토리 트리")
    print("```")
    print("\n".join(tree_lines[:200]))
    print("```")

    print("\n## 파일 요약")
    if len(files) > MAX_FILES:
        print(f"(파일 {len(files)}개 중 상위 {MAX_FILES}개만 요약)")
        files = files[:MAX_FILES]
    for path in files:
        summarize_file(path, root)

    print("\n---")
    print("→ 이 요약을 Codex 첫 메시지에 붙여 맥락을 한 번에 주면, "
          "AI가 파일을 일일이 열어보지 않아 토큰을 아낍니다.")


def main():
    root = sys.argv[1] if len(sys.argv) >= 2 else "."
    if not os.path.isdir(root):
        print(f"폴더가 아닙니다: {root}")
        sys.exit(1)
    scan(root)


if __name__ == "__main__":
    main()
