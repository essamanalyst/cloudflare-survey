import streamlit as st
import json
from typing import Optional, List, Tuple, Dict
from datetime import datetime
from pathlib import Path
import os
from cloudflare import CloudflareD1

class Database:
    def __init__(self):
        self.d1 = CloudflareD1(
    account_id=os.getenv('CF_ACCOUNT_ID'),
    api_token=os.getenv('CF_API_TOKEN'),
    database_id=os.getenv('CF_D1_DATABASE_ID')
)
    
    async def init_db(self):
        """تهيئة الجداول في قاعدة البيانات"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS Users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                assigned_region INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                FOREIGN KEY(assigned_region) REFERENCES Regions(region_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS Governorates (
                governorate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                governorate_name TEXT NOT NULL UNIQUE,
                description TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS HealthAdministrations (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_name TEXT NOT NULL,
                description TEXT,
                governorate_id INTEGER NOT NULL,
                FOREIGN KEY(governorate_id) REFERENCES Governorates(governorate_id),
                UNIQUE(admin_name, governorate_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS Surveys (
                survey_id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_name TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY(created_by) REFERENCES Users(user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS Survey_Fields (
                field_id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_id INTEGER NOT NULL,
                field_type TEXT NOT NULL,
                field_label TEXT NOT NULL,
                field_options TEXT,
                is_required BOOLEAN DEFAULT FALSE,
                field_order INTEGER NOT NULL,
                FOREIGN KEY(survey_id) REFERENCES Surveys(survey_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS Responses (
                response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                region_id INTEGER NOT NULL,
                submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_completed BOOLEAN DEFAULT FALSE,
                FOREIGN KEY(survey_id) REFERENCES Surveys(survey_id),
                FOREIGN KEY(user_id) REFERENCES Users(user_id),
                FOREIGN KEY(region_id) REFERENCES Regions(region_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS Response_Details (
                detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id INTEGER NOT NULL,
                field_id INTEGER NOT NULL,
                answer_value TEXT,
                FOREIGN KEY(response_id) REFERENCES Responses(response_id),
                FOREIGN KEY(field_id) REFERENCES Survey_Fields(field_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS GovernorateAdmins (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                governorate_id INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES Users(user_id),
                FOREIGN KEY(governorate_id) REFERENCES Governorates(governorate_id),
                UNIQUE(user_id, governorate_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS UserSurveys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                survey_id INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES Users(user_id),
                FOREIGN KEY(survey_id) REFERENCES Surveys(survey_id),
                UNIQUE(user_id, survey_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS SurveyGovernorate (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_id INTEGER NOT NULL,
                governorate_id INTEGER NOT NULL,
                FOREIGN KEY(survey_id) REFERENCES Surveys(survey_id),
                FOREIGN KEY(governorate_id) REFERENCES Governorates(governorate_id),
                UNIQUE(survey_id, governorate_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS AuditLog (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                table_name TEXT NOT NULL,
                record_id INTEGER,
                old_value TEXT,
                new_value TEXT,
                action_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES Users(user_id)
            )
            """
        ]

        for table in tables:
            await self.d1.execute(table)
        
        # إضافة مستخدم admin افتراضي إذا لم يكن موجوداً
        admin_count = await self.d1.fetch_one(
            "SELECT COUNT(*) FROM Users WHERE role='admin'"
        )
        if admin_count[0] == 0:
            from auth import hash_password
            admin_password = hash_password("admin123")
            await self.d1.execute(
                "INSERT INTO Users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", admin_password, "admin")
            )

    async def get_user_by_username(self, username):
        """الحصول على بيانات المستخدم باستخدام اسم المستخدم"""
        user = await self.d1.fetch_one(
            "SELECT * FROM Users WHERE username=?", (username,)
        )
        
        if user:
            return {
                'user_id': user[0],
                'username': user[1],
                'password_hash': user[2],
                'role': user[3],
                'assigned_region': user[4],
                'created_at': user[5],
                'last_login': user[6]
            }
        return None

    async def get_user_role(self, user_id):
        """الحصول على دور المستخدم"""
        role = await self.d1.fetch_one(
            "SELECT role FROM Users WHERE user_id=?", (user_id,)
        )
        return role[0] if role else None

    async def get_health_admins(self):
        """استرجاع جميع الإدارات الصحية من قاعدة البيانات"""
        return await self.d1.fetch_all(
            "SELECT admin_id, admin_name FROM HealthAdministrations"
        )

    async def get_health_admin_name(self, admin_id):
        """استرجاع اسم الإدارة الصحية بناءً على المعرف"""
        if admin_id is None:
            return "غير معين"
        
        try:
            result = await self.d1.fetch_one(
                "SELECT admin_name FROM HealthAdministrations WHERE admin_id=?", (admin_id,)
            )
            return result[0] if result else "غير معروف"
        except Exception as e:
            print(f"خطأ في جلب اسم الإدارة الصحية: {e}")
            return "خطأ في النظام"

    async def save_response(self, survey_id, user_id, region_id, is_completed=False):
        """حفظ استجابة جديدة في قاعدة البيانات"""
        try:
            result = await self.d1.execute(
                """INSERT INTO Responses 
                   (survey_id, user_id, region_id, is_completed) 
                   VALUES (?, ?, ?, ?)""",
                (survey_id, user_id, region_id, is_completed)
            )
            return result.lastrowid
        except Exception as e:
            st.error(f"حدث خطأ في حفظ الاستجابة: {str(e)}")
            return None

    async def save_response_detail(self, response_id, field_id, answer_value):
        """حفظ تفاصيل الإجابة"""
        try:
            await self.d1.execute(
                """INSERT INTO Response_Details 
                   (response_id, field_id, answer_value) 
                   VALUES (?, ?, ?)""",
                (response_id, field_id, str(answer_value) if answer_value is not None else ""))
            return True
        except Exception as e:
            st.error(f"حدث خطأ في حفظ تفاصيل الإجابة: {str(e)}")
            return False

    async def save_survey(self, survey_name, fields, governorate_ids=None):
        """حفظ استبيان جديد مع حقوله في قاعدة البيانات"""
        try:
            # 1. حفظ الاستبيان الأساسي
            result = await self.d1.execute(
                "INSERT INTO Surveys (survey_name, created_by) VALUES (?, ?)",
                (survey_name, st.session_state.user_id)
            )
            survey_id = result.lastrowid
            
            # 2. ربط الاستبيان بالمحافظات
            if governorate_ids:
                for gov_id in governorate_ids:
                    await self.d1.execute(
                        "INSERT INTO SurveyGovernorate (survey_id, governorate_id) VALUES (?, ?)",
                        (survey_id, gov_id)
                    )
            
            # 3. حفظ حقول الاستبيان
            for i, field in enumerate(fields):
                field_options = json.dumps(field.get('field_options', [])) if field.get('field_options') else None
                
                await self.d1.execute(
                    """INSERT INTO Survey_Fields 
                       (survey_id, field_type, field_label, field_options, is_required, field_order) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (survey_id, 
                     field['field_type'], 
                     field['field_label'],
                     field_options,
                     field.get('is_required', False),
                     i + 1)
                )
            
            return True
        except Exception as e:
            st.error(f"حدث خطأ في حفظ الاستبيان: {str(e)}")
            return False

    async def update_last_login(self, user_id):
        """تحديث وقت آخر دخول للمستخدم"""
        await self.d1.execute(
            "UPDATE Users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?", 
            (user_id,)
        )

    async def update_user_activity(self, user_id):
        """تحديث وقت النشاط الأخير للمستخدم"""
        await self.d1.execute(
            "UPDATE Users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?", 
            (user_id,)
        )

    async def delete_survey(self, survey_id):
        """حذف استبيان وجميع بياناته المرتبطة"""
        try:
            # حذف تفاصيل الإجابات المرتبطة
            await self.d1.execute(
                """DELETE FROM Response_Details 
                   WHERE response_id IN (
                       SELECT response_id FROM Responses WHERE survey_id = ?
                   )""", (survey_id,))
            
            # حذف الإجابات المرتبطة
            await self.d1.execute(
                "DELETE FROM Responses WHERE survey_id = ?", (survey_id,))
            
            # حذف حقول الاستبيان
            await self.d1.execute(
                "DELETE FROM Survey_Fields WHERE survey_id = ?", (survey_id,))
            
            # حذف الاستبيان نفسه
            await self.d1.execute(
                "DELETE FROM Surveys WHERE survey_id = ?", (survey_id,))
            
            st.success("تم حذف الاستبيان بنجاح")
            return True
        except Exception as e:
            st.error(f"حدث خطأ أثناء حذف الاستبيان: {str(e)}")
            return False

    async def add_health_admin(self, admin_name, description, governorate_id):
        """إضافة إدارة صحية جديدة إلى قاعدة البيانات مع التحقق من التكرار"""
        try:
            # التحقق من وجود الإدارة مسبقاً في نفس المحافظة
            existing = await self.d1.fetch_one(
                "SELECT 1 FROM HealthAdministrations WHERE admin_name=? AND governorate_id=?", 
                (admin_name, governorate_id))
            
            if existing:
                st.error("هذه الإدارة الصحية موجودة بالفعل في هذه المحافظة!")
                return False
            
            # إضافة الإدارة الجديدة
            await self.d1.execute(
                "INSERT INTO HealthAdministrations (admin_name, description, governorate_id) VALUES (?, ?, ?)",
                (admin_name, description, governorate_id)
            )
            
            st.success(f"تمت إضافة الإدارة الصحية '{admin_name}' بنجاح")
            return True
        except Exception as e:
            st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
            return False

    async def get_governorates_list(self):
        """استرجاع قائمة المحافظات للاستخدام في القوائم المنسدلة"""
        return await self.d1.fetch_all(
            "SELECT governorate_id, governorate_name FROM Governorates"
        )

    async def update_survey(self, survey_id, survey_name, is_active, fields):
        """تحديث بيانات الاستبيان وحقوله"""
        try:
            # 1. تحديث بيانات الاستبيان الأساسية
            await self.d1.execute(
                "UPDATE Surveys SET survey_name=?, is_active=? WHERE survey_id=?",
                (survey_name, is_active, survey_id)
            )
            
            # 2. تحديث الحقول الموجودة أو إضافة جديدة
            for field in fields:
                field_options = json.dumps(field.get('field_options', [])) if field.get('field_options') else None
                
                if 'field_id' in field:  # حقل موجود يتم تحديثه
                    await self.d1.execute(
                        """UPDATE Survey_Fields 
                           SET field_label=?, field_type=?, field_options=?, is_required=?
                           WHERE field_id=?""",
                        (field['field_label'], 
                         field['field_type'],
                         field_options,
                         field.get('is_required', False),
                         field['field_id'])
                    )
                else:  # حقل جديد يتم إضافته
                    max_order = await self.d1.fetch_one(
                        "SELECT MAX(field_order) FROM Survey_Fields WHERE survey_id=?", (survey_id,))
                    max_order = max_order[0] or 0
                    
                    await self.d1.execute(
                        """INSERT INTO Survey_Fields 
                           (survey_id, field_label, field_type, field_options, is_required, field_order) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (survey_id,
                         field['field_label'],
                         field['field_type'],
                         field_options,
                         field.get('is_required', False),
                         max_order + 1)
                    )
            
            st.success("تم تحديث الاستبيان بنجاح")
            return True
        except Exception as e:
            st.error(f"حدث خطأ في تحديث الاستبيان: {str(e)}")
            return False

    async def update_user(self, user_id, username, role, region_id=None):
        """تحديث بيانات المستخدم"""
        try:
            # الحصول على القيم القديمة أولاً
            old_data = await self.d1.fetch_one(
                "SELECT username, role, assigned_region FROM Users WHERE user_id=?", (user_id,))
            
            # التحقق من عدم تكرار اسم المستخدم
            existing = await self.d1.fetch_one(
                "SELECT 1 FROM Users WHERE username=? AND user_id!=?", (username, user_id))
            
            if existing:
                st.error("اسم المستخدم موجود بالفعل!")
                return False
            
            # تحديث بيانات المستخدم
            await self.d1.execute(
                "UPDATE Users SET username=?, role=?, assigned_region=? WHERE user_id=?",
                (username, role, region_id, user_id)
            )
            
            if role == 'governorate_admin':
                await self.d1.execute(
                    "DELETE FROM GovernorateAdmins WHERE user_id=?", (user_id,))
            
            # تسجيل التعديل في سجل التعديلات
            new_data = (username, role, region_id)
            changes = {
                'username': {'old': old_data[0], 'new': new_data[0]},
                'role': {'old': old_data[1], 'new': new_data[1]},
                'assigned_region': {'old': old_data[2], 'new': new_data[2]}
            }
            
            await self.log_audit_action(
                st.session_state.user_id, 
                'UPDATE', 
                'Users', 
                user_id,
                old_data,
                new_data
            )
            
            st.success("تم تحديث بيانات المستخدم بنجاح")
            return True
        except Exception as e:
            st.error(f"حدث خطأ في تحديث المستخدم: {str(e)}")
            return False

    async def add_user(self, username, password, role, region_id=None):
        """إضافة مستخدم جديد إلى قاعدة البيانات"""
        from auth import hash_password
        
        try:
            # التحقق من عدم تكرار اسم المستخدم
            existing = await self.d1.fetch_one(
                "SELECT 1 FROM Users WHERE username=?", (username,))
            
            if existing:
                st.error("اسم المستخدم موجود بالفعل!")
                return False
            
            # إضافة المستخدم الجديد
            await self.d1.execute(
                "INSERT INTO Users (username, password_hash, role, assigned_region) VALUES (?, ?, ?, ?)",
                (username, hash_password(password), role, region_id)
            )
            
            st.success("تمت إضافة المستخدم بنجاح")
            return True
        except Exception as e:
            st.error(f"حدث خطأ في إضافة المستخدم: {str(e)}")
            return False

    async def get_governorate_admin(self, user_id):
        """الحصول على بيانات مسؤول المحافظة"""
        return await self.d1.fetch_all(
            """SELECT g.governorate_id, g.governorate_name 
               FROM GovernorateAdmins ga
               JOIN Governorates g ON ga.governorate_id = g.governorate_id
               WHERE ga.user_id = ?""", (user_id,)
        )

    async def add_governorate_admin(self, user_id, governorate_id):
        """إضافة مسؤول محافظة جديد"""
        try:
            await self.d1.execute(
                "INSERT INTO GovernorateAdmins (user_id, governorate_id) VALUES (?, ?)",
                (user_id, governorate_id)
            )
            return True
        except Exception as e:
            st.error(f"خطأ في إضافة مسؤول المحافظة: {str(e)}")
            return False

    async def get_governorate_admin_data(self, user_id):
        """الحصول على بيانات مسؤول المحافظة"""
        try:
            return await self.d1.fetch_one(
                """SELECT g.governorate_id, g.governorate_name, g.description 
                   FROM GovernorateAdmins ga
                   JOIN Governorates g ON ga.governorate_id = g.governorate_id
                   WHERE ga.user_id = ?""", (user_id,))
        except Exception as e:
            st.error(f"خطأ في جلب بيانات المحافظة: {str(e)}")
            return None

    async def get_governorate_surveys(self, governorate_id):
        """الحصول على الاستبيانات الخاصة بمحافظة معينة"""
        return await self.d1.fetch_all(
            """SELECT s.survey_id, s.survey_name, s.created_at, s.is_active
               FROM Surveys s
               JOIN SurveyGovernorate sg ON s.survey_id = sg.survey_id
               WHERE sg.governorate_id = ?
               ORDER BY s.created_at DESC""", (governorate_id,))
    
    async def get_governorate_employees(self, governorate_id):
        """الحصول على الموظفين التابعين لمحافظة معينة"""
        return await self.d1.fetch_all(
            """SELECT u.user_id, u.username, ha.admin_name
               FROM Users u
               JOIN HealthAdministrations ha ON u.assigned_region = ha.admin_id
               WHERE ha.governorate_id = ? AND u.role = 'employee'
               ORDER BY u.username""", (governorate_id,))
    
    async def get_allowed_surveys(self, user_id):
        """الحصول على الاستبيانات المسموح بها للموظف"""
        try:
            # الحصول على المحافظة التابعة للمستخدم
            governorate_id = await self.d1.fetch_one(
                """SELECT ha.governorate_id 
                   FROM Users u
                   JOIN HealthAdministrations ha ON u.assigned_region = ha.admin_id
                   WHERE u.user_id = ?""", (user_id,))
            
            if not governorate_id:
                return []
                
            # الحصول على الاستبيانات المسموحة للمحافظة
            return await self.d1.fetch_all(
                """SELECT s.survey_id, s.survey_name
                   FROM Surveys s
                   JOIN SurveyGovernorate sg ON s.survey_id = sg.survey_id
                   WHERE sg.governorate_id = ?
                   ORDER BY s.survey_name""", (governorate_id[0],))
        except Exception as e:
            st.error(f"حدث خطأ في جلب الاستبيانات المسموح بها: {str(e)}")
            return []

    async def get_survey_fields(self, survey_id):
        """الحصول على حقول استبيان معين"""
        try:
            return await self.d1.fetch_all(
                """SELECT 
                       field_id, 
                       field_label, 
                       field_type, 
                       field_options, 
                       is_required, 
                       field_order
                   FROM Survey_Fields
                   WHERE survey_id = ?
                   ORDER BY field_order""", (survey_id,))
        except Exception as e:
            st.error(f"حدث خطأ في جلب حقول الاستبيان: {str(e)}")
            return []

    async def get_user_allowed_surveys(self, user_id):
        """الحصول على الاستبيانات المسموح بها للمستخدم"""
        try:
            return await self.d1.fetch_all(
                """SELECT s.survey_id, s.survey_name 
                   FROM Surveys s
                   JOIN UserSurveys us ON s.survey_id = us.survey_id
                   WHERE us.user_id = ?
                   ORDER BY s.survey_name""", (user_id,))
        except Exception as e:
            st.error(f"حدث خطأ في جلب الاستبيانات المسموح بها: {str(e)}")
            return []

    async def update_user_allowed_surveys(self, user_id, survey_ids):
        """تحديث الاستبيانات المسموح بها للمستخدم"""
        try:
            # الحصول على محافظة المستخدم
            governorate_id = await self.d1.fetch_one(
                """SELECT ha.governorate_id 
                   FROM Users u
                   JOIN HealthAdministrations ha ON u.assigned_region = ha.admin_id
                   WHERE u.user_id = ?""", (user_id,))
            
            if not governorate_id:
                st.error("المستخدم غير مرتبط بمحافظة")
                return False
            
            # التحقق من أن الاستبيانات مسموحة للمحافظة
            valid_surveys = []
            for survey_id in survey_ids:
                existing = await self.d1.fetch_one(
                    """SELECT 1 FROM SurveyGovernorate 
                       WHERE survey_id = ? AND governorate_id = ?""",
                    (survey_id, governorate_id[0]))
                
                if existing:
                    valid_surveys.append(survey_id)
            
            # حذف جميع التصاريح الحالية
            await self.d1.execute(
                "DELETE FROM UserSurveys WHERE user_id=?", (user_id,))
            
            # إضافة التصاريح الجديدة
            for survey_id in valid_surveys:
                await self.d1.execute(
                    "INSERT INTO UserSurveys (user_id, survey_id) VALUES (?, ?)",
                    (user_id, survey_id))
            
            return True
        except Exception as e:
            st.error(f"حدث خطأ في تحديث الاستبيانات المسموح بها: {str(e)}")
            return False

    async def get_response_details(self, response_id):
        """الحصول على تفاصيل إجابة محددة"""
        try:
            return await self.d1.fetch_all(
                """SELECT rd.detail_id, rd.field_id, sf.field_label, 
                      sf.field_type, sf.field_options, rd.answer_value
                   FROM Response_Details rd
                   JOIN Survey_Fields sf ON rd.field_id = sf.field_id
                   WHERE rd.response_id = ?
                   ORDER BY sf.field_order""", (response_id,))
        except Exception as e:
            st.error(f"حدث خطأ في جلب تفاصيل الإجابة: {str(e)}")
            return []

    async def update_response_detail(self, detail_id, new_value):
        """تحديث قيمة إجابة محددة"""
        try:
            await self.d1.execute(
                "UPDATE Response_Details SET answer_value = ? WHERE detail_id = ?",
                (new_value, detail_id)
            )
            return True
        except Exception as e:
            st.error(f"حدث خطأ في تحديث الإجابة: {str(e)}")
            return False

    async def get_response_info(self, response_id):
        """الحصول على معلومات أساسية عن الإجابة"""
        try:
            return await self.d1.fetch_one(
                """SELECT r.response_id, s.survey_name, u.username, 
                      ha.admin_name, g.governorate_name, r.submission_date
                   FROM Responses r
                   JOIN Surveys s ON r.survey_id = s.survey_id
                   JOIN Users u ON r.user_id = u.user_id
                   JOIN HealthAdministrations ha ON r.region_id = ha.admin_id
                   JOIN Governorates g ON ha.governorate_id = g.governorate_id
                   WHERE r.response_id = ?""", (response_id,))
        except Exception as e:
            st.error(f"حدث خطأ في جلب معلومات الإجابة: {str(e)}")
            return None

    async def log_audit_action(self, user_id, action_type, table_name, record_id=None, old_value=None, new_value=None):
        """تسجيل إجراء في سجل التعديلات"""
        try:
            await self.d1.execute(
                """INSERT INTO AuditLog 
                   (user_id, action_type, table_name, record_id, old_value, new_value)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, action_type, table_name, record_id, 
                 json.dumps(old_value) if old_value else None,
                 json.dumps(new_value) if new_value else None)
            )
            return True
        except Exception as e:
            st.error(f"حدث خطأ في تسجيل الإجراء: {str(e)}")
            return False

    async def get_audit_logs(self, table_name=None, action_type=None, username=None, date_range=None, search_query=None):
        """الحصول على سجل التعديلات مع فلاتر متقدمة"""
        try:
            query = """
                SELECT a.log_id, u.username, a.action_type, a.table_name, 
                       a.record_id, a.old_value, a.new_value, a.action_timestamp
                FROM AuditLog a
                JOIN Users u ON a.user_id = u.user_id
            """
            params = []
            conditions = []
            
            # تطبيق الفلاتر
            if table_name:
                conditions.append("a.table_name = ?")
                params.append(table_name)
            if action_type:
                conditions.append("a.action_type = ?")
                params.append(action_type)
            if username:
                conditions.append("u.username LIKE ?")
                params.append(f"%{username}%")
            if date_range and len(date_range) == 2:
                start_date, end_date = date_range
                conditions.append("DATE(a.action_timestamp) BETWEEN ? AND ?")
                params.extend([start_date, end_date])
            if search_query:
                conditions.append("""
                    (a.old_value LIKE ? OR 
                     a.new_value LIKE ? OR 
                     u.username LIKE ? OR 
                     a.table_name LIKE ? OR
                     a.action_type LIKE ?)
                """)
                search_term = f"%{search_query}%"
                params.extend([search_term, search_term, search_term, search_term, search_term])
            
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
                
            query += ' ORDER BY a.action_timestamp DESC'
            
            return await self.d1.fetch_all(query, params)
        except Exception as e:
            st.error(f"حدث خطأ في جلب سجل التعديلات: {str(e)}")
            return []

    async def has_completed_survey_today(self, user_id, survey_id):
        """التحقق مما إذا كان المستخدم قد أكمل الاستبيان اليوم"""
        try:
            result = await self.d1.fetch_one(
                """SELECT 1 FROM Responses 
                   WHERE user_id = ? AND survey_id = ? AND is_completed = TRUE
                   AND DATE(submission_date) = DATE('now')
                   LIMIT 1""", (user_id, survey_id))
            return result is not None
        except Exception as e:
            st.error(f"حدث خطأ في التحقق من إكمال الاستبيان: {str(e)}")
            return False
    async def get_user_role(self, user_id):

        role = await self.d1.fetch_one(
            "SELECT role FROM Users WHERE user_id=?", (user_id,)
        )
        return role[0] if role else None
# إنشاء نسخة واحدة من قاعدة البيانات لتستخدمها التطبيق
db = Database()
