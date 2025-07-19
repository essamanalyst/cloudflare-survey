import streamlit as st
import pandas as pd
from datetime import datetime
from database import db

async def show_employee_dashboard():
    if not st.session_state.get('region_id'):
        st.error("حسابك غير مرتبط بأي منطقة. يرجى التواصل مع المسؤول.")
        return

    region_info = await get_employee_region_info(st.session_state.region_id)
    if not region_info:
        st.error("لم يتم العثور على معلومات المنطقة الخاصة بك في النظام")
        return

    await display_employee_header(region_info)
    allowed_surveys = await get_allowed_surveys(st.session_state.user_id)
    
    if not allowed_surveys:
        st.info("لا توجد استبيانات متاحة لك حاليًا")
        return

    selected_surveys = await display_survey_selection(allowed_surveys)
    
    for survey_id in selected_surveys:
        await display_single_survey(survey_id, region_info['admin_id'])

async def get_employee_region_info(region_id):
    try:
        result = await db.d1.fetch_one('''
            SELECT h.admin_id, h.admin_name, g.governorate_name, g.governorate_id
            FROM HealthAdministrations h
            JOIN Governorates g ON h.governorate_id = g.governorate_id
            WHERE h.admin_id = ?
        ''', (region_id,))
        return {
            'admin_id': result[0],
            'admin_name': result[1],
            'governorate_name': result[2],
            'governorate_id': result[3]
        } if result else None
    except Exception as e:
        st.error(f"خطأ في قاعدة البيانات: {str(e)}")
        return None

async def display_employee_header(region_info):
    st.set_page_config(layout="wide")
    st.title(f"لوحة الموظف - {region_info['admin_name']}")
    
    last_login = await get_last_login(st.session_state.user_id)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("المحافظة")
        st.info(region_info['governorate_name'])
    with col2:
        st.subheader("الإدارة الصحية")
        st.info(region_info['admin_name'])
    with col3:
        st.subheader("آخر دخول")
        st.info(last_login if last_login else "غير معروف")

async def get_last_login(user_id):
    try:
        result = await db.d1.fetch_one("SELECT last_login FROM Users WHERE user_id=?", (user_id,))
        return result[0] if result and result[0] else None
    except Exception as e:
        st.error(f"حدث خطأ في جلب وقت آخر دخول: {str(e)}")
        return None

async def display_survey_selection(allowed_surveys):
    st.header("الاستبيانات المتاحة")
    
    selected_surveys = st.multiselect(
        "اختر استبيان أو أكثر",
        options=[s[0] for s in allowed_surveys],
        format_func=lambda x: next(s[1] for s in allowed_surveys if s[0] == x),
        key="selected_surveys"
    )
    
    return selected_surveys

async def display_single_survey(survey_id, region_id):
    survey_info = await db.d1.fetch_one('''
        SELECT survey_name, created_at FROM Surveys WHERE survey_id = ?
    ''', (survey_id,))
    
    if not survey_info:
        st.error("الاستبيان المحدد غير موجود")
        return
        
    if await db.has_completed_survey_today(st.session_state.user_id, survey_id):
        st.warning(f"لقد أكملت استبيان '{survey_info[0]}' اليوم. يمكنك إكماله مرة أخرى غدًا.")
        return
        
    with st.expander(f"📋 {survey_info[0]} (تاريخ الإنشاء: {survey_info[1]})"):
        fields = await db.get_survey_fields(survey_id)
        await display_survey_form(survey_id, region_id, fields, survey_info[0])

async def display_survey_form(survey_id, region_id, fields, survey_name):
    with st.form(f"survey_form_{survey_id}"):
        st.markdown("**يرجى تعبئة جميع الحقول المطلوبة (*)**")
        st.subheader("🧾 بيانات الاستبيان")
        answers = {}
        for field in fields:
            field_id, label, field_type, options, is_required, _ = field
            answers[field_id] = render_field(field_id, label, field_type, options, is_required)
        
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("🚀 إرسال النموذج")
        with col2:
            save_draft = st.form_submit_button("💾 حفظ مسودة")
        
        if submitted or save_draft:
            await process_survey_submission(
                survey_id,
                region_id,
                fields,
                answers,
                submitted,
                survey_name
            )

def render_field(field_id, label, field_type, options, is_required):
    required_mark = " *" if is_required else ""
    
    if field_type == 'text':
        return st.text_input(label + required_mark, key=f"text_{field_id}")
    elif field_type == 'number':
        return st.number_input(label + required_mark, key=f"number_{field_id}")
    elif field_type == 'dropdown':
        options_list = json.loads(options) if options else []
        return st.selectbox(label + required_mark, options_list, key=f"dropdown_{field_id}")
    elif field_type == 'checkbox':
        return st.checkbox(label + required_mark, key=f"checkbox_{field_id}")
    elif field_type == 'date':
        return st.date_input(label + required_mark, key=f"date_{field_id}")
    else:
        st.warning(f"نوع الحقل غير معروف: {field_type}")
        return None

async def process_survey_submission(survey_id, region_id, fields, answers, is_completed, survey_name):
    missing_fields = check_required_fields(fields, answers)
    
    if missing_fields and is_completed:
        st.error(f"الحقول التالية مطلوبة: {', '.join(missing_fields)}")
        return
    
    if is_completed and await db.has_completed_survey_today(st.session_state.user_id, survey_id):
        st.error("لقد قمت بإكمال هذا الاستبيان اليوم بالفعل. يمكنك إكماله مرة أخرى غدًا.")
        return
    
    response_id = await db.save_response(
        survey_id=survey_id,
        user_id=st.session_state.user_id,
        region_id=region_id,
        is_completed=is_completed
    )
    
    if not response_id:
        st.error("حدث خطأ أثناء حفظ البيانات")
        return
    
    await save_response_details(response_id, answers)
    show_submission_message(is_completed, survey_name)

def check_required_fields(fields, answers):
    missing_fields = []
    for field in fields:
        field_id, label, _, _, is_required, _ = field
        if is_required and not answers.get(field_id):
            missing_fields.append(label)
    return missing_fields

async def save_response_details(response_id, answers):
    for field_id, answer in answers.items():
        if answer is not None:
            await db.save_response_detail(
                response_id=response_id,
                field_id=field_id,
                answer_value=str(answer)
            )

def show_submission_message(is_completed, survey_name):
    if is_completed:
        st.success(f"تم إرسال استبيان '{survey_name}' بنجاح")
        cols = st.columns(3)
        cols[0].info(f"الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        cols[1].info(f"بواسطة: {st.session_state.username}")
        cols[2].info(f"حالة: مكتمل")
    else:
        st.success(f"تم حفظ مسودة استبيان '{survey_name}' بنجاح")

async def get_allowed_surveys(user_id):
    try:
        return await db.d1.fetch_all('''
            SELECT s.survey_id, s.survey_name 
            FROM Surveys s
            JOIN UserSurveys us ON s.survey_id = us.survey_id
            WHERE us.user_id = ?
            ORDER BY s.survey_name
        ''', (user_id,))
    except Exception as e:
        st.error(f"حدث خطأ في جلب الاستبيانات المسموح بها: {str(e)}")
        return []

async def view_survey_responses(survey_id):
    survey = await db.d1.fetch_one(
        "SELECT survey_name FROM Surveys WHERE survey_id=?",
        (survey_id,)
    )
    
    st.subheader(f"إجابات استبيان {survey[0]} (عرض فقط)")
    
    responses = await db.d1.fetch_all('''
        SELECT r.response_id, r.submission_date, r.is_completed
        FROM Responses r
        WHERE r.survey_id = ? AND r.user_id = ?
        ORDER BY r.submission_date DESC
    ''', (survey_id, st.session_state.user_id))
    
    if not responses:
        st.info("لا توجد إجابات مسجلة لهذا الاستبيان")
        return
    
    df = pd.DataFrame(
        [(r[0], r[1], "✔️" if r[2] else "✖️") 
         for r in responses],
        columns=["ID", "التاريخ", "الحالة"]
    )
    
    st.dataframe(df, use_container_width=True)
    
    selected_response_id = st.selectbox(
        "اختر إجابة لعرض تفاصيلها",
        options=[r[0] for r in responses],
        format_func=lambda x: f"إجابة #{x}"
    )

    if selected_response_id:
        details = await db.d1.fetch_all('''
            SELECT sf.field_label, rd.answer_value
            FROM Response_Details rd
            JOIN Survey_Fields sf ON rd.field_id = sf.field_id
            WHERE rd.response_id = ?
            ORDER BY sf.field_order
        ''', (selected_response_id,))

        st.subheader("تفاصيل الإجابة المحددة")
        for field, answer in details:
            st.write(f"**{field}:** {answer if answer else 'غير مدخل'}")