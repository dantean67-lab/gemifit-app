import streamlit as st

ACTIVITY_FACTORS = {
    "יושבני (עבודה משרדית, כמעט ללא פעילות)": 1.2,
    "קל (הליכה או אימון קל 1-3 פעמים בשבוע)": 1.375,
    "בינוני (אימון 3-5 פעמים בשבוע)": 1.55,
    "גבוה (אימון אינטנסיבי 6-7 פעמים בשבוע)": 1.725,
    "גבוה מאוד (אימונים קשים יומיים או עבודה פיזית)": 1.9,
}

GOAL_CALORIE_ADJUSTMENT = {
    "הרזיה": -500,
    "שמירה על המשקל": 0,
    "עלייה במסת שריר": 300,
}

GOAL_PROTEIN_PER_KG = {
    "הרזיה": 2.0,
    "שמירה על המשקל": 1.6,
    "עלייה במסת שריר": 1.8,
}

FAT_SHARE_OF_CALORIES = 0.30
CALORIE_FLOOR = {"זכר": 1500, "נקבה": 1200}


def calculate_calorie_plan(sex, age, weight, height, activity_label, goal):
    if sex == "זכר":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    tdee = bmr * ACTIVITY_FACTORS[activity_label]
    target = tdee + GOAL_CALORIE_ADJUSTMENT[goal]

    floor = CALORIE_FLOOR[sex]
    clamped = target < floor
    if clamped:
        target = floor

    protein_g = GOAL_PROTEIN_PER_KG[goal] * weight
    protein_kcal = protein_g * 4
    fat_kcal = target * FAT_SHARE_OF_CALORIES
    fat_g = fat_kcal / 9
    carbs_kcal = max(0, target - protein_kcal - fat_kcal)
    carbs_g = carbs_kcal / 4

    return {
        "sex": sex,
        "goal": goal,
        "weight": weight,
        "bmr": round(bmr),
        "tdee": round(tdee),
        "target_calories": round(target),
        "protein_g": round(protein_g),
        "fat_g": round(fat_g),
        "carbs_g": round(carbs_g),
        "clamped": clamped,
        "floor": floor,
    }


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

    /* Keep Streamlit's icon glyphs (expander arrows, etc.) from being
       broken by the font-family override above. */
    [data-testid="stIconMaterial"] {
        font-family: "Material Symbols Rounded" !important;
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
        gap: 0.9rem;
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
        padding: 6px 14px;
        border: 1px solid #223028;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #b6c2c9;
        font-weight: 600;
        padding: 0.65rem 1.3rem;
    }

    .stTabs [data-baseweb="tab"]:not(:last-child) {
        border-left: 1px solid rgba(182, 194, 201, 0.18);
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

    /* ---------- Caution note (calculator safety floor) ---------- */
    .gemifit-caution {
        background-color: #2a1f0d;
        border: 1px solid #f5b942;
        color: #f5d78e;
        border-radius: 10px;
        padding: 0.9rem 1.1rem;
        margin: 1rem 0;
        direction: rtl;
        text-align: right;
        font-size: 0.92rem;
        line-height: 1.6;
    }

    /* ---------- Metric result cards ---------- */
    .gemifit-metric-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 0.7rem;
        margin: 1.2rem 0 0.5rem 0;
    }

    .gemifit-metric-card {
        background-color: #161b22;
        border: 1px solid #223028;
        border-radius: 12px;
        padding: 1rem 0.4rem;
        text-align: center;
        flex: 1 1 21%;
        min-width: 100px;
    }

    .gemifit-metric-card.highlight {
        background: linear-gradient(160deg, #1f3d30, #16241c);
        border: 1px solid #34e0a1;
    }

    .gemifit-metric-value {
        font-size: 1.5rem;
        font-weight: 800;
        color: #e6edf3;
    }

    .gemifit-metric-card.highlight .gemifit-metric-value {
        font-size: 2rem;
        color: #34e0a1;
    }

    .gemifit-metric-label {
        font-size: 0.82rem;
        color: #9fb3ac;
        margin-top: 0.3rem;
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
            padding: 0.4rem 0.6rem;
        }
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        .gemifit-metric-card {
            flex: 1 1 40%;
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
    with st.form("calorie_calculator_form"):
        sex = st.radio("מין", ["זכר", "נקבה"], horizontal=True)

        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("גיל", min_value=18, max_value=90, value=30, step=1)
            height = st.number_input(
                "גובה בס\"מ", min_value=120, max_value=230, value=170, step=1
            )
        with col2:
            weight = st.number_input(
                "משקל בק\"ג", min_value=35.0, max_value=250.0, value=70.0, step=0.5
            )

        activity_label = st.selectbox("רמת פעילות", list(ACTIVITY_FACTORS.keys()))
        goal = st.radio(
            "מטרה", ["הרזיה", "שמירה על המשקל", "עלייה במסת שריר"]
        )

        submitted = st.form_submit_button("חשב לי")

    if submitted:
        st.session_state["calorie_plan"] = calculate_calorie_plan(
            sex, age, weight, height, activity_label, goal
        )

    plan = st.session_state.get("calorie_plan")

    if plan:
        if plan["clamped"]:
            st.markdown(
                f"""
                <div class="gemifit-caution">
                    ⚠️ שימו לב: היעד היומי המחושב היה נמוך מסף הבטיחות המומלץ,
                    ולכן הוגדר לרף מינימלי של {plan['floor']} קק"ל ליום.
                    מומלץ להתייעץ עם רופא/ה או דיאטן/ית מוסמך/ת לפני שממשיכים בתזונה דלה בקלוריות.
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""
            <div class="gemifit-metric-grid">
                <div class="gemifit-metric-card highlight">
                    <div class="gemifit-metric-value">{plan['target_calories']}</div>
                    <div class="gemifit-metric-label">קלוריות יומיות</div>
                </div>
                <div class="gemifit-metric-card">
                    <div class="gemifit-metric-value">{plan['protein_g']} גרם</div>
                    <div class="gemifit-metric-label">חלבון</div>
                </div>
                <div class="gemifit-metric-card">
                    <div class="gemifit-metric-value">{plan['carbs_g']} גרם</div>
                    <div class="gemifit-metric-label">פחמימות</div>
                </div>
                <div class="gemifit-metric-card">
                    <div class="gemifit-metric-value">{plan['fat_g']} גרם</div>
                    <div class="gemifit-metric-label">שומן</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("איך חישבנו?"):
            st.markdown(
                f"""
                קצב חילוף חומרים בסיסי (BMR): **{plan['bmr']} קק"ל** —
                כמות הקלוריות שהגוף שורף במנוחה מוחלטת.

                הוצאה קלורית יומית כוללת (TDEE): **{plan['tdee']} קק"ל** —
                ה-BMR מוכפל ברמת הפעילות שבחרתם.

                מהערך הזה חישבנו את היעד היומי לפי המטרה שסימנתם, וחילקנו אותו
                לחלבון, פחמימות ושומן בהתאם.
                """
            )

with tab_weight:
    st.markdown(placeholder_html, unsafe_allow_html=True)

with tab_workout:
    st.markdown(placeholder_html, unsafe_allow_html=True)

with tab_nutrition:
    st.markdown(placeholder_html, unsafe_allow_html=True)
