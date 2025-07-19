import streamlit as st
import hashlib
from datetime import datetime, timedelta
from database import db

async def authenticate():
    if 'authenticated' in st.session_state and st.session_state.authenticated:
        if 'last_activity' in st.session_state:
            if (datetime.now() - st.session_state.last_activity) < timedelta(hours=1):
                st.session_state.last_activity = datetime.now()
                return True
            else:
                logout()
        else:
            st.session_state.last_activity = datetime.now()
            return True
    
    st.title("تسجيل الدخول")
    
    with st.form("login_form"):
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        submitted = st.form_submit_button("تسجيل الدخول")
        
        if submitted:
            user = await db.get_user_by_username(username)
            if user and check_password(user['password_hash'], password):
                # إنشاء جلسة جديدة
                st.session_state.authenticated = True
                st.session_state.user_id = user['user_id']
                st.session_state.username = user['username']
                st.session_state.role = user['role']
                st.session_state.region_id = user['assigned_region']
                st.session_state.last_activity = datetime.now()
                st.session_state.login_time = datetime.now()
                await db.update_last_login(user['user_id'])
                st.rerun()
                return True
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة")
    return False

def check_password(hashed_password, user_password):
    return hashed_password == hash_password(user_password)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def logout():
    keys = list(st.session_state.keys())
    for key in keys:
        del st.session_state[key]
    st.rerun()
