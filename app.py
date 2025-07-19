import asyncio
import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

async def main():
    st.set_page_config(page_title="نظام إدارة الاستبيانات", page_icon="📋", layout="wide")
    
    from auth import authenticate, logout
    from database import db, get_user_role
    from admin_views import show_admin_dashboard
    from employee_views import show_employee_dashboard
    from governorate_admin_views import show_governorate_admin_dashboard
    
    # تهيئة قاعدة البيانات
    await db.init_db()
    
    # التحقق من حالة الجلسة
    if await authenticate():
        st.session_state.last_activity = datetime.now()
        user_role = await get_user_role(st.session_state.user_id)
        
        st.sidebar.button("تسجيل الخروج", on_click=logout)
        
        if user_role == 'admin':
            await show_admin_dashboard()
        elif user_role == 'governorate_admin':
            await show_governorate_admin_dashboard()
        else:
            await show_employee_dashboard()

if __name__ == "__main__":
    asyncio.run(main())
