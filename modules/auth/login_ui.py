import streamlit as st
from modules.auth.auth_service import authenticate
from branding.conduro_theme import load_conduro_theme

def render_login(db):

    load_conduro_theme()

    st.markdown("""
    <div class="conduro-shell">
        <div class="conduro-brandbar">
            <div>
                <div class="conduro-kicker">CONDURO VENTURES LLC</div>
                <div class="conduro-title">Stock Research Terminal</div>
                <div class="conduro-subtitle">AI-Powered Equity Research Platform</div>
            </div>
            <div class="conduro-pill">Professional Edition</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:rgba(12,21,36,.85);border:1px solid rgba(103,232,249,.18);
    border-radius:24px;padding:30px;margin-bottom:25px;">
    <h2 style="margin-top:0;color:white;">Sign In</h2>
    <p style="color:#A8B3C7;">Access your Stock Research Terminal workspace.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="conduro-card">
    <h3>Platform Features</h3>
    <p>✓ AI Rankings</p>
    <p>✓ AI Scanner</p>
    <p>✓ Portfolio Analytics</p>
    <p>✓ Options Intelligence</p>
    <p>✓ Research Reports</p>
    <p>✓ Advisor Collaboration</p>
    </div>
    """, unsafe_allow_html=True)

    email = st.text_input("Email Address", placeholder="admin@test.com")
    password = st.text_input("Password", type="password", placeholder="Enter password")

    if st.button("Access Research Terminal", key="login_btn", use_container_width=True):
        user = authenticate(db, email, password)

        if user:
            st.session_state["user"] = user
            st.session_state["last_activity_ts"] = __import__("time").time()
            st.success("Login successful")

            st.session_state["authenticated"] = True

            return
        else:
            st.error("Invalid credentials")

    st.markdown("""
    <hr>
    <div style="text-align:center;color:#A8B3C7;font-size:12px;">
    © 2026 Conduro Ventures LLC<br>
    Stock Research Terminal
    </div>
    """, unsafe_allow_html=True)
