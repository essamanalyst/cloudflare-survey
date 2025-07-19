import streamlit as st
import pandas as pd
import json
from datetime import datetime
from database import db

async def show_admin_dashboard():
    st.title("لوحة تحكم النظام")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "إدارة المستخدمين",
        "إدارة المحافظات", 
        "إدارة الإدارات الصحية",     
        "إدارة الاستبيانات", 
        "عرض البيانات"
    ])
    
    with tab1:
        await manage_users()
    with tab2:
        await manage_governorates()
    with tab3:
        await manage_regions()
    with tab4:
        await manage_surveys()
    with tab5:
        await view_data()

async def manage_users():
    st.header("إدارة المستخدمين")
    
    users = await db.d1.fetch_all('''
    SELECT u.user_id, u.username, u.role, 
           COALESCE(g.governorate_name, ga.governorate_name) as governorate_name, 
           h.admin_name
    FROM Users u
    LEFT JOIN HealthAdministrations h ON u.assigned_region = h.admin_id
    LEFT JOIN Governorates g ON h.governorate_id = g.governorate_id
    LEFT JOIN (
        SELECT ga.user_id, g.governorate_name 
        FROM GovernorateAdmins ga
        JOIN Governorates g ON ga.governorate_id = g.governorate_id
    ) ga ON u.user_id = ga.user_id
    ORDER BY u.user_id
    ''')
    
    for user in users:
        col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 1, 1])
        with col1:
            st.write(user[1])
        with col2:
            role = "مسؤول نظام" if user[2] == "admin" else "مسؤول محافظة" if user[2] == "governorate_admin" else "موظف"
            st.write(role)
        with col3:
            st.write(user[3] if user[3] else "غير محدد")
        with col4:
            st.write(user[4] if user[4] else "غير محدد")
        with col5:
            if st.button("تعديل", key=f"edit_{user[0]}"):
                st.session_state.editing_user = user[0]
        with col6:
            if st.button("حذف", key=f"delete_{user[0]}"):
                await delete_user(user[0])
                st.rerun()
    
    if 'editing_user' in st.session_state:
        await edit_user_form(st.session_state.editing_user)
    
    with st.expander("إضافة مستخدم جديد"):
        await add_user_form()

async def add_user_form():
    governorates = await db.get_governorates_list()
    surveys = await db.d1.fetch_all("SELECT survey_id, survey_name FROM Surveys")
    
    if 'add_user_form_data' not in st.session_state:
        st.session_state.add_user_form_data = {
            'username': '',
            'password': '',
            'role': 'employee',
            'governorate_id': None,
            'admin_id': None,
            'allowed_surveys': []
        }

    form = st.form(key="add_user_form", clear_on_submit=True)
    
    with form:
        st.subheader("المعلومات الأساسية")
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("اسم المستخدم*", 
                                   value=st.session_state.add_user_form_data['username'],
                                   key="new_user_username")
        with col2:
            password = st.text_input("كلمة المرور*", 
                                   type="password",
                                   value=st.session_state.add_user_form_data['password'],
                                   key="new_user_password")

        role = st.selectbox("الدور*", 
                          ["admin", "governorate_admin", "employee"],
                          index=["admin", "governorate_admin", "employee"].index(
                              st.session_state.add_user_form_data['role']),
                          key="new_user_role")

        if role == "governorate_admin":
            st.subheader("بيانات مسؤول المحافظة")
            if governorates:
                selected_gov = st.selectbox(
                    "المحافظة*",
                    options=[g[0] for g in governorates],
                    index=[g[0] for g in governorates].index(
                        st.session_state.add_user_form_data['governorate_id']) 
                        if st.session_state.add_user_form_data['governorate_id'] in [g[0] for g in governorates] else 0,
                    format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                    key="gov_admin_select")
                st.session_state.add_user_form_data['governorate_id'] = selected_gov
            else:
                st.warning("لا توجد محافظات متاحة. يرجى إضافة محافظة أولاً.")

        elif role == "employee":
            st.subheader("بيانات الموظف")
            if governorates:
                selected_gov = st.selectbox(
                    "المحافظة*",
                    options=[g[0] for g in governorates],
                    index=[g[0] for g in governorates].index(
                        st.session_state.add_user_form_data['governorate_id']) 
                        if st.session_state.add_user_form_data['governorate_id'] in [g[0] for g in governorates] else 0,
                    format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                    key="employee_gov_select")
                st.session_state.add_user_form_data['governorate_id'] = selected_gov

                health_admins = await db.d1.fetch_all(
                    "SELECT admin_id, admin_name FROM HealthAdministrations WHERE governorate_id=?",
                    (selected_gov,)
                )
                
                if health_admins:
                    selected_admin = st.selectbox(
                        "الإدارة الصحية*",
                        options=[a[0] for a in health_admins],
                        index=[a[0] for a in health_admins].index(
                            st.session_state.add_user_form_data['admin_id']) 
                            if st.session_state.add_user_form_data['admin_id'] in [a[0] for a in health_admins] else 0,
                        format_func=lambda x: next(a[1] for a in health_admins if a[0] == x),
                        key="employee_admin_select")
                    st.session_state.add_user_form_data['admin_id'] = selected_admin
                else:
                    st.warning("لا توجد إدارات صحية في هذه المحافظة. يرجى إضافتها أولاً.")
            else:
                st.warning("لا توجد محافظات متاحة. يرجى إضافة محافظة أولاً.")

        if role != "admin" and surveys:
            st.subheader("الصلاحيات")
            selected_surveys = st.multiselect(
                "الاستبيانات المسموح بها",
                options=[s[0] for s in surveys],
                default=st.session_state.add_user_form_data['allowed_surveys'],
                format_func=lambda x: next(s[1] for s in surveys if s[0] == x),
                key="allowed_surveys_select")
            st.session_state.add_user_form_data['allowed_surveys'] = selected_surveys

        col1, col2 = st.columns([3, 1])
        with col1:
            submit_button = st.form_submit_button("💾 حفظ المستخدم")
        with col2:
            clear_button = st.form_submit_button("🧹 تنظيف الحقول")

        if submit_button:
            if not username or not password:
                st.error("يرجى إدخال اسم المستخدم وكلمة المرور")
                return

            if role == "governorate_admin" and not st.session_state.add_user_form_data['governorate_id']:
                st.error("يرجى اختيار محافظة لمسؤول المحافظة")
                return

            if role == "employee" and not st.session_state.add_user_form_data['admin_id']:
                st.error("يرجى اختيار إدارة صحية للموظف")
                return

            if await db.add_user(username, password, role, st.session_state.add_user_form_data['admin_id']):
                user_id = (await db.get_user_by_username(username))['user_id']

                if role == "governorate_admin":
                    await db.add_governorate_admin(user_id, st.session_state.add_user_form_data['governorate_id'])

                if role != "admin" and st.session_state.add_user_form_data['allowed_surveys']:
                    await db.update_user_allowed_surveys(user_id, st.session_state.add_user_form_data['allowed_surveys'])

                st.success(f"تمت إضافة المستخدم {username} بنجاح")
                st.session_state.add_user_form_data = {
                    'username': '',
                    'password': '',
                    'role': 'employee',
                    'governorate_id': None,
                    'admin_id': None,
                    'allowed_surveys': []
                }
                st.rerun()

        if clear_button:
            st.session_state.add_user_form_data = {
                'username': '',
                'password': '',
                'role': 'employee',
                'governorate_id': None,
                'admin_id': None,
                'allowed_surveys': []
            }
            st.rerun()

async def edit_user_form(user_id):
    user = await db.d1.fetch_one('''
        SELECT username, role, assigned_region 
        FROM Users 
        WHERE user_id=?
    ''', (user_id,))
    
    if user is None:
        st.error("المستخدم غير موجود!")
        del st.session_state.editing_user
        return
        
    governorates = await db.get_governorates_list()
    surveys = await db.d1.fetch_all("SELECT survey_id, survey_name FROM Surveys")
    allowed_surveys = await db.d1.fetch_all('''
        SELECT survey_id FROM UserSurveys WHERE user_id=?
    ''', (user_id,))
    allowed_surveys = [s[0] for s in allowed_surveys]
    
    current_gov = None
    current_admin = user[2]
    if user[1] == 'governorate_admin':
        gov_info = await db.d1.fetch_one('''
            SELECT governorate_id FROM GovernorateAdmins 
            WHERE user_id=?
        ''', (user_id,))
        current_gov = gov_info[0] if gov_info else None
    
    with st.form(f"edit_user_{user_id}"):
        new_username = st.text_input("اسم المستخدم", value=user[0])
        new_role = st.selectbox(
            "الدور", 
            ["admin", "governorate_admin", "employee"],
            index=["admin", "governorate_admin", "employee"].index(user[1])
        )
        
        if new_role == "governorate_admin":
            selected_gov = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                index=[g[0] for g in governorates].index(current_gov) if current_gov else 0,
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                key=f"gov_edit_{user_id}"
            )
        elif new_role == "employee":
            selected_gov = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                index=[g[0] for g in governorates].index(current_gov) if current_gov else 0,
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                key=f"emp_gov_{user_id}"
            )
            
            health_admins = await db.d1.fetch_all(
                "SELECT admin_id, admin_name FROM HealthAdministrations WHERE governorate_id=?",
                (selected_gov,)
            )
            
            admin_options = [a[0] for a in health_admins]
            try:
                admin_index = admin_options.index(current_admin) if current_admin else 0
            except ValueError:
                admin_index = 0
            
            selected_admin = st.selectbox(
                "الإدارة الصحية",
                options=admin_options,
                index=admin_index,
                format_func=lambda x: next(a[1] for a in health_admins if a[0] == x),
                key=f"admin_edit_{user_id}"
            )
        
        if new_role != "admin" and surveys:
            selected_surveys = st.multiselect(
                "الاستبيانات المسموح بها",
                options=[s[0] for s in surveys],
                default=[s for s in allowed_surveys if s in [s[0] for s in surveys]],
                format_func=lambda x: next(s[1] for s in surveys if s[0] == x),
                key=f"surveys_edit_{user_id}"
            )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                if new_role == "governorate_admin":
                    await db.update_user(user_id, new_username, new_role)
                    await db.d1.execute("DELETE FROM GovernorateAdmins WHERE user_id=?", (user_id,))
                    await db.d1.execute(
                        "INSERT INTO GovernorateAdmins (user_id, governorate_id) VALUES (?, ?)",
                        (user_id, selected_gov)
                    )
                    if new_role != "admin":
                        await db.update_user_allowed_surveys(user_id, selected_surveys)
                else:
                    await db.update_user(user_id, new_username, new_role, selected_admin if new_role == "employee" else None)
                    if new_role != "admin":
                        await db.update_user_allowed_surveys(user_id, selected_surveys)
                del st.session_state.editing_user
                st.rerun()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_user
                st.rerun()

async def delete_user(user_id):
    try:
        has_responses = await db.d1.fetch_one("SELECT 1 FROM Responses WHERE user_id=?", (user_id,))
        if has_responses:
            st.error("لا يمكن حذف المستخدم لأنه لديه إجابات مسجلة!")
            return False
        
        await db.d1.execute("DELETE FROM Users WHERE user_id=?", (user_id,))
        st.success("تم حذف المستخدم بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ أثناء الحذف: {str(e)}")
        return False

async def manage_surveys():
    st.header("إدارة الاستبيانات")
    
    surveys = await db.d1.fetch_all("SELECT survey_id, survey_name, created_at, is_active FROM Surveys")
    
    for survey in surveys:
        col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
        with col1:
            st.write(f"**{survey[1]}** (تم الإنشاء في {survey[2]})")
        with col2:
            status = "نشط" if survey[3] else "غير نشط"
            st.write(f"الحالة: {status}")
        with col3:
            if st.button("تعديل", key=f"edit_survey_{survey[0]}"):
                st.session_state.editing_survey = survey[0]
        with col4:
            if st.button("حذف", key=f"delete_survey_{survey[0]}"):
                await db.delete_survey(survey[0])
                st.rerun()
    
    if 'editing_survey' in st.session_state:
        await edit_survey(st.session_state.editing_survey)
    
    with st.expander("إنشاء استبيان جديد"):
        await create_survey_form()

async def edit_survey(survey_id):
    survey = await db.d1.fetch_one("SELECT survey_name, is_active FROM Surveys WHERE survey_id=?", (survey_id,))
    fields = await db.get_survey_fields(survey_id)
    
    if 'new_survey_fields' not in st.session_state:
        st.session_state.new_survey_fields = []
    
    with st.form(f"edit_survey_{survey_id}"):
        st.subheader("تعديل الاستبيان")
        new_name = st.text_input("اسم الاستبيان", value=survey[0])
        is_active = st.checkbox("نشط", value=bool(survey[1]))
        
        st.subheader("الحقول الحالية")
        updated_fields = []
        for field in fields:
            field_id = field[0]
            with st.expander(f"حقل: {field[1]} (نوع: {field[2]})"):
                col1, col2 = st.columns(2)
                with col1:
                    new_label = st.text_input("تسمية الحقل", value=field[1], key=f"label_{field_id}")
                    new_type = st.selectbox(
                        "نوع الحقل",
                        ["text", "number", "dropdown", "checkbox", "date"],
                        index=["text", "number", "dropdown", "checkbox", "date"].index(field[2]),
                        key=f"type_{field_id}"
                    )
                with col2:
                    new_required = st.checkbox("مطلوب", value=bool(field[4]), key=f"required_{field_id}")
                    if new_type == 'dropdown':
                        options = "\n".join(json.loads(field[3])) if field[3] else ""
                        new_options = st.text_area(
                            "خيارات القائمة المنسدلة (سطر لكل خيار)",
                            value=options,
                            key=f"options_{field_id}"
                        )
                    else:
                        new_options = None
                
                updated_fields.append({
                    'field_id': field_id,
                    'field_label': new_label,
                    'field_type': new_type,
                    'field_options': [opt.strip() for opt in new_options.split('\n')] if new_options else None,
                    'is_required': new_required
                })
        
        st.subheader("إضافة حقول جديدة")
        for i, field in enumerate(st.session_state.new_survey_fields):
            st.markdown(f"#### الحقل الجديد {i+1}")
            col1, col2 = st.columns(2)
            with col1:
                field['field_label'] = st.text_input("تسمية الحقل", 
                                                   value=field.get('field_label', ''),
                                                   key=f"new_label_{i}")
                field['field_type'] = st.selectbox(
                    "نوع الحقل",
                    ["text", "number", "dropdown", "checkbox", "date"],
                    index=["text", "number", "dropdown", "checkbox", "date"].index(field.get('field_type', 'text')),
                    key=f"new_type_{i}"
                )
            with col2:
                field['is_required'] = st.checkbox("مطلوب", 
                                                 value=field.get('is_required', False),
                                                 key=f"new_required_{i}")
                if field['field_type'] == 'dropdown':
                    options = st.text_area(
                        "خيارات القائمة المنسدلة (سطر لكل خيار)",
                        value="\n".join(field.get('field_options', [])),
                        key=f"new_options_{i}"
                    )
                    field['field_options'] = [opt.strip() for opt in options.split('\n') if opt.strip()]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.form_submit_button("➕ إضافة حقل جديد"):
                st.session_state.new_survey_fields.append({
                    'field_label': '',
                    'field_type': 'text',
                    'is_required': False,
                    'field_options': []
                })
                st.rerun()
        with col2:
            if st.form_submit_button("🗑️ حذف آخر حقل") and st.session_state.new_survey_fields:
                st.session_state.new_survey_fields.pop()
                st.rerun()
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 حفظ التعديلات"):
                all_fields = updated_fields + st.session_state.new_survey_fields
                if await db.update_survey(survey_id, new_name, is_active, all_fields):
                    st.success("تم تحديث الاستبيان بنجاح")
                    st.session_state.new_survey_fields = []
                    del st.session_state.editing_survey
                    st.rerun()
        with col2:
            if st.form_submit_button("❌ إلغاء"):
                st.session_state.new_survey_fields = []
                del st.session_state.editing_survey
                st.rerun()

async def create_survey_form():
    if 'create_survey_fields' not in st.session_state:
        st.session_state.create_survey_fields = []
    
    governorates = await db.get_governorates_list()
    
    with st.form("create_survey_form"):
        survey_name = st.text_input("اسم الاستبيان")
        selected_governorates = st.multiselect(
            "المحافظات المسموحة",
            options=[g[0] for g in governorates],
            format_func=lambda x: next(g[1] for g in governorates if g[0] == x)
        )
        
        st.subheader("حقول الاستبيان")
        for i, field in enumerate(st.session_state.create_survey_fields):
            st.subheader(f"الحقل {i+1}")
            col1, col2 = st.columns(2)
            with col1:
                field['field_label'] = st.text_input("تسمية الحقل", value=field.get('field_label', ''), key=f"new_label_{i}")
                field['field_type'] = st.selectbox(
                    "نوع الحقل",
                    ["text", "number", "dropdown", "checkbox", "date"],
                    index=["text", "number", "dropdown", "checkbox", "date"].index(field.get('field_type', 'text')),
                    key=f"new_type_{i}"
                )
            with col2:
                field['is_required'] = st.checkbox("مطلوب", value=field.get('is_required', False), key=f"new_required_{i}")
                if field['field_type'] == 'dropdown':
                    options = st.text_area(
                        "خيارات القائمة المنسدلة (سطر لكل خيار)",
                        value="\n".join(field.get('field_options', [])),
                        key=f"new_options_{i}"
                    )
                    field['field_options'] = [opt.strip() for opt in options.split('\n') if opt.strip()]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.form_submit_button("إضافة حقل جديد"):
                st.session_state.create_survey_fields.append({
                    'field_label': '',
                    'field_type': 'text',
                    'is_required': False,
                    'field_options': []
                })
        with col2:
            if st.form_submit_button("حذف آخر حقل") and st.session_state.create_survey_fields:
                st.session_state.create_survey_fields.pop()
        with col3:
            if st.form_submit_button("حفظ الاستبيان") and survey_name:
                await db.save_survey(survey_name, st.session_state.create_survey_fields, selected_governorates)
                st.session_state.create_survey_fields = []
                st.rerun()

async def display_survey_data(survey_id):
    survey_name = await db.d1.fetch_one(
        "SELECT survey_name FROM Surveys WHERE survey_id = ?", 
        (survey_id,)
    )
    
    if not survey_name:
        st.error("الاستبيان المحدد غير موجود")
        return
        
    survey_name = survey_name[0]
    st.subheader(f"بيانات الاستبيان: {survey_name}")

    total_responses = await db.d1.fetch_one(
        "SELECT COUNT(*) FROM Responses WHERE survey_id = ?", 
        (survey_id,)
    )
    total_responses = total_responses[0] if total_responses else 0

    if total_responses == 0:
        st.info("لا توجد بيانات متاحة لهذا الاستبيان بعد")
        return

    responses = await db.d1.fetch_all('''
        SELECT r.response_id, u.username, h.admin_name, g.governorate_name,
               r.submission_date, r.is_completed
        FROM Responses r
        JOIN Users u ON r.user_id = u.user_id
        JOIN HealthAdministrations h ON r.region_id = h.admin_id
        JOIN Governorates g ON h.governorate_id = g.governorate_id
        WHERE r.survey_id = ?
        ORDER BY r.submission_date DESC
    ''', (survey_id,))

    completed_responses = sum(1 for r in responses if r[5])
    regions_count = len(set(r[2] for r in responses))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("إجمالي الإجابات", total_responses)
    with col2:
        st.metric("الإجابات المكتملة", completed_responses)
    with col3:
        st.metric("عدد المناطق", regions_count)

    df = pd.DataFrame(
        [(r[0], r[1], r[2], r[3], r[4], "مكتملة" if r[5] else "مسودة") for r in responses],
        columns=["ID", "المستخدم", "الإدارة الصحية", "المحافظة", "تاريخ التقديم", "الحالة"]
    )
    
    st.dataframe(df)
    
    if st.button("تصدير شامل لجميع البيانات إلى Excel", key=f"export_excel_{survey_id}"):
        import re
        from io import BytesIO
        
        filename = re.sub(r'[^\w\-_]', '_', survey_name) + "_كامل_" + datetime.now().strftime("%Y%m%d_%H%M") + ".xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='ملخص_الإجابات', index=False)
            
            all_details = []
            for response in responses:
                details = await db.d1.fetch_all('''
                    SELECT sf.field_label, rd.answer_value, 
                           u.username as entered_by, 
                           r.submission_date as entry_date,
                           r.is_completed
                    FROM Response_Details rd
                    JOIN Survey_Fields sf ON rd.field_id = sf.field_id
                    JOIN Responses r ON rd.response_id = r.response_id
                    JOIN Users u ON r.user_id = u.user_id
                    WHERE rd.response_id = ?
                    ORDER BY sf.field_order
                ''', (response[0],))
                
                for detail in details:
                    all_details.append({
                        "ID الإجابة": response[0],
                        "الحقل": detail[0],
                        "القيمة": detail[1],
                        "أدخلها": detail[2],
                        "تاريخ الإدخال": detail[3],
                        "حالة الإجابة": "مكتملة" if detail[4] else "مسودة"
                    })
            
            if all_details:
                details_df = pd.DataFrame(all_details)
                details_df.to_excel(writer, sheet_name='تفاصيل_الإجابات', index=False)
            
            fields = await db.d1.fetch_all('''
                SELECT field_label, field_type, field_options, is_required
                FROM Survey_Fields
                WHERE survey_id = ?
                ORDER BY field_order
            ''', (survey_id,))
            
            fields_df = pd.DataFrame(
                [(f[0], f[1], json.loads(f[2]) if f[2] else None, "نعم" if f[3] else "لا") for f in fields],
                columns=["اسم الحقل", "نوع الحقل", "الخيارات", "مطلوب"]
            )
            fields_df.to_excel(writer, sheet_name='حقول_الاستبيان', index=False)
            
            users_df = pd.DataFrame(
                [(r[1], r[2], r[3], r[4], "مكتملة" if r[5] else "مسودة") for r in responses],
                columns=["المستخدم", "الإدارة الصحية", "المحافظة", "تاريخ التقديم", "الحالة"]
            )
            users_df.drop_duplicates().to_excel(writer, sheet_name='المستخدمين', index=False)
   
        with open(filename, "rb") as f:
            st.download_button(
                label="تنزيل ملف Excel الكامل",
                data=f,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"download_excel_{survey_id}"
            )
        st.success("تم إنشاء ملف Excel الشامل بنجاح")

    selected_response_id = st.selectbox(
        "اختر إجابة لعرض وتعديل تفاصيلها",
        options=[r[0] for r in responses],
        format_func=lambda x: f"إجابة #{x}",
        key=f"select_response_{survey_id}"
    )

    if selected_response_id:
        response_info = await db.get_response_info(selected_response_id)
        if response_info:
            st.subheader(f"تفاصيل الإجابة #{selected_response_id}")
            st.markdown(f"""
            **الاستبيان:** {response_info[1]}  
            **المستخدم:** {response_info[2]}  
            **الإدارة الصحية:** {response_info[3]}  
            **المحافظة:** {response_info[4]}  
            **تاريخ التقديم:** {response_info[5]}
            """)
            
            details = await db.get_response_details(selected_response_id)
            updates = {}
            
            with st.form(key=f"edit_response_form_{selected_response_id}"):
                for detail in details:
                    detail_id, field_id, label, field_type, options, answer = detail
                    
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.markdown(f"**{label}**")
                    with col2:
                        if field_type == 'dropdown':
                            options_list = json.loads(options) if options else []
                            new_value = st.selectbox(
                                label,
                                options_list,
                                index=options_list.index(answer) if answer in options_list else 0,
                                key=f"dropdown_{detail_id}_{selected_response_id}"
                            )
                        else:
                            new_value = st.text_input(
                                label,
                                value=answer,
                                key=f"input_{detail_id}_{selected_response_id}"
                            )
                        
                        if new_value != answer:
                            updates[detail_id] = new_value
                
                col1, col2 = st.columns(2)
                with col1:
                    save_clicked = st.form_submit_button("💾 حفظ جميع التعديلات")
                    if save_clicked:
                        if updates:
                            success_count = 0
                            for detail_id, new_value in updates.items():
                                if await db.update_response_detail(detail_id, new_value):
                                    success_count += 1
                            
                            if success_count == len(updates):
                                st.success("تم تحديث جميع التعديلات بنجاح")
                            else:
                                st.error(f"تم تحديث {success_count} من أصل {len(updates)} تعديلات")
                            st.rerun()
                        else:
                            st.info("لم تقم بإجراء أي تعديلات")
                with col2:
                    cancel_clicked = st.form_submit_button("❌ إلغاء التعديلات")
                    if cancel_clicked:
                        st.rerun()

async def view_data():
    st.header("عرض البيانات المجمعة")
    
    surveys = await db.d1.fetch_all(
        "SELECT survey_id, survey_name FROM Surveys ORDER BY survey_name"
    )
    
    if not surveys:
        st.warning("لا توجد استبيانات متاحة")
        return
        
    selected_survey = st.selectbox(
        "اختر استبيان",
        surveys,
        format_func=lambda x: x[1],
        key="survey_select"
    )
    
    if selected_survey:
        await display_survey_data(selected_survey[0])

async def manage_governorates():
    st.header("إدارة المحافظات")
    governorates = await db.d1.fetch_all("SELECT governorate_id, governorate_name, description FROM Governorates")
    
    for gov in governorates:
        col1, col2, col3, col4 = st.columns([4, 3, 1, 1])
        with col1:
            st.write(f"**{gov[1]}**")
        with col2:
            st.write(gov[2] if gov[2] else "لا يوجد وصف")
        with col3:
            if st.button("تعديل", key=f"edit_gov_{gov[0]}"):
                st.session_state.editing_gov = gov[0]
        with col4:
            if st.button("حذف", key=f"delete_gov_{gov[0]}"):
                await delete_governorate(gov[0])
                st.rerun()
    
    if 'editing_gov' in st.session_state:
        await edit_governorate(st.session_state.editing_gov)
    
    with st.expander("إضافة محافظة جديدة"):
        with st.form("add_governorate_form"):
            governorate_name = st.text_input("اسم المحافظة")
            description = st.text_area("الوصف")
            
            submitted = st.form_submit_button("حفظ")
            
            if submitted:
                if governorate_name:
                    existing = await db.d1.fetch_one("SELECT 1 FROM Governorates WHERE governorate_name=?", 
                                                  (governorate_name,))
                    if existing:
                        st.error("هذه المحافظة موجودة بالفعل!")
                    else:
                        await db.d1.execute(
                            "INSERT INTO Governorates (governorate_name, description) VALUES (?, ?)",
                            (governorate_name, description)
                        )
                        st.success("تمت إضافة المحافظة بنجاح")
                        st.rerun()
                else:
                    st.warning("يرجى إدخال اسم المحافظة")

async def edit_governorate(gov_id):
    gov = await db.d1.fetch_one("SELECT governorate_name, description FROM Governorates WHERE governorate_id=?", 
                              (gov_id,))
    
    with st.form(f"edit_gov_{gov_id}"):
        new_name = st.text_input("اسم المحافظة", value=gov[0])
        new_desc = st.text_area("الوصف", value=gov[1] if gov[1] else "")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                existing = await db.d1.fetch_one("SELECT 1 FROM Governorates WHERE governorate_name=? AND governorate_id!=?", 
                                              (new_name, gov_id))
                if existing:
                    st.error("هذا الاسم مستخدم بالفعل لمحافظة أخرى!")
                else:
                    await db.d1.execute(
                        "UPDATE Governorates SET governorate_name=?, description=? WHERE governorate_id=?",
                        (new_name, new_desc, gov_id)
                    )
                    st.success("تم تحديث المحافظة بنجاح")
                    del st.session_state.editing_gov
                    st.rerun()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_gov
                st.rerun()

async def delete_governorate(gov_id):
    try:
        has_regions = await db.d1.fetch_one("SELECT 1 FROM HealthAdministrations WHERE governorate_id=?", 
                                         (gov_id,))
        if has_regions:
            st.error("لا يمكن حذف المحافظة لأنها تحتوي على إدارات صحية!")
            return False
        
        await db.d1.execute("DELETE FROM Governorates WHERE governorate_id=?", (gov_id,))
        st.success("تم حذف المحافظة بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ أثناء الحذف: {str(e)}")
        return False

async def manage_regions():
    st.header("إدارة الإدارات الصحية")
    
    regions = await db.d1.fetch_all('''
        SELECT h.admin_id, h.admin_name, h.description, g.governorate_name 
        FROM HealthAdministrations h
        JOIN Governorates g ON h.governorate_id = g.governorate_id
    ''')
    
    for reg in regions:
        col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
        with col1:
            st.write(f"**{reg[1]}**")
        with col2:
            st.write(reg[2] if reg[2] else "لا يوجد وصف")
        with col3:
            st.write(reg[3])
        with col4:
            if st.button("تعديل", key=f"edit_reg_{reg[0]}"):
                st.session_state.editing_reg = reg[0]
        with col5:
            if st.button("حذف", key=f"delete_reg_{reg[0]}"):
                await delete_health_admin(reg[0])
                st.rerun()
    
    if 'editing_reg' in st.session_state:
        await edit_health_admin(st.session_state.editing_reg)
    
    with st.expander("إضافة إدارة صحية جديدة"):
        governorates = await db.get_governorates_list()
        
        if not governorates:
            st.warning("لا توجد محافظات متاحة. يرجى إضافة محافظة أولاً.")
            return
            
        with st.form("add_health_admin_form"):
            admin_name = st.text_input("اسم الإدارة الصحية")
            description = st.text_area("الوصف")
            governorate_id = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x))
            
            submitted = st.form_submit_button("حفظ")
            
            if submitted:
                if admin_name:
                    existing = await db.d1.fetch_one('''
                        SELECT 1 FROM HealthAdministrations 
                        WHERE admin_name=? AND governorate_id=?
                    ''', (admin_name, governorate_id))
                    
                    if existing:
                        st.error("هذه الإدارة الصحية موجودة بالفعل في هذه المحافظة!")
                    else:
                        await db.d1.execute(
                            "INSERT INTO HealthAdministrations (admin_name, description, governorate_id) VALUES (?, ?, ?)",
                            (admin_name, description, governorate_id)
                        )
                        st.success("تمت إضافة الإدارة الصحية بنجاح")
                        st.rerun()
                else:
                    st.warning("يرجى إدخال اسم الإدارة الصحية")

async def edit_health_admin(admin_id):
    admin = await db.d1.fetch_one('''
        SELECT h.admin_name, h.description, h.governorate_id, g.governorate_name
        FROM HealthAdministrations h
        JOIN Governorates g ON h.governorate_id = g.governorate_id
        WHERE h.admin_id=?
    ''', (admin_id,))
    
    if admin is None:
        st.error("الإدارة الصحية المطلوبة غير موجودة!")
        del st.session_state.editing_reg
        return
    
    governorates = await db.get_governorates_list()
    
    with st.form(f"edit_admin_{admin_id}"):
        new_name = st.text_input("اسم الإدارة الصحية", value=admin[0])
        new_desc = st.text_area("الوصف", value=admin[1] if admin[1] else "")
        new_gov = st.selectbox(
            "المحافظة",
            options=[g[0] for g in governorates],
            index=[g[0] for g in governorates].index(admin[2]),
            format_func=lambda x: next(g[1] for g in governorates if g[0] == x))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                existing = await db.d1.fetch_one('''
                    SELECT 1 FROM HealthAdministrations 
                    WHERE admin_name=? AND governorate_id=? AND admin_id!=?
                ''', (new_name, new_gov, admin_id))
                
                if existing:
                    st.error("هذا الاسم مستخدم بالفعل لإدارة صحية أخرى في هذه المحافظة!")
                else:
                    await db.d1.execute(
                        "UPDATE HealthAdministrations SET admin_name=?, description=?, governorate_id=? WHERE admin_id=?",
                        (new_name, new_desc, new_gov, admin_id)
                    )
                    st.success("تم تحديث الإدارة الصحية بنجاح")
                    del st.session_state.editing_reg
                    st.rerun()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_reg
                st.rerun()

async def delete_health_admin(admin_id):
    try:
        has_users = await db.d1.fetch_one("SELECT 1 FROM Users WHERE assigned_region=?", 
                                       (admin_id,))
        if has_users:
            st.error("لا يمكن حذف الإدارة الصحية لأنها مرتبطة بمستخدمين!")
            return False
        
        await db.d1.execute("DELETE FROM HealthAdministrations WHERE admin_id=?", (admin_id,))
        st.success("تم حذف الإدارة الصحية بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ أثناء الحذف: {str(e)}")
        return False