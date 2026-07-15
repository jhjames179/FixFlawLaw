import streamlit as st
import json
import os
import random
import re
import shutil
from datetime import datetime
from fpdf import FPDF
from openai import OpenAI

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_openai_api_key() -> str | None:
    """Streamlit secrets에서 OpenAI API 키를 조회합니다."""
    try:
        key = st.secrets["OPENAI_API_KEY"]
        if key and str(key).strip():
            return str(key).strip()
    except (KeyError, FileNotFoundError, AttributeError, TypeError):
        pass
    return None


#---------------------------------------------------------------------------
# [환경 설정 및 API Key 로드]
#---------------------------------------------------------------------------
api_key = _load_openai_api_key()
if not api_key:
    st.error(
        "OpenAI API 키가 설정되지 않았습니다.\n\n"
        "**로컬 실행:** 프로젝트 폴더에 `.streamlit/secrets.toml` 파일을 만들고 "
        "`OPENAI_API_KEY = \"your-key\"` 를 입력하세요.\n\n"
        "**Streamlit Cloud:** 앱 **Settings → Secrets** 에 아래 형식으로 추가하세요.\n\n"
        "```toml\nOPENAI_API_KEY = \"your-key\"\n```"
    )
    st.stop()

MODEL_NAME = "gpt-5.5"
client = OpenAI(api_key=api_key)

#---------------------------------------------------------------------------
# [로컬 '인공지능기본법.txt' 파일 로드 및 지식 베이스화]
#---------------------------------------------------------------------------
@st.cache_data
def load_local_txt_guideline(file_path):
    if not os.path.exists(file_path):
        return "기본 지식 베이스 지침 적용됨", ""
    
    encodings = ["utf-8", "cp949", "utf-8-sig"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                text_content = f.read()
            return "✅ '인공지능기본법.txt' 법령 동기화 완료", text_content
        except UnicodeDecodeError:
            continue
    return "파일 인코딩 분석 실패", ""


@st.cache_data
def extract_article_text(law_text: str, article_num: str, title_keyword: str = "") -> str:
    """인공지능기본법.txt에서 특정 조문 본문을 추출합니다."""
    if not law_text:
        return ""
    marker = f"제{article_num}조({title_keyword}" if title_keyword else f"제{article_num}조("
    start = law_text.find(marker)
    if start == -1:
        return ""
    rest = law_text[start + len(marker):]
    m = re.search(r"\n\s*제\d+조\(", rest) or re.search(r"\n\s*제\d+조", rest)
    end = start + len(marker) + (m.start() if m else min(1200, len(law_text) - start))
    return law_text[start:end].strip()


def build_heavy_compute_law_citation(law_text: str) -> str:
    """대규모 연산량 관련 제32조 및 대통령령 위임 규정 인용문 생성."""
    art32 = extract_article_text(law_text, "32", "인공지능 안전성 확보 의무")
    if art32:
        return (
            "[인공지능 기본법 제32조 — 인공지능 안전성 확보 의무]\n"
            f"{art32}\n\n"
            "※ 위 조문에 따르면 '학습에 사용된 누적 연산량'의 구체적 기준·산정 방식·"
            "이행 결과 제출 절차 등은 「대통령령」으로 정합니다. "
            "귀사 모델이 해당 기준 이상이면 수명주기 전반의 위험 식별·평가·완화 및 "
            "안전사고 모니터링·대응 위험관리체계 구축 의무가 발생합니다."
        )
    return (
        "[인공지능 기본법 제32조 제1항] 인공지능사업자는 학습에 사용된 누적 연산량이 "
        "대통령령으로 정하는 기준 이상인 인공지능시스템의 안전성을 확보하기 위하여 "
        "① 인공지능 수명주기 전반에 걸친 위험의 식별·평가 및 완화, "
        "② 인공지능 관련 안전사고를 모니터링하고 대응하는 위험관리체계 구축을 이행하여야 합니다. "
        "구체적 누적 연산량 기준은 대통령령으로 정합니다."
    )


FALLBACK_ETHICS_KNOWLEDGE = [
    "🧠 [인간 존엄성 원칙] 인간의 가치는 기계보다 우선시되어야 하며, 인권보장·프라이버시 보호·다양성 존중·침해금지를 핵심으로 합니다.",
    "🛠️ [기술의 합목적성 원칙] AI는 인간의 삶을 돕는 도구여야 하며, 데이터 관리 거버넌스, 책임 주체 명확화, 상시 통제 및 투명성을 확보해야 합니다.",
    "🤝 [사회의 공공선 원칙] 사회적 약자의 접근성을 보장(정보격차 완화)하고 인류의 보편적 복지 향상과 연대성을 추구해야 합니다.",
]


def extract_ethics_section(law_text: str) -> str:
    """인공지능기본법.txt 하단 '-AI 윤리 상식' 섹션을 추출합니다."""
    if not law_text:
        return ""
    for marker in ("-AI 윤리 상식", "- AI 윤리 상식"):
        idx = law_text.find(marker)
        if idx != -1:
            return law_text[idx + len(marker):].strip()
    return ""


def build_ethics_knowledge_bank(law_text: str) -> list[str]:
    """인공지능기본법.txt 윤리 상식 섹션 및 관련 조문에서 오늘의 윤리 상식 목록을 생성합니다."""
    tips: list[str] = []

    if law_text:
        ethics_def = re.search(
            r'11\.\s*["""]?인공지능윤리["""]?란\s*(.+?)(?:\n\n|\n\s*12\.)',
            law_text,
            re.DOTALL,
        )
        if ethics_def:
            definition = re.sub(r"\s+", " ", ethics_def.group(1)).strip()
            tips.append(
                "⚖️ [인공지능 기본법 제2조 제11호 — 인공지능윤리] "
                f"{definition}"
            )

    if extract_article_text(law_text, "27", "인공지능 윤리원칙"):
        tips.append(
            "📜 [인공지능 기본법 제27조 — 윤리원칙] 정부는 안전성·신뢰성, 접근성, "
            "사람의 삶과 번영에의 공헌을 포함하는 인공지능 윤리원칙을 제정·공표할 수 있습니다. "
            "과기정통부 장관은 실천방안을 수립해 공개·홍보·교육해야 하며, "
            "타 기관의 윤리기준 제정 시 연계성·정합성에 관한 권고를 할 수 있습니다."
        )

    if extract_article_text(law_text, "28", "민간자율인공지능윤리위원회"):
        tips.append(
            "🏛️ [인공지능 기본법 제28조 — 민간자율위원회] 인공지능사업자·연구기관 등은 "
            "윤리원칙 준수를 위해 민간자율인공지능윤리위원회를 둘 수 있으며, "
            "윤리 준수 확인·안전·인권침해 조사·감독·교육·분야별 윤리 지침 마련 업무를 자율 수행합니다. "
            "특정 성별로만 구성할 수 없고, 외부 전문가를 포함해야 합니다."
        )

    ethics = extract_ethics_section(law_text)

    theme_tips = [
        (
            "Accenture",
            "📊 [신뢰 조사 — Accenture]",
            "전 세계 소비자의 35%만이 조직의 AI 기술 구현 방식을 신뢰하며, "
            "77%는 조직이 AI 오용에 대해 책임을 져야 한다고 응답했습니다. "
            "투명성·안전성·책임성 확보가 신뢰 인프라의 핵심입니다.",
        ),
        (
            "신뢰를 구축하기 위해",
            "🛡️ [신뢰성·안전성]",
            "AI 시스템은 설계대로 작동하고, 예기치 않은 조건에 안전하게 대응하며, "
            "유해한 조작에 저항해야 합니다. 개발·테스트 단계에서 예상 상황 범위를 충분히 반영해야 합니다.",
        ),
        (
            "사람들은 이러한 결정이",
            "🔍 [설명 가능성]",
            "신용 심사·채용 선발 등 삶에 영향을 주는 결정에서 이용자는 판단 근거를 이해할 권리가 있습니다. "
            "인공지능 기본법 제3조 제2항의 설명 제공 권리와 직결됩니다.",
        ),
        (
            "개인 정보 보호",
            "🔒 [프라이버시·데이터 보안]",
            "AI는 정확한 예측을 위해 데이터가 필요하므로 개인정보 보호법 준수와 데이터 보안 설계가 필수입니다. "
            "생성형·에이전트 AI 활용 시 민감 정보 유출 방지 체계를 갖추어야 합니다.",
        ),
        (
            "책임을 져야 합니다",
            "⚖️ [책임성·인간 통제]",
            "시스템 설계·배포자는 작동 방식에 책임을 지며, AI가 최종 결정권자가 아니도록 "
            "인간이 의미 있는 제어를 유지하는 업계 책임 규범이 필요합니다.",
        ),
        (
            "책임 있는 AI",
            "🤝 [책임 있는 AI]",
            "시스템 목적 정의부터 사용자 상호작용까지 모든 설계 결정에서 사람과 목표를 중심에 두고, "
            "공정성·신뢰성·투명성을 존중하는 접근입니다.",
        ),
        (
            "2010년대",
            "📈 [AI 윤리의 부상]",
            "빅데이터와 컴퓨팅 파워 확대로 머신러닝이 대중화되면서 편향·투명성·개인데이터 사용 문제가 대두되어 "
            "AI 윤리가 독립 분야로 성장했습니다.",
        ),
        (
            "투명해야 합니다",
            "💡 [투명성]",
            "이해관계자의 신뢰를 얻으려면 학습 데이터·알고리즘·추천 근거를 가능한 범위에서 명확히 밝혀야 하며, "
            "중요한 결정에 AI를 쓸 때는 그 이유를 설명할 수 있어야 합니다.",
        ),
    ]
    if ethics:
        for keyword, title, content in theme_tips:
            if keyword in ethics:
                tips.append(f"{title} {content}")

        capability_tips = [
            (
                "예측 정확도",
                "📐 [예측 정확도]",
                "시뮬레이션과 아웃풋·학습 데이터 비교로 판단하며, "
                "LIME(Local Interpretable Model-agnostic Explanations)이 분류기 예측 설명에 널리 쓰입니다.",
            ),
            (
                "추적성",
                "🔗 [추적성]",
                "데이터 문서화와 모델의 처리 경로를 추적할 수 있는 속성으로, 설명 가능성 달성의 핵심 기술입니다. "
                "의사결정 범위를 제한하고 규칙·기능 범위를 좁혀 구현할 수 있습니다.",
            ),
            (
                "의사 결정 이해",
                "👤 [의사 결정 이해]",
                "실무자는 AI 결론 도출 방식과 이유를 이해할 수 있어야 하며, "
                "지속적인 교육·정책 소통 채널을 통해 달성합니다.",
            ),
            (
                "공정성",
                "⚖️ [공정성]",
                "머신러닝의 통계적 차별이 특권·비특권 집단에 제도적으로 불리하게 작용하지 않도록, "
                "라벨 편향·과소·과잉 샘플링 등 학습 데이터 편향을 점검해야 합니다.",
            ),
        ]
        for keyword, title, content in capability_tips:
            if keyword in ethics:
                tips.append(f"{title} {content}")

        principle_tips = [
            (
                "1. 인간 존엄성 원칙",
                "🧠 [인간 존엄성 원칙]",
                "인간의 가치는 어떤 기계보다 우선하며, 정신·신체 건강에 해가 되지 않도록 안정성·견고성을 갖춰야 합니다. "
                "인권보장·프라이버시 보호·다양성 존중·침해금지가 핵심 요건입니다.",
            ),
            (
                "2. 사회의 공공선 원칙",
                "🤝 [사회의 공공선 원칙]",
                "사회적 약자 접근성 보장(정보격차 완화), 인류 보편 복지, 미래 세대를 배려하는 연대성, "
                "공정한 참여 기회 제공을 추구합니다.",
            ),
            (
                "3. 기술의 합목적성 원칙",
                "🛠️ [기술의 합목적성 원칙]",
                "AI는 인간을 돕는 도구이며 본래 목적에 부합해야 합니다. "
                "데이터 관리·책임성·안정성(비상 통제)·투명성(사전 정보 제공)을 확보해야 합니다.",
            ),
        ]
        for keyword, title, content in principle_tips:
            if keyword in ethics:
                tips.append(f"{title} {content}")

        category_icons = {
            "인권보장": "🧠",
            "프라이버시": "🔒",
            "다양성": "🌈",
            "침해금지": "🚫",
            "공공성": "🌍",
            "연대성": "🤲",
            "데이터 관리": "💾",
            "책임성": "⚖️",
            "안전성": "🛡️",
            "투명성": "💡",
        }
        for line in ethics.splitlines():
            line = line.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            name, desc = line[2:].split(":", 1)
            icon = "📌"
            for cat, cat_icon in category_icons.items():
                if cat in name:
                    icon = cat_icon
                    break
            tips.append(f"{icon} [{name.strip()}] {desc.strip()}")

        if "가상 결과물" in ethics:
            tips.append(
                "🎬 [가상 결과물] AI·CG·VR 등으로 생성된 실제 존재하지 않는 디지털 콘텐츠를 말합니다. "
                "인공지능 기본법 제31조 제3항에 따라 실제와 구분하기 어려운 경우 "
                "이용자가 명확히 인식할 수 있도록 고지·표시해야 합니다."
            )

    seen: set[str] = set()
    unique: list[str] = []
    for tip in tips:
        if tip not in seen:
            seen.add(tip)
            unique.append(tip)

    return unique if unique else FALLBACK_ETHICS_KNOWLEDGE

#---------------------------------------------------------------------------
# [페이지 기본 설정 및 프리미엄 블루 커스텀 테마 디자인]
#---------------------------------------------------------------------------
st.set_page_config(
    page_title="fixflawlaw",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def _ensure_fpdf2():
    return FPDF


_ensure_fpdf2()

# 프리미엄 딥 블루 UI 테마 — 전역 적용
st.markdown(
    """
    <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

        :root {
            --bg-page: #F1F5F9;
            --bg-card: #FFFFFF;
            --text-primary: #1E293B;
            --text-secondary: #64748B;
            --blue: #2563EB;
            --blue-dark: #1D4ED8;
            --blue-light: #DBEAFE;
            --green: #22C55E;
            --green-dark: #16A34A;
            --green-light: #DCFCE7;
            --orange: #F97316;
            --orange-light: #FFEDD5;
            --red: #EF4444;
            --red-light: #FEE2E2;
            --border: #E2E8F0;
            --shadow: 0 1px 3px rgba(15,23,42,0.06), 0 4px 16px rgba(15,23,42,0.04);
            --radius: 12px;
            --blue-50: #EFF6FF;
            --blue-100: #DBEAFE;
            --blue-200: #BFDBFE;
            --blue-300: #93C5FD;
            --blue-600: #2563EB;
            --blue-700: #1D4ED8;
            --blue-800: #1E40AF;
            --blue-900: #1E3A8A;
        }

        html, body {
            background: var(--bg-page) !important;
            background-color: var(--bg-page) !important;
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            min-height: 100% !important;
            overflow-x: hidden;
        }
        #root, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > section,
        [data-testid="stAppViewContainer"] .main, section.main, .stApp, [data-testid="stMain"] {
            background: var(--bg-page) !important;
            background-color: var(--bg-page) !important;
        }
        .stApp {
            --primary-color: #2563EB;
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
            color: var(--text-primary);
            min-height: 100vh;
            min-height: 100dvh;
            width: 100% !important;
        }
        header[data-testid="stHeader"] {
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
        }
        h1 { border-bottom: none; padding-bottom: 0; }
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        footer {
            background: transparent !important;
            background-color: transparent !important;
        }
        .main .block-container {
            width: 100% !important;
            max-width: min(1280px, 100%) !important;
            padding-top: 0.5rem;
            padding-bottom: clamp(1rem, 3vh, 2.5rem);
            padding-left: clamp(0.75rem, 2.5vw, 2rem);
            padding-right: clamp(0.75rem, 2.5vw, 2rem);
            margin-left: auto;
            margin-right: auto;
            box-sizing: border-box;
        }
        p, li, span, label, .stMarkdown { color: var(--text-primary); }
        h1, h2, h3, h4, h5, h6 {
            color: var(--text-primary) !important;
            font-family: 'Pretendard', sans-serif;
            font-weight: 700;
        }

        /* ── 탭 네비게이션 ── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background: var(--bg-card);
            border-radius: var(--radius);
            padding: 10px 14px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
        }
        .stTabs [data-baseweb="tab-list"] button[data-baseweb="tab"] {
            flex: 1 1 0 !important;
            min-width: 0 !important;
            min-height: 52px;
            padding: 0.85rem 0.5rem !important;
            margin: 0 !important;
        }
        .stTabs [data-baseweb="tab"] {
            background: transparent;
            color: var(--text-secondary);
            border-radius: 10px;
            font-weight: 600;
            font-size: 1.05rem !important;
            line-height: 1.4 !important;
            letter-spacing: -0.01em;
        }
        .stTabs [data-baseweb="tab"] p,
        .stTabs [data-baseweb="tab"] span,
        .stTabs [data-baseweb="tab"] div {
            font-size: 1.05rem !important;
            line-height: 1.4 !important;
            white-space: nowrap;
        }
        .stTabs [aria-selected="true"] {
            background: var(--blue) !important;
            color: #FFFFFF !important;
            box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
        }
        .stTabs [aria-selected="true"] p,
        .stTabs [aria-selected="true"] span,
        .stTabs [aria-selected="true"] div {
            color: #FFFFFF !important;
        }
        .stTabs [data-baseweb="tab-highlight"] { background: var(--blue) !important; height: 3px !important; }
        .stTabs [data-baseweb="tab-panel"] { background: transparent; padding-top: 1.5rem; }

        /* ── 버튼 ── */
        div.stButton > button, div.stFormSubmitButton > button, div[data-testid="stDownloadButton"] > button {
            background: var(--blue) !important; color: #FFFFFF !important;
            border-radius: 999px !important; border: none !important;
            padding: 0.7rem 1.75rem !important;
            min-height: 44px;
            font-size: 1rem !important;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(37,99,235,0.25);
        }
        div.stButton > button:hover, div.stFormSubmitButton > button:hover {
            background: var(--blue-dark) !important;
        }

        /* ── 알림·상태 박스 ── */
        .stAlert, div[data-testid="stNotification"],
        div[data-testid="stInfo"], div[data-testid="stSuccess"],
        div[data-testid="stWarning"], div[data-testid="stError"] {
            border-left: 5px solid var(--blue-800) !important;
            background-color: var(--blue-100) !important;
            color: var(--blue-900) !important;
            border-radius: 8px;
        }
        div[data-testid="stInfo"] { background-color: var(--blue-light) !important; border: 1px solid var(--blue-200) !important; }
        div[data-testid="stSuccess"] { background-color: var(--green-light) !important; border-left-color: var(--green) !important; }
        div[data-testid="stWarning"] { background-color: var(--orange-light) !important; border-left-color: var(--orange) !important; }
        div[data-testid="stError"] { background-color: var(--red-light) !important; border-left-color: var(--red) !important; }

        /* ── 프로그레스·스피너 ── */
        div.stProgress > div > div > div > div { background: var(--blue) !important; }
        div[data-testid="stSpinner"] {
            color: var(--blue-800) !important;
        }
        div[data-testid="stSpinner"] svg {
            stroke: var(--blue-600) !important;
        }

        /* ── 텍스트 입력·숫자·텍스트영역 ── */
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {
            background-color: var(--bg-card) !important;
            border: 1.5px solid var(--border) !important;
            color: var(--text-primary) !important;
            border-radius: 8px !important;
        }
        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stNumberInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus,
        div[data-baseweb="input"]:focus-within > div,
        div[data-baseweb="textarea"]:focus-within > div {
            border-color: var(--blue-600) !important;
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.25) !important;
        }
        div[data-testid="stTextInput"] label,
        div[data-testid="stNumberInput"] label,
        div[data-testid="stTextArea"] label,
        div[data-testid="stSelectbox"] label,
        div[data-testid="stMultiSelect"] label,
        div[data-testid="stRadio"] label,
        div[data-testid="stCheckbox"] label,
        div[data-testid="stFileUploader"] label {
            color: var(--blue-800) !important;
            font-weight: 600;
        }

        /* ── Selectbox·Multiselect (전역) ── */
        div[data-baseweb="select"] > div {
            background-color: var(--blue-50) !important;
            border-color: var(--blue-300) !important;
            color: var(--blue-900) !important;
            border-radius: 8px !important;
        }
        div[data-baseweb="select"]:hover > div,
        div[data-baseweb="select"]:focus-within > div {
            border-color: var(--blue-600) !important;
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2) !important;
        }
        [data-baseweb="tag"] {
            background-color: var(--blue-800) !important;
            color: #FFFFFF !important;
            border: 1px solid var(--blue-900) !important;
        }
        [data-baseweb="tag"] *,
        [data-baseweb="tag"] span,
        [data-baseweb="tag"] button {
            color: #FFFFFF !important;
        }
        [data-baseweb="tag"] svg,
        [data-baseweb="tag"] svg path {
            fill: #FFFFFF !important;
            stroke: #FFFFFF !important;
        }
        div[data-baseweb="popover"] ul,
        div[data-baseweb="menu"],
        div[role="listbox"] {
            background-color: var(--blue-50) !important;
            border: 1px solid var(--blue-400) !important;
            box-shadow: 0 8px 24px rgba(30, 58, 138, 0.2) !important;
        }
        div[data-baseweb="popover"] li,
        div[role="option"] {
            color: var(--blue-900) !important;
            background-color: var(--blue-50) !important;
        }
        div[data-baseweb="popover"] li:hover,
        div[role="option"]:hover {
            background-color: var(--blue-200) !important;
        }
        div[aria-selected="true"][role="option"] {
            background-color: var(--blue-700) !important;
            color: #FFFFFF !important;
        }

        /* ── Radio·Checkbox (전역) ── */
        .stCheckbox {
            background-color: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.5rem 0.75rem;
        }
        .stRadio label, .stCheckbox label {
            color: var(--blue-900) !important;
        }
        /* 체크박스 */
        label[data-baseweb="checkbox"] > div {
            border-color: var(--blue-400) !important;
            background-color: var(--blue-100) !important;
        }
        label[data-baseweb="checkbox"][aria-checked="true"] > div {
            background-color: var(--blue-700) !important;
            border-color: var(--blue-800) !important;
        }
        label[data-baseweb="checkbox"][aria-checked="true"] svg {
            fill: #FFFFFF !important;
        }
        /* 라디오 — 선택된 동그라미만 파랑, 선지 텍스트는 기본 스타일 유지 */
        label[data-baseweb="radio"][aria-checked="true"] > div {
            background-color: var(--blue-700) !important;
            border-color: var(--blue-800) !important;
        }
        /* ── 파일 업로더 ── */
        div[data-testid="stFileUploader"] section {
            background-color: var(--blue-50) !important;
            border: 2px dashed var(--blue-400) !important;
            border-radius: 10px !important;
        }
        div[data-testid="stFileUploader"] section:hover {
            border-color: var(--blue-600) !important;
            background-color: var(--blue-100) !important;
        }
        div[data-testid="stFileUploader"] button {
            background: var(--blue-700) !important;
            color: #FFFFFF !important;
            border: none !important;
        }
        div[data-testid="stFileUploader"] small {
            color: var(--blue-700) !important;
        }

        /* ── 슬라이더·토글 ── */
        div[data-baseweb="slider"] div[data-testid="stThumbValue"],
        div[data-baseweb="slider"] [role="slider"] {
            background-color: var(--blue-600) !important;
        }
        div[data-baseweb="slider"] > div > div {
            background: var(--blue-200) !important;
        }
        div[data-baseweb="slider"] > div > div > div {
            background: var(--blue-600) !important;
        }
        div[data-testid="stToggle"] label {
            color: var(--blue-900) !important;
        }

        /* ── Expander ── */
        details[data-testid="stExpander"] {
            border: 1px solid var(--blue-300) !important;
            border-radius: 10px !important;
            background-color: var(--blue-50) !important;
        }
        details[data-testid="stExpander"] summary {
            color: var(--blue-800) !important;
            font-weight: 600;
        }
        details[data-testid="stExpander"] summary svg {
            fill: var(--blue-700) !important;
        }

        /* ── 메트릭·카드·구분선 ── */
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid var(--blue-200);
            border-radius: 10px;
            padding: 12px 16px;
            box-shadow: 0 2px 6px rgba(30, 64, 175, 0.1);
        }
        div[data-testid="stMetric"] label { color: var(--blue-800) !important; }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: var(--blue-900) !important; }
        div[data-testid="stMetric"] [data-testid="stMetricDelta"] svg { fill: var(--blue-600) !important; }
        hr { border-color: var(--blue-300) !important; }

        /* ── 테이블·데이터프레임 ── */
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--blue-300);
            border-radius: 8px;
            overflow: hidden;
        }
        div[data-testid="stDataFrame"] div[role="grid"] {
            background-color: var(--blue-50) !important;
        }
        div[data-testid="stDataFrame"] div[role="columnheader"] {
            background-color: var(--blue-200) !important;
            color: var(--blue-900) !important;
        }

        /* ── 코드 블록 ── */
        code, pre {
            background-color: var(--blue-100) !important;
            color: var(--blue-900) !important;
            border: 1px solid var(--blue-300);
            border-radius: 6px;
        }

        /* ── 툴팁·도움말 ── */
        span[data-testid="stTooltipIcon"] {
            color: var(--blue-600) !important;
            font-weight: bold;
        }
        span[data-testid="stTooltipIcon"]:hover { color: var(--blue-700) !important; }
        /* 래퍼 레이어: 배경·테두리 제거 (겹친 네모칸 방지) */
        div[data-baseweb="popover"]:has([data-testid="stTooltipContent"]),
        div[data-baseweb="popover"]:has([data-testid="stTooltipContent"]) > div,
        div[data-baseweb="popover"]:has([data-testid="stTooltipContent"]) > div > div,
        div[data-baseweb="tooltip"],
        div[data-baseweb="tooltip"] > div,
        div[role="tooltip"] {
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: visible !important;
        }
        /* 실제 툴팁 박스: 단일 레이어만 스타일 (연한 파랑) */
        [data-testid="stTooltipContent"] {
            background-color: var(--blue-600) !important;
            color: #FFFFFF !important;
            border: 1px solid var(--blue-500) !important;
            border-radius: 8px !important;
            padding: 0.65rem 0.9rem !important;
            max-width: 28rem !important;
            min-width: 0 !important;
            width: max-content !important;
            white-space: normal !important;
            word-break: keep-all !important;
            overflow-wrap: break-word !important;
            line-height: 1.55 !important;
            font-size: 0.9rem !important;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2) !important;
            z-index: 999999 !important;
            opacity: 1 !important;
            visibility: visible !important;
        }
        [data-testid="stTooltipContent"] * {
            color: #FFFFFF !important;
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
        }

        /* ── 상단 헤더 (브랜드 + 탭) ── */
        .app-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 0.75rem 1.25rem;
            margin-bottom: 1.25rem;
            box-shadow: var(--shadow);
            flex-wrap: nowrap;
            overflow: hidden;
            width: 100%;
            box-sizing: border-box;
        }
        .header-brand {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            flex-shrink: 0;
            min-width: 0;
        }
        .nav-logo {
            background: var(--blue);
            color: #fff;
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .nav-logo svg { width: 22px; height: 22px; stroke: #fff; fill: none; }
        .brand-name {
            font-size: 1.05rem;
            font-weight: 800;
            color: var(--text-primary);
            line-height: 1.2;
        }
        .brand-sub {
            font-size: 0.72rem;
            color: var(--text-secondary);
            font-weight: 500;
            line-height: 1.2;
            margin-top: 0.1rem;
        }
        .header-nav {
            display: flex;
            align-items: center;
            gap: 0.25rem;
            flex: 1 1 auto;
            justify-content: flex-end;
            min-width: 0;
            flex-wrap: nowrap;
            overflow-x: auto;
            overflow-y: hidden;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: thin;
        }
        .header-nav::-webkit-scrollbar { height: 4px; }
        .nav-tab {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.55rem 0.7rem;
            border-radius: 10px;
            text-decoration: none !important;
            color: var(--text-secondary) !important;
            font-size: 0.78rem;
            font-weight: 600;
            white-space: nowrap;
            flex-shrink: 0;
            transition: background 0.15s, color 0.15s;
        }
        .nav-tab svg {
            width: 16px;
            height: 16px;
            stroke: currentColor;
            fill: none;
            flex-shrink: 0;
        }
        .nav-tab:hover {
            background: var(--blue-light);
            color: var(--blue) !important;
        }
        .nav-tab.nav-tab-active {
            background: #EFF6FF;
            color: var(--blue) !important;
        }
        .nav-tab span { color: inherit !important; }

        /* ── 디자인 컴포넌트 (레거시) ── */
        .app-navbar {
            display: none;
        }

        .hero-card {
            background: linear-gradient(135deg, #EFF6FF 0%, #FFFFFF 60%);
            border: 1px solid var(--border); border-radius: 16px;
            padding: 2rem 2.5rem; margin-bottom: 1.25rem; box-shadow: var(--shadow);
        }
        .hero-title { font-size: 1.75rem; font-weight: 800; color: var(--text-primary); margin: 0 0 0.5rem 0; }
        .hero-sub { color: var(--text-secondary); font-size: 1rem; margin-bottom: 1.25rem; }

        .dash-card {
            background: var(--bg-card); border: 1px solid var(--border);
            border-radius: var(--radius); padding: 1.25rem; box-shadow: var(--shadow); text-align: center;
        }
        .dash-card .dash-val { font-size: 1.75rem; font-weight: 800; margin: 0.25rem 0; }
        .dash-card .dash-lbl { font-size: 0.8rem; color: var(--text-secondary); font-weight: 500; }
        .dash-safe { color: var(--green); }
        .dash-warn { color: var(--orange); }
        .dash-danger { color: var(--red); }

        .gauge-circle {
            width: 100px; height: 100px; border-radius: 50%;
            border: 6px solid var(--green); display: flex; flex-direction: column;
            align-items: center; justify-content: center; margin: 0 auto;
            background: var(--green-light);
        }
        .gauge-score { font-size: 1.6rem; font-weight: 800; color: var(--green-dark); line-height: 1; }
        .gauge-label { font-size: 0.7rem; color: var(--green-dark); font-weight: 600; }

        .category-card {
            background: var(--bg-card); border: 1px solid var(--border);
            border-radius: var(--radius); padding: 1.25rem; box-shadow: var(--shadow);
            transition: transform 0.15s, box-shadow 0.15s; cursor: default; height: 100%;
        }
        .category-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(15,23,42,0.08); }
        .category-icon { font-size: 1.5rem; margin-bottom: 0.5rem; }
        .category-title { font-weight: 700; font-size: 0.95rem; color: var(--text-primary); margin-bottom: 0.25rem; line-height: 1.35; }
        .category-desc { font-size: 0.8rem; color: var(--text-secondary); line-height: 1.4; }

        .stepper { display: flex; align-items: center; gap: 0; margin-bottom: 1.5rem; flex-wrap: nowrap; width: 100%; }
        .step-item { display: flex; align-items: center; justify-content: center; gap: 0.4rem; padding: 0.5rem 0.5rem;
            border-radius: 8px; font-size: 0.8rem; color: var(--text-secondary); font-weight: 500;
            flex: 1 1 0; min-width: 0; white-space: nowrap; }
        .step-item span:last-child { overflow: hidden; text-overflow: ellipsis; }
        .step-item.step-active { background: var(--blue-light); color: var(--blue); font-weight: 700; }
        .step-item.step-done { color: var(--green-dark); }
        .step-num { background: var(--border); color: var(--text-secondary); width: 24px; height: 24px;
            border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
            font-size: 0.7rem; font-weight: 700; }
        .step-active .step-num { background: var(--blue); color: #fff; }
        .step-done .step-num { background: var(--green); color: #fff; }
        .step-line { width: 24px; height: 2px; background: var(--border); }

        .law-card {
            background: var(--bg-card); border: 1px solid var(--border);
            border-radius: var(--radius); padding: 1.25rem; box-shadow: var(--shadow); height: 100%;
        }
        .law-card-icon { font-size: 1.4rem; margin-bottom: 0.5rem; }
        .law-card-title { font-weight: 700; font-size: 0.95rem; color: var(--text-primary); margin-bottom: 0.35rem; }
        .law-card-desc { font-size: 0.82rem; color: var(--text-secondary); line-height: 1.5; }
        .law-card-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            grid-auto-rows: 1fr;
            gap: 1rem;
            margin-top: 0.75rem;
        }
        .law-card-grid .law-card {
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        .ethics-core-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 0.75rem;
            margin-bottom: 1.25rem;
        }
        .ethics-core-card {
            display: flex;
            align-items: flex-start;
            gap: 0.9rem;
            min-height: 142px;
            padding: 1.2rem;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            box-sizing: border-box;
        }
        .ethics-core-icon {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 42px;
            height: 42px;
            flex: 0 0 42px;
            border-radius: 11px;
            background: var(--blue-light);
            font-size: 1.25rem;
        }
        .ethics-core-content { flex: 1; min-width: 0; }
        .ethics-core-head {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            margin-bottom: 0.45rem;
        }
        .ethics-core-number {
            color: var(--blue);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.04em;
        }
        .ethics-core-title {
            color: var(--text-primary);
            font-size: 0.95rem;
            font-weight: 750;
        }
        .ethics-core-desc {
            color: var(--text-secondary);
            font-size: 0.82rem;
            line-height: 1.55;
            word-break: keep-all;
        }
        @media (max-width: 768px) {
            .ethics-core-grid { grid-template-columns: 1fr; gap: 0.75rem; }
            .ethics-core-card { min-height: 0; }
        }

        .ai-generated-label {
            text-align: center;
            color: #64748B;
            font-size: 0.88rem;
            margin: 0.75rem 0 1.5rem;
            padding: 0.55rem 0.75rem;
            background: #F8FAFC;
            border: 1px dashed #CBD5E1;
            border-radius: 8px;
        }
        .global-reg-caption {
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin: 0.75rem 0 0;
            line-height: 1.45;
        }
        .global-source-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 0.75rem;
        }
        .global-source-region {
            font-size: 0.88rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 0.45rem;
        }
        .global-source-list {
            margin: 0;
            padding-left: 1.1rem;
            color: var(--text-secondary);
            font-size: 0.82rem;
            line-height: 1.55;
        }
        .global-source-list a {
            color: var(--blue);
            text-decoration: none;
        }
        .global-source-list a:hover { text-decoration: underline; }
        @media (max-width: 768px) {
            .global-source-grid { grid-template-columns: 1fr; }
        }
        .category-card-link,
        .category-card-link:visited,
        .category-card-link:hover,
        .category-card-link:active,
        .category-card-link:focus {
            text-decoration: none !important;
            color: inherit !important;
            display: block;
            height: 100%;
            border: none !important;
            box-shadow: none !important;
        }
        .category-card-link .category-title {
            color: var(--text-primary) !important;
            text-decoration: none !important;
        }
        .category-card-link .category-desc {
            color: var(--text-secondary) !important;
            text-decoration: none !important;
        }
        .category-card-link .category-icon {
            text-decoration: none !important;
        }
        .category-card-link .category-card {
            cursor: pointer;
        }
        .category-card-link:hover .category-card {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(15,23,42,0.08);
        }

        .content-card {
            background: var(--bg-card); border: 1px solid var(--border);
            border-radius: var(--radius); padding: 1.5rem; box-shadow: var(--shadow); margin-bottom: 1rem;
        }

        .quiz-card {
            background: var(--bg-card); border: 1px solid var(--border);
            border-left: 4px solid var(--blue); border-radius: var(--radius);
            padding: 1.25rem 1.5rem; margin-bottom: 1rem; box-shadow: var(--shadow);
        }
        .quiz-progress-label { font-size: 0.85rem; color: var(--text-secondary); font-weight: 600; margin-bottom: 0.25rem; }
        .wizard-progress-label { font-size: 0.85rem; color: var(--text-secondary); font-weight: 600; margin-bottom: 0.35rem; }

        .score-panel {
            background: var(--bg-card); border: 1px solid var(--border);
            border-radius: var(--radius); padding: 1.25rem; box-shadow: var(--shadow);
        }
        .score-panel h4 { margin: 0 0 1rem 0; font-size: 0.95rem; color: var(--text-primary); }
        .score-item { display: flex; justify-content: space-between; padding: 0.5rem 0;
            border-bottom: 1px solid var(--border); font-size: 0.85rem; }
        .score-item:last-child { border-bottom: none; }
        .score-val { font-weight: 700; color: var(--blue); }

        .risk-tag-high { background: var(--red-light); color: var(--red); padding: 0.3rem 0.75rem;
            border-radius: 999px; font-size: 0.8rem; font-weight: 600; display: inline-block; }
        .risk-tag-mid { background: var(--orange-light); color: var(--orange); padding: 0.3rem 0.75rem;
            border-radius: 999px; font-size: 0.8rem; font-weight: 600; display: inline-block; }
        .risk-tag-low { background: var(--green-light); color: var(--green-dark); padding: 0.3rem 0.75rem;
            border-radius: 999px; font-size: 0.8rem; font-weight: 600; display: inline-block; }

        .action-item-card {
            background: var(--green-light); border: 1px solid #BBF7D0;
            border-radius: 10px; padding: 0.85rem 1rem; margin: 0.4rem 0;
            display: flex; gap: 0.75rem; align-items: flex-start;
        }
        .action-num { background: var(--green); color: #fff; width: 24px; height: 24px;
            border-radius: 50%; display: flex; align-items: center; justify-content: center;
            font-size: 0.75rem; font-weight: 700; flex-shrink: 0; }

        .report-preview {
            background: var(--bg-card); border: 1px solid var(--border);
            border-radius: var(--radius); padding: 2rem; box-shadow: var(--shadow);
        }
        .report-header { text-align: center; border-bottom: 2px solid var(--border); padding-bottom: 1rem; margin-bottom: 1.5rem; }
        .report-title { font-size: 1.25rem; font-weight: 800; color: var(--text-primary); }

        .risk-status-high { color: var(--red) !important; font-weight: bold; }
        .risk-status-mid  { color: var(--orange) !important; font-weight: bold; }
        .risk-status-low  { color: var(--green-dark) !important; font-weight: bold; }

        /* ── 마이페이지 ── */
        .mp-page-header { margin-bottom: 1.25rem; }
        .mp-page-title { font-size: 1.65rem; font-weight: 800; color: var(--text-primary); margin: 0 0 0.35rem 0; }
        .mp-page-sub { font-size: 0.92rem; color: var(--text-secondary); margin: 0; }
        .mp-hero {
            display: flex; align-items: stretch; gap: 1.25rem;
            background: var(--bg-card); border: 1px solid var(--border);
            border-radius: 14px; padding: 1.35rem 1.5rem; margin-bottom: 1.25rem;
            box-shadow: var(--shadow); flex-wrap: wrap;
        }
        .mp-hero-profile {
            display: flex; gap: 1rem; align-items: flex-start;
            flex: 0 0 220px; min-width: 200px;
        }
        .mp-hero-icon {
            width: 52px; height: 52px; border-radius: 12px;
            background: linear-gradient(135deg, #3B82F6, #2563EB);
            display: flex; align-items: center; justify-content: center;
            font-size: 1.5rem; flex-shrink: 0;
        }
        .mp-hero-name { font-size: 1.15rem; font-weight: 800; color: var(--text-primary); margin: 0 0 0.2rem 0; }
        .mp-hero-date { font-size: 0.78rem; color: var(--text-secondary); margin: 0 0 0.55rem 0; }
        .mp-hero-tags { display: flex; flex-wrap: wrap; gap: 0.35rem; }
        .mp-tag {
            font-size: 0.72rem; font-weight: 600; padding: 0.22rem 0.55rem;
            border-radius: 999px; background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE;
        }
        .mp-hero-metrics {
            display: flex; flex: 1 1 auto; gap: 0.75rem; min-width: 0; flex-wrap: wrap;
        }
        .mp-metric {
            flex: 1 1 0; min-width: 120px;
            background: #FAFBFC; border: 1px solid var(--border);
            border-radius: 12px; padding: 0.85rem 1rem;
        }
        .mp-metric-label { font-size: 0.78rem; color: var(--text-secondary); font-weight: 600; margin-bottom: 0.35rem; }
        .mp-metric-score { font-size: 1.55rem; font-weight: 800; color: var(--text-primary); line-height: 1.1; }
        .mp-metric-score span { font-size: 0.95rem; font-weight: 600; color: var(--text-secondary); }
        .mp-bar { height: 5px; background: #E5E7EB; border-radius: 999px; margin-top: 0.55rem; overflow: hidden; }
        .mp-bar-fill { height: 100%; border-radius: 999px; transition: width 0.3s; }
        .mp-risk-value { font-size: 1.65rem; font-weight: 800; color: var(--text-primary); line-height: 1.1; }
        .mp-risk-icon { font-size: 1.1rem; margin-bottom: 0.15rem; }
        .mp-risk-badge {
            display: inline-block; margin-top: 0.45rem; font-size: 0.72rem; font-weight: 700;
            padding: 0.2rem 0.55rem; border-radius: 999px;
        }
        .mp-risk-badge-low { background: #DCFCE7; color: #15803D; }
        .mp-risk-badge-mid { background: #FFEDD5; color: #C2410C; }
        .mp-risk-badge-high { background: #FEE2E2; color: #B91C1C; }
        .mp-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }
        @media (max-width: 900px) { .mp-grid { grid-template-columns: 1fr; } }
        .mp-section {
            background: var(--bg-card); border: 1px solid var(--border);
            border-radius: 14px; padding: 1.15rem 1.25rem; margin-bottom: 1rem;
            box-shadow: var(--shadow);
        }
        .mp-section-title {
            font-size: 0.98rem; font-weight: 800; color: var(--text-primary);
            margin: 0 0 0.85rem 0; padding-bottom: 0.65rem; border-bottom: 1px solid var(--border);
        }
        .mp-field {
            display: flex; align-items: flex-start; gap: 0.65rem;
            padding: 0.55rem 0; border-bottom: 1px solid #F3F4F6;
        }
        .mp-field:last-child { border-bottom: none; }
        .mp-field-icon {
            width: 28px; height: 28px; border-radius: 8px; background: #EFF6FF;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.85rem; flex-shrink: 0;
        }
        .mp-field-body { flex: 1; min-width: 0; }
        .mp-field-label { font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.1rem; }
        .mp-field-value { font-size: 0.88rem; font-weight: 600; color: var(--text-primary); word-break: break-word; }
        .mp-val-good { color: #15803D !important; }
        .mp-val-bad { color: #DC2626 !important; }
        .mp-val-neutral { color: var(--text-primary) !important; }
        .mp-subsection { margin-top: 0.85rem; }
        .mp-subsection-title { font-size: 0.85rem; font-weight: 700; color: var(--text-primary); margin: 0 0 0.45rem 0; }
        .mp-bullet {
            display: flex; gap: 0.5rem; align-items: flex-start;
            font-size: 0.82rem; color: var(--text-secondary); line-height: 1.55;
            margin-bottom: 0.55rem;
        }
        .mp-bullet-check { color: #2563EB; font-weight: 700; flex-shrink: 0; margin-top: 0.1rem; }
        .mp-note {
            display: flex; gap: 0.65rem; align-items: flex-start;
            background: #F8FAFC; border: 1px solid var(--border);
            border-radius: 10px; padding: 0.75rem 0.85rem; margin-bottom: 0.55rem;
        }
        .mp-note-icon { font-size: 1rem; flex-shrink: 0; margin-top: 0.1rem; }
        .mp-note-title { font-size: 0.82rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.15rem; }
        .mp-note-text { font-size: 0.8rem; color: var(--text-secondary); line-height: 1.5; }
        .mp-analysis { font-size: 0.84rem; color: var(--text-secondary); line-height: 1.65; }
        .mp-toolbar { display: flex; justify-content: flex-end; margin-bottom: 0.5rem; }
        .mp-history-bar { margin-bottom: 1rem; }

        div[data-testid="stForm"] {
            border: 1px solid var(--border); border-radius: var(--radius);
            padding: 1.25rem; background: var(--bg-card); box-shadow: var(--shadow);
        }

        /* ── 사이드바 ── */
        section[data-testid="stSidebar"] {
            background: var(--bg-card) !important;
            border-right: 1px solid var(--border);
        }

        /* ── 스크롤바 ── */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--blue-100); border-radius: 4px; }
        ::-webkit-scrollbar-thumb { background: var(--blue-400); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--blue-600); }

        /* ── 캡션·작은 텍스트 ── */
        .stCaption, [data-testid="stCaptionContainer"] {
            color: var(--blue-700) !important;
        }

        div[data-testid="stForm"] {
            border: 1px solid var(--border); border-radius: var(--radius);
            padding: 1.25rem; background: var(--bg-card); box-shadow: var(--shadow);
        }

        /* ── 진한 배경 위 흰색 텍스트 ── */
        div.stButton > button,
        div.stButton > button *,
        div.stFormSubmitButton > button,
        div.stFormSubmitButton > button *,
        div[data-testid="stDownloadButton"] > button,
        div[data-testid="stDownloadButton"] > button *,
        div[data-testid="stFileUploader"] button,
        div[data-testid="stFileUploader"] button *,
        .stTabs [aria-selected="true"],
        .stTabs [aria-selected="true"] *,
        div[data-baseweb="tag"],
        div[data-baseweb="tag"] *,
        div[aria-selected="true"][role="option"],
        div[aria-selected="true"][role="option"] * {
            color: #FFFFFF !important;
        }
        div.stButton > button svg,
        div.stFormSubmitButton > button svg,
        div[data-testid="stDownloadButton"] > button svg,
        div[data-testid="stFileUploader"] button svg,
        .stTabs [aria-selected="true"] svg,
        div[data-baseweb="tag"] svg {
            fill: #FFFFFF !important;
            stroke: #FFFFFF !important;
        }

        /* ── 툴팁 최종 우선순위 (전역 텍스트 규칙 덮어쓰기) ── */
        body [data-testid="stTooltipContent"],
        body [data-testid="stTooltipContent"] p,
        body [data-testid="stTooltipContent"] span {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }

        /* ── 반응형: 다양한 화면비·해상도 ── */
        img, video, svg { max-width: 100%; height: auto; }
        .hero-card, .content-card, .dash-card, .law-card, .category-card, .app-navbar {
            box-sizing: border-box;
            max-width: 100%;
        }

        /* 태블릿 이하 */
        @media (max-width: 1024px) {
            .hero-title { font-size: clamp(1.35rem, 4vw, 1.75rem); }
            .hero-card { padding: clamp(1.25rem, 3vw, 2rem); }
            .step-item { font-size: 0.75rem; padding: 0.45rem 0.35rem; }
            .step-line { width: 16px; }
            .law-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }

        /* 모바일·세로 화면 */
        @media (max-width: 768px) {
            .main .block-container {
                padding-left: 0.75rem;
                padding-right: 0.75rem;
            }
            div[data-testid="stHorizontalBlock"]:not(:has(.nav-btn-marker)) {
                flex-wrap: wrap !important;
            }
            div[data-testid="stHorizontalBlock"]:not(:has(.nav-btn-marker)) > div[data-testid="column"] {
                flex: 1 1 100% !important;
                min-width: 100% !important;
                width: 100% !important;
            }
            .app-header {
                flex-direction: row;
                align-items: center;
                padding: 0.65rem 0.85rem;
                gap: 0.5rem;
            }
            .header-brand { flex-shrink: 0; }
            .header-nav {
                justify-content: flex-start;
                padding-bottom: 0.1rem;
                flex: 1 1 auto;
                min-width: 0;
            }
            .nav-tab {
                padding: 0.45rem 0.55rem;
                font-size: 0.72rem;
            }
            .nav-tab svg { width: 14px; height: 14px; }
            .brand-name { font-size: 0.92rem; }
            .brand-sub { font-size: 0.65rem; }
            .nav-logo { width: 34px; height: 34px; }
            .stepper { flex-wrap: wrap; gap: 0.35rem; }
            .step-item { flex: 1 1 calc(50% - 0.5rem); }
            .step-line { display: none; }
            .app-navbar { padding: 0.75rem 1rem; }
            .nav-brand { font-size: 1rem; }
            .gauge-circle { width: 84px; height: 84px; }
            .gauge-score { font-size: 1.35rem; }
            .law-card-grid { grid-template-columns: minmax(0, 1fr); }
        }

        /* 초소형 화면 */
        @media (max-width: 480px) {
            .hero-sub { font-size: 0.9rem; }
            div.stButton > button, div.stFormSubmitButton > button {
                padding: 0.65rem 1.1rem !important;
                font-size: 0.9rem !important;
            }
            .step-item { flex: 1 1 100%; justify-content: flex-start; }
        }

        /* 울트라와이드·가로 화면 */
        @media (min-width: 1600px) {
            .main .block-container { max-width: min(1440px, 92vw) !important; }
        }
        @media (min-aspect-ratio: 21/9) {
            .main .block-container { max-width: min(1600px, 88vw) !important; }
        }
    </style>
    """,
    unsafe_allow_html=True
)

#---------------------------------------------------------------------------
# [데이터 지식 베이스 및 퀴즈 은행 데이터 선언 (각 20문항, 총 40문항)]
#---------------------------------------------------------------------------
LAW_TIPS = [
    "💡 [법 제4조 역외적용] 국외에서 이루어진 행위라도 국내 시장 또는 이용자에게 영향을 미치는 경우에는 인공지능 기본법이 엄격히 적용됩니다.",
    "💡 [법 제31조 투명성] 고영향 또는 생성형 AI 기반 제품/서비스는 사전 고지 및 AI 생성 표시가 의무화되며 위반 시 최대 3천만 원의 과태료가 부과됩니다.",
    "💡 [법 제3조 설명의무] 영향받는 자는 인공지능의 최종결과 도출에 활용된 주요 기준 및 원리에 대해 명확하고 의미 있는 설명을 제공받을 권리가 있습니다.",
    "💡 [법 제27조 윤리원칙] 정부는 안전성·신뢰성·접근성·공헌을 담은 인공지능 윤리원칙을 제정할 수 있으며, 실천방안 홍보·교육이 의무화됩니다.",
    "💡 [법 제28조 민간자율위원회] 인공지능사업자는 민간자율인공지능윤리위원회를 설치해 윤리 준수 확인·조사·감독·교육을 자율 수행할 수 있습니다.",
]

# 인공지능 기본법 관련 20문항 데이터셋
LAW_QUIZ_BANK = [
    {"q": "인공지능 기본법의 목적(제1조)으로 가장 적절하지 않은 것은?", "a": ["① 국민의 권익과 존엄성 보호", "② 국민의 삶의 질 향상", "③ 국가경쟁력 강화", "④ 인공지능 제품의 무제한적 자율성 보장"], "ans": "④", "exp": "제1조에 따르면 법은 건전한 발전과 '신뢰 기반 조성'을 목적으로 하며, 무제한적 자율성이 아닌 국민의 권익과 존엄성 보호를 선포하고 있습니다."},
    {"q": "법 제2조에 따른 '고영향 인공지능' 정의 중 기본권에 중대한 영향을 미치는 영역이 아닌 것은?", "a": ["① 먹는물의 생산 공정 관리", "② 채용 및 대출 심사 시스템", "③ 일반 기업의 소셜미디어 카드뉴스 자동 생성기", "④ 유아·초등·중등교육에서의 학생 평가"], "ans": "③", "exp": "단순 카드뉴스나 마케팅 문구 생성은 사람의 생명, 신체 안전 및 기본권에 중대한 우려를 초래하는 11대 고영향 영역에 포함되지 않습니다."},
    {"q": "국외에서 발생한 AI 행위라도 국내 시장이나 이용자에게 영향을 미칠 때 법을 적용하는 조항(제4조)은?", "a": ["① 역내제한 조항", "② 역외적용 조항", "③ 상호주의 조항", "④ 안보예외 조항"], "ans": "②", "exp": "제4조 제1항은 국외 행위라도 국내 시장이나 이용자에게 영향을 미치는 경우 본 법을 적용하도록 명시하는 '역외적용'을 규정합니다."},
    {"q": "다음 중 인공지능 기본법의 적용을 받지 않는 인공지능시스템(제4조제2항)은?", "a": ["① 민간 금융권의 대출 신용평가 AI", "② 국방 또는 국가안보 목적으로만 개발·이용되는 인공지능", "③ 병원 응급실에서 쓰는 디지털의료기기 AI", "④ 공공기관의 자격 확인용 의사결정 AI"], "ans": "②", "exp": "제4조 제2항에 따라 국방 또는 국가안보 목적으로만 개발·이용되는 인공지능으로서 대통령령으로 정하는 인공지능은 적용에서 제외됩니다."},
    {"q": "이용자가 AI의 최종결과 도출 기준과 원리에 대해 명확한 설명을 요구할 수 있는 근거 조항(제3조)은?", "a": ["① 설명의무 및 권리", "② 비밀유지 의무", "③ 집적화 촉진 권리", "④ 형사처벌 조항"], "ans": "①", "exp": "제3조 제2항에 따라 영향받는 자는 기술적·합리적으로 가능한 범위에서 최종결과 도출에 활용된 주요 기준 및 원리에 대해 명확하고 의미 있는 설명을 제공받을 수 있어야 합니다."},
    {"q": "생성형 AI 서비스를 제공하려는 사업자가 이용자에게 가장 먼저 이행해야 할 투명성 확보 의무(제31조제1항)는?", "a": ["① 개발자 인적사항 전수 공개", "② 해당 서비스가 인공지능에 기반하여 운용된다는 사실의 사전 고지", "③ 소스코드 정부 기관 제출", "④ 무단 크롤링 데이터의 세부 출처 백과사전식 명시"], "ans": "②", "exp": "제31조 제1항에 의거, 고영향 또는 생성형 AI 서비스를 제공하려는 경우 해당 인공지능에 기반하여 운용된다는 사실을 이용자에게 '사전에 고지'하여야 합니다."},
    {"q": "생성형 AI 결과물을 배포할 때 결과물 표면에 취해야 하는 법적 조치(제31조제2항)는?", "a": ["① 원작자 저작권 양도 마크 부착", "② 생성형 인공지능에 의해 생성되었다는 사실을 표시", "③ 이용자의 주민등록번호 해싱 임베딩", "④ 실시간 연산 비용 청구서 팝업 연동"], "ans": "②", "exp": "제31조 제2항에 따라 생성형 인공지능 또는 이를 이용한 제품·서비스를 제공하는 경우 그 결과물이 생성형 인공지능에 의해 생성되었다는 사실을 명확히 '표시'해야 합니다."},
    {"q": "실제와 구분하기 어려운 가상의 이미지, 영상(딥페이크 등)을 제공할 때 지켜야 할 의무(제31조제3항)는?", "a": ["① 영상 상영을 전면 금지함", "② 정부의 승인을 얻은 경우에만 유통함", "③ 이용자가 가상 결과물임을 명확하게 인식할 수 있는 방식으로 고지 또는 표시", "④ 실제 인물의 서면 동의서를 화면 중앙에 워터마크로 투사"], "ans": "③", "exp": "제31조 제3항에 따라 실제와 구분하기 어려운 가상의 음향, 이미지, 영상 등을 제공하는 경우 이용자가 이를 명확하게 인식할 수 있는 방식으로 고지·표시해야 합니다."},
    {"q": "인공지능 기본법상 제31조 제1항(사전고지 의무)을 위반하여 고지를 이행하지 않은 자에 대한 과태료 한도(제43조)는?", "a": ["① 500만 원 이하", "1,000만 원 이하", "③ 3,000만 원 이하", "④ 1억 원 이하"], "ans": "③", "exp": "제43조 제1항 제1호에 따라 제31조 제1항의 사전고지 의무를 위반하여 고지를 이행하지 아니한 자에게는 3천만 원 이하의 과태료를 부과합니다."},
    {"q": "국내에 주소나 영업소가 없는 해외 AI 사업자가 이용자 보호 및 규제 대응을 위해 지정해야 하는 주체(제36조)는?", "a": ["① 사설 정보보호 대행업체", "② 국내대리인", "③ 국무총리 직속 비서관", "④ 다국적 기업 법률 연합"], "ans": "②", "exp": "제36조 제1항에 따라 국내에 주소 또는 영업소가 없는 외국 사업자 중 일정 기준에 해당하는 자는 안전성 확보 조치 이행 등을 대리하는 '국내대리인'을 서면 지정해야 합니다."},
    {"q": "국내대리인을 지정하지 않은 해외 사업자에게 부과되는 벌칙성 제재(제43조)는?", "a": ["① 3년 이하의 징역", "② 3,000만 원 이하의 과태료", "③ 영업소 강제 폐쇄 명령", "④ 국가 정보망 접속 원천 차단"], "ans": "②", "exp": "제43조 제1항 제2호에 따라 제36조 제1항을 위반하여 국내대리인을 지정하지 아니한 자에게는 3,000만 원 이하의 과태료가 부과됩니다."},
    {"q": "과기정통부 장관이 기본법 위반 혐의나 신고를 접수했을 때 수행할 수 있는 권한(제40조)은?", "a": ["① 대표이사 즉시 구속 수사", "② 관련 자료 제출 요구 및 소속 공무원을 통한 사실조사", "③ 기업 자산 국유화 강제 집행", "④ 소스코드의 경쟁사 전면 무상 공개 명령"], "ans": "②", "exp": "제40조 제1항 및 제2항에 따라 장관은 자료 제출을 명하거나 소속 공무원으로 하여금 사무소·사업장에 출입하여 장부 및 서류를 조사하게 할 수 있습니다."},
    {"q": "사실조사 결과 법 위반이 인정될 때 장관이 사업자에게 내릴 수 있는 처분(제40조제3항)은?", "a": ["① 형사 고발 전용 징벌적 과징금 부과", "② 위반행위의 중지나 시정을 위하여 필요한 조치 명령", "③ 즉각적인 파산 선고 청구", "④ 해당 기술의 국가 귀속 조치"], "ans": "②", "exp": "제40조 제3항에 의거, 위반 사실이 있다고 인정되면 인공지능사업자에게 해당 위반행위의 중지나 시정을 위하여 필요한 조치를 명할 수 있습니다."},
    {"q": "정부의 중지명령이나 시정명령을 정당한 사유 없이 이행하지 아니한 자에게 부과되는 법적 과태료(제43조)는?", "a": ["① 1,000만 원 이하", "② 2,000만 원 이하", "③ 3,000만 원 이하", "④ 5,000만 원 이하"], "ans": "③", "exp": "제43조 제1항 제3호에 따라 제40조 제3항에 따른 중지명령이나 시정명령을 이행하지 아니한 자에게는 3,000만 원 이하의 과태료가 처분됩니다."},
    {"q": "대통령 소속으로 인공지능 발전과 신뢰 기반 조성을 위한 국가 비전 및 중장기 전략을 심의·의결하는 추진체계(제7조)는?", "a": ["① 한국인공지능수사처", "② 국가인공지능전략위원회", "③ 정보통신심의연합회", "④ 미래기술진흥재단"], "ans": "②", "exp": "제7조 제1항에 따라 인공지능 발전과 신뢰 기반 조성 등을 위한 주요 정책을 심의·의결하기 위해 대통령 소속으로 '국가인공지능전략위원회'를 둡니다."},
    {"q": "과기정통부 장관이 인공지능 관련 정책의 개발과 국제규범 정립·확산 업무를 수행하기 위해 지정할 수 있는 기관(제11조)은?", "a": ["① 인공지능정책센터", "② 미래과학혁신원", "③ 글로벌디지털통상국", "④ 지능정보산업연구회"], "ans": "①", "exp": "제11조 제1항에 의거, 장관은 정책 개발과 국제규범 정립·확산에 필요한 업무를 종합 수행하기 위해 '인공지능정책센터'를 지정할 수 있습니다."},
    {"q": "인공지능 관련 위험을 정의·분석하고 안전 평가 기준 및 방법 등을 전문 연구하기 위해 설립되는 소(제12조)는?", "a": ["① 사이버테러방지연구소", "② 인공지능안전연구소", "③ 첨단컴퓨팅검증원", "④ 국가안보보안연구원"], "ans": "②", "exp": "제12조 제1항에 따라 위험으로부터 국민의 생명·신체·재산 등을 보호하기 위해 전문 연구를 수행하는 '인공지능안전연구소'를 운영할 수 있습니다."},
    {"q": "학습에 사용된 누적 연산량이 기준 이상인 인공지능시스템에 대하여 안전성 확보를 위해 구축해야 하는 것(제32조)은?", "a": ["① 실시간 매출 정산 시스템", "② 안전사고를 모니터링하고 대응하는 위험관리체계", "③ 분기별 주주총회 보고 체계", "④ 소스코드 완전 오픈소스화 메커니즘"], "ans": "②", "exp": "제32조 제1항에 따라 대규모 누적 연산량 이상을 사용하는 인공지능시스템 사업자는 수명주기 전반의 위험 식별 및 안전사고 모니터링 대응 '위험관리체계'를 구축해야 합니다."},
    {"q": "인공지능 기본법에 따라 인공지능 관련 시책을 시행할 때 우선적으로 고려하고 지원해야 하는 대상(제17조)은?", "a": ["① 해외 다국적 독점 테크 기업", "② 중소기업 및 스타트업 등 중소기업등", "③ 자본금 1조원 이상의 대기업 금융 지주", "④ 정부 산하 직속 행정 부처 전 부서"], "ans": "②", "exp": "제17조 제1항 및 제3항에 따라 인공지능 관련 각종 지원시책 시행 시 '중소기업등'을 우선 고려해야 하며, 영향평가 및 안전 조치 이행 비용을 지원할 수 있습니다."},
    {"q": "인공지능 발전과 신뢰 조성을 위한 기본계획은 과학기술정보통신부 장관이 몇 년마다 수립해야 하는가(제6조)?", "a": ["① 매년 수립", "② 2년마다 수립", "③ 3년마다 수립", "④ 5년마다 수립"], "ans": "③", "exp": "제6조 제1항에 따라 과학기술정보통신부장관은 국가경쟁력 강화를 위하여 3년마다 인공지능 기본계획을 수립·시행하여야 합니다."}
]

# 책임 있는 AI 윤리 관련 20문항 데이터셋
ETHICS_QUIZ_BANK = [
    {"q": "과기정통부 가이드라인에 따른 '책임 있는 AI' 3대 기본원칙에 포함되지 않는 것은?", "a": ["① 인간 존엄성 원칙", "② 사회의 공공선 원칙", "③ 기술의 합목적성 원칙", "④ 기업 이윤 극대화 원칙"], "ans": "④", "exp": "3대 기본원칙은 '인간 존엄성 원칙', '사회의 공공선 원칙', '기술의 합목적성 원칙'으로 구성되며 기업의 영리 추구만을 정당화하는 요건은 배제됩니다."},
    {"q": "인간의 가치가 기계의 가치보다 항상 우선되어야 함을 선언한 기본 윤리 원칙은?", "a": ["① 인간 존엄성 원칙", "② 효율성 우선 원칙", "③ 기술 만능주의 원칙", "④ 연대성 집중 원칙"], "ans": "①", "exp": "인간 존엄성 원칙은 인간이 기계의 수단이 될 수 없으며, 인간 고유의 정신적·신체적 존엄성과 대체 불가능한 가치를 보장하라는 의미입니다."},
    {"q": "장애인, 고령자 등 소외계층의 접근성을 높여 정보격차를 줄이고 보편 복지를 실현하라는 세부 요건은?", "a": ["① 데이터 관리 요건", "② 공공성 요건", "③ 투명성 요건", "④ 인권보장 요건"], "ans": "②", "exp": "사회의 공공선 원칙의 하위 요건인 '공공성'은 사회 전체와 인류의 보편적 복지 및 사회적 약자의 정보 격차 완화를 목표로 삼습니다."},
    {"q": "인공지능 시스템이 인간의 통제를 벗어나지 않도록 '비상정지 기능' 등 안전장치를 부여하라는 요건은?", "a": ["① 연대성 요건", "② 침해금지 요건", "③ 다양성 존중 요건", "④ 기술의 안정성 요건"], "ans": "④", "exp": "기술의 합목적성 원칙 하의 '안정성' 요건은 문제 발생 시 인간이 개입하여 시스템을 제어하거나 멈출 수 있는 안전장치 제공을 골자로 합니다."},
    {"q": "AI 의사결정의 내부 요인과 가중치를 추적하여 설명 가능성을 측정하는 대표적인 해석 모델 기술은?", "a": ["① LIME (Local Interpretable Model-agnostic Explanations)", "② Data Poisoning 테스팅", "③ AES 암호화 프로토콜", "④ 부하 분산 밸런싱 기술"], "ans": "①", "exp": "LIME은 AI의 아웃풋을 분석하여 특정 판단을 내린 원인과 알고리즘 기여도를 인간이 직관적으로 이해하도록 돕는 설명 가능성 기술입니다."},
    {"q": "데이터 수집 단계에서 가짜 뉴스나 악성 패킷을 의도적으로 주입하여 AI 시스템을 오염시키는 유해 공격은?", "a": ["① 블랙박스 프롬프트 인젝션", "② 데이터 포이즈닝 (Data Poisoning)", "③ 화이트박스 역산 추출", "④ 워터마크 마스킹 기법"], "ans": "②", "exp": "데이터 포이즈닝(악성 데이터 오염)은 수집·학습 단계에서 원천 소스를 변조하여 시스템의 판단 체계를 마비시키는 중대한 보안 위협입니다."},
    {"q": "외부에서 완성된 AI 솔루션을 도입할 때 구매 기업이 취해야 할 책임성(Accountability) 태도는?", "a": ["① 모든 결함은 개발 공급업체의 전적인 책임이므로 방관함", "② '공급업체 책임 연대'에 의거하여 도입 기업도 비즈니스 목적에 맞춰 책임을 공유함", "③ 정부의 검·인증을 통과했다면 사후 모니터링을 영구 생략함", "④ 문제 발생 시 해당 오픈소스 커뮤니티에 민사 소송만을 제기함"], "ans": "②", "exp": "책임성 원칙에 따르면 외부 솔루션을 구매해 사용할지라도 도입 기업은 자사 비즈니스 도메인 맥락 안에서 안전 관리를 연대하여 책임져야 합니다."},
    {"q": "AI 인사(HR) 시스템이 특정 성별이나 인종의 가점/감점을 유발하는 통계적 차별을 방지하기 위한 윤리 요건은?", "a": ["① 연대성 요건", "② 다양성 존중 요건", "③ 암호화 보안 요건", "④ 하드웨어 견고성 요건"], "ans": "②", "exp": "인간 존엄성 원칙의 '다양성 존중' 요건은 학습 데이터 편향으로 인해 특정 집단이 차별받거나 제도적으로 불이익을 당하는 리스크를 최소화할 것을 명시합니다."},
    {"q": "AI가 도출한 의사결정의 중간 경로와 데이터 처리 이력을 문서화하여 투명하게 추적할 수 있는 속성은?", "a": ["① 예측 정확도 (Accuracy)", "② 추적성 (Traceability)", "③ 확장성 (Scalability)", "④ 익명성 (Anonymity)"], "ans": "②", "exp": "추적성(Traceability)은 모델의 원천 데이터 문서화 및 처리 경로를 추적 가능하게 구비하여 투명성과 설명 가능성을 담보하는 핵심 속성입니다."},
    {"q": "생성형 AI 모델 운용 시 사용자의 중요 기업 자산이나 민감 정보가 불법적으로 외부 유출되지 않도록 통제하는 요건은?", "a": ["① 다양성 존중 요건", "② 프라이버시 보호 요건", "③ 글로벌 협력 요건", "④ 공공성 요건"], "ans": "②", "exp": "인간 존엄성 원칙의 '프라이버시 보호' 요건은 AI 활용 및 프롬프트 처리 과정에서 개인정보 주권 및 민감 정보 오용을 차단할 보안 시스템 구축을 요구합니다."},
    {"q": "인공지능의 순기능을 극대화하여 미래 세대와 후손들의 참여 기회 및 삶의 영역까지 배려하라는 윤리 요건은?", "a": ["① 인권보장 요건", "② 침해금지 요건", "③ 연대성 요건", "④ 투명성 요건"], "ans": "③", "exp": "사회의 공공선 원칙 하의 '연대성' 요건은 현 세대뿐 아니라 미래 후손들을 배려하고 공정한 사회 참여 기회를 연대하여 제공하는 것을 지향합니다."},
    {"q": "대화형 AI가 악성 코드 제작법이나 랜섬웨어 유포 사기 기법을 답변하지 못하도록 필터링하는 안전 거버넌스는?", "a": ["① 침해금지 요건 (유해 응답 통제)", "② 다국어 번역 요건", "③ 예측 성능 고도화 요건", "④ 자격 확인 간소화 요건"], "ans": "①", "exp": "인간 존엄성 원칙의 '침해금지' 요건은 정신적·신체적 건강에 유해하거나 범죄를 유도하는 응답 출력을 인프라 단에서 차단·통제할 것을 강조합니다."},
    {"q": "AI 윤리를 실천하기 위해 기업 내부에서 자체적으로 조직하여 자율적 심사 및 감독을 수행할 수 있는 기구는?", "a": ["① 중앙분쟁조정위원회", "② 민간자율인공지능윤리위원회", "③ 첨단기술금융연합회", "④ 미래노동권익보호원"], "ans": "②", "exp": "인공지능 기본법 및 윤리 지침은 기업들이 사내에 '민간자율인공지능윤리위원회'를 공식 설치하여 자율적인 점검 가이드라인을 이행하도록 권고하고 있습니다."},
    {"q": "AI가 사람의 삶에 직결된 도구를 결정할 때 사전에 편향과 위험 요소를 체계적으로 스크리닝하는 제도는?", "a": ["① 자율윤리영향평가", "② 실시간 트래픽 과금 평가", "③ 하드웨어 수명 측정 평가", "④ 주식 가치 정량 평가"], "ans": "①", "exp": "고위험군 도구를 배포하기 전 편향과 부작용을 선제적으로 걸러내기 위해 자율적인 'AI 윤리영향평가' 체계를 작동시키는 것이 권장됩니다."},
    {"q": "AI 시스템 개발 시 인간 감독관이 기계의 결과물을 독립적으로 검토하고 언제든 수정·파기할 수 있는 권한 체계는?", "a": ["① 기계 학습 자동화", "② 실질적 사람의 관리·감독", "③ 사용자 경험 단순화", "④ 데이터 포이즈닝 수용"], "ans": "②", "exp": "책임성 요건을 충족하기 위해서는 '최종 결정은 사람이 했다'는 형식적 결재를 넘어, 인간 감독관의 '실질적 관리·감독' 권한이 보장되어야 합니다."},
    {"q": "2010년대 이후 빅데이터의 가파른 성장과 머신러닝의 광범위한 채택으로 인해 AI 윤리가 독립 분야로 부상하게 된 주원인은?", "a": ["① 연산 속도의 저하 문제", "② 알고리즘 블랙박스 편향 및 개인 데이터 무단 사용 등 부작용 등장", "③ 오픈소스 라이선스의 완전 유료화 기조", "④ 글로벌 하드웨어 반도체 공급망 부족"], "ans": "②", "exp": "머신러닝이 대중화되면서 나타난 알고리즘 투명성 결여, 편향성, 프라이버시 침해 등의 사회적 위기가 AI 윤리학의 출범을 이끌었습니다."},
    {"q": "AI 예측 모델의 타당성을 입증하기 위해 시뮬레이션 결과와 아웃풋 데이터를 실제 데이터셋 결과와 비교 분석하는 속성은?", "a": ["① 예측 정확도 (Accuracy)", "② 추적성 (Traceability)", "③ 연대성 (Solidarity)", "④ 다양성 (Diversity)"], "ans": "①", "exp": "예측 정확도는 일상 업무에서 AI 시스템을 성공적으로 신뢰하고 쓸 수 있는 핵심 척도로서, 실제 아웃풋 데이터 세트의 오차 범위 비교를 통해 확인됩니다."},
    {"q": "책임 있는 AI 시스템 디자인의 중심에 두어야 할 가장 본질적인 두 가지 요소는?", "a": ["① 초고속 인프라와 고자본 투자", "② 사람과 인류 보편적 이익 목표", "③ 완벽한 자율성과 기계적 가치", "④ 마케팅 홍보 효과와 경쟁사 차단"], "ans": "②", "exp": "책임 있는 AI(Responsible AI)는 사람과 인류 공동체의 안전 목표를 디자인 중심에 두고 공정성, 신뢰성을 확보해 나가는 접근 방식입니다."},
    {"q": "AI 기술의 성능 경쟁이나 단기적 영업 이익에만 매몰되지 않고, 전체 신뢰도를 높여 부작용을 최소화하려는 거버넌스 가치는?", "a": ["① 기술 만능 인프라 구축", "② 디지털 신뢰 인프라 확립 (사회의 공공선)", "③ 완전 블랙박스 모델화", "④ 역내 시장 독점 체제 확립"], "ans": "②", "exp": "사회 전체의 디지털 신뢰 인프라를 넓히는 방향으로 서비스를 설계 및 배포하는 행위는 '사회의 공공선 원칙'에 완벽히 부합합니다."},
    {"q": "UN, ITU 등 국제기구가 주관하는 거버넌스 자리에 동참하여 상호 운용 가능한 글로벌 디지털 규격을 도출하려는 실천 요건은?", "a": ["① 글로벌 표준 협력 및 연대성", "② 기업 기밀 자산 폐쇄화", "③ 개별 독자 규격 강제화", "④ 사내 인사 시스템 자동 선별"], "ans": "①", "exp": "개방형 디지털 신뢰 표준 정립을 위한 국제사회와의 연대와 글로벌 표준 협력 조치는 공공선 원칙 중 '연대성' 요건의 주요 실천 지표입니다."}
]

# ---------------------------------------------------------------------------
# 법령 텍스트 로드 및 지식 베이스 생성
# ---------------------------------------------------------------------------
TXT_CANDIDATE_PATHS = [
    os.path.join(APP_DIR, "인공지능기본법.txt"),
    os.path.join(APP_DIR, "data", "인공지능기본법.txt"),
]
TXT_FILE_PATH = next((p for p in TXT_CANDIDATE_PATHS if os.path.exists(p)), TXT_CANDIDATE_PATHS[-1])
status_msg, txt_knowledge_base = load_local_txt_guideline(TXT_FILE_PATH)
HEAVY_COMPUTE_LAW_CITATION = build_heavy_compute_law_citation(txt_knowledge_base)
ETHICS_KNOWLEDGE = build_ethics_knowledge_bank(txt_knowledge_base)

# ---------------------------------------------------------------------------
# Session State 초기화
# ---------------------------------------------------------------------------
if "contract_signed" not in st.session_state:
    st.session_state.contract_signed = False
if "current_tip" not in st.session_state:
    st.session_state.current_tip = random.choice(LAW_TIPS)
if "current_ethics" not in st.session_state:
    st.session_state.current_ethics = random.choice(ETHICS_KNOWLEDGE)
if "main_tab" not in st.session_state:
    st.session_state.main_tab = "home"

HISTORY_FILE = os.path.join(APP_DIR, "fixflawlaw_records.json")

NAV_TABS = [
    ("home", "홈"),
    ("diagnosis", "환경 진단"),
    ("asset", "산출물 분석"),
    ("law", "인공지능기본법 핵심만 알아보기"),
    ("ethics", "AI 윤리"),
    ("quiz", "퀴즈"),
    ("mypage", "마이페이지"),
]

NAV_TAB_DISPLAY = {
    "home": "홈",
    "diagnosis": "환경 진단",
    "asset": "산출물 분석",
    "law": "인공지능기본법",
    "ethics": "AI 윤리",
    "quiz": "퀴즈",
    "mypage": "마이페이지",
}

NAV_TAB_ICONS = {
    "home": '<svg viewBox="0 0 24 24" stroke-width="2"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20h14V9.5"/><path d="M9 20v-6h6v6"/></svg>',
    "diagnosis": '<svg viewBox="0 0 24 24" stroke-width="2"><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h6M9 11h6M9 15h4"/></svg>',
    "asset": '<svg viewBox="0 0 24 24" stroke-width="2"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>',
    "law": '<svg viewBox="0 0 24 24" stroke-width="2"><path d="M7 4h10v16H7z"/><path d="M9 8h6M9 12h6M9 16h4"/></svg>',
    "ethics": '<svg viewBox="0 0 24 24" stroke-width="2"><path d="M12 3 4 7v6c0 5 3.4 8.7 8 9 4.6-.3 8-4 8-9V7l-8-4z"/></svg>',
    "quiz": '<svg viewBox="0 0 24 24" stroke-width="2"><path d="M12 3 2 8l10 5 10-5-10-5Z"/><path d="M6 11v4c0 2.2 2.7 4 6 4s6-1.8 6-4v-4"/></svg>',
    "mypage": '<svg viewBox="0 0 24 24" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20a8 8 0 0 1 16 0"/></svg>',
}

LAW_INFO_CARDS = [
    {"icon": "📜", "title": "목적", "article": "제1조", "desc": "인공지능의 건전한 발전과 신뢰 기반 조성, 국민 권익·존엄성 보호 및 삶의 질 향상"},
    {"icon": "⚖️", "title": "기본원칙", "article": "제3조", "desc": "안전성·신뢰성 제고 방향 발전, 영향받는 자의 설명 제공 권리, 취약계층 참여 보장"},
    {"icon": "🔴", "title": "고영향 AI", "article": "제2조·제33조", "desc": "생명·신체 안전 및 기본권에 중대한 영향을 미치는 11대 영역 AI, 사전 검토·영향평가 대상"},
    {"icon": "🔍", "title": "투명성 의무", "article": "제31조", "desc": "생성형·고영향 AI 사전 고지, AI 생성 표시, 가상 결과물 인식 조치 의무화"},
    {"icon": "🛡️", "title": "안전성 확보", "article": "제32조·제34조", "desc": "대규모 연산량 AI 위험관리체계, 고영향 AI 안전성·신뢰성 확보 조치 및 문서 보관"},
    {"icon": "💰", "title": "과태료·제재", "article": "제40조·제43조", "desc": "사전고지 미이행 3천만 원 이하 과태료, 시정명령·중지명령 및 국내대리인 미지정 제재"},
]

LAW_OFFICIAL_URL = (
    "https://www.law.go.kr/lsSc.do?menuId=1&subMenuId=15&tabMenuId=81"
    "&query=%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5%20%EB%B0%9C%EC%A0%84%EA%B3%BC%20"
    "%EC%8B%A0%EB%A2%B0%20%EA%B8%B0%EB%B0%98%20%EC%A1%B0%EC%84%B1%20%EB%93%B1%EC%97%90%20"
    "%EA%B4%80%ED%95%9C%20%EA%B8%B0%EB%B3%B8%EB%B2%95#undefined"
)

AI_ETHICS_OFFICIAL_URL = "https://ai.kisdi.re.kr/aieth/main/contents.do?menuNo=400029"

ASSETS_DIR = os.path.join(APP_DIR, "assets")
GLOBAL_REG_IMAGE_MODELS = os.path.join(ASSETS_DIR, "global_ai_regulation_models.png")
GLOBAL_REG_IMAGE_EU_KR = os.path.join(ASSETS_DIR, "global_ai_regulation_eu_kr.png")

GLOBAL_REGULATION_EU_SOURCES = [
    ("김·장 법률사무소 뉴스레터 (EU AI Act)", "https://www.shinkim.com/newsletter/2024/GA/2024_vol232/links/2024_vol232_403.pdf"),
    ("K-brainnet 블로그", "https://blog.naver.com/kbrainnet/224335535890"),
    ("한국인정지원센터 블로그", "https://blog.naver.com/kab_accreditation/223829696086"),
]

GLOBAL_REGULATION_JP_CN_SOURCES = [
    ("DBpia - 일본 AI법 제정 과정에 관한 연구", "https://www.dbpia.co.kr/journal/articleDetail?nodeId=NODE12702873"),
]

ETHICS_PRINCIPLE_CARDS = [
    {"icon": "🧠", "title": "인간 존엄성 원칙", "items": "인권보장 · 프라이버시 보호 · 다양성 존중 · 침해금지"},
    {"icon": "🤝", "title": "사회의 공공선 원칙", "items": "공공성 · 연대성 · 정보격차 완화 · 보편 복지"},
    {"icon": "🛠️", "title": "기술의 합목적성 원칙", "items": "데이터 관리 · 책임성 · 안정성 · 투명성"},
]

ETHICS_CORE_REQUIREMENTS = [
    {
        "icon": "⚖️",
        "title": "인권보장",
        "desc": "고위험 HR 통제: 인사 영역 AI 자동 선별·승진 결정 시 노동권·기본권 침해 여부 점검. "
                "실질적 관리 감독: 형식적 결재가 아닌 인간 감독관의 독립 검토·수정 권한이 실제 작동하는가.",
    },
    {
        "icon": "🔒",
        "title": "프라이버시 보호",
        "desc": "생성형·에이전트 AI 활용 과정에서 민감 정보·기업 자산이 불법 유출·오용되지 않도록 제어 시스템을 갖추었는가.",
    },
    {
        "icon": "🌈",
        "title": "다양성 존중",
        "desc": "고위험 AI 도입 시 AI 윤리영향평가를 선제 시행하여 차별·편향을 걸러내고 있는가.",
    },
    {
        "icon": "🚫",
        "title": "침해금지",
        "desc": "대화형·생성형 AI가 악성 코드, 사기 기법, 혐오 표현 등 유해 응답을 출력하지 못하도록 차단·통제 인프라를 확립했는가.",
    },
    {
        "icon": "🌍",
        "title": "공공성",
        "desc": "성능 경쟁·이익 극대화에만 치우치지 않고 사회 전체 신뢰도를 높이고 부작용을 최소화하는 방향으로 서비스를 설계·운영하는가.",
    },
    {
        "icon": "🔗",
        "title": "연대성",
        "desc": "UN·ITU 등 국제 거버넌스에 참여하고, 상호 운용 가능한 개방형 디지털 신뢰 표준 정립을 위해 국제사회와 연대하는가.",
    },
    {
        "icon": "💾",
        "title": "데이터 관리",
        "desc": "데이터 수집 단계부터 가짜 뉴스·피싱·랜섬웨어 등 악성 데이터 오염(Data Poisoning)을 방어하고 무결성을 유지하는 거버넌스가 있는가.",
    },
    {
        "icon": "📋",
        "title": "책임성",
        "desc": "민간 자율 AI 윤리위원회 설치 및 사내 표준 윤리 지침 이행. 외부 솔루션 도입 시에도 도입 기업이 비즈니스 맥락에서 책임을 연대하는가.",
    },
    {
        "icon": "🛡️",
        "title": "안정성",
        "desc": "단순 사내 도구라도 최종 활용 목적(예: HR, 신용평가 등 고위험군)을 기준으로 위험도를 지속 측정하고 안전장치를 부여하는가.",
    },
    {
        "icon": "💡",
        "title": "투명성",
        "desc": "의사결정·산출물의 알고리즘 요인을 정량적으로 밝히고, AI 정책 소통 채널 등을 통해 기준을 투명하게 공유하는가.",
    },
]


GLOBAL_REG_SECTIONS = [
    (GLOBAL_REG_IMAGE_MODELS, "주요국 AI 규제 모델 비교와 한국의 '황금 밸런스' 모델"),
    (GLOBAL_REG_IMAGE_EU_KR, "EU AI Act vs 한국 AI 기본법 한눈에 비교"),
]


def _category_card_html(icon: str, title: str, desc: str) -> str:
    return (
        f'<div class="category-card">'
        f'<div class="category-icon">{icon}</div>'
        f'<div class="category-title">{title}</div>'
        f'<div class="category-desc">{desc}</div>'
        f'</div>'
    )


def _render_learn_category_card(icon: str, title: str, desc: str, link: str):
    card = _category_card_html(icon, title, desc)
    external = link.startswith("http")
    target = ' target="_blank" rel="noopener noreferrer"' if external else ""
    st.markdown(f'<a href="{link}"{target} class="category-card-link">{card}</a>', unsafe_allow_html=True)


def _global_regulations_body():
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="law-card-icon">🌍</div>'
        '<div class="law-card-desc">주요국 AI 규제 모델 비교와 한국의 \'황금 밸런스\' 모델, '
        'EU AI Act와 국내 프레임워크를 한눈에 확인하세요.</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    for image_path, caption in GLOBAL_REG_SECTIONS:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        if os.path.exists(image_path):
            st.image(image_path, use_container_width=True)
            st.markdown(f'<p class="global-reg-caption">{caption}</p>', unsafe_allow_html=True)
        else:
            st.warning(f"{caption} 이미지를 찾을 수 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<p class="ai-generated-label">본 이미지는 AI로 생성하였습니다.</p>',
        unsafe_allow_html=True,
    )

    source_html = ['<div class="global-source-grid">']
    for region, sources in [
        ("유럽", GLOBAL_REGULATION_EU_SOURCES),
        ("일본·중국", GLOBAL_REGULATION_JP_CN_SOURCES),
    ]:
        source_html.append(f'<div class="global-source-group"><div class="global-source-region">{region}</div><ul class="global-source-list">')
        for label, url in sources:
            source_html.append(
                f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a></li>'
            )
        source_html.append("</ul></div>")
    source_html.append("</div>")

    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown('<div class="law-card-title">📚 출처</div>', unsafe_allow_html=True)
    st.markdown("".join(source_html), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


@st.dialog("세계 여러나라의 인공지능 규제 법령", width="large")
def show_global_regulations_modal():
    _global_regulations_body()


def render_global_ai_regulations():
    st.header("세계 여러나라의 인공지능 규제 법령")
    _global_regulations_body()


def render_header_nav():
    current = st.session_state.get("main_tab", "home")
    if current == "template":
        current = "mypage"
        st.session_state.main_tab = "mypage"
    if current not in {t[0] for t in NAV_TABS}:
        st.session_state.main_tab = "home"
        current = "home"

    tab_links = []
    for tab_id, label in NAV_TABS:
        active_cls = " nav-tab-active" if current == tab_id else ""
        icon = NAV_TAB_ICONS.get(tab_id, "")
        display = NAV_TAB_DISPLAY.get(tab_id, label)
        tab_links.append(
            f'<a class="nav-tab{active_cls}" href="?tab={tab_id}" target="_self">{icon}<span>{display}</span></a>'
        )

    st.markdown(
        f"""
        <div class="app-header">
            <div class="header-brand">
                <div class="nav-logo">
                    <svg viewBox="0 0 24 24" stroke-width="2">
                        <circle cx="8" cy="12" r="4"/>
                        <circle cx="16" cy="12" r="4"/>
                        <path d="M10.5 12h3"/>
                        <path d="M4 12h0M20 12h0"/>
                    </svg>
                </div>
                <div>
                    <div class="brand-name">fixflawlaw</div>
                    <div class="brand-sub">AI 컴플라이언스 진단 플랫폼</div>
                </div>
            </div>
            <nav class="header-nav">{"".join(tab_links)}</nav>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_navbar():
    render_header_nav()


def render_main_nav():
    pass


def render_stepper(current: int, steps: list[str] | None = None):
    if steps is None:
        steps = ["서비스 정보", "기술 사양", "규제 준수", "결과"]
    html = '<div class="stepper">'
    for i, label in enumerate(steps):
        cls = "step-active" if i == current else ("step-done" if i < current else "")
        html += f'<div class="step-item {cls}"><span class="step-num">{i+1:02d}</span><span>{label}</span></div>'
        if i < len(steps) - 1:
            html += '<div class="step-line"></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def sync_nav_from_query():
    tab = st.query_params.get("tab")
    if not tab:
        return
    if tab == "analysis":
        sub = st.query_params.get("sub", "business")
        st.session_state.main_tab = "diagnosis" if sub == "business" else "asset"
    elif tab in {t[0] for t in NAV_TABS}:
        st.session_state.main_tab = tab
    elif tab == "template":
        st.session_state.main_tab = "mypage"


def build_quiz_hint(item: dict) -> str:
    answer_text = next((a for a in item["a"] if a.startswith(item["ans"])), "")
    answer_text = answer_text.lstrip("①②③④ ").strip()
    hint = item["exp"]
    keywords = [w for w in re.split(r"[\s·,()'\"“”]+", answer_text) if len(w) >= 2]
    for w in sorted(set(keywords), key=len, reverse=True):
        hint = hint.replace(w, "『○○』")
    return hint.replace(item["ans"], "○")


def render_sequential_quiz(bank: list, prefix: str):
    total = len(bank)
    idx_key, score_key, streak_key, attempts_key = f"{prefix}_idx", f"{prefix}_score", f"{prefix}_streak", f"{prefix}_attempts"
    for k, v in [(idx_key, 0), (score_key, 0), (streak_key, 0), (attempts_key, 0)]:
        if k not in st.session_state:
            st.session_state[k] = v
    idx = st.session_state[idx_key]
    correct_count = st.session_state[score_key] // 10
    accuracy = min(100, int(correct_count / st.session_state[attempts_key] * 100)) if st.session_state[attempts_key] else 0

    col_main, col_side = st.columns([3, 1])
    with col_side:
        st.markdown(
            f"""
            <div class="score-panel">
                <h4>📊 현재 점수</h4>
                <div class="score-item"><span>획득 점수</span><span class="score-val">{st.session_state[score_key]}점</span></div>
                <div class="score-item"><span>연속 정답</span><span class="score-val">{st.session_state[streak_key]}회</span></div>
                <div class="score-item"><span>정답률</span><span class="score-val">{accuracy}%</span></div>
                <div class="score-item"><span>진행</span><span class="score-val">{min(idx, total)}/{total}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_main:
        if idx >= total:
            st.progress(1.0)
            st.success(f"🎉 전체 {total}문항 완료! 최종 점수: {st.session_state[score_key]}점 (정답률 {accuracy}%)")
            if st.button("🔄 처음부터 다시 풀기", key=f"{prefix}_restart"):
                for i in range(total):
                    for suffix in ("_q_", "_hint_", "_done_"):
                        st.session_state.pop(f"{prefix}{suffix}{i}", None)
                for k in (idx_key, score_key, streak_key, attempts_key):
                    st.session_state[k] = 0
                st.rerun()
            return

        pct = int((idx / total) * 100)
        st.markdown(f'<p class="quiz-progress-label">Question {idx+1} / {total} &nbsp;·&nbsp; {pct}%</p>', unsafe_allow_html=True)
        st.progress(idx / total)

        item = bank[idx]
        st.markdown(f'<div class="quiz-card"><strong>Q{idx+1}. {item["q"]}</strong></div>', unsafe_allow_html=True)
        user_ans = st.radio("보기를 선택하세요.", item["a"], key=f"{prefix}_q_{idx}", label_visibility="collapsed")

        done_key = f"{prefix}_done_{idx}"
        c1, c2 = st.columns(2)
        with c1:
            check = st.button("✅ 정답 확인", key=f"{prefix}_chk_{idx}")
        with c2:
            if st.button("💡 힌트 보기", key=f"{prefix}_hint_btn_{idx}"):
                st.session_state[f"{prefix}_hint_{idx}"] = True

        if st.session_state.get(f"{prefix}_hint_{idx}"):
            st.warning(f"💡 **힌트** — 핵심 키워드를 『○○』로 가렸습니다.\n\n{build_quiz_hint(item)}")

        if check and st.session_state.get(done_key) is not True:
            st.session_state[attempts_key] += 1
            correct = user_ans.startswith(item["ans"])
            st.session_state[done_key] = correct
            if correct:
                st.session_state[score_key] += 10
                st.session_state[streak_key] += 1
            else:
                st.session_state[streak_key] = 0
            st.rerun()

        if st.session_state.get(done_key) is True:
                st.success(f"정답입니다! ({item['ans']})")
                st.info(f"**해설** {item['exp']}")
                if st.button("➡️ 다음 문제", key=f"{prefix}_next_{idx}"):
                    st.session_state[idx_key] += 1
                    st.session_state.pop(done_key, None)
                    st.rerun()
        elif st.session_state.get(done_key) is False:
            st.error("오답입니다. 다시 선택해 보세요.")


ASSET_STEPS = ["자원 선택", "스크리닝", "분석 결과"]
DIAGNOSIS_STEPS = ["서약 동의", "기업·기술 사양", "규제 준수", "분석 결과"]


def load_diagnosis_history(force: bool = False):
    if not force and st.session_state.get("diagnosis_history_loaded"):
        return
    records: list = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                records = data
        except (OSError, json.JSONDecodeError, TypeError):
            records = []
    st.session_state.diagnosis_history = records
    st.session_state.diagnosis_history_loaded = True


def persist_diagnosis_history():
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state.get("diagnosis_history", []), f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _init_diagnosis_history():
    load_diagnosis_history()


def _append_diagnosis_history(record: dict):
    _init_diagnosis_history()
    st.session_state.diagnosis_history.insert(0, record)
    st.session_state.diagnosis_history = st.session_state.diagnosis_history[:20]
    persist_diagnosis_history()


def compute_diagnosis_result(form: dict) -> dict:
    is_generative = form["is_generative"]
    user_notify = form["user_notify"]
    virtual_content = form["virtual_content"]
    virtual_notify = form["virtual_notify"]
    high_impact_domain = form["high_impact_domain"]
    explainable = form["explainable"]
    heavy_compute = form["heavy_compute"]
    data_sources = form["data_sources"]

    risk_score = 20
    reasons = []
    if is_generative == "예" and user_notify == "미이행":
        risk_score = 95
        reasons.append("생성형 AI 서비스를 제공하면서 제31조 제1항(사전고지 의무)을 준수하지 않아 최대 3천만 원 이하의 과태료 부과 대상.")
    elif virtual_content == "예" and virtual_notify == "미이행":
        risk_score = 90
        reasons.append("실제와 구분하기 어려운 가상 결과물을 제공하면서 명확한 인식 표시(워터마크 등)를 누락하여 법 제31조 제3항 위반 위험 검출.")
    else:
        if high_impact_domain != "해당 없음 (일반 사무, 단순 요약 등)":
            risk_score += 30
            reasons.append("법 제2조 제4호에 따른 고영향 인공지능 영역에 속해 엄격한 위험관리방안 수립 대상에 해당함.")
        if explainable == "불가능":
            risk_score += 25
            reasons.append("제3조 제2항에 따른 이용자의 결과 도출 원리 설명 청구 권리 미비.")
        if heavy_compute == "예":
            risk_score += 20
            reasons.append(
                "학습에 사용된 누적 연산량이 대통령령 기준 이상으로 판단되어 "
                "제32조 제1항에 따른 위험 식별·평가·완화 및 안전사고 모니터링 위험관리체계 구축 의무 대상."
            )
        if "인터넷 무단 크롤링 데이터 포함" in data_sources:
            risk_score += 15
            reasons.append("데이터 수집 과정에서의 저작권 데이터 무단 복제 리스크 존재.")

    risk_score = min(risk_score, 100)
    safe_score = max(0, 100 - risk_score)
    law_score = max(0, 100 - risk_score + 5)
    ethics_score = max(0, 100 - risk_score - 5)
    if risk_score >= 70:
        status_text, risk_tag = "고위험", "risk-tag-high"
    elif risk_score >= 40:
        status_text, risk_tag = "유의", "risk-tag-mid"
    else:
        status_text, risk_tag = "안전", "risk-tag-low"

    return {
        "risk_score": risk_score,
        "safe_score": safe_score,
        "law_score": law_score,
        "ethics_score": ethics_score,
        "status_text": status_text,
        "risk_tag": risk_tag,
        "reasons": reasons,
    }


def _save_diagnosis_history(form: dict, result: dict, analysis: str):
    token = st.session_state.get("diagnosis_run_token")
    if not token or st.session_state.get("last_saved_diagnosis_token") == token:
        return
    _append_diagnosis_history({
        "id": token,
        "type": "환경 진단",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": form.get("service_name", "AI 서비스"),
        "summary": {
            "종합 점수": result["safe_score"],
            "법률 준수": result["law_score"],
            "윤리 점수": result["ethics_score"],
            "리스크": result["status_text"],
            "리스크 스코어": f'{result["risk_score"]}%',
        },
        "reasons": result["reasons"],
        "risk_tag": result["risk_tag"],
        "form": dict(form),
        "analysis": analysis,
    })
    st.session_state.last_saved_diagnosis_token = token
    st.session_state.latest_diagnosis = st.session_state.diagnosis_history[0]


def _sanitize_asset_report(text: str) -> str:
    """산출물 분석서에서 법령·조문 인용 표현을 제거합니다."""
    if not text:
        return ""
    cleaned = text
    patterns = [
        r"인공지능\s*기본법\s*제\s*\d+조[^\n]*",
        r"개인정보보호법\s*제\s*\d+조[^\n]*",
        r"제\s*\d+조\s*제?\s*\d+항[^\n]*",
        r"제\s*\d+조[^\n]*",
        r"\[출력\s*규칙\][^\n]*",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _sanitize_core_report(text: str) -> str:
    """분석 본문에서 예시·조문 인용을 제거해 핵심 판단만 남깁니다."""
    if not text:
        return ""
    cleaned = _sanitize_asset_report(text)
    patterns = [
        r"(?im)^\s*(예시|예:|예를\s*들어|사례)\s*[:：]?.*$",
        r"(?im)^\s*(법적\s*근거|관련\s*근거|근거\s*조항)\s*[:：].*$",
        r"\([^\)]*제\s*\d+조[^\)]*\)",
        r"\[[^\]]*제\s*\d+조[^\]]*\]",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


DIAGNOSIS_SECTION_HELP = {
    "진단 요약": "인공지능 기본법 제3조(기본원칙), 제31조(투명성 의무), 제33조·제34조(고영향 AI 확인 및 안전성·신뢰성 확보)를 기준으로 종합 판단합니다.",
    "우선 조치": "인공지능 기본법 제31조(사전고지·생성물 표시·가상 결과물 표시), 제32조(안전성 확보), 제34조(고영향 AI 조치)를 근거로 긴급 개선 항목을 정합니다.",
    "운영 가이드": "인공지능 기본법 제3조(설명 제공 권리), 제15조(학습용데이터 관리), 개인정보보호법상 적법 수집·이용 원칙을 운영 기준으로 반영합니다.",
    "재점검 기준": "인공지능 기본법 제40조(자료 제출·사실조사 및 시정명령), 제43조(과태료)를 고려해 변경·배포 전 점검 기준을 제시합니다.",
}


ASSET_SECTION_HELP = {
    "분석 개요": "인공지능 기본법 제31조의 생성형 AI 사전고지·표시 의무와 이용자 오인 방지 관점에서 산출물 성격을 요약합니다.",
    "주요 리스크": "인공지능 기본법 제31조 제2항·제3항의 생성물 표시 및 가상 결과물 인식 조치, 딥페이크·오인 가능성을 기준으로 판단합니다.",
    "개선 권고 사항": "인공지능 기본법 제31조의 투명성 의무 이행을 위해 표시, 워터마크, 안내문구, 배포 전 확인 조치를 권고합니다.",
    "종합 의견": "인공지능 기본법 제3조의 신뢰성 원칙과 제31조의 투명성 의무를 바탕으로 배포 가능성과 보완 우선순위를 정리합니다.",
}


def _render_report_sections(report: str, section_help: dict[str, str]):
    """Markdown 보고서의 제목을 Streamlit 제목+? 도움말로 렌더링합니다."""
    report = _sanitize_core_report(report)
    if not report:
        st.info("분석 결과가 없습니다.")
        return
    parts = re.split(r"(?m)^##\s+(.+?)\s*$", report)
    if len(parts) == 1:
        st.markdown(report)
        return

    preamble = parts[0].strip()
    if preamble:
        st.markdown(preamble)
    for idx in range(1, len(parts), 2):
        title = parts[idx].strip().strip("*")
        body = parts[idx + 1].strip() if idx + 1 < len(parts) else ""
        help_text = next((help_msg for key, help_msg in section_help.items() if key in title), None)
        st.subheader(title, help=help_text)
        if body:
            st.markdown(body)


def _save_asset_history(media_choice: str, resource_label: str, analysis: str):
    token = st.session_state.get("asset_run_token")
    if not token or st.session_state.get("last_saved_asset_token") == token:
        return
    _append_diagnosis_history({
        "id": token,
        "type": "산출물 분석",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": resource_label,
        "summary": {"분석 유형": media_choice, "대상": resource_label},
        "reasons": [],
        "form": {"media_choice": media_choice, "resource": resource_label},
        "analysis": analysis,
    })
    st.session_state.last_saved_asset_token = token
    st.session_state.latest_asset = st.session_state.diagnosis_history[0]


def _mp_fmt_date(created_at: str) -> str:
    try:
        return datetime.strptime(created_at, "%Y-%m-%d %H:%M").strftime("%Y.%m.%d %H:%M")
    except ValueError:
        return created_at


def _mp_val_class(field: str, value) -> str:
    if field == "ai_marking":
        return "mp-val-good" if value else "mp-val-bad"
    if value in ("이행 완료", "가능", "예"):
        return "mp-val-good"
    if value in ("미이행", "불가능"):
        return "mp-val-bad"
    return "mp-val-neutral"


def _mp_display_val(field: str, value) -> str:
    if field == "ai_marking":
        return "True" if value else "False"
    if isinstance(value, list):
        return ", ".join(value)
    return str(value)


def _mp_risk_meta(status: str) -> tuple[str, str]:
    mapping = {
        "안전": ("낮은 위험", "mp-risk-badge-low"),
        "유의": ("중간 위험", "mp-risk-badge-mid"),
        "고위험": ("높은 위험", "mp-risk-badge-high"),
    }
    return mapping.get(status, ("-", "mp-risk-badge-low"))


def _mp_field_row(icon: str, label: str, value: str, val_class: str = "mp-val-neutral") -> str:
    return (
        f'<div class="mp-field">'
        f'<div class="mp-field-icon">{icon}</div>'
        f'<div class="mp-field-body"><div class="mp-field-label">{label}</div>'
        f'<div class="mp-field-value {val_class}">{value}</div></div></div>'
    )


def _mp_build_legal_bullets(form: dict) -> str:
    location = form.get("business_location", "국내")
    explainable = form.get("explainable", "가능")
    bullets = [
        (
            "적용 범위",
            f"본 서비스는 사업자 소재지가 '{location}'이며, "
            "국내 시장·이용자에게 영향을 미치는 경우 인공지능 기본법의 적용 대상이 될 수 있습니다.",
        ),
        (
            "기본 원칙",
            "인공지능의 안전성·신뢰성 제고 방향으로 발전하도록 하며, "
            "이용자의 설명 제공 권리를 보장해야 합니다.",
        ),
        (
            "기술적 설명력",
            f"기술적 설명력이 '{explainable}'로 평가되었으며, "
            + (
                "이용자에게 결과 도출 원리에 대한 의미 있는 설명을 제공할 수 있는 상태입니다."
                if explainable == "가능"
                else "이용자 설명 청구 권리 대응을 위한 설명 체계 구축이 필요합니다."
            ),
        ),
    ]
    html = '<div class="mp-subsection"><div class="mp-subsection-title">3.1 인공지능 기본법 준수</div>'
    for title, text in bullets:
        html += (
            f'<div class="mp-bullet"><span class="mp-bullet-check">✓</span>'
            f"<div><strong>{title}:</strong> {text}</div></div>"
        )
    html += "</div>"
    html += (
        '<div class="mp-subsection"><div class="mp-subsection-title">3.2 윤리적 기준 준수</div>'
        '<div class="mp-bullet"><span class="mp-bullet-check">✓</span>'
        "<div><strong>인공지능윤리:</strong> 인간의 존엄성과 기본권을 존중하고, "
        "안전하고 신뢰할 수 있는 AI 서비스 제공을 위해 윤리적 기준을 준수해야 합니다.</div></div>"
        "</div>"
    )
    return html


def _mp_build_additional_notes(form: dict) -> str:
    notes: list[tuple[str, str, str]] = []
    if form.get("is_generative") == "예" and not form.get("ai_marking"):
        notes.append((
            "👁",
            "AI 표시 여부",
            "현재 'False'로 표시되어 있으나, 이용자에게 AI 사용 사실을 명확히 알리는 것이 권장됩니다.",
        ))
    data_sources = form.get("data_sources", [])
    if data_sources:
        notes.append((
            "🗄",
            "데이터 수집 및 활용",
            f"데이터 수집 출처는 {', '.join(data_sources)}에 기반하고 있으며, "
            "적법한 절차와 이용자 동의를 준수하는지 지속 점검이 필요합니다.",
        ))
    if form.get("user_notify") == "미이행":
        notes.append((
            "⚠",
            "사전 고지",
            "생성형 AI 서비스 이용자 사전 고지 의무가 미이행 상태입니다. 즉시 고지 체계를 구축하세요.",
        ))
    if form.get("virtual_content") == "예" and form.get("virtual_notify") == "미이행":
        notes.append((
            "⚠",
            "가상 결과물 표시",
            "가상 결과물 인식 조치가 미이행 상태입니다. 워터마크 등 표시 조치가 필요합니다.",
        ))
    if not notes:
        notes.append((
            "✓",
            "종합 검토",
            "현재 입력된 정보 기준으로 추가 긴급 조치 항목은 없습니다. 정기적인 재진단을 권장합니다.",
        ))
    html = ""
    for icon, title, text in notes:
        html += (
            f'<div class="mp-note"><span class="mp-note-icon">{icon}</span>'
            f'<div><div class="mp-note-title">{title}</div><div class="mp-note-text">{text}</div></div></div>'
        )
    return html


def _mp_build_report_md(record: dict) -> str:
    lines = [
        f"# fixflawlaw 진단 보고서",
        f"",
        f"- 유형: {record.get('type', '-')}",
        f"- 제목: {record.get('title', '-')}",
        f"- 일시: {record.get('created_at', '-')}",
        f"",
    ]
    summary = record.get("summary", {})
    if record.get("type") == "환경 진단":
        lines.extend([
            "## 점수 요약",
            f"- 종합 점수: {summary.get('종합 점수', '-')}",
            f"- 법률 준수: {summary.get('법률 준수', '-')}",
            f"- 윤리 점수: {summary.get('윤리 점수', '-')}",
            f"- 리스크: {summary.get('리스크', '-')}",
            "",
        ])
        form = record.get("form", {})
        lines.extend([
            "## 서비스 개요",
            f"- 서비스명: {form.get('service_name', '-')}",
            f"- 규모: {form.get('company_size', '-')}",
            f"- 도메인: {form.get('high_impact_domain', '-')}",
            "",
            "## 분석 내용",
            record.get("analysis", "분석 내용 없음"),
        ])
    else:
        lines.extend([
            "## 분석 요약",
            f"- 분석 유형: {summary.get('분석 유형', '-')}",
            f"- 대상: {summary.get('대상', '-')}",
            "",
            "## 분석 내용",
            record.get("analysis", "분석 내용 없음"),
        ])
    return "\n".join(lines)


def _mp_find_korean_font() -> str | None:
    bundled_candidates = [
        os.path.join(ASSETS_DIR, "malgun.ttf"),
        os.path.join(ASSETS_DIR, "fonts", "NotoSansKR-Regular.otf"),
        os.path.join(ASSETS_DIR, "fonts", "NanumGothic.ttf"),
    ]
    bundled = next((path for path in bundled_candidates if os.path.exists(path)), None)
    if bundled:
        return bundled

    system_candidates = [
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "malgun.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "malgunsl.ttf"),
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    source = next((path for path in system_candidates if os.path.exists(path)), None)
    if not source:
        return None

    os.makedirs(ASSETS_DIR, exist_ok=True)
    target = os.path.join(ASSETS_DIR, "malgun.ttf")
    if not os.path.exists(target):
        shutil.copy2(source, target)
    return target


def _mp_pdf_sanitize(text) -> str:
    if text is None:
        return ""
    text = str(text)
    replacements = {
        "✓": "[O]",
        "✔": "[O]",
        "⚠": "!",
        "⚠️": "!",
        "•": "-",
        "·": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "–": "-",
        "—": "-",
        "\u00a0": " ",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def _mp_plain_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
    return _mp_pdf_sanitize(text.strip())


def _mp_pdf_grade(score: int) -> tuple[str, tuple[int, int, int]]:
    if score >= 85:
        return "우수", (22, 163, 74)
    if score >= 70:
        return "양호", (37, 99, 235)
    return "보통", (249, 115, 22)


def _mp_pdf_overall_label(score: int) -> str:
    if score >= 85:
        return "우수"
    if score >= 70:
        return "양호"
    return "보통"


def _mp_clip(text: str, limit: int = 180) -> str:
    text = _mp_plain_text(text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _mp_parse_asset_sections(analysis: str) -> dict[str, str]:
    text = analysis or ""
    sections = {"개요": "", "리스크": "", "권고": "", "결론": ""}
    patterns = [
        ("개요", r"##\s*분석\s*개요\s*(.*?)(?=##\s*|$)"),
        ("리스크", r"##\s*주요\s*리스크\s*(.*?)(?=##\s*|$)"),
        ("권고", r"##\s*개선\s*권고\s*사항\s*(.*?)(?=##\s*|$)"),
        ("결론", r"##\s*종합\s*의견\s*(.*?)(?=##\s*|$)"),
    ]
    for key, pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            sections[key] = _mp_plain_text(m.group(1))
    if not any(sections.values()):
        plain = _mp_plain_text(text)
        sections["개요"] = _mp_clip(plain, 220)
        sections["결론"] = _mp_clip(plain, 180)
    return sections


def _mp_split_bullets(text: str, limit: int = 4) -> list[str]:
    if not text:
        return []
    lines = []
    for raw in re.split(r"[\n;]+", text):
        line = raw.strip(" -\t•*·")
        if len(line) >= 8:
            lines.append(_mp_clip(line, 110))
    if not lines and text.strip():
        lines = [_mp_clip(text, 110)]
    return lines[:limit]


def _mp_pdf_detail_scores(form: dict, summary: dict) -> list[tuple[str, int, str, str]]:
    law = int(summary.get("법률 준수", 80) or 0)
    ethics = int(summary.get("윤리 점수", 75) or 0)

    transparency = 90 if form.get("user_notify") == "이행 완료" else 60
    if form.get("is_generative") == "예" and not form.get("ai_marking"):
        transparency -= 15
    transparency = max(0, min(100, transparency))

    safety = 88 if form.get("heavy_compute") == "아니오" else 68
    if form.get("high_impact_domain") != "해당 없음 (일반 사무, 단순 요약 등)":
        safety -= 12
    safety = max(0, min(100, safety))

    fairness = ethics
    accountability = min(100, law)
    privacy = 92 if "적법한 절차 및 이용자 동의 기반" in form.get("data_sources", []) else 58
    explainability = 86 if form.get("explainable") == "가능" else 48

    return [
        ("투명성", transparency, "생성형 AI 사전 고지 및 AI 표시 의무 이행 상태를 점검했습니다.", "제31조 (투명성 의무)"),
        ("안전성", safety, "고영향 AI·대규모 연산량 사용 여부에 따른 안전 관리 수준을 평가했습니다.", "제32조 (안전성 확보)"),
        ("공정성", fairness, "차별·편향 방지 및 공정한 AI 운영 체계를 점검했습니다.", "AI 윤리 기준"),
        ("책임성", accountability, "기업의 책임 있는 AI 운영 및 내부 통제 수준을 평가했습니다.", "기업 책임 원칙"),
        ("프라이버시 보호", privacy, "데이터 수집·활용 절차의 적법성과 보호 수준을 확인했습니다.", "개인정보보호법"),
        ("설명가능성", explainability, "이용자 설명 제공 권리 대응 및 결과 설명 체계를 점검했습니다.", "설명 제공 권리"),
    ]


def _mp_pdf_asset_detail_scores(record: dict, sections: dict[str, str]) -> list[tuple[str, int, str, str]]:
    analysis = (record.get("analysis") or "").lower()
    media = str(record.get("summary", {}).get("분석 유형", ""))
    risk_hits = sum(1 for k in ("딥페이크", "오인", "고위험", "유포", "허위", "미표시") if k in analysis)
    ok_hits = sum(1 for k in ("양호", "적절", "충분", "명확", "권장 준수") if k in analysis)

    def clamp(v: int) -> int:
        return max(35, min(95, v))

    base = 78 - risk_hits * 8 + ok_hits * 4
    marking = clamp(base - (12 if "표시" in analysis and ("부족" in analysis or "미" in analysis) else 0))
    transparency = clamp(base - (10 if "고지" in analysis and ("부족" in analysis or "필요" in analysis) else 0))
    safety = clamp(base - risk_hits * 6)
    authenticity = clamp(base - (14 if "딥페이크" in analysis or "합성" in analysis else 0))
    distribution = clamp(base - (10 if "유포" in analysis else 0))
    usability = clamp(base + (4 if "이미지" in media else 0))

    return [
        ("투명성", transparency, "AI 생성 사실 고지 및 이용자 인식 가능성을 점검했습니다.", "투명성 실무 기준"),
        ("표시·워터마크", marking, "생성물 표시·워터마크 등 식별 조치 수준을 평가했습니다.", "표시·고지 실무"),
        ("안전성", safety, "오인·남용·유해 활용 가능성에 대한 안전 수준을 평가했습니다.", "안전 관리 실무"),
        ("진위·오인 방지", authenticity, "실제 콘텐츠로 오인될 수 있는지 여부를 점검했습니다.", "오인 방지 기준"),
        ("유포 리스크", distribution, "재배포·확산에 따른 리스크 관리 필요성을 확인했습니다.", "유포 관리 실무"),
        ("이용자 안내", usability, "이용자 안내문·주의문구 제공 수준을 점검했습니다.", "이용자 안내 실무"),
    ]


def _mp_pdf_analysis_points(form: dict, detail_scores: list) -> list[tuple[str, str]]:
    points: list[tuple[str, str]] = []
    service_name = form.get("service_name", "서비스")
    points.append(("ok", f"{service_name}의 주요 기능과 목적이 명확하게 정의되어 있습니다."))
    if "적법한 절차 및 이용자 동의 기반" in form.get("data_sources", []):
        points.append(("ok", "데이터 수집 및 활용 절차가 적절히 마련되어 있습니다."))
    else:
        points.append(("warn", "데이터 수집 및 활용 절차의 적법성을 재점검할 필요가 있습니다."))

    explain_score = next((s for n, s, _, _ in detail_scores if n == "설명가능성"), 70)
    if explain_score < 75:
        points.append(("warn", "AI 모델의 의사결정 과정에 대한 설명이 부족합니다."))
    else:
        points.append(("ok", "AI 모델의 의사결정 과정 설명 체계가 마련되어 있습니다."))

    fairness_score = next((s for n, s, _, _ in detail_scores if n == "공정성"), 70)
    if fairness_score < 75:
        points.append(("warn", "잠재적 편향에 대한 모니터링 및 대응 체계가 필요합니다."))
    else:
        points.append(("ok", "공정성·편향 관리 체계가 비교적 양호합니다."))
    return points[:4]


def _mp_pdf_asset_analysis_points(sections: dict[str, str], detail_scores: list) -> list[tuple[str, str]]:
    points: list[tuple[str, str]] = []
    overview = _mp_split_bullets(sections.get("개요", ""), 1)
    risks = _mp_split_bullets(sections.get("리스크", ""), 2)
    recs = _mp_split_bullets(sections.get("권고", ""), 1)

    if overview:
        points.append(("ok", overview[0]))
    else:
        points.append(("ok", "산출물 분석 대상과 검토 범위가 확인되었습니다."))

    weak = sorted(detail_scores, key=lambda x: x[1])[:2]
    for name, score, _, _ in weak:
        kind = "warn" if score < 75 else "ok"
        msg = f"{name} 항목 점수({score}점)에 대한 추가 점검이 필요합니다." if kind == "warn" else f"{name} 항목은 양호한 수준입니다."
        points.append((kind, msg))

    for risk in risks[:1]:
        points.append(("warn", risk))
    for rec in recs[:1]:
        points.append(("warn", rec))
    return points[:4]


def _mp_pdf_recommendations(form: dict, detail_scores: list) -> list[tuple[str, str, str]]:
    recs: list[tuple[str, str, str]] = []
    explain_score = next((s for n, s, _, _ in detail_scores if n == "설명가능성"), 70)
    fairness_score = next((s for n, s, _, _ in detail_scores if n == "공정성"), 70)

    if explain_score < 80:
        recs.append((
            "설명가능성 강화",
            "AI 모델의 의사결정 과정에 대한 설명 절차를 마련하고, 이용자 요청 시 의미 있는 설명을 제공하세요.",
            "+10점",
        ))
    if fairness_score < 80:
        recs.append((
            "편향 모니터링 체계 구축",
            "데이터 및 모델의 편향 가능성을 정기적으로 점검하고, 이상 징후 발생 시 대응 절차를 수립하세요.",
            "+8점",
        ))
    if form.get("is_generative") == "예" and not form.get("ai_marking"):
        recs.append((
            "AI 사용 고지 강화",
            "이용자에게 AI 사용 사실과 범위를 명확히 고지하고, 생성물 표시를 적용하세요.",
            "+5점",
        ))
    if form.get("user_notify") == "미이행":
        recs.append((
            "사전 고지 의무 이행",
            "생성형 AI 서비스 이용 전 사전 고지 체계를 즉시 구축·운영하세요.",
            "+12점",
        ))
    if form.get("heavy_compute") == "예":
        recs.append((
            "안전관리체계 고도화",
            "대규모 연산량 AI에 대한 위험 식별·평가·완화 및 사고 대응 체계를 점검하세요.",
            "+7점",
        ))
    if not recs:
        recs.append((
            "정기 재진단 수행",
            "현재 준수 수준을 유지하기 위해 분기별 자가 점검 및 재진단을 권장합니다.",
            "+3점",
        ))
    while len(recs) < 3:
        recs.append((
            "내부 점검 체계 유지",
            "주요 변경 사항 발생 시 동일 기준의 재진단을 수행해 준수 수준을 유지하세요.",
            "+3점",
        ))
    return recs[:3]


def _mp_pdf_asset_recommendations(sections: dict[str, str], detail_scores: list) -> list[tuple[str, str, str]]:
    recs: list[tuple[str, str, str]] = []
    for bullet in _mp_split_bullets(sections.get("권고", ""), 3):
        title = _mp_clip(bullet, 18).rstrip("…")
        recs.append((title or "개선 권고", bullet, "+6점"))

    weak = sorted(detail_scores, key=lambda x: x[1])
    for name, score, desc, _ in weak:
        if score >= 80:
            continue
        gain = f"+{max(5, (80 - score) // 2)}점"
        recs.append((f"{name} 보완", desc, gain))

    if not recs:
        recs.append((
            "표시·고지 재점검",
            "배포 전 AI 생성 고지와 표시 조치를 한 번 더 확인하세요.",
            "+5점",
        ))
    while len(recs) < 3:
        recs.append((
            "배포 전 최종 점검",
            "배포 채널별 안내문구와 식별 표시가 누락되지 않았는지 확인하세요.",
            "+3점",
        ))
    return recs[:3]


class _ComplianceReportPdf:
    """제시된 카드형 1페이지 레이아웃으로 환경진단/산출물 PDF를 생성합니다."""

    FOOTER_Y = 284
    CONTENT_BOTTOM = 278

    def __init__(self, font_path: str):
        FPDF = _ensure_fpdf2()
        self.pdf = FPDF(orientation="P", unit="mm", format="A4")
        # 자동 페이지 추가는 빈 장을 만들 수 있어 수동으로만 관리합니다.
        self.pdf.set_auto_page_break(auto=False, margin=12)
        self.pdf.set_margins(10, 10, 10)
        self.pdf.alias_nb_pages()
        self.pdf.add_page()
        self.pdf.add_font("K", "", font_path)
        self.x0 = self.pdf.l_margin
        self.w = self.pdf.epw
        self.gap = 4.0
        self.col_w = (self.w - self.gap) / 2
        self.y = self.pdf.t_margin

    def _line_h(self, size: float) -> float:
        return max(3.4, size * 0.40)

    def _set_style(self, size: float, bold: bool = False, color: tuple[int, int, int] = (30, 41, 59)):
        self.pdf.set_font("K", "", size + (0.7 if bold else 0))
        self.pdf.set_text_color(*color)

    def _measure(self, text: str, w: float, size: float, bold: bool = False, lh: float | None = None) -> float:
        from fpdf.enums import MethodReturnValue

        text = _mp_pdf_sanitize(text)
        if not text:
            return 0.0
        line_h = lh or self._line_h(size)
        self._set_style(size, bold)
        height = self.pdf.multi_cell(
            w, line_h, text, align="L", dry_run=True, output=MethodReturnValue.HEIGHT,
        )
        return float(height)

    def _txt(self, x: float, y: float, text: str, size: float = 9, bold: bool = False,
             color: tuple[int, int, int] = (30, 41, 59), w: float | None = None, align: str = "L",
             lh: float | None = None, max_h: float | None = None) -> float:
        text = _mp_pdf_sanitize(text)
        if not text:
            return y
        line_h = lh or self._line_h(size)
        width = w if w and w > 0 else max(10, self.w - (x - self.x0))
        if max_h is not None:
            # 높이 제한 초과 시 잘라 빈 페이지/넘침을 방지합니다.
            while text and self._measure(text, width, size, bold, line_h) > max_h:
                text = text[:-8].rstrip() + "…"
                if len(text) < 12:
                    break
        self._set_style(size, bold, color)
        self.pdf.set_xy(x, y)
        self.pdf.multi_cell(width, line_h, text, align=align)
        return self.pdf.get_y()

    def _txt_block(self, x: float, y: float, text: str, w: float, size: float = 9,
                   bold: bool = False, color: tuple[int, int, int] = (71, 85, 105),
                   line_h: float | None = None, max_h: float | None = None) -> float:
        return self._txt(x, y, text, size=size, bold=bold, color=color, w=w, lh=line_h, max_h=max_h)

    def _rounded(self, x: float, y: float, w: float, h: float,
                 fill: tuple[int, int, int] = (255, 255, 255), draw: bool = True):
        self.pdf.set_fill_color(*fill)
        self.pdf.set_draw_color(226, 232, 240)
        self.pdf.set_line_width(0.28)
        style = "DF" if draw else "F"
        self.pdf.rect(x, y, w, h, style=style, round_corners=True, corner_radius=1.8)

    def _card(self, x: float, y: float, w: float, h: float, title: str) -> float:
        self._rounded(x, y, w, h, fill=(255, 255, 255), draw=True)
        self.pdf.set_fill_color(248, 250, 252)
        self.pdf.rect(x, y, w, 8.2, style="F", round_corners=True, corner_radius=1.8)
        self.pdf.rect(x, y + 4, w, 4.2, style="F")
        self.pdf.set_draw_color(226, 232, 240)
        self.pdf.line(x, y + 8.2, x + w, y + 8.2)
        self._txt(x + 3.2, y + 1.5, title, size=8.6, bold=True, color=(37, 99, 235), w=w - 6, lh=3.8)
        return y + 10.2

    def _progress(self, x: float, y: float, w: float, score: int, color: tuple[int, int, int], h: float = 2.2):
        self.pdf.set_fill_color(241, 245, 249)
        self.pdf.rect(x, y, w, h, style="F", round_corners=True, corner_radius=0.8)
        fill_w = max(0.5, w * max(0, min(100, score)) / 100)
        self.pdf.set_fill_color(*color)
        self.pdf.rect(x, y, fill_w, h, style="F", round_corners=True, corner_radius=0.8)

    def _hline_bar(self, x: float, y: float, w: float, label: str, score: int,
                   color: tuple[int, int, int]) -> float:
        label_w = w * 0.36
        score_w = 16
        self._txt(x, y, label, size=7.4, color=(71, 85, 105), w=label_w, lh=3.4)
        self._txt(x + w - score_w, y, f"{score}/100", size=7.2, bold=True, w=score_w, align="R", lh=3.4)
        self._progress(x, y + 4.0, w, score, color, h=2.0)
        return y + 8.0

    def _draw_donut(self, cx: float, cy: float, r: float, score: int, label: str):
        d = r * 2
        box_x, box_y = cx - r, cy - r
        self.pdf.set_draw_color(226, 232, 240)
        self.pdf.set_line_width(4.2)
        self.pdf.arc(box_x, box_y, d, 0, 359.9)
        if score > 0:
            self.pdf.set_draw_color(37, 99, 235)
            sweep = min(359.5, 360.0 * score / 100.0)
            self.pdf.arc(box_x, box_y, d, 90, 90 - sweep, clockwise=True)
        self._txt(cx - 12, cy - 6.2, f"{score}", size=13, bold=True, w=24, align="C", lh=5.0)
        self._txt(cx - 12, cy - 0.8, "/ 100", size=7.2, color=(100, 116, 139), w=24, align="C", lh=3.2)
        self._txt(cx - 12, cy + 3.6, label, size=8.2, bold=True, color=(37, 99, 235), w=24, align="C", lh=3.5)

    def _footer(self, page: int | None = None):
        page = page or self.pdf.page_no()
        self.pdf.set_draw_color(226, 232, 240)
        self.pdf.line(self.x0, self.FOOTER_Y, self.x0 + self.w, self.FOOTER_Y)
        self._txt(
            self.x0, self.FOOTER_Y + 1.8,
            "본 보고서는 입력 정보 및 진단 결과를 바탕으로 자동 생성되었습니다.",
            size=6.8, color=(148, 163, 184), w=self.w * 0.72, lh=3.2,
        )
        self._txt(
            self.x0 + self.w - 32, self.FOOTER_Y + 1.8,
            f"페이지 {page} / {{nb}}",
            size=6.8, color=(148, 163, 184), w=32, align="R", lh=3.2,
        )

    def _draw_header(self, created: str, report_title: str = "AI 컴플라이언스\n진단 보고서"):
        self._rounded(self.x0, self.y, self.w, 16.5)
        self.pdf.set_fill_color(37, 99, 235)
        self.pdf.rect(self.x0 + 3.2, self.y + 4.0, 6.4, 6.4, style="F", round_corners=True, corner_radius=1.2)
        self._txt(self.x0 + 4.2, self.y + 4.8, "f", size=9, bold=True, color=(255, 255, 255), w=5, align="C", lh=3.8)
        self._txt(self.x0 + 12, self.y + 3.6, "fixflawlaw", size=11, bold=True, lh=4.5)
        self._txt(self.x0 + 12, self.y + 8.8, "AI 컴플라이언스 진단 플랫폼", size=6.8, color=(100, 116, 139), lh=3.2)
        self._txt(
            self.x0 + self.w - 72, self.y + 2.8, report_title,
            size=10.5, bold=True, w=70, align="R", lh=4.2,
        )
        self._txt(
            self.x0 + self.w - 72, self.y + 11.6, f"생성일: {created}",
            size=7.0, color=(100, 116, 139), w=70, align="R", lh=3.2,
        )
        return self.y + 19.5

    def _draw_kv_fields(self, x: float, y: float, w: float, fields: list[tuple[str, str]]) -> float:
        fy = y
        for label, value in fields:
            self._txt(x, fy, label, size=7.0, color=(100, 116, 139), w=26, lh=3.3)
            fy = self._txt(x + 27, fy, str(value), size=7.6, bold=True, w=w - 29, lh=3.4, max_h=7.0) + 1.0
        return fy

    def _draw_score_side(self, x: float, y: float, law: int, ethics: int,
                         risk_status: str, risk_sub: str, risk_color: tuple[int, int, int]) -> float:
        self._txt(x, y, "법률 준수 점수", size=6.8, color=(100, 116, 139), w=34, lh=3.2)
        self._txt(x + 34, y, f"{law}/100", size=7.4, bold=True, w=18, align="R", lh=3.2)
        self._progress(x, y + 4.0, 52, law, (34, 197, 94), h=1.8)

        self._txt(x, y + 8.0, "윤리 점수", size=6.8, color=(100, 116, 139), w=34, lh=3.2)
        self._txt(x + 34, y + 8.0, f"{ethics}/100", size=7.4, bold=True, w=18, align="R", lh=3.2)
        self._progress(x, y + 12.0, 52, ethics, (139, 92, 246), h=1.8)

        self._txt(x, y + 16.2, "리스크 수준", size=6.8, color=(100, 116, 139), w=34, lh=3.2)
        self._txt(x + 20, y + 16.2, f"{risk_status} ({risk_sub})", size=7.4, bold=True,
                  color=risk_color, w=36, align="R", lh=3.2)
        return y + 22

    def _draw_analysis_cards(self, x: float, y: float, w: float, intro: str,
                             points: list[tuple[str, str]], max_bottom: float) -> float:
        py = self._txt_block(x, y, intro, w, size=6.9, line_h=3.5, max_h=11)
        py += 1.2
        for kind, text in points:
            remain = max_bottom - py
            if remain < 8:
                break
            mark = "[O]" if kind == "ok" else "[!]"
            color = (22, 163, 74) if kind == "ok" else (249, 115, 22)
            fill = (240, 253, 244) if kind == "ok" else (255, 247, 237)
            box_h = min(10.5, remain - 0.5)
            self._rounded(x, py, w, box_h, fill=fill, draw=True)
            self._txt(x + 1.8, py + 1.4, mark, size=7.2, bold=True, color=color, w=7, lh=3.2)
            self._txt_block(x + 8.5, py + 1.4, text, w - 10.5, size=6.6, line_h=3.2, max_h=box_h - 2.5)
            py += box_h + 1.2
        return py

    def _draw_detail_table(self, x: float, y: float, w: float,
                           detail_scores: list[tuple[str, int, str, str]],
                           max_bottom: float) -> float:
        cols = [24, 72, 18, 16, w - 24 - 72 - 18 - 16 - 4]
        headers = ["항목", "진단 내용", "점수", "결과", "관련 기준"]
        hx = x + 2
        self.pdf.set_fill_color(241, 245, 249)
        self.pdf.rect(x + 1.5, y, w - 3, 6.4, style="F", round_corners=True, corner_radius=0.8)
        for header, cw in zip(headers, cols):
            self._txt(hx, y + 1.2, header, size=6.6, bold=True, color=(51, 65, 85), w=cw - 1, lh=3.2)
            hx += cw
        ty = y + 7.2
        for name, score, desc, law_ref in detail_scores:
            if ty + 7.5 > max_bottom:
                break
            row_top = ty
            self._txt(x + 2.2, row_top + 0.5, name, size=6.7, bold=True, w=cols[0] - 1.5, lh=3.1, max_h=6)
            desc_bottom = self._txt_block(
                x + 2 + cols[0], row_top + 0.4, desc, cols[1] - 1.5, size=6.3, line_h=3.1, max_h=7.5,
            )
            cx = x + 2 + cols[0] + cols[1]
            self._txt(cx, row_top + 0.5, f"{score}/100", size=6.6, w=cols[2] - 1, align="C", lh=3.1)
            grade, grade_color = _mp_pdf_grade(score)
            cx += cols[2]
            self._txt(cx, row_top + 0.5, grade, size=6.6, bold=True, color=grade_color, w=cols[3] - 1, align="C", lh=3.1)
            cx += cols[3]
            law_bottom = self._txt(cx, row_top + 0.4, law_ref, size=6.2, color=(71, 85, 105), w=cols[4] - 1, lh=3.1, max_h=7.5)
            ty = max(desc_bottom, law_bottom, row_top + 6.2) + 1.1
        return ty

    def _draw_recommendations(self, x: float, y: float, w: float,
                              recommendations: list[tuple[str, str, str]],
                              max_bottom: float) -> float:
        colors = [(220, 38, 38), (249, 115, 22), (234, 179, 8)]
        ry = y
        for idx, (title, desc, effect) in enumerate(recommendations[:3], start=1):
            if ry + 10 > max_bottom:
                break
            c = colors[idx - 1]
            self.pdf.set_fill_color(*c)
            self.pdf.ellipse(x + 0.8, ry + 0.6, 4.0, 4.0, style="F")
            self._txt(x + 0.8, ry + 0.9, str(idx), size=6.5, bold=True, color=(255, 255, 255), w=4.0, align="C", lh=3.2)
            self._txt(x + 6.2, ry, title, size=7.2, bold=True, w=w - 24, lh=3.4, max_h=3.8)
            self._txt(x + w - 16, ry, effect, size=6.4, bold=True, color=(220, 38, 38), w=15, align="R", lh=3.2)
            ry = self._txt_block(x + 6.2, ry + 3.8, desc, w - 8, size=6.4, line_h=3.2, max_h=7.0) + 1.6
        return ry

    def _build_common_layout(
        self,
        *,
        created: str,
        report_title: str,
        overview_fields: list[tuple[str, str]],
        total: int,
        overall: str,
        law: int,
        ethics: int,
        risk_status: str,
        risk_sub: str,
        risk_color: tuple[int, int, int],
        summary_note: str,
        detail_scores: list[tuple[str, int, str, str]],
        analysis_intro: str,
        analysis_points: list[tuple[str, str]],
        recommendations: list[tuple[str, str, str]],
        conclusion: str,
        overview_title: str = "서비스 개요",
        result_title: str = "종합 진단 결과",
        score_title: str = "세부 점수",
        analysis_title: str = "분석 요약",
        table_title: str = "상세 진단 결과",
        rec_title: str = "권고 사항 (우선순위)",
        conclusion_title: str = "종합 결론",
    ) -> bytes:
        y = self._draw_header(created, report_title)
        left_x = self.x0
        right_x = self.x0 + self.col_w + self.gap
        bar_colors = [
            (37, 99, 235), (34, 197, 94), (139, 92, 246),
            (249, 115, 22), (20, 184, 166), (59, 130, 246),
        ]

        # Row 1: overview + overall
        row1_h = 42
        inner = self._card(left_x, y, self.col_w, row1_h, overview_title)
        self._draw_kv_fields(left_x + 3.5, inner, self.col_w - 7, overview_fields)

        inner = self._card(right_x, y, self.col_w, row1_h, result_title)
        self._draw_donut(right_x + 22, inner + 14, 13.5, total, overall)
        self._draw_score_side(right_x + 40, inner + 1.5, law, ethics, risk_status, risk_sub, risk_color)
        self._txt_block(
            right_x + 3.5, inner + 26.5, summary_note,
            self.col_w - 7, size=6.3, line_h=3.1, max_h=8.5,
        )
        y += row1_h + 3.2

        # Row 2: detail scores + analysis
        row2_h = 58
        inner = self._card(left_x, y, self.col_w, row2_h, score_title)
        by = inner
        for (name, score, _, _), color in zip(detail_scores, bar_colors):
            by = self._hline_bar(left_x + 3.5, by, self.col_w - 7, name, score, color)

        inner = self._card(right_x, y, self.col_w, row2_h, analysis_title)
        self._draw_analysis_cards(
            right_x + 3.2, inner, self.col_w - 6.4, analysis_intro, analysis_points, y + row2_h - 2.5,
        )
        y += row2_h + 3.2

        # Row 3: detail table
        table_h = 62
        inner = self._card(self.x0, y, self.w, table_h, table_title)
        self._draw_detail_table(self.x0 + 1.5, inner, self.w - 3, detail_scores, y + table_h - 2.2)
        y += table_h + 3.2

        # Row 4: recommendations + conclusion (서명/사인 이미지 없음)
        row4_h = 40
        if y + row4_h > self.CONTENT_BOTTOM:
            row4_h = max(28, self.CONTENT_BOTTOM - y)

        inner = self._card(left_x, y, self.col_w, row4_h, rec_title)
        self._draw_recommendations(left_x + 3.2, inner, self.col_w - 6.4, recommendations, y + row4_h - 2.2)

        inner = self._card(right_x, y, self.col_w, row4_h, conclusion_title)
        self._txt_block(
            right_x + 3.5, inner, conclusion,
            self.col_w - 7, size=7.0, line_h=3.5, max_h=row4_h - 13,
        )

        self._footer(1)
        return bytes(self.pdf.output())

    def build_diagnosis(self, record: dict) -> bytes:
        form = record.get("form", {})
        summary = record.get("summary", {})
        total = int(summary.get("종합 점수", 0) or 0)
        law = int(summary.get("법률 준수", 0) or 0)
        ethics = int(summary.get("윤리 점수", 0) or 0)
        risk_status = summary.get("리스크", "안전")
        risk_sub, _ = _mp_risk_meta(risk_status)
        created = _mp_fmt_date(record.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M")))
        service_type = "생성형 AI 서비스" if form.get("is_generative") == "예" else "일반 AI 서비스"
        detail_scores = _mp_pdf_detail_scores(form, summary)
        analysis_points = _mp_pdf_analysis_points(form, detail_scores)
        recommendations = _mp_pdf_recommendations(form, detail_scores)
        overall = _mp_pdf_overall_label(total)
        risk_color = (22, 163, 74) if risk_status == "안전" else ((249, 115, 22) if risk_status == "유의" else (220, 38, 38))

        weak_names = [n for n, s, _, _ in sorted(detail_scores, key=lambda x: x[1])[:2]]
        analysis_intro = (
            f"{form.get('service_name', '서비스')}는 인공지능 기본법의 주요 요건을 전반적으로 준수하고 있으나, "
            f"{'·'.join(weak_names)} 측면에서 개선이 필요합니다."
        )
        summary_note = (
            f"종합 {total}점({overall}) · 법률 {law}점 · 윤리 {ethics}점. "
            f"리스크는 {risk_status}({risk_sub})로 평가되었습니다."
        )
        conclusion = (
            f"{form.get('service_name', '해당 서비스')}는 전반적으로 {overall}한 컴플라이언스 수준을 보이고 있습니다. "
            "본 보고서에서 확인된 개선 항목을 보완하면 더욱 신뢰할 수 있는 AI 서비스로 성장할 수 있습니다. "
            "정기 재진단을 통해 준수 수준을 유지·향상하시기 바랍니다."
        )

        return self._build_common_layout(
            created=created,
            report_title="AI 컴플라이언스\n진단 보고서",
            overview_fields=[
                ("서비스명", form.get("service_name", "-")),
                ("서비스 유형", service_type),
                ("규모", form.get("company_size", "-")),
                ("도메인", form.get("high_impact_domain", "-")),
                ("진단 일시", created),
            ],
            total=total,
            overall=overall,
            law=law,
            ethics=ethics,
            risk_status=risk_status,
            risk_sub=risk_sub,
            risk_color=risk_color,
            summary_note=summary_note,
            detail_scores=detail_scores,
            analysis_intro=analysis_intro,
            analysis_points=analysis_points,
            recommendations=recommendations,
            conclusion=conclusion,
        )

    def build_asset(self, record: dict) -> bytes:
        summary = record.get("summary", {})
        created = _mp_fmt_date(record.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M")))
        sections = _mp_parse_asset_sections(record.get("analysis", ""))
        detail_scores = _mp_pdf_asset_detail_scores(record, sections)
        analysis_points = _mp_pdf_asset_analysis_points(sections, detail_scores)
        recommendations = _mp_pdf_asset_recommendations(sections, detail_scores)

        total = int(round(sum(s for _, s, _, _ in detail_scores) / max(1, len(detail_scores))))
        law = next((s for n, s, _, _ in detail_scores if n == "투명성"), total)
        ethics = next((s for n, s, _, _ in detail_scores if n == "진위·오인 방지"), total)
        overall = _mp_pdf_overall_label(total)

        if total >= 80:
            risk_status, risk_sub, risk_color = "안전", "낮은 위험", (22, 163, 74)
        elif total >= 65:
            risk_status, risk_sub, risk_color = "유의", "중간 위험", (249, 115, 22)
        else:
            risk_status, risk_sub, risk_color = "고위험", "높은 위험", (220, 38, 38)

        target = str(record.get("title", summary.get("대상", "-")))
        media = str(summary.get("분석 유형", "-"))
        analysis_intro = _mp_clip(
            sections.get("개요")
            or f"{target}에 대한 산출물 컴플라이언스 스크리닝 결과입니다.",
            140,
        )
        summary_note = (
            f"산출물 종합 {total}점({overall}). 투명성 {law}점 · 진위/오인 방지 {ethics}점. "
            f"리스크는 {risk_status}({risk_sub})로 평가되었습니다."
        )
        conclusion = _mp_clip(
            sections.get("결론")
            or (
                f"{target} 산출물은 전반적으로 {overall} 수준입니다. "
                "표시·고지 및 오인 방지 조치를 보완하면 배포 리스크를 더 낮출 수 있습니다."
            ),
            260,
        )

        return self._build_common_layout(
            created=created,
            report_title="AI 산출물\n진단 보고서",
            overview_fields=[
                ("산출물명", _mp_clip(target, 42)),
                ("분석 유형", media),
                ("대상", _mp_clip(str(summary.get("대상", target)), 42)),
                ("검토 관점", "투명성·표시·오인 방지"),
                ("진단 일시", created),
            ],
            total=total,
            overall=overall,
            law=law,
            ethics=ethics,
            risk_status=risk_status,
            risk_sub=risk_sub,
            risk_color=risk_color,
            summary_note=summary_note,
            detail_scores=detail_scores,
            analysis_intro=analysis_intro,
            analysis_points=analysis_points,
            recommendations=recommendations,
            conclusion=conclusion,
            overview_title="산출물 개요",
            result_title="종합 진단 결과",
            score_title="세부 점수",
            analysis_title="분석 요약",
            table_title="상세 진단 결과",
            rec_title="권고 사항 (우선순위)",
            conclusion_title="종합 결론",
        )


def _mp_build_report_pdf(record: dict) -> bytes:
    font_path = _mp_find_korean_font()
    if not font_path:
        raise FileNotFoundError("한글 PDF 폰트를 찾을 수 없습니다.")
    builder = _ComplianceReportPdf(font_path)
    if record.get("type") == "환경 진단":
        return builder.build_diagnosis(record)
    return builder.build_asset(record)


def _render_mypage_diagnosis(record: dict):
    form = record.get("form", {})
    summary = record.get("summary", {})
    total = summary.get("종합 점수", 0)
    law = summary.get("법률 준수", 0)
    ethics = summary.get("윤리 점수", 0)
    risk_status = summary.get("리스크", "안전")
    risk_sub, risk_cls = _mp_risk_meta(risk_status)
    service_type = "생성형 AI 서비스" if form.get("is_generative") == "예" else "일반 AI 서비스"

    hero_html = f"""
    <div class="mp-hero">
        <div class="mp-hero-profile">
            <div class="mp-hero-icon">🧠</div>
            <div>
                <p class="mp-hero-name">{form.get("service_name", record.get("title", "AI 서비스"))}</p>
                <p class="mp-hero-date">{_mp_fmt_date(record.get("created_at", ""))}</p>
                <div class="mp-hero-tags">
                    <span class="mp-tag">{service_type}</span>
                    <span class="mp-tag">{form.get("company_size", "-")}</span>
                </div>
            </div>
        </div>
        <div class="mp-hero-metrics">
            <div class="mp-metric">
                <div class="mp-metric-label">종합 점수</div>
                <div class="mp-metric-score">{total} <span>/ 100</span></div>
                <div class="mp-bar"><div class="mp-bar-fill" style="width:{total}%;background:#2563EB;"></div></div>
            </div>
            <div class="mp-metric">
                <div class="mp-metric-label">법률 준수 점수</div>
                <div class="mp-metric-score">{law} <span>/ 100</span></div>
                <div class="mp-bar"><div class="mp-bar-fill" style="width:{law}%;background:#22C55E;"></div></div>
            </div>
            <div class="mp-metric">
                <div class="mp-metric-label">윤리 점수</div>
                <div class="mp-metric-score">{ethics} <span>/ 100</span></div>
                <div class="mp-bar"><div class="mp-bar-fill" style="width:{ethics}%;background:#8B5CF6;"></div></div>
            </div>
            <div class="mp-metric">
                <div class="mp-metric-label">리스크 수준</div>
                <div class="mp-risk-icon">⚠</div>
                <div class="mp-risk-value">{risk_status}</div>
                <span class="mp-risk-badge {risk_cls}">{risk_sub}</span>
            </div>
        </div>
    </div>
    """
    st.markdown(hero_html, unsafe_allow_html=True)

    section1 = (
        '<div class="mp-section"><div class="mp-section-title">1. 서비스 개요</div>'
        + _mp_field_row("🏠", "서비스명", form.get("service_name", "-"))
        + _mp_field_row("👥", "규모", form.get("company_size", "-"))
        + _mp_field_row("🌐", "도메인", form.get("high_impact_domain", "-"))
        + "</div>"
    )
    section2 = (
        '<div class="mp-section"><div class="mp-section-title">2. 인공지능 특성 및 준수 사항</div>'
        + _mp_field_row("🤖", "생성형 AI 여부", form.get("is_generative", "-"), _mp_val_class("is_generative", form.get("is_generative")))
        + _mp_field_row("📋", "사전고지 상태", form.get("user_notify", "-"), _mp_val_class("user_notify", form.get("user_notify")))
        + _mp_field_row("🏷", "AI 표시 여부", _mp_display_val("ai_marking", form.get("ai_marking")), _mp_val_class("ai_marking", form.get("ai_marking")))
        + _mp_field_row("💾", "데이터 수집 출처", _mp_display_val("data_sources", form.get("data_sources", [])), "mp-val-good" if "적법한 절차 및 이용자 동의 기반" in form.get("data_sources", []) else "mp-val-neutral")
        + _mp_field_row("⚡", "연산량 규모", form.get("heavy_compute", "-"), _mp_val_class("heavy_compute", form.get("heavy_compute")))
        + _mp_field_row("💡", "기술적 설명력", form.get("explainable", "-"), _mp_val_class("explainable", form.get("explainable")))
        + "</div>"
    )
    section3 = (
        '<div class="mp-section"><div class="mp-section-title">3. 법적 준수 및 윤리적 고려 사항</div>'
        + _mp_build_legal_bullets(form)
        + "</div>"
    )
    section4 = (
        '<div class="mp-section"><div class="mp-section-title">4. 추가 고려 사항</div>'
        + _mp_build_additional_notes(form)
        + "</div>"
    )

    left_html = section1 + section2
    right_html = section3 + section4
    st.markdown(
        f'<div class="mp-grid"><div>{left_html}</div><div>{right_html}</div></div>',
        unsafe_allow_html=True,
    )

    analysis = record.get("analysis", "").strip()
    if analysis:
        st.markdown(
            '<div class="mp-section"><div class="mp-section-title">AI 맞춤 분석 리포트</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(analysis)


def _render_mypage_asset(record: dict):
    summary = record.get("summary", {})
    st.markdown(
        f"""
        <div class="mp-hero">
            <div class="mp-hero-profile">
                <div class="mp-hero-icon">📁</div>
                <div>
                    <p class="mp-hero-name">{record.get("title", "산출물")}</p>
                    <p class="mp-hero-date">{_mp_fmt_date(record.get("created_at", ""))}</p>
                    <div class="mp-hero-tags">
                        <span class="mp-tag">{summary.get("분석 유형", "산출물 분석")}</span>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="mp-section"><div class="mp-section-title">분석 결과</div>', unsafe_allow_html=True)
    st.markdown(record.get("analysis", "분석 내용이 없습니다."))
    st.markdown("</div>", unsafe_allow_html=True)


def render_mypage():
    load_diagnosis_history(force=True)
    history = st.session_state.diagnosis_history

    title_col, btn_col = st.columns([4.5, 1.5])
    with title_col:
        st.markdown(
            '<div class="mp-page-header">'
            '<p class="mp-page-title">마이페이지</p>'
            '<p class="mp-page-sub">최근 환경 진단 · 산출물 분석 기록을 확인할 수 있습니다.</p>'
            "</div>",
            unsafe_allow_html=True,
        )
    if not history:
        st.info("아직 저장된 진단 기록이 없습니다. **환경 진단** 또는 **산출물 분석**을 완료하면 이곳에 자동 저장됩니다.")
        return

    if len(history) > 1:
        labels = [f'{r["type"]} · {r["title"]} ({r["created_at"]})' for r in history]
        selected = st.selectbox("진단 기록 선택", range(len(history)), format_func=lambda i: labels[i], key="mypage_record_select")
        record = history[selected]
    else:
        record = history[0]

    with btn_col:
        try:
            pdf_bytes = _mp_build_report_pdf(record)
            st.download_button(
                "보고서 다운로드 (PDF)",
                data=pdf_bytes,
                file_name=f"fixflawlaw_report_{record.get('id', 'latest')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="mypage_download",
            )
        except Exception as e:
            st.download_button(
                "보고서 다운로드 (PDF)",
                data=_mp_build_report_md(record).encode("utf-8"),
                file_name=f"fixflawlaw_report_{record.get('id', 'latest')}.txt",
                mime="text/plain",
                use_container_width=True,
                key="mypage_download_fallback",
                help=f"PDF 생성 실패: {e}",
            )

    if record["type"] == "환경 진단":
        _render_mypage_diagnosis(record)
    else:
        _render_mypage_asset(record)

    if len(history) > 1:
        st.markdown("---")
        st.caption("이전 기록은 상단 선택 상자에서 확인할 수 있습니다.")

    c1, c2 = st.columns([4, 1])
    with c2:
        if st.button("🗑️ 전체 기록 삭제", key="mypage_clear_history", use_container_width=True):
            st.session_state.diagnosis_history = []
            st.session_state.pop("latest_diagnosis", None)
            st.session_state.pop("latest_asset", None)
            persist_diagnosis_history()
            st.rerun()


def _wizard_nav(
    prev_step: int | None,
    next_label: str,
    next_key: str,
    next_step: int,
    next_help: str | None = None,
):
    c1, c2 = st.columns(2)
    with c1:
        if prev_step is not None and st.button("← 이전 단계", key=f"{next_key}_prev"):
            return prev_step
    with c2:
        if st.button(next_label, key=next_key, type="primary", help=next_help):
            return next_step
    return None


def render_sequential_asset():
    if "asset_step" not in st.session_state:
        st.session_state.asset_step = 0

    step = st.session_state.asset_step
    render_stepper(step, ASSET_STEPS)
    st.markdown('<div class="content-card">', unsafe_allow_html=True)

    if step == 0:
        st.markdown("분석할 산출물 유형과 파일(또는 URL)을 선택하세요.")
        st.info("**AI 이미지만 넣으십시오.**")
        media_choice = st.radio(
            "분석하려는 가상 자원 종류",
            ["이미지 파일 업로드 검증", "동영상 파일 업로드 검증", "웹사이트 배포 URL 검증"],
            key="asset_media_choice",
            help=(
                "이미지·동영상은 AI 생성 표시와 오인 가능성을, URL은 공개 화면의 "
                "고지·표시 상태를 중심으로 점검합니다."
            ),
        )
        uploaded_file, target_url = None, ""
        if media_choice == "이미지 파일 업로드 검증":
            uploaded_file = st.file_uploader(
                "AI 생성 이미지 (.png, .jpg)",
                type=["png", "jpg", "jpeg"],
                key="asset_img",
                help="AI 생성 이미지의 표시·워터마크·오인 가능성을 검토합니다.",
            )
        elif media_choice == "동영상 파일 업로드 검증":
            uploaded_file = st.file_uploader(
                "AI 생성 동영상 (.mp4)",
                type=["mp4"],
                key="asset_vid",
                help="AI 생성 동영상의 딥페이크·오인·유포 위험을 검토합니다.",
            )
        else:
            target_url = st.text_input(
                "배포 URL",
                value=st.session_state.get("asset_target_url", "https://"),
                key="asset_url",
                help="공개 접속 가능한 URL에서 AI 사용 고지와 생성물 표시 상태를 점검합니다.",
            )

        if st.button("다음 단계 →", key="asset_next_0", type="primary"):
            if media_choice == "웹사이트 배포 URL 검증":
                if not target_url or target_url.strip() == "https://":
                    st.error("분석할 URL을 입력해 주세요.")
                else:
                    st.session_state.asset_target_url = target_url.strip()
                    st.session_state.pop("asset_file_name", None)
                    st.session_state.pop("asset_file_bytes", None)
                    st.session_state.asset_step = 1
                    st.rerun()
            elif uploaded_file is None:
                st.error("분석할 파일을 업로드해 주세요.")
            else:
                st.session_state.asset_file_name = uploaded_file.name
                st.session_state.asset_file_bytes = uploaded_file.getvalue()
                st.session_state.pop("asset_target_url", None)
                st.session_state.asset_step = 1
                st.rerun()

    elif step == 1:
        media_choice = st.session_state.get("asset_media_choice", "")
        resource_label = st.session_state.get("asset_file_name") or st.session_state.get("asset_target_url", "")
        st.info(f"**선택된 자원** · {media_choice}\n\n`{resource_label}`")
        st.markdown("선택한 산출물에 대해 컴플라이언스 관점의 스크리닝을 실행합니다.")

        nav = _wizard_nav(
            0,
            "⚖️ 스크리닝 실행",
            "asset_run",
            2,
            next_help=(
                "투명성, 표시·워터마크, 딥페이크·오인·유포 위험과 즉시 개선 조치를 "
                "짧은 보고서로 생성합니다."
            ),
        )
        if nav == 0:
            st.session_state.asset_step = 0
            st.rerun()
        elif nav == 2:
            st.session_state.asset_run_token = datetime.now().strftime("%Y%m%d%H%M%S")
            st.session_state.pop("last_saved_asset_token", None)
            resource_details = (
                f"타입: {media_choice} | 자원: {resource_label}"
            )
            independent_prompt = f"""
            당신은 AI 산출물 컴플라이언스 실무 컨설턴트입니다. 다음 자원을 심사하여 실무 중심 분석서를 작성하세요.
            - {resource_details}

            [분석 관점]
            - AI 생성물 여부 및 가상·합성 콘텐츠로 오인될 수 있는지
            - 이용자 고지·표시·워터마크 등 투명성 보완 필요 여부
            - 딥페이크·오인·유포 리스크 수준
            - 즉시 개선이 필요한 사항과 권고 조치

            [출력 규칙 — 반드시 준수]
            1. 법령명, 조문 번호(제○조), 시행령·별표 인용을 절대 나열하지 마세요.
            2. "○○법 제○조에 따르면" 같은 법 조항 인용 문장을 사용하지 마세요.
            3. 일반인이 이해할 수 있는 실무 언어로 리스크와 개선안만 작성하세요.
            4. 전체 분량은 한글 600~900자 이내로 간결하게 작성하세요.
            5. 각 항목은 핵심 문장 또는 불릿 2개 이내로 제한하세요.
            6. 예시, 사례, 가정 상황, 장황한 배경 설명은 생략하세요.
            7. 법적 근거는 화면의 물음표 도움말에 표시되므로 본문에는 조문명·조문번호를 쓰지 마세요.
            8. 아래 형식을 정확히 따르세요:
               ## 분석 개요
               ## 주요 리스크
               ## 개선 권고 사항
               ## 종합 의견
            """
            with st.spinner("산출물 스크리닝 및 분석 중..."):
                try:
                    response = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "AI 생성 산출물의 컴플라이언스를 실무 관점으로 설명하는 컨설턴트입니다. "
                                    "법령·조문을 나열하거나 인용하지 않습니다."
                                ),
                            },
                            {"role": "user", "content": independent_prompt},
                        ],
                        reasoning_effort="low",
                        max_completion_tokens=900,
                    )
                    st.session_state.asset_report = _sanitize_core_report(
                        response.choices[0].message.content
                    )
                    st.session_state.asset_step = 2
                    st.rerun()
                except Exception as e:
                    st.error(f"분석 오류: {e}")

    else:
        report = st.session_state.get("asset_report", "분석 결과가 없습니다.")
        media_choice = st.session_state.get("asset_media_choice", "")
        resource_label = st.session_state.get("asset_file_name") or st.session_state.get("asset_target_url", "")
        _save_asset_history(media_choice, resource_label, report)

        st.subheader(
            "AI 산출물 컴플라이언스 분석서",
            help=(
                "업로드한 산출물의 AI 생성 표시, 투명성, 오인·딥페이크·유포 위험을 "
                "실무 관점에서 요약한 결과입니다."
            ),
        )
        _render_report_sections(report, ASSET_SECTION_HELP)
        if st.button("🔄 처음부터 다시 분석", key="asset_restart"):
            for key in (
                "asset_step", "asset_media_choice", "asset_file_name",
                "asset_file_bytes", "asset_target_url", "asset_report",
            ):
                st.session_state.pop(key, None)
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _default_diagnosis_form() -> dict:
    return {
        "service_name": "My_AI_Service",
        "business_location": "국내",
        "company_size": "중소기업 (스타트업 포함)",
        "data_sources": ["적법한 절차 및 이용자 동의 기반"],
        "high_impact_domain": "해당 없음 (일반 사무, 단순 요약 등)",
        "heavy_compute": "아니오",
        "explainable": "가능",
        "is_generative": "아니오",
        "user_notify": "이행 완료",
        "ai_marking": False,
        "virtual_content": "아니오",
        "virtual_notify": "해당 없음",
    }


def render_sequential_diagnosis():
    if "diagnosis_step" not in st.session_state:
        st.session_state.diagnosis_step = 0
    if "diagnosis_form" not in st.session_state:
        st.session_state.diagnosis_form = _default_diagnosis_form()
    if st.session_state.get("contract_signed") and st.session_state.diagnosis_step == 0:
        st.session_state.diagnosis_step = 1

    step = st.session_state.diagnosis_step
    render_stepper(step, DIAGNOSIS_STEPS)
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    form = st.session_state.diagnosis_form

    if step == 0:
        st.warning("🚨 본 진단을 진행하기 전, 책임 있는 AI 실천을 위한 전사 서약 동의가 요구됩니다.")
        with st.expander("🤝 책임 있는 AI 신뢰 구축 서약서 (내용 검토 및 동의)", expanded=True):
            st.markdown(
                """
                최신 Accenture 시장 신뢰도 조사 결과, **전 세계 소비자의 단 10%만이** 조직의 무분별한 AI 기술 구현 방식을 신뢰한다고 답했습니다.
                또한 **77%의 압도적인 소비자들은** 조직이 AI의 오용에 대해 전적인 사회적 책임을 져야 한다고 강력히 요구하고 있습니다.

                이에 본 인공지능 사업자는 투명성을 극대화하고 이용자의 존엄성을 보호하기 위해 다음 사항을 준수할 것을 서약합니다.

                * **하나,** 인공지능 기본법의 규정을 전사적으로 준수하며 기계적 이익보다 **인간 존엄성**을 최우선시한다.
                * **하나,** 이용자 사전 고지 및 AI 생성 표시 의무를 명확히 이행하여 신뢰 인프라 구축에 앞장선다.
                * **하나,** AI 기술 오용에 따른 가짜뉴스, 편향성, 인권 침해 리스크 발생 시 도망치지 않고 그 책임을 명확히 수행한다.
                """
            )
        if st.button("위 서약에 동의하고 다음 단계 →", key="diag_next_0", type="primary"):
            st.session_state.contract_signed = True
            st.session_state.diagnosis_step = 1
            st.rerun()

    elif step == 1:
        st.markdown("기업 및 기술 사양을 입력한 뒤 다음 단계로 이동하세요.")
        form["service_name"] = st.text_input(
            "서비스 명칭", value=form["service_name"],
            help="[인공지능 기본법 제31조 제1항] 고영향 또는 생성형 AI 제품·서비스 제공 시 이용자에게 사전 고지해야 하므로, 진단·보고서에 식별 가능한 서비스 명칭을 기록합니다.",
        )
        form["business_location"] = st.selectbox(
            "사업자 소재지",
            ["국내", "국외 (대한민국 시장/이용자에게 영향 미침)", "국외 (국내 영향 없음)"],
            index=["국내", "국외 (대한민국 시장/이용자에게 영향 미침)", "국외 (국내 영향 없음)"].index(form["business_location"]),
            help="[인공지능 기본법 제4조 제1항] 국외 행위라도 국내 시장·이용자에게 영향을 미치면 적용됩니다.",
        )
        form["company_size"] = st.radio(
            "기업 규모", ["중소기업 (스타트업 포함)", "대기업/중견기업"],
            index=0 if form["company_size"] == "중소기업 (스타트업 포함)" else 1,
            help="[인공지능 기본법 제17조·제30조] 중소기업등 우선 지원 및 안전성 확보 지원 대상 여부를 확인합니다.",
        )
        form["data_sources"] = st.multiselect(
            "학습 데이터 수집 출처",
            ["적법한 절차 및 이용자 동의 기반", "인터넷 무단 크롤링 데이터 포함", "공공 데이터 포털 오픈데이터", "구매 가공 데이터셋"],
            default=form["data_sources"],
            help="[인공지능 기본법 제3조·제15조] 데이터 출처·동의·품질 확인이 신뢰성 확보의 핵심입니다.",
        )
        domain_options = [
            "해당 없음 (일반 사무, 단순 요약 등)",
            "가. 에너지의 공급 및 나. 먹는물의 생산 공정",
            "다. 보건의료의 제공체계 및 라. 의료기기/디지털의료제품 개발",
            "바. 범죄 수사 및 체포 업무를 위한 생체인식정보 분석",
            "사. 채용, 대출 심사 등 개인의 권리·의무/판단 및 평가 (HR 영역 등)",
            "아. 교통수단, 교통시설, 교통체계의 주요한 작동 및 운영",
            "자. 공공서비스 제공에 필요한 자격 확인 및 결정/비용징수",
            "차. 유아교육·초등교육 및 중등교육에서의 학생 평가",
        ]
        form["high_impact_domain"] = st.selectbox(
            "인공지능 기술이 활용되는 주 도메인", domain_options,
            index=domain_options.index(form["high_impact_domain"]) if form["high_impact_domain"] in domain_options else 0,
            help="[인공지능 기본법 제2조·제33조·제34조] 고영향 AI 해당 여부를 판단합니다.",
        )
        form["heavy_compute"] = st.radio(
            "대규모 연산량 사용 여부", ["예", "아니오"],
            index=0 if form["heavy_compute"] == "예" else 1,
            help=HEAVY_COMPUTE_LAW_CITATION,
        )
        form["explainable"] = st.radio(
            "결과 도출 기준 설명 가능 여부", ["가능", "불가능"],
            index=0 if form["explainable"] == "가능" else 1,
            help="[인공지능 기본법 제3조 제2항] 설명 제공 권리 대응 여부를 점검합니다.",
        )
        st.session_state.diagnosis_form = form
        nav = _wizard_nav(0, "다음 단계 →", "diag_next_1", 2)
        if nav == 0:
            st.session_state.diagnosis_step = 0
            st.rerun()
        elif nav == 2:
            st.session_state.diagnosis_step = 2
            st.rerun()

    elif step == 2:
        st.markdown("규제 준수 현황을 입력한 뒤 진단을 실행하세요.")
        form["is_generative"] = st.radio(
            "생성형 AI 기술 활용 여부", ["예", "아니오"],
            index=0 if form["is_generative"] == "예" else 1,
            help="[인공지능 기본법 제2조 제5호] 생성형 AI 해당 시 제31조 투명성 의무를 점검합니다.",
        )
        form["user_notify"] = st.radio(
            "이용자 사전 고지 여부", ["미이행", "이행 완료"],
            index=0 if form["user_notify"] == "미이행" else 1,
            help="[인공지능 기본법 제31조 제1항] 사전고지 미이행 시 과태료 대상입니다.",
        )
        form["ai_marking"] = st.checkbox(
            "결과물에 'AI 생성' 표시 적용 여부", value=form["ai_marking"],
            help="[인공지능 기본법 제31조 제2항] 생성형 AI 결과물 표시 의무입니다.",
        )
        form["virtual_content"] = st.radio(
            "가상 결과물(딥페이크 등) 활용 여부", ["예", "아니오"],
            index=0 if form["virtual_content"] == "예" else 1,
            help="[인공지능 기본법 제31조 제3항] 가상 결과물 고지·표시 의무입니다.",
        )
        form["virtual_notify"] = st.radio(
            "가상 결과물 인식 조치 여부", ["미이행", "이행 완료", "해당 없음"],
            index=["미이행", "이행 완료", "해당 없음"].index(form["virtual_notify"]),
            help="[인공지능 기본법 제31조 제3항·제4항] 이용자 인식 조치 의무입니다.",
        )
        st.session_state.diagnosis_form = form
        nav = _wizard_nav(
            1,
            "⚖️ 비즈니스 컴플라이언스 위험도 진단 실행",
            "diag_run",
            3,
            next_help=(
                "입력한 서비스 정보를 기준으로 법률 준수, 윤리, 위험 요소와 맞춤 개선 "
                "가이드라인을 짧은 보고서로 생성합니다."
            ),
        )
        if nav == 1:
            st.session_state.diagnosis_step = 1
            st.rerun()
        elif nav == 3:
            st.session_state.diagnosis_run_token = datetime.now().strftime("%Y%m%d%H%M%S")
            st.session_state.pop("last_saved_diagnosis_token", None)
            st.session_state.pop("diagnosis_llm_report", None)
            st.session_state.diagnosis_step = 3
            st.rerun()

    else:
        form = st.session_state.diagnosis_form
        service_name = form["service_name"]
        company_size = form["company_size"]
        data_sources = form["data_sources"]
        high_impact_domain = form["high_impact_domain"]
        heavy_compute = form["heavy_compute"]
        explainable = form["explainable"]
        is_generative = form["is_generative"]
        user_notify = form["user_notify"]
        ai_marking = form["ai_marking"]
        virtual_content = form["virtual_content"]
        virtual_notify = form["virtual_notify"]

        st.markdown("### 📊 비즈니스 환경 진단 리포트")
        result = compute_diagnosis_result(form)
        risk_score = result["risk_score"]
        safe_score = result["safe_score"]
        law_score = result["law_score"]
        ethics_score = result["ethics_score"]
        status_text = result["status_text"]
        risk_tag = result["risk_tag"]
        reasons = result["reasons"]

        if risk_score >= 70:
            bar_color = "#EF4444"
        elif risk_score >= 40:
            bar_color = "#F97316"
        else:
            bar_color = "#22C55E"

        st.markdown(f"<style>div.stProgress > div > div > div > div {{background-color: {bar_color} !important;}}</style>", unsafe_allow_html=True)
        st.markdown("### 분석 결과")
        r1, r2, r3, r4, r5 = st.columns(5)
        with r1:
            st.markdown(
                f'<div class="dash-card"><div class="gauge-circle" style="border-color:{bar_color};background:{"#FEE2E2" if risk_score>=70 else "#FFEDD5" if risk_score>=40 else "#DCFCE7"};">'
                f'<span class="gauge-score" style="color:{bar_color};">{safe_score}</span><span class="gauge-label" style="color:{bar_color};">{status_text}</span></div></div>',
                unsafe_allow_html=True,
            )
        for col, val, lbl in [(r2, law_score, "법률 준수"), (r3, ethics_score, "윤리 점수"), (r4, status_text, "리스크"), (r5, len(reasons), "조치 필요")]:
            with col:
                st.markdown(f'<div class="dash-card"><p class="dash-lbl">{lbl}</p><p class="dash-val">{val}</p></div>', unsafe_allow_html=True)

        st.markdown(f'<p>진단 상태: <span class="{risk_tag}">{status_text}</span> &nbsp; 리스크 스코어 {risk_score}%</p>', unsafe_allow_html=True)
        st.progress(risk_score / 100)
        if reasons:
            st.markdown("**발견된 리스크 요소**")
            for r in reasons:
                st.markdown(f"- 🔴 {r}")

        if heavy_compute == "예":
            st.info(HEAVY_COMPUTE_LAW_CITATION)

        st.markdown("---")
        st.subheader("맞춤 조치 항목")
        if is_generative == "예" and user_notify == "미이행":
            st.checkbox("🚨 [조치 명령] 사전 고지 시스템을 배포하십시오.", help="제31조 제1항·제43조 제1항 제1호")
        if is_generative == "예" and not ai_marking:
            st.checkbox("🚨 [조치 명령] 'AI Generated' 레이블링을 적용하십시오.", help="제31조 제2항")
        if virtual_content == "예" and virtual_notify == "미이행":
            st.checkbox("🚨 [조치 명령] 가상 결과물 워터마크를 적용하십시오.", help="제31조 제3항")
        if high_impact_domain != "해당 없음 (일반 사무, 단순 요약 등)":
            st.checkbox("⚠️ [조치 명령] 민간자율인공지능윤리위원회 설치 및 영향평가를 구비하십시오.", help="제34조·제35조")
        if explainable == "불가능":
            st.checkbox("⚠️ [조치 명령] LIME 등 설명 가능성 체계를 구축하십시오.", help="제3조 제2항")
        if "인터넷 무단 크롤링 데이터 포함" in data_sources:
            st.checkbox("⚠️ [조치 명령] 불법 크롤링 파이프라인을 차단하십시오.", help="제3조·제15조")
        if heavy_compute == "예":
            st.checkbox("⚠️ [조치 명령] 제32조 위험관리체계를 구축·제출하십시오.", help=HEAVY_COMPUTE_LAW_CITATION)
        if company_size == "중소기업 (스타트업 포함)":
            st.info("💡 [중소기업 우선지원 특례] 법 제17조·제30조에 따른 지원 자격이 있을 수 있습니다.")

        st.subheader(
            "🤖 [F-02] 윤리 원칙 및 맞춤 가이드라인 정성 분석",
            help=(
                "입력한 서비스 특성과 진단 점수를 바탕으로 우선 조치, 운영 기준, "
                "점검 주기를 간결하게 제안합니다."
            ),
        )
        if "diagnosis_llm_report" not in st.session_state:
            prompt_content = f"""
            당신은 대한민국 인공지능 기본법 및 책임 있는 AI 윤리 전문가입니다. 아래 속성을 분석하여 간결한 실무 보고서로 답변해 주세요.
            [입력 데이터]
            - 서비스명: {service_name} | 규모: {company_size} | 도메인: {high_impact_domain}
            - 생성형 AI 여부: {is_generative} | 사전고지 상태: {user_notify} | AI 표시 여부: {ai_marking}
            - 데이터 수집 출처: {", ".join(data_sources)} | 연산량 규모: {heavy_compute} | 기술적 설명력: {explainable}
            [준거 지식 베이스]
            {txt_knowledge_base[:2500]}
            [출력 스타일 규칙 - 엄격 준수]
            1. 전체 분량은 한글 700~1,000자 이내로 제한할 것.
            2. 아래 4개 제목만 `##` 형식으로 사용할 것.
               ## 진단 요약
               ## 우선 조치
               ## 운영 가이드
               ## 재점검 기준
            3. 각 제목 아래에는 핵심 불릿을 2개 이내로 작성할 것.
            4. 예시, 사례, 가정 상황, 장황한 배경 설명은 생략할 것.
            5. 법적 근거는 화면의 물음표 도움말에 표시되므로 본문에는 조문명·조문번호를 쓰지 말 것.
            6. 중복 설명, 긴 법령 원문, 과도한 이모티콘은 제외할 것.
            """
            with st.spinner("AI가 맞춤 가이드라인을 제작 중입니다..."):
                try:
                    response = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[
                            {"role": "system", "content": "당신은 가독성 높고 정제된 법률 실무 서식 형태로 답변하는 AI 전문 윤리 검토관입니다."},
                            {"role": "user", "content": prompt_content},
                        ],
                        reasoning_effort="low",
                        max_completion_tokens=1100,
                    )
                    st.session_state.diagnosis_llm_report = _sanitize_core_report(response.choices[0].message.content)
                except Exception as e:
                    st.session_state.diagnosis_llm_report = f"LLM 분석 실패: {e}"
        _save_diagnosis_history(form, result, st.session_state.diagnosis_llm_report)
        _render_report_sections(st.session_state.diagnosis_llm_report, DIAGNOSIS_SECTION_HELP)

        if st.button("🔄 처음부터 다시 진단", key="diag_restart"):
            st.session_state.diagnosis_step = 0
            st.session_state.diagnosis_form = _default_diagnosis_form()
            st.session_state.contract_signed = False
            st.session_state.pop("diagnosis_llm_report", None)
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

#---------------------------------------------------------------------------
# 네비게이션 + 메인 화면
#---------------------------------------------------------------------------
sync_nav_from_query()
load_diagnosis_history()
render_header_nav()

main_tab = st.session_state.main_tab

#---------------------------------------------------------------------------
# 홈
#---------------------------------------------------------------------------
if main_tab == "home":
    hero_l, hero_r = st.columns([3, 2])
    with hero_l:
        st.markdown(
            """
            <div class="hero-card">
                <p class="hero-title">우리 서비스, 안전한가요?</p>
                <p class="hero-sub">인공지능 기본법과 책임 있는 AI 윤리 기준에 따라<br>서비스 컴플라이언스를 무료로 진단하세요.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("무료로 시작하기 →", key="hero_start"):
            st.session_state.main_tab = "diagnosis"
            if st.session_state.get("contract_signed"):
                st.session_state.diagnosis_step = 1
            else:
                st.session_state.diagnosis_step = 0
            st.query_params["tab"] = "diagnosis"
            st.rerun()
    with hero_r:
        st.markdown(
            """
            <div class="dash-card">
                <div class="gauge-circle"><span class="gauge-score">89</span><span class="gauge-label">안전</span></div>
                <p class="dash-lbl" style="margin-top:0.75rem;">종합 컴플라이언스 점수 (예시)</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    m1, m2, m3, m4 = st.columns(4)
    for col, val, lbl, cls in [
        (m1, "92", "법률 준수", "dash-safe"),
        (m2, "84", "윤리 점수", "dash-safe"),
        (m3, "낮음", "리스크", "dash-safe"),
        (m4, "3건", "조치 필요", "dash-warn"),
    ]:
        with col:
            st.markdown(f'<div class="dash-card"><p class="dash-lbl">{lbl}</p><p class="dash-val {cls}">{val}</p></div>', unsafe_allow_html=True)

    st.markdown("#### 💡 오늘의 AI 윤리 상식 및 기본법 가이드라인")
    c1, c2 = st.columns(2)
    with c1:
        st.info(st.session_state.current_ethics)
    with c2:
        st.info(st.session_state.current_tip)
    if st.button("🔄 윤리 상식 및 법령 가이드 새로고침", key="home_refresh"):
        st.session_state.current_tip = random.choice(LAW_TIPS)
        st.session_state.current_ethics = random.choice(ETHICS_KNOWLEDGE)
        st.rerun()

    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("#### 📅 데일리 컴플라이언스 체크북")
    st.caption("각 항목 옆 **?** 아이콘에 마우스를 올리면 관련 법령을 확인할 수 있습니다.")
    chk_l, chk_r = st.columns([2, 1])
    with chk_l:
        h1 = st.checkbox(
            "배포 모듈의 유저 사전 고지 문구가 누락 없이 정상 렌더링되고 있는가?",
            help="[인공지능 기본법 제31조 제1항, 제43조 제1항 제1호] 고영향 인공지능 또는 생성형 인공지능을 이용한 제품·서비스를 제공하려는 경우, 제품 또는 서비스가 인공지능에 기반하여 운용된다는 사실을 이용자에게 사전에 고지해야 합니다. 이를 이행하지 않으면 3천만 원 이하의 과태료 대상이 됩니다.",
        )
        h2 = st.checkbox(
            "학습 데이터 수집 파이프라인 내 권리 침해 및 무단 정보 크롤링 요소가 차단되었는가?",
            help="[인공지능 기본법 제3조 제1항, 제15조 제1항] 인공지능기술과 산업은 안전성과 신뢰성을 제고하는 방향으로 발전되어야 하며, 학습용데이터의 생산·수집·관리·유통·활용 촉진 및 품질수준 확보가 요구됩니다.",
        )
        h3 = st.checkbox(
            "AI 시스템 산출 결과 아웃풋의 로직 설명력 및 추적성(LIME)이 사내 보장되었는가?",
            help="[인공지능 기본법 제3조 제2항, 제34조 제1항 제5호] 영향받는 자는 최종결과 도출에 활용된 주요 기준 및 원리 등에 관하여 기술적·합리적으로 가능한 범위에서 명확하고 의미 있는 설명을 제공받을 수 있어야 합니다.",
        )
    with chk_r:
        chk_score = sum([h1, h2, h3])
        st.metric("오늘의 실천율", f"{int(chk_score/3*100)}%")
        st.progress(chk_score / 3)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### 더 알아보기")
    learn_cards = [
        ("🔍", "환경 진단", "비즈니스 컴플라이언스 진단", "?tab=diagnosis"),
        ("📜", "인공지능기본법", "법령 조문 안내", LAW_OFFICIAL_URL),
        ("🛡️", "AI 윤리", "3대 윤리 원칙", AI_ETHICS_OFFICIAL_URL),
        ("🌍", "세계 여러나라의 인공지능 규제 법령", "국제 AI 법령·가이드라인", "?tab=home&learn=global"),
    ]
    cats = st.columns(4)
    for col, (icon, title, desc, link) in zip(cats, learn_cards):
        with col:
            _render_learn_category_card(icon, title, desc, link)

    if st.query_params.get("learn") == "global":
        if "learn" in st.query_params:
            del st.query_params["learn"]
        show_global_regulations_modal()

#---------------------------------------------------------------------------
# 환경 진단
#---------------------------------------------------------------------------
elif main_tab == "diagnosis":
    st.header("AI 비즈니스 컴플라이언스 환경 진단")
    render_sequential_diagnosis()

#---------------------------------------------------------------------------
# 산출물 분석
#---------------------------------------------------------------------------
elif main_tab == "asset":
    st.header("산출물 분석")
    render_sequential_asset()

#---------------------------------------------------------------------------
# 인공지능기본법
#---------------------------------------------------------------------------
elif main_tab == "law":
    st.header("인공지능기본법 핵심만 알아보기")
    st.markdown("인공지능 기본법의 핵심 조문과 의무 사항을 한눈에 확인하세요.")
    law_cards_html = "".join(
        f'<div class="law-card"><div class="law-card-icon">{card["icon"]}</div>'
        f'<div class="law-card-title">{card["title"]} <span style="color:#2563EB;font-size:0.8rem;">({card["article"]})</span></div>'
        f'<div class="law-card-desc">{card["desc"]}</div></div>'
        for card in LAW_INFO_CARDS
    )
    st.markdown(f'<div class="law-card-grid">{law_cards_html}</div>', unsafe_allow_html=True)

#---------------------------------------------------------------------------
# AI 윤리
#---------------------------------------------------------------------------
elif main_tab == "ethics":
    st.header("AI 윤리")
    st.markdown("책임 있는 AI 3대 기본원칙과 10대 핵심 실천 요건입니다.")
    pcols = st.columns(3)
    for col, card in zip(pcols, ETHICS_PRINCIPLE_CARDS):
        with col:
            st.markdown(
                f'<div class="law-card"><div class="law-card-icon">{card["icon"]}</div>'
                f'<div class="law-card-title">{card["title"]}</div>'
                f'<div class="law-card-desc">{card["items"]}</div></div>',
                unsafe_allow_html=True,
            )
    st.markdown("---")
    st.subheader("10대 핵심요건")
    core_cards = []
    for index, item in enumerate(ETHICS_CORE_REQUIREMENTS, start=1):
        core_cards.append(
            f'<div class="ethics-core-card">'
            f'<div class="ethics-core-icon">{item["icon"]}</div>'
            f'<div class="ethics-core-content">'
            f'<div class="ethics-core-head">'
            f'<span class="ethics-core-number">{index:02d}</span>'
            f'<span class="ethics-core-title">{item["title"]}</span>'
            f'</div>'
            f'<div class="ethics-core-desc">{item["desc"]}</div>'
            f'</div></div>'
        )
    st.markdown(
        f'<div class="ethics-core-grid">{"".join(core_cards)}</div>',
        unsafe_allow_html=True,
    )

#---------------------------------------------------------------------------
# 퀴즈
#---------------------------------------------------------------------------
elif main_tab == "quiz":
    st.header("퀴즈")
    if "quiz_sub" not in st.session_state:
        st.session_state.quiz_sub = "law"

    sub_l, sub_r = st.columns(2)
    with sub_l:
        if st.button(
            "⚖️ 인공지능기본법",
            key="quiz_sub_law",
            use_container_width=True,
            type="primary" if st.session_state.quiz_sub == "law" else "secondary",
        ):
            st.session_state.quiz_sub = "law"
            st.rerun()
    with sub_r:
        if st.button(
            "🛡️ AI 윤리",
            key="quiz_sub_eth",
            use_container_width=True,
            type="primary" if st.session_state.quiz_sub == "eth" else "secondary",
        ):
            st.session_state.quiz_sub = "eth"
            st.rerun()

    st.markdown("---")
    if st.session_state.quiz_sub == "law":
        st.caption(f"총 {len(LAW_QUIZ_BANK)}문항 · 순차 진행 · 힌트 제공")
        render_sequential_quiz(LAW_QUIZ_BANK, "law")
    else:
        st.caption(f"총 {len(ETHICS_QUIZ_BANK)}문항 · 순차 진행 · 힌트 제공")
        render_sequential_quiz(ETHICS_QUIZ_BANK, "eth")

#---------------------------------------------------------------------------
# 마이페이지
#---------------------------------------------------------------------------
elif main_tab == "mypage":
    render_mypage()

