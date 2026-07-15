# fixflawlaw

AI 컴플라이언스 진단 플랫폼 — 인공지능기본법·AI 윤리 기반 환경 진단 및 산출물 분석 Streamlit 앱.

## 로컬 실행

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

API 키 설정:

`.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` 로 복사한 뒤 `OPENAI_API_KEY` 값을 입력하세요.

```bash
streamlit run fixflawlaw__v1.py
```

## GitHub 배포 — 포함해야 할 파일

Streamlit Cloud는 저장소에 있는 파일만 읽을 수 있습니다. **파이썬 파일만 올리면** 이미지·법령 TXT·폰트를 찾지 못해 배포 후 오류가 납니다.

### 업로드 대상

| 구분 | 파일 경로 | 용도 |
|------|-----------|------|
| 실행 코드 | `fixflawlaw__v1.py` | `streamlit run fixflawlaw__v1.py` 로 실행하는 메인 파일 |
| 추가 파이썬 | *(없음)* | 단일 파일 앱 — `import` 하는 다른 `.py` 없음 |
| 이미지 | `assets/global_ai_regulation_models.png` | 글로벌 AI 규제 모델 비교 차트 |
| 이미지 | `assets/global_ai_regulation_eu_kr.png` | EU AI Act와 한국 AI 기본법 비교 |
| 폰트 | `assets/malgun.ttf` | PDF 보고서 한글 렌더링 |
| 텍스트 | `인공지능기본법.txt` | 법령 지식 베이스 (`open()` 으로 로드) |
| 데이터 (CSV/XLSX) | *(없음)* | 앱에서 사용하지 않음 |
| 페이지 | *(없음)* | `pages/` 멀티페이지 구조 미사용 |
| 설정 | `requirements.txt` | Python 패키지 (streamlit, openai, fpdf2) |
| 설정 | `packages.txt` | Linux 시스템 폰트 (`fonts-nanum`) |
| 설정 | `.streamlit/config.toml` | 테마·서버 설정 |
| 설정 | `.streamlit/secrets.toml.example` | Secrets 입력 예시 (실제 키 없음) |
| 기타 | `README.md`, `.gitignore` | 문서·Git 제외 규칙 |

### 업로드 금지 (비밀·로컬 전용)

| 파일 | 이유 |
|------|------|
| `.streamlit/secrets.toml` | OpenAI API 키 포함 → Cloud **Settings → Secrets** 에 직접 입력 |
| `key.env`, `.env` | API 키·환경 변수 (더 이상 앱에서 사용하지 않음) |
| `fixflawlaw_records.json` | 마이페이지 진단 기록 — 런타임에 자동 생성 |
| `__pycache__/`, `.venv/`, `venv/` | 로컬 캐시·가상환경 |

### 경로 확인

코드는 `APP_DIR`(프로젝트 폴더 기준) 상대경로만 사용합니다. `C:\Users\...` 같은 절대경로는 **없습니다**.

```python
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(APP_DIR, "assets")
TXT_FILE_PATH = os.path.join(APP_DIR, "인공지능기본법.txt")
```

### Git 업로드 명령어

```bash
git init
git add fixflawlaw__v1.py requirements.txt packages.txt README.md .gitignore \
  .streamlit/config.toml .streamlit/secrets.toml.example \
  assets/global_ai_regulation_models.png assets/global_ai_regulation_eu_kr.png assets/malgun.ttf \
  인공지능기본법.txt
git commit -m "Initial commit: fixflawlaw Streamlit app"
git branch -M main
git remote add origin https://github.com/<YOUR_USER>/<YOUR_REPO>.git
git push -u origin main
```

## Streamlit Community Cloud 배포

1. [share.streamlit.io](https://share.streamlit.io) 에서 GitHub 계정 연결
2. **New app** → Repository / Branch 선택
3. **Main file path:** `fixflawlaw__v1.py`
4. **App settings → Secrets** 에 아래 형식으로 입력:

```toml
OPENAI_API_KEY = "your-openai-api-key-here"
```

5. **Deploy** 클릭

### 참고

- 마이페이지 진단 기록은 Cloud 환경에서 세션/컨테이너 단위로 저장됩니다.
- `assets/malgun.ttf`는 PDF 한글 렌더링에 사용됩니다.
