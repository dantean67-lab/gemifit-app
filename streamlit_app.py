import streamlit as st

st.set_page_config(
    page_title="ג'מי כושר",
    page_icon="💪",
    layout="centered",
)

CUSTOM_CSS = """
<style>
    /* ---------- Global RTL ---------- */
    html, body, [class*="css"] {
        direction: rtl;
    }

    .stApp {
        direction: rtl;
        text-align: right;
    }

    .stApp, .stApp * {
        font-family: "Segoe UI", "Arial", sans-serif;
    }

    /* Markdown, headers, paragraphs */
    .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown h1,
    .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
        direction: rtl;
        text-align: right;
    }

    /* Inputs, textareas, selects, number inputs */
    .stTextInput input, .stTextArea textarea, .stNumberInput input,
    .stSelectbox div[data-baseweb="select"], .stDateInput input {
        direction: rtl;
        text-align: right;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        direction: rtl;
        gap: 0.5rem;
    }

    .stTabs [data-baseweb="tab"] {
        direction: rtl;
    }

    /* ---------- Fitness dark theme accents ---------- */
    .stApp {
        background: radial-gradient(circle at 20% 0%, #16241c 0%, #0e1117 45%);
    }

    h1, h2, h3 {
        color: #34e0a1;
    }

    .stTabs [data-baseweb="tab-list"] {
        background-color: #161b22;
        border-radius: 12px;
        padding: 6px;
        border: 1px solid #223028;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #b6c2c9;
        font-weight: 600;
    }

    .stTabs [aria-selected="true"] {
        background-color: #1f3d30 !important;
        color: #34e0a1 !important;
    }

    /* ---------- Header ---------- */
    .gemifit-header {
        text-align: center;
        padding: 1.2rem 0 0.5rem 0;
    }

    .gemifit-title {
        font-size: 2.4rem;
        font-weight: 800;
        color: #34e0a1;
        margin-bottom: 0.2rem;
        text-shadow: 0 0 18px rgba(52, 224, 161, 0.25);
    }

    .gemifit-subtitle {
        font-size: 1.05rem;
        color: #9fb3ac;
        margin-bottom: 1rem;
    }

    /* ---------- Warning box ---------- */
    .gemifit-warning {
        background-color: #2a1f0d;
        border: 1px solid #f5b942;
        color: #f5d78e;
        border-radius: 10px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 1.5rem;
        direction: rtl;
        text-align: right;
        font-size: 0.95rem;
        line-height: 1.6;
    }

    /* ---------- Placeholder cards ---------- */
    .gemifit-placeholder {
        background-color: #161b22;
        border: 1px dashed #2f6b52;
        border-radius: 12px;
        padding: 2.5rem 1rem;
        text-align: center;
        color: #7fdcb0;
        font-size: 1.2rem;
        margin-top: 1rem;
    }

    /* ---------- Hide Streamlit chrome ---------- */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header [data-testid="stToolbar"] {visibility: hidden;}
    [data-testid="stDecoration"] {display: none;}

    /* ---------- Mobile responsive ---------- */
    @media (max-width: 640px) {
        .gemifit-title {
            font-size: 1.9rem;
        }
        .gemifit-subtitle {
            font-size: 0.9rem;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 0.8rem;
            padding: 0.4rem 0.5rem;
        }
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="gemifit-header">
        <div class="gemifit-title">💪 ג'מי כושר</div>
        <div class="gemifit-subtitle">בריאות, תזונה וכושר — הכל במקום אחד</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="gemifit-warning">
        ⚠️ המידע באתר כללי בלבד ואינו תחליף לייעוץ רפואי.
        לפני שינוי בתזונה או באימונים יש להתייעץ עם רופא או דיאטן מוסמך.
    </div>
    """,
    unsafe_allow_html=True,
)

tab_calories, tab_weight, tab_workout, tab_nutrition = st.tabs(
    ["מחשבון קלוריות", "מעקב משקל", "תוכנית אימון", "תפריט תזונה"]
)

placeholder_html = '<div class="gemifit-placeholder">🚧 בקרוב...</div>'

with tab_calories:
    st.markdown(placeholder_html, unsafe_allow_html=True)

with tab_weight:
    st.markdown(placeholder_html, unsafe_allow_html=True)

with tab_workout:
    st.markdown(placeholder_html, unsafe_allow_html=True)

with tab_nutrition:
    st.markdown(placeholder_html, unsafe_allow_html=True)
