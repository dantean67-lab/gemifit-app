from datetime import date

import pandas as pd

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


WEIGHT_BACKUP_COLUMNS = ["date", "weight_kg"]


def get_weight_entries():
    if "weight_entries" not in st.session_state:
        st.session_state["weight_entries"] = pd.DataFrame(columns=WEIGHT_BACKUP_COLUMNS)
    return st.session_state["weight_entries"]


def upsert_weight_entry(df, entry_date, weight_kg):
    df = df[df["date"] != entry_date]
    new_row = pd.DataFrame([{"date": entry_date, "weight_kg": weight_kg}])
    df = pd.concat([df, new_row], ignore_index=True)
    return df.sort_values("date").reset_index(drop=True)


def delete_weight_entry(df, entry_date):
    return df[df["date"] != entry_date].reset_index(drop=True)


def parse_weight_backup_csv(uploaded_file):
    backup_df = pd.read_csv(uploaded_file)
    if list(backup_df.columns) != WEIGHT_BACKUP_COLUMNS:
        raise ValueError("עמודות הקובץ אינן תואמות לפורמט הגיבוי")
    if backup_df.empty:
        return backup_df.astype({"date": "object", "weight_kg": "float"})

    backup_df["date"] = pd.to_datetime(backup_df["date"], format="%Y-%m-%d").dt.date
    backup_df["weight_kg"] = pd.to_numeric(backup_df["weight_kg"])
    return backup_df.sort_values("date").reset_index(drop=True)


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

    /* ---------- Info note (subtle, non-urgent) ---------- */
    .gemifit-note {
        background-color: #12201c;
        border: 1px solid #223028;
        color: #9fb3ac;
        border-radius: 10px;
        padding: 0.7rem 1rem;
        margin: 0.9rem 0;
        direction: rtl;
        text-align: right;
        font-size: 0.85rem;
        line-height: 1.5;
    }

    /* ---------- Tables ---------- */
    .stTable table, .stDataFrame, table {
        direction: rtl;
    }

    .stTable th, .stTable td {
        text-align: right !important;
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

    /* Keep signed numbers (e.g. +2.3 / -1.5) from having their sign
       flipped to the wrong side by the RTL bidi algorithm. */
    .gemifit-ltr {
        direction: ltr;
        unicode-bidi: embed;
        display: inline-block;
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
            st.caption(
                "המחשבון מיועד לגילאי 18 ומעלה. "
                "מתחת לגיל 18 — פנו לרופא או לדיאטן מוסמך."
            )
            height = st.number_input(
                "גובה בס״מ", min_value=120, max_value=230, value=170, step=1
            )
        with col2:
            weight = st.number_input(
                "משקל בק״ג", min_value=35.0, max_value=250.0, value=70.0, step=0.5
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
                    ולכן הוגדר לרף מינימלי של {plan['floor']} קק״ל ליום.
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
                קצב חילוף חומרים בסיסי (BMR): **{plan['bmr']} קק״ל** —
                כמות הקלוריות שהגוף שורף במנוחה מוחלטת.

                הוצאה קלורית יומית כוללת (TDEE): **{plan['tdee']} קק״ל** —
                ה-BMR מוכפל ברמת הפעילות שבחרתם.

                מהערך הזה חישבנו את היעד היומי לפי המטרה שסימנתם, וחילקנו אותו
                לחלבון, פחמימות ושומן בהתאם.
                """
            )

with tab_weight:
    weight_df = get_weight_entries()

    default_weight = (
        float(weight_df.sort_values("date").iloc[-1]["weight_kg"])
        if not weight_df.empty
        else 70.0
    )

    with st.form("weight_entry_form"):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            entry_date = st.date_input("תאריך", value=date.today())
        with col2:
            entry_weight = st.number_input(
                "משקל בק״ג",
                min_value=35.0,
                max_value=250.0,
                value=default_weight,
                step=0.1,
            )
        with col3:
            st.markdown("<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True)
            add_submitted = st.form_submit_button("הוסף מדידה")

    if add_submitted:
        weight_df = upsert_weight_entry(weight_df, entry_date, entry_weight)
        st.session_state["weight_entries"] = weight_df
        st.rerun()

    if weight_df.empty:
        st.markdown(
            '<div class="gemifit-placeholder">'
            "📈 עדיין אין מדידות. הוסיפו את המדידה הראשונה שלכם למעלה "
            "כדי להתחיל לעקוב אחרי ההתקדמות שלכם."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        sorted_asc = weight_df.sort_values("date").reset_index(drop=True)
        current_weight = sorted_asc.iloc[-1]["weight_kg"]
        first_weight = sorted_asc.iloc[0]["weight_kg"]
        change = current_weight - first_weight

        st.markdown(
            f"""
            <div class="gemifit-metric-grid">
                <div class="gemifit-metric-card">
                    <div class="gemifit-metric-value">{current_weight:.1f}</div>
                    <div class="gemifit-metric-label">משקל נוכחי</div>
                </div>
                <div class="gemifit-metric-card">
                    <div class="gemifit-metric-value"><span class="gemifit-ltr">{change:+.1f}</span></div>
                    <div class="gemifit-metric-label">שינוי מאז המדידה הראשונה</div>
                </div>
                <div class="gemifit-metric-card">
                    <div class="gemifit-metric-value">{len(sorted_asc)}</div>
                    <div class="gemifit-metric-label">מספר מדידות</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        chart_series = sorted_asc.set_index("date")["weight_kg"].rename("משקל בק״ג")
        st.line_chart(chart_series)

        sorted_desc = weight_df.sort_values("date", ascending=False).reset_index(drop=True)
        display_df = pd.DataFrame(
            {
                "תאריך": sorted_desc["date"].apply(lambda d: d.strftime("%d/%m/%Y")),
                "משקל בק״ג": sorted_desc["weight_kg"].apply(lambda w: f"{w:.1f}"),
            }
        )
        display_df.index = display_df.index + 1
        st.table(display_df)

        st.markdown("##### מחיקת מדידה")
        del_col1, del_col2 = st.columns([3, 1])
        with del_col1:
            date_to_delete = st.selectbox(
                "תאריך למחיקה",
                sorted_desc["date"].tolist(),
                format_func=lambda d: d.strftime("%d/%m/%Y"),
                label_visibility="collapsed",
            )
        with del_col2:
            if st.button("מחק מדידה"):
                weight_df = delete_weight_entry(weight_df, date_to_delete)
                st.session_state["weight_entries"] = weight_df
                st.rerun()

    st.markdown("##### גיבוי ושחזור")

    backup_csv = weight_df.assign(date=weight_df["date"].astype(str)).to_csv(index=False)
    st.download_button(
        "הורד גיבוי CSV",
        data=backup_csv.encode("utf-8"),
        file_name="gemifit_weight_backup.csv",
        mime="text/csv",
        disabled=weight_df.empty,
    )

    uploaded_backup = st.file_uploader("טען גיבוי", type=["csv"])
    if uploaded_backup is not None:
        backup_signature = (uploaded_backup.name, uploaded_backup.size)
        if st.session_state.get("_weight_backup_signature") != backup_signature:
            st.session_state["_weight_backup_signature"] = backup_signature
            try:
                restored_df = parse_weight_backup_csv(uploaded_backup)
                st.session_state["weight_entries"] = restored_df
                st.success("הגיבוי נטען בהצלחה!")
                st.rerun()
            except Exception:
                st.error(
                    "קובץ הגיבוי אינו תקין. ודאו שמדובר בקובץ CSV שהופק "
                    "מהאפליקציה (עמודות date ו-weight_kg) ונסו שוב."
                )

    st.markdown(
        """
        <div class="gemifit-note">
            ℹ️ הנתונים נשמרים למשך הביקור הנוכחי בלבד. כדי לשמור לאורך זמן —
            הורידו גיבוי והעלו אותו בביקור הבא.
        </div>
        """,
        unsafe_allow_html=True,
    )

with tab_workout:
    st.markdown(placeholder_html, unsafe_allow_html=True)

with tab_nutrition:
    st.markdown(placeholder_html, unsafe_allow_html=True)
