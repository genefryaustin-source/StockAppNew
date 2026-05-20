import streamlit as st
from modules.auth.auth_service import authenticate

from PIL import Image

st.warning("LOGIN_UI FINGERPRINT")
# Custom CSS for better logo display
st.markdown("""
    <style>
        .logo-container {
            display: flex;
            justify-content: center;
            margin-bottom: 30px;
        }
        .stImage {
            max-width: 250px;
        }
    </style>
""", unsafe_allow_html=True)

# Display logo at the top (centered)
col1, col2, col3 = st.columns([1, 2, 1])
#with col2:
    #try:
        #logo = Image.open("logo.png")  # Put your logo file in the same folder
        #st.image(logo) # use_container_width=True
    #except FileNotFoundError:
        #st.error("Logo file 'logo.png' not found. Please add it to your project folder.")


import streamlit as st
from modules.auth.auth_service import authenticate


def render_login(db):
    st.title("Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login", key="login_btn"):
        user = authenticate(db, email, password)

        if user:
            st.session_state["user"] = user
            st.session_state["last_activity_ts"] = __import__("time").time()
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")