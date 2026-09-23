# Add this import to the existing login UI file:
from modules.legal_portal import render_login_legal_links


# Add immediately after the Access Research Terminal button/error area
# and before the copyright footer:
render_login_legal_links()


# The generated links open public Streamlit routes:
# /?page=legal&legal_document=privacy-policy
# /?page=legal&legal_document=terms-of-service
# /?page=legal&legal_document=cookie-policy
# /?page=legal&legal_document=financial-disclaimer
# /?page=legal&legal_document=risk-disclosure
