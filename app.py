# app.py
import streamlit as st
import time
import subprocess
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
from register import  students_collection, access_codes_collection

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Beyond The Brush",
    page_icon="static/icons.png",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- ENV + DB CONNECTION ---
load_dotenv()

try:
    MONGODB_URI = st.secrets["MONGODB_URI"]
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI not set in secrets.toml")

    # Configure MongoDB client with updated SSL settings
    client = MongoClient(
        MONGODB_URI,
        tls=True,
        tlsAllowInvalidCertificates=False,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000
    )
    # Test the connection
    client.admin.command('ping')
    db = client["beyond_the_brush"]
    students_collection = db["students"]
    access_codes_collection = db["access_codes"]
except Exception as e:
    st.error(f"MongoDB connection failed: {str(e)}")
    st.error("Please check your internet connection and MongoDB Atlas settings.")
    st.stop()

# --- SESSION STATE ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_type' not in st.session_state:
    st.session_state.user_type = None
if 'username' not in st.session_state:
    st.session_state.username = None


# --- STYLING ---
def load_css():
    st.markdown("""
    <style>
    body {
        background-color: #0E1117;
        color: white;
    }
    h1, h3 {
        text-align: center;
        color: white;
    }
    .stTextInput > div > div > input {
        background-color: rgba(30, 30, 47, 0.7) !important;
        color: white !important;
        border-radius: 8px;
        padding: 10px;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .stButton > button {
        background: linear-gradient(90deg, #6a11cb 0%, #2575fc 100%);
        color: white;
        border: none;
        padding: 12px;
        border-radius: 8px;
        font-weight: 600;
        box-shadow: 0 4px 15px rgba(106, 17, 203, 0.3);
        width: 100%;
        transition: all 0.2s ease-in-out;
    }
    .stRadio > div {
        justify-content: center;
        gap: 2rem;
    }
    /* Progress bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #6a11cb 0%, #2575fc 100%);
        height: 10px;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)


# --- UTILS ---
def set_loading(state=True):
    st.session_state.is_loading = state


def show_loading_screen(duration=2.0):
    set_loading(True)
    with st.spinner("Launching application..."):
        time.sleep(duration)
    set_loading(False)


def launch_virtual_painter(role):
    if getattr(sys, 'frozen', False):
        subprocess.Popen([sys.executable, "VirtualPainter.py", role])
    else:
        subprocess.Popen([sys.executable, "-m", "streamlit", "run", "VirtualPainter.py", "--", role])
        time.sleep(1)

    st.markdown(f"""<meta http-equiv="refresh" content="0; url='./'">""", unsafe_allow_html=True)


# --- VERIFICATION LOGIC ---
def verify_code(code, role, name):
    code_data = access_codes_collection.find_one({"code": code})
    student_data = students_collection.find_one({"access_code": code, "name": name})

    if role == "student":
        if student_data:
            st.session_state.authenticated = True
            st.session_state.user_type = "student"
            st.session_state.username = name
            st.success("Access granted!")
            st.rerun()
        else:
            st.error("Invalid name or code.")
    elif role == "educator" and code_data:
        st.session_state.authenticated = True
        st.session_state.user_type = "educator"
        st.success("Access granted!")
        st.rerun()
    else:
        st.error("Access code incorrect.")


# --- MAIN ---
def main():
    load_css()

    if not st.session_state.authenticated:
        st.title("Beyond The Brush")

        # Create three columns for the buttons
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:  # Center column
            st.markdown("### Select your role:")
            role = st.radio("", ["Student", "Educator"], key="role_radio", label_visibility="collapsed")

            if role == "Student":
                st.markdown("#### Login")
                name = st.text_input("Enter your name", placeholder="Your name", key="name_input")
                code = st.text_input("Enter access code", placeholder="Access code", type="password", key="access_code")

                if st.button("Login"):
                    verify_code(code, "student", name)

                if st.button("Register New Student"):
                    st.session_state.user_type = "register"
                    st.rerun()

            elif role == "Educator":
                st.markdown("#### Educator Access")
                code = st.text_input("Access code", type="password", key="admin_code")

                if st.button("Login"):
                    verify_code(code, "educator", "")

    else:
        # User is authenticated, show appropriate page
        if st.session_state.user_type == "student":
            st.switch_page("pages/2_student.py")
        elif st.session_state.user_type == "educator":
            st.switch_page("pages/1_educator.py")
        elif st.session_state.user_type == "register":
            st.switch_page("pages/3_register.py")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--painter":
        import VirtualPainter

        if not st.session_state.get('access_granted'):
            st.error("Please authenticate from main screen.")
            st.stop()
        VirtualPainter.run_application(sys.argv[2] if len(sys.argv) > 2 else "student")
    else:
        main()
