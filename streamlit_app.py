from datetime import date

import gspread
import groq
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


def render_weight_stats_and_history(entries_df, on_delete):
    if entries_df.empty:
        st.markdown(
            '<div class="gemifit-placeholder">'
            "📈 עדיין אין מדידות. הוסיפו את המדידה הראשונה שלכם למעלה "
            "כדי להתחיל לעקוב אחרי ההתקדמות שלכם."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    sorted_asc = entries_df.sort_values("date").reset_index(drop=True)
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

    sorted_desc = entries_df.sort_values("date", ascending=False).reset_index(drop=True)
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
            key="weight_delete_select",
        )
    with del_col2:
        if st.button("מחק מדידה", key="weight_delete_btn"):
            on_delete(date_to_delete)


def parse_weight_backup_csv(uploaded_file):
    backup_df = pd.read_csv(uploaded_file)
    if list(backup_df.columns) != WEIGHT_BACKUP_COLUMNS:
        raise ValueError("עמודות הקובץ אינן תואמות לפורמט הגיבוי")
    if backup_df.empty:
        return backup_df.astype({"date": "object", "weight_kg": "float"})

    backup_df["date"] = pd.to_datetime(backup_df["date"], format="%Y-%m-%d").dt.date
    backup_df["weight_kg"] = pd.to_numeric(backup_df["weight_kg"])
    return backup_df.sort_values("date").reset_index(drop=True)


def is_auth_configured():
    try:
        return bool(st.secrets.get("auth"))
    except st.errors.StreamlitSecretNotFoundError:
        return False


def get_logged_in_user():
    """Returns the logged-in user's email, or None in guest mode / on any error."""
    if not is_auth_configured():
        return None
    try:
        if st.user.is_logged_in:
            return st.user.email
    except Exception:
        return None
    return None


def get_logged_in_display_name():
    try:
        return getattr(st.user, "given_name", None) or getattr(st.user, "name", None) or st.user.email
    except Exception:
        return None


def is_gsheets_configured():
    try:
        gsheets_secrets = st.secrets.get("connections", {}).get("gsheets")
    except st.errors.StreamlitSecretNotFoundError:
        return False
    return bool(gsheets_secrets)


CLOUD_WEIGHT_WORKSHEET = "weights"
CLOUD_WEIGHT_COLUMNS = ["email", "date", "weight_kg"]

CLOUD_WATER_WORKSHEET = "water"
CLOUD_WATER_COLUMNS = ["email", "date", "ml_total", "goal_ml"]

DEFAULT_WATER_GOAL_ML = 2500


@st.cache_resource(show_spinner=False)
def _get_gsheets_spreadsheet():
    gsheets_secrets = dict(st.secrets["connections"]["gsheets"])
    spreadsheet_ref = gsheets_secrets.pop("spreadsheet")

    client = gspread.service_account_from_dict(gsheets_secrets)
    return (
        client.open_by_url(spreadsheet_ref)
        if spreadsheet_ref.startswith("http")
        else client.open_by_key(spreadsheet_ref)
    )


def _get_or_create_worksheet(title, columns):
    spreadsheet = _get_gsheets_spreadsheet()
    try:
        worksheet = spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(columns))
        worksheet.update(range_name="A1", values=[columns])
    return worksheet


@st.cache_resource(show_spinner=False)
def get_cloud_weight_worksheet():
    return _get_or_create_worksheet(CLOUD_WEIGHT_WORKSHEET, CLOUD_WEIGHT_COLUMNS)


@st.cache_resource(show_spinner=False)
def get_cloud_water_worksheet():
    return _get_or_create_worksheet(CLOUD_WATER_WORKSHEET, CLOUD_WATER_COLUMNS)


@st.cache_data(ttl=5, show_spinner=False)
def _read_all_cloud_weight_rows():
    worksheet = get_cloud_weight_worksheet()
    records = worksheet.get_all_records(expected_headers=CLOUD_WEIGHT_COLUMNS)
    df = pd.DataFrame(records, columns=CLOUD_WEIGHT_COLUMNS)

    df["email"] = df["email"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["weight_kg"] = pd.to_numeric(df["weight_kg"], errors="coerce")
    df = df.dropna(subset=["email", "date", "weight_kg"])
    return df[df["email"] != ""].reset_index(drop=True)


def load_all_cloud_weight_rows(fresh=False):
    if fresh:
        st.cache_data.clear()
    return _read_all_cloud_weight_rows()


def save_all_cloud_weight_rows(df):
    worksheet = get_cloud_weight_worksheet()
    sorted_df = df.sort_values(["email", "date"]).reset_index(drop=True)
    values = [CLOUD_WEIGHT_COLUMNS] + [
        [row.email, row.date.isoformat(), row.weight_kg] for row in sorted_df.itertuples(index=False)
    ]
    worksheet.clear()
    worksheet.update(range_name="A1", values=values)
    st.cache_data.clear()


def get_user_cloud_weight_entries(email):
    all_rows = load_all_cloud_weight_rows()
    user_rows = all_rows[all_rows["email"] == email][["date", "weight_kg"]]
    return user_rows.sort_values("date").reset_index(drop=True)


def upsert_cloud_weight_entry(email, entry_date, weight_kg):
    all_rows = load_all_cloud_weight_rows(fresh=True)
    other_rows = all_rows[~((all_rows["email"] == email) & (all_rows["date"] == entry_date))]
    new_row = pd.DataFrame([{"email": email, "date": entry_date, "weight_kg": weight_kg}])
    save_all_cloud_weight_rows(pd.concat([other_rows, new_row], ignore_index=True))


def delete_cloud_weight_entry(email, entry_date):
    all_rows = load_all_cloud_weight_rows(fresh=True)
    remaining = all_rows[~((all_rows["email"] == email) & (all_rows["date"] == entry_date))]
    save_all_cloud_weight_rows(remaining)


def delete_all_cloud_weight_entries(email):
    all_rows = load_all_cloud_weight_rows(fresh=True)
    remaining = all_rows[all_rows["email"] != email]
    save_all_cloud_weight_rows(remaining)


@st.cache_data(ttl=5, show_spinner=False)
def _read_all_cloud_water_rows():
    worksheet = get_cloud_water_worksheet()
    records = worksheet.get_all_records(expected_headers=CLOUD_WATER_COLUMNS)
    df = pd.DataFrame(records, columns=CLOUD_WATER_COLUMNS)

    df["email"] = df["email"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["ml_total"] = pd.to_numeric(df["ml_total"], errors="coerce")
    df["goal_ml"] = pd.to_numeric(df["goal_ml"], errors="coerce")
    df = df.dropna(subset=["email", "date", "ml_total", "goal_ml"])
    return df[df["email"] != ""].reset_index(drop=True)


def load_all_cloud_water_rows(fresh=False):
    if fresh:
        st.cache_data.clear()
    return _read_all_cloud_water_rows()


def save_all_cloud_water_rows(df):
    worksheet = get_cloud_water_worksheet()
    sorted_df = df.sort_values(["email", "date"]).reset_index(drop=True)
    values = [CLOUD_WATER_COLUMNS] + [
        [row.email, row.date.isoformat(), row.ml_total, row.goal_ml]
        for row in sorted_df.itertuples(index=False)
    ]
    worksheet.clear()
    worksheet.update(range_name="A1", values=values)
    st.cache_data.clear()


def get_user_cloud_water_today(email):
    today = date.today()
    all_rows = load_all_cloud_water_rows()
    match = all_rows[(all_rows["email"] == email) & (all_rows["date"] == today)]
    if match.empty:
        return 0, DEFAULT_WATER_GOAL_ML
    row = match.iloc[0]
    return int(row["ml_total"]), int(row["goal_ml"])


def save_cloud_water_today(email, ml_total, goal_ml):
    today = date.today()
    all_rows = load_all_cloud_water_rows(fresh=True)
    other_rows = all_rows[~((all_rows["email"] == email) & (all_rows["date"] == today))]
    new_row = pd.DataFrame(
        [{"email": email, "date": today, "ml_total": ml_total, "goal_ml": goal_ml}]
    )
    save_all_cloud_water_rows(pd.concat([other_rows, new_row], ignore_index=True))


def ensure_guest_water_state():
    today = date.today()
    if st.session_state.get("water_date") != today:
        st.session_state["water_date"] = today
        st.session_state["water_ml_total"] = 0
    st.session_state.setdefault("water_goal_ml", DEFAULT_WATER_GOAL_ML)


def render_water_tracker(ml_total, goal_ml, on_add, on_set_goal, on_reset):
    st.markdown("##### 💧 מעקב מים יומי")

    goal_col, _ = st.columns([2, 2])
    with goal_col:
        new_goal = st.number_input(
            "יעד יומי (מ״ל)",
            min_value=1000,
            max_value=5000,
            value=int(goal_ml),
            step=250,
            key="water_goal_input",
        )
    if new_goal != goal_ml:
        on_set_goal(new_goal)
        goal_ml = new_goal

    progress_ratio = min(ml_total / goal_ml, 1.0) if goal_ml else 0.0
    st.progress(progress_ratio)
    st.markdown(
        f"<div style='text-align:center; font-weight:700; font-size:1.1rem; margin:0.4rem 0;'>"
        f"<span class='gemifit-ltr'>{ml_total}</span> מתוך "
        f"<span class='gemifit-ltr'>{goal_ml}</span> מ״ל</div>",
        unsafe_allow_html=True,
    )

    if ml_total >= goal_ml:
        encouragement = "🎉 כל הכבוד! הגעתם ליעד המים היומי שלכם!"
    elif ml_total >= goal_ml * 0.5:
        encouragement = "💪 כבר באמצע הדרך — כל הכבוד, המשיכו כך!"
    else:
        encouragement = "🚰 בואו נתחיל לשתות, כל כוס עוזרת!"
    st.markdown(f'<div class="gemifit-note">{encouragement}</div>', unsafe_allow_html=True)

    qa_col1, qa_col2, qa_col3 = st.columns(3)
    with qa_col1:
        if st.button("+ כוס (250)", key="water_add_cup", use_container_width=True):
            on_add(250)
    with qa_col2:
        if st.button("+ בקבוק (500)", key="water_add_bottle", use_container_width=True):
            on_add(500)
    with qa_col3:
        if st.button("אפס להיום", key="water_reset_btn", use_container_width=True):
            on_reset()

    custom_col1, custom_col2 = st.columns([3, 1])
    with custom_col1:
        custom_ml = st.number_input(
            "כמות מותאמת אישית (מ״ל)",
            min_value=0,
            max_value=3000,
            value=0,
            step=50,
            key="water_custom_ml",
        )
    with custom_col2:
        st.markdown("<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True)
        if st.button("הוסף", key="water_add_custom_btn", use_container_width=True):
            if custom_ml > 0:
                on_add(custom_ml)


GROQ_MODEL = "openai/gpt-oss-120b"

WORKOUT_GOALS = ["בניית שריר וחיזוק", "ירידה במשקל", "שיפור כושר וסיבולת"]
WORKOUT_LEVELS = ["מתחיל", "בינוני", "מתקדם"]
WORKOUT_EQUIPMENT = ["ללא ציוד (משקל גוף)", "משקולות בסיסיות בבית", "חדר כושר מלא"]

WORKOUT_SYSTEM_PROMPT = """\
את/ה מאמן/ת כושר מוסמך/ת ומנוסה, וכותב/ת בעברית טבעית וברורה.
בנה/י תוכנית אימונים שבועית שמתאימה בדיוק למטרה, לרמת המתאמן/ת, למספר ימי \
האימון בשבוע, למשך האימון ולציוד הזמין שצוינו על ידי המשתמש/ת.

מבנה התשובה:
1. שורת פתיחה קצרה אחת שמתארת את התוכנית.
2. לכל יום אימון: כותרת מודגשת (לדוגמה **יום 1 — פלג גוף עליון**), שורת חימום \
קצרה, ולאחריה רשימת תרגילים בפורמט: "שם התרגיל — 3x12, מנוחה 60 שניות". \
לתרגילי קרדיו טהורים (כמו קפיצות פיסוק, הרמות ברכיים, ריצה במקום, ברפיז) \
יש לציין משך זמן במקום מספר חזרות, לדוגמה "45 שניות, מנוחה 30 שניות". \
לשם כל תרגיל יש לבחור שם עברי טבעי ומקובל אם קיים כזה, ואם לא — להשתמש בשם \
הנפוץ בחדרי כושר; אסור בהחלט לערבב עברית ואנגלית באותו שם תרגיל.
3. חלוקת ימי האימון לאורך השבוע, בלי לציין ימים ספציפיים (כמו "יום שני") — \
יש לציין באופן כללי שיש לפזר את האימונים לאורך השבוע כך שיהיה לפחות יום \
מנוחה אחד בין כל שני ימי אימון.
4. בסיום, בדיוק 3 כללי בטיחות קצרים: טכניקה לפני משקל, עצירה מיידית אם יש \
כאב, והתקדמות הדרגתית.
5. שורת סיום אחת שאומרת שהתוכנית כללית, מיועדת למבוגרים בריאים, ושיש \
להתייעץ עם רופא/ה במקרה של ספק.

לעולם אל תיתן/י ייעוץ רפואי, טיפול בפציעות או המלצות על תוספי תזונה.
"""


def build_workout_user_prompt(goal, level, days_per_week, duration_minutes, equipment):
    return (
        f"מטרה: {goal}\n"
        f"רמה: {level}\n"
        f"ימי אימון בשבוע: {days_per_week}\n"
        f"משך כל אימון: {duration_minutes} דקות\n"
        f"ציוד זמין: {equipment}\n"
        "בנה/י עבורי תוכנית אימונים שבועית מותאמת."
    )


def generate_workout_plan(api_key, goal, level, days_per_week, duration_minutes, equipment):
    client = groq.Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": WORKOUT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_workout_user_prompt(
                    goal, level, days_per_week, duration_minutes, equipment
                ),
            },
        ],
        temperature=0.4,
        max_tokens=2500,
    )
    return response.choices[0].message.content


NUTRITION_STYLES = ["רגיל", "צמחוני", "טבעוני"]
MEALS_PER_DAY_OPTIONS = [3, 4, 5]

NUTRITION_SYSTEM_PROMPT = """\
את/ה בונה/ת תפריטי תזונה יומיים מעשיים בעברית טבעית וברורה.
בנה/י תפריט ליום שלם אחד, מחולק למספר הארוחות שהתבקש.
לכל ארוחה: כותרת מודגשת, פירוט מזונות עם כמויות מעשיות (גרם, יחידות, כוסות) \
וכמות קלוריות משוערת לארוחה.

טבלת ייחוס תזונתית (קק״ל ל-100 גרם אלא אם צוין אחרת) — עגן/י כל הערכה לפי \
הטבלה הזו:
לחם ופיתה: 250-280 (פיתה קטנה אחת ≈ 60 גרם)
אורז מבושל: 115-130
פסטה יבשה: 350
עדשים מבושלות: 115
חומוס מוכן: 170-200
טחינה גולמית: 590-620
שמן זית: כף אחת = 120 קק״ל
ביצה אחת = 70-80 קק״ל
חזה עוף: 110-120
גבינה לבנה 5%: 95
קוטג' 5%: 100
יוגורט 3%: 60
בננה בינונית = 90-105 ליחידה
תפוח = 80-95 ליחידה
אבוקדו: 160
טופו: 76-120
שיבולת שועל: 370-390
משקה סויה ללא סוכר = 33-40 ל-100 מ״ל

חובה: מספר הקלוריות של כל פריט חייב להתאים בדיוק לכמות שצוינה עבורו לפי \
הטבלה הזו (ולערכים תזונתיים מקובלים לפריטים שאינם בטבלה). לפני כתיבת \
התשובה הסופית, חשב/י בפועל את סכום הקלוריות של הפריטים בכל ארוחה ואמת/י \
שהוא תואם למספר שמוצג לצד הארוחה, ולאחר מכן חשב/י את סך הקלוריות היומי \
כסכום כל הארוחות ואמת/י שהוא בטווח של עד 5% מהיעד שצוין — אם יש פער, תקן/י \
את הכמויות לפני שאת/ה עונה/ת. ודא/י שמשקלי הפריטים הגיוניים ומציאותיים.

כתוב/כתבי מספרים בצורה פשוטה (למשל 1780) בלי פסיק מפריד אלפים, השתמש/י \
בסימן ≈ לכל היותר פעם אחת בכל שורה, והימנע/י ממילים כפולות בכותרות הארוחות.
יש לכבד את סגנון התזונה שנבחר, את כללי הכשרות אם צוינו, ואת רשימת המאכלים \
להימנעות.
העדף/י מזונות פשוטים, זולים וזמינים בישראל.
כלול/י שורה אחת על שתיית מים לאורך היום.
אם המשתמש/ת ציין/ה אלרגיות, הוסף/י שורת אזהרה אחת שיש לבדוק את רכיבי \
המוצרים באופן אישי.
סיים/י בשורה שהתפריט כללי, מיועד למבוגרים בריאים, ושיש להתייעץ עם רופא/ה \
או דיאטן/ית במקרה של ספק.
לעולם אל תבנה/י תפריט מתחת ל-1200 קלוריות, ולעולם אל תמליץ/י על תוספי תזונה \
ואל תיתן/י ייעוץ רפואי.
"""


def build_nutrition_user_prompt(
    calorie_target, protein_g, carbs_g, fat_g, style, kosher, meals_per_day, avoid_foods
):
    macro_line = ""
    if protein_g is not None:
        macro_line = (
            f"פילוח מקרו-נוטריאנטים יעד: חלבון {protein_g} גרם, "
            f"פחמימות {carbs_g} גרם, שומן {fat_g} גרם.\n"
        )

    lines = [
        f"יעד קלוריות יומי: {calorie_target} קלוריות",
        macro_line,
        f"סגנון תזונה: {style}",
        f"שומר/ת כשרות: {'כן — ללא חזיר ופירות ים, ואיסור ערבוב בשר וחלב באותה ארוחה' if kosher else 'לא'}",
        f"מספר ארוחות ביום: {meals_per_day}",
        f"מאכלים להימנעות (אלרגיות או העדפות): {avoid_foods if avoid_foods.strip() else 'אין'}",
        "בנה/י עבורי תפריט יומי מותאם.",
    ]
    return "\n".join(line for line in lines if line)


def generate_nutrition_menu(
    api_key, calorie_target, protein_g, carbs_g, fat_g, style, kosher, meals_per_day, avoid_foods
):
    client = groq.Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": NUTRITION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_nutrition_user_prompt(
                    calorie_target,
                    protein_g,
                    carbs_g,
                    fat_g,
                    style,
                    kosher,
                    meals_per_day,
                    avoid_foods,
                ),
            },
        ],
        temperature=0.45,
        max_tokens=2500,
    )
    return response.choices[0].message.content


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

    /* ---------- Auth bar ---------- */
    .gemifit-auth-greeting {
        text-align: center;
        color: #9fb3ac;
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 0.3rem;
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

if is_auth_configured():
    try:
        user_is_logged_in = st.user.is_logged_in
    except Exception:
        user_is_logged_in = False

    auth_col, _ = st.columns([1.4, 3])
    with auth_col:
        if user_is_logged_in:
            st.markdown(
                f'<div class="gemifit-auth-greeting">שלום, {get_logged_in_display_name()}</div>',
                unsafe_allow_html=True,
            )
            if st.button("התנתק", key="gemifit_logout_btn", use_container_width=True):
                st.logout()
        else:
            if st.button("התחבר עם גוגל", key="gemifit_login_btn", use_container_width=True):
                st.login()

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
    current_user_email = get_logged_in_user()

    if current_user_email:
        st.caption("מה נשמר: כתובת האימייל והמדידות שלך בלבד.")

        if not is_gsheets_configured():
            st.error(
                "חסרה הגדרת שמירת נתונים בענן (Google Sheets). "
                "פנו למנהל האתר כדי להשלים את ההגדרה — בינתיים לא ניתן לשמור מדידות."
            )
        else:
            try:
                cloud_entries = get_user_cloud_weight_entries(current_user_email)
                cloud_load_error = None
            except Exception:
                cloud_entries = pd.DataFrame(columns=WEIGHT_BACKUP_COLUMNS)
                cloud_load_error = "אירעה שגיאה בטעינת הנתונים מהענן. נסו לרענן את הדף בעוד רגע."

            if cloud_load_error:
                st.error(cloud_load_error)

            default_weight = (
                float(cloud_entries.sort_values("date").iloc[-1]["weight_kg"])
                if not cloud_entries.empty
                else 70.0
            )

            with st.form("weight_entry_form_cloud"):
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
                    st.markdown(
                        "<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True
                    )
                    add_submitted = st.form_submit_button("הוסף מדידה")

            if add_submitted:
                try:
                    upsert_cloud_weight_entry(current_user_email, entry_date, entry_weight)
                    st.rerun()
                except Exception:
                    st.error(
                        "אירעה שגיאה בשמירת המדידה בענן. המדידה שהזנתם לא נשמרה — נסו שוב."
                    )

            def _cloud_delete_entry(entry_date_to_delete):
                try:
                    delete_cloud_weight_entry(current_user_email, entry_date_to_delete)
                    st.rerun()
                except Exception:
                    st.error("אירעה שגיאה במחיקת המדידה. נסו שוב.")

            render_weight_stats_and_history(cloud_entries, _cloud_delete_entry)

            st.markdown("##### גיבוי")
            backup_csv = cloud_entries.assign(date=cloud_entries["date"].astype(str)).to_csv(
                index=False
            )
            st.download_button(
                "הורד גיבוי CSV",
                data=backup_csv.encode("utf-8"),
                file_name="gemifit_weight_backup.csv",
                mime="text/csv",
                disabled=cloud_entries.empty,
                key="cloud_backup_download",
            )

            st.markdown(
                """
                <div class="gemifit-note">
                    ☁️ המדידות שלך נשמרות בחשבון שלך בענן.
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("##### מחיקת כל הנתונים שלי")
            if st.session_state.get("confirm_delete_all_weight"):
                st.warning("פעולה זו תמחק לצמיתות את כל המדידות שלך. האם להמשיך?")
                confirm_col1, confirm_col2 = st.columns(2)
                with confirm_col1:
                    if st.button("כן, מחק את כל הנתונים שלי", key="confirm_delete_all_yes"):
                        try:
                            delete_all_cloud_weight_entries(current_user_email)
                            st.session_state["confirm_delete_all_weight"] = False
                            st.success("כל הנתונים נמחקו.")
                            st.rerun()
                        except Exception:
                            st.error("אירעה שגיאה במחיקת הנתונים. נסו שוב.")
                with confirm_col2:
                    if st.button("ביטול", key="confirm_delete_all_no"):
                        st.session_state["confirm_delete_all_weight"] = False
                        st.rerun()
            else:
                if st.button("מחק את כל הנתונים שלי", key="delete_all_weight_btn"):
                    st.session_state["confirm_delete_all_weight"] = True
                    st.rerun()

            st.markdown("---")

            try:
                cloud_ml_total, cloud_goal_ml = get_user_cloud_water_today(current_user_email)
                water_load_error = None
            except Exception:
                cloud_ml_total, cloud_goal_ml = 0, DEFAULT_WATER_GOAL_ML
                water_load_error = "אירעה שגיאה בטעינת נתוני השתייה מהענן. נסו לרענן את הדף בעוד רגע."

            if water_load_error:
                st.error(water_load_error)

            def _cloud_water_add(amount_ml):
                try:
                    ml_total, goal_ml = get_user_cloud_water_today(current_user_email)
                    save_cloud_water_today(current_user_email, ml_total + amount_ml, goal_ml)
                    st.rerun()
                except Exception:
                    st.error("אירעה שגיאה בשמירת נתוני השתייה בענן. נסו שוב.")

            def _cloud_water_set_goal(new_goal_ml):
                try:
                    ml_total, _ = get_user_cloud_water_today(current_user_email)
                    save_cloud_water_today(current_user_email, ml_total, new_goal_ml)
                except Exception:
                    st.error("אירעה שגיאה בשמירת היעד היומי. נסו שוב.")

            def _cloud_water_reset():
                try:
                    _, goal_ml = get_user_cloud_water_today(current_user_email)
                    save_cloud_water_today(current_user_email, 0, goal_ml)
                    st.rerun()
                except Exception:
                    st.error("אירעה שגיאה באיפוס נתוני השתייה. נסו שוב.")

            render_water_tracker(
                cloud_ml_total,
                cloud_goal_ml,
                _cloud_water_add,
                _cloud_water_set_goal,
                _cloud_water_reset,
            )

    else:
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

        def _guest_delete_entry(entry_date_to_delete):
            updated = delete_weight_entry(get_weight_entries(), entry_date_to_delete)
            st.session_state["weight_entries"] = updated
            st.rerun()

        render_weight_stats_and_history(weight_df, _guest_delete_entry)

        st.markdown("##### גיבוי ושחזור")

        backup_csv = weight_df.assign(date=weight_df["date"].astype(str)).to_csv(index=False)
        st.download_button(
            "הורד גיבוי CSV",
            data=backup_csv.encode("utf-8"),
            file_name="gemifit_weight_backup.csv",
            mime="text/csv",
            disabled=weight_df.empty,
            key="guest_backup_download",
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

        st.markdown("---")

        ensure_guest_water_state()

        def _guest_water_add(amount_ml):
            st.session_state["water_ml_total"] += amount_ml
            st.rerun()

        def _guest_water_set_goal(new_goal_ml):
            st.session_state["water_goal_ml"] = new_goal_ml

        def _guest_water_reset():
            st.session_state["water_ml_total"] = 0
            st.rerun()

        render_water_tracker(
            st.session_state["water_ml_total"],
            st.session_state["water_goal_ml"],
            _guest_water_add,
            _guest_water_set_goal,
            _guest_water_reset,
        )

with tab_workout:
    try:
        api_key = st.secrets.get("GROQ_API_KEY")
    except st.errors.StreamlitSecretNotFoundError:
        api_key = None

    if not api_key:
        st.markdown(
            """
            <div class="gemifit-warning">
                ⚠️ חסר מפתח AI. יש להגדיר GROQ_API_KEY בהגדרות הסודות של האתר.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        with st.form("workout_plan_form"):
            goal = st.radio("מטרה", WORKOUT_GOALS)
            level = st.radio("רמה", WORKOUT_LEVELS, horizontal=True)

            col1, col2 = st.columns(2)
            with col1:
                days_per_week = st.number_input(
                    "ימי אימון בשבוע", min_value=2, max_value=6, value=3, step=1
                )
            with col2:
                duration_minutes = st.radio(
                    "משך אימון", [30, 45, 60], horizontal=True, format_func=lambda m: f"{m} דקות"
                )

            equipment = st.radio("ציוד זמין", WORKOUT_EQUIPMENT)

            workout_submitted = st.form_submit_button("צור לי תוכנית אימון")

        if workout_submitted:
            with st.spinner("בונה לך תוכנית מותאמת..."):
                try:
                    plan_text = generate_workout_plan(
                        api_key, goal, level, days_per_week, duration_minutes, equipment
                    )
                    st.session_state["workout_plan"] = plan_text
                    st.session_state.pop("workout_error", None)
                except groq.RateLimitError:
                    st.session_state["workout_error"] = (
                        "המכסה היומית של ה-AI הסתיימה — נסו שוב מאוחר יותר."
                    )
                    st.session_state.pop("workout_plan", None)
                except groq.APIError:
                    st.session_state["workout_error"] = (
                        "אירעה שגיאה בתקשורת עם שירות ה-AI. נסו שוב בעוד כמה רגעים."
                    )
                    st.session_state.pop("workout_plan", None)

        workout_error = st.session_state.get("workout_error")
        if workout_error:
            st.error(workout_error)

        workout_plan = st.session_state.get("workout_plan")
        if workout_plan:
            st.markdown(workout_plan)
            st.download_button(
                "הורד את התוכנית",
                data=workout_plan.encode("utf-8"),
                file_name="gemifit_workout_plan.txt",
                mime="text/plain",
            )

with tab_nutrition:
    try:
        nutrition_api_key = st.secrets.get("GROQ_API_KEY")
    except st.errors.StreamlitSecretNotFoundError:
        nutrition_api_key = None

    if not nutrition_api_key:
        st.markdown(
            """
            <div class="gemifit-warning">
                ⚠️ חסר מפתח AI. יש להגדיר GROQ_API_KEY בהגדרות הסודות של האתר.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        calorie_plan = st.session_state.get("calorie_plan")

        if calorie_plan:
            st.markdown(
                f"התפריט מבוסס על היעד שחישבת: "
                f"**{calorie_plan['target_calories']} קלוריות**."
            )
            calorie_target = calorie_plan["target_calories"]
            protein_g = calorie_plan["protein_g"]
            carbs_g = calorie_plan["carbs_g"]
            fat_g = calorie_plan["fat_g"]
        else:
            calorie_target = st.number_input(
                "יעד קלוריות יומי",
                min_value=1200,
                max_value=4000,
                value=2000,
                step=50,
            )
            st.caption("טיפ: בתפריט מחשבון קלוריות תוכלו לחשב יעד קלוריות מותאם אישית.")
            protein_g = carbs_g = fat_g = None

        with st.form("nutrition_menu_form"):
            style = st.radio("סגנון תזונה", NUTRITION_STYLES, horizontal=True)
            kosher = st.checkbox("שומר/ת כשרות")
            meals_per_day = st.radio(
                "מספר ארוחות ביום", MEALS_PER_DAY_OPTIONS, horizontal=True
            )
            avoid_foods = st.text_input(
                "מאכלים להימנע מהם (אלרגיות או העדפות) — לא חובה"
            )

            nutrition_submitted = st.form_submit_button("צור לי תפריט")

        if nutrition_submitted:
            with st.spinner("מרכיב לך תפריט..."):
                try:
                    menu_text = generate_nutrition_menu(
                        nutrition_api_key,
                        calorie_target,
                        protein_g,
                        carbs_g,
                        fat_g,
                        style,
                        kosher,
                        meals_per_day,
                        avoid_foods,
                    )
                    st.session_state["nutrition_menu"] = menu_text
                    st.session_state.pop("nutrition_error", None)
                except groq.RateLimitError:
                    st.session_state["nutrition_error"] = (
                        "המכסה היומית של ה-AI הסתיימה — נסו שוב מאוחר יותר."
                    )
                    st.session_state.pop("nutrition_menu", None)
                except groq.APIError:
                    st.session_state["nutrition_error"] = (
                        "אירעה שגיאה בתקשורת עם שירות ה-AI. נסו שוב בעוד כמה רגעים."
                    )
                    st.session_state.pop("nutrition_menu", None)

        nutrition_error = st.session_state.get("nutrition_error")
        if nutrition_error:
            st.error(nutrition_error)

        nutrition_menu = st.session_state.get("nutrition_menu")
        if nutrition_menu:
            st.markdown(nutrition_menu)
            st.caption("הערכים המוצגים הם הערכה בלבד ואינם מדידה מדויקת.")
            st.download_button(
                "הורד את התפריט",
                data=nutrition_menu.encode("utf-8"),
                file_name="gemifit_nutrition_menu.txt",
                mime="text/plain",
            )
