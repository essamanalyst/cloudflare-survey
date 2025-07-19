import streamlit as st
from datetime import datetime, timedelta 
from auth import authenticate, logout
from admin_views import show_admin_dashboard
from employee_views import show_employee_dashboard
from database import db, get_user_role
from governorate_admin_views import show_governorate_admin_dashboard

async def main():
    st.set_page_config(page_title="نظام إدارة الاستبيانات", page_icon="📋", layout="wide")
    
    # تهيئة قاعدة البيانات
    await db.init_db()
    
    # التحقق من حالة الجلسة
    if await authenticate():  # إذا كان مسجل الدخول
        # تحديث وقت النشاط عند كل تفاعل
        st.session_state.last_activity = datetime.now()
        
        # عرض واجهة المستخدم حسب الدور
        user_role = await get_user_role(st.session_state.user_id)
        
        # زر تسجيل الخروج
        st.sidebar.button("تسجيل الخروج", on_click=logout)
        
        if user_role == 'admin':
            await show_admin_dashboard()
        elif user_role == 'governorate_admin':
            await show_governorate_admin_dashboard()
        else:
            await show_employee_dashboard()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())