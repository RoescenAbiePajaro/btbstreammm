import streamlit as st
import subprocess
import time
from pymongo import MongoClient
from contextlib import contextmanager
from VirtualPainterEduc import run_virtual_painter


st.set_page_config(
    page_title="Educator Portal",
    page_icon="static/icons.png",
    layout="wide"
)

# Add loading screen CSS
st.markdown(
    """
    <style>
    /* Progress bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #6a11cb 0%, #2575fc 100%);
        height: 10px;
        border-radius: 5px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state for Virtual Painter if not exists
if 'virtual_painter_active' not in st.session_state:
    st.session_state.virtual_painter_active = False


@contextmanager
def get_mongodb_connection():
    """Context manager for MongoDB connection"""
    client = None
    try:
        MONGODB_URI = st.secrets["MONGODB_URI"]
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI not set in secrets.toml")

        # Configure MongoDB client with SSL settings
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
        yield students_collection, access_codes_collection
    except Exception as e:
        st.error(f"MongoDB connection failed: {str(e)}")
        st.error("Please check your internet connection and MongoDB Atlas settings.")
        st.stop()
    finally:
        if client:
            client.close()


def clear_session_state():
    """Clear all session state variables and release resources"""
    # Don't clear authentication state
    auth_state = st.session_state.get('authenticated')
    user_type = st.session_state.get('user_type')

    # Release camera if it exists
    if 'cap' in st.session_state:
        try:
            st.session_state.cap.release()
        except:
            pass
        del st.session_state.cap

    # Clear virtual painter state
    if 'virtual_painter_active' in st.session_state:
        del st.session_state.virtual_painter_active

    # Clear camera initialization state
    if 'camera_initialized' in st.session_state:
        del st.session_state.camera_initialized

    # Clear editing state
    if 'editing_student' in st.session_state:
        del st.session_state.editing_student

    # Clear all other session state variables except authentication
    for key in list(st.session_state.keys()):
        if key not in ['authenticated', 'user_type']:
            del st.session_state[key]

    # Restore authentication state
    if auth_state:
        st.session_state.authenticated = auth_state
    if user_type:
        st.session_state.user_type = user_type


def admin_portal():
    # Check authentication state
    if not st.session_state.get('authenticated') or st.session_state.get('user_type') != 'educator':
        st.error("Access denied. Please login as an educator.")
        st.stop()

    # Initialize session state for navigation if not exists
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Student Registrations"

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Student Registrations", "Access Codes", "Virtual Painter"])

    # Update current page in session state
    st.session_state.current_page = page

    # Debug information
    st.sidebar.write(f"Current page: {page}")

    # Add logout button at the bottom of sidebar
    st.sidebar.markdown("---")  # Add a separator
    if st.sidebar.button("Logout", key="educator_portal_logout"):
        # Release camera if it exists
        if 'camera' in st.session_state:
            st.session_state.camera.release()  # Turn off camera
            del st.session_state.camera  # Clean up the session

        # Clear all session state including authentication
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        # Redirect to main page
        st.markdown(
            """
            <meta http-equiv="refresh" content="0; url=./" />
            """,
            unsafe_allow_html=True
        )
        st.stop()

    # Clear virtual painter state when switching to other pages
    if page != "Virtual Painter" and st.session_state.get('virtual_painter_active'):
        clear_session_state()
        st.session_state.virtual_painter_active = False
        st.rerun()

    if page == "Student Registrations":
        st.session_state.virtual_painter_active = False
        st.title("Student Registrations")

        with get_mongodb_connection() as (students_collection, _):
            # Display all registered students
            students = list(students_collection.find())

            if students:
                for student in students:
                    col1, col2, col3 = st.columns([4, 1, 1])
                    with col1:
                        st.write(f"**{student['name']}** (Registered: {time.ctime(student['registered_at'])})")
                    with col2:
                        if st.button(f"Edit {student['name']}", key=f"edit_{student['_id']}"):
                            st.session_state['editing_student'] = student['_id']
                    with col3:
                        if st.button(f"Delete {student['name']}", key=f"delete_{student['_id']}"):
                            students_collection.delete_one({"_id": student["_id"]})
                            st.rerun()

                # Show edit form if a student is being edited
                if 'editing_student' in st.session_state:
                    student_to_edit = next((s for s in students if s['_id'] == st.session_state['editing_student']),
                                           None)
                    if student_to_edit:
                        with st.form(key=f"edit_form_{student_to_edit['_id']}"):
                            new_name = st.text_input("New Name", value=student_to_edit['name'])
                            submit_edit = st.form_submit_button("Save Changes")
                            cancel_edit = st.form_submit_button("Cancel")

                            if submit_edit and new_name:
                                students_collection.update_one(
                                    {"_id": student_to_edit["_id"]},
                                    {"$set": {"name": new_name}}
                                )
                                del st.session_state['editing_student']
                                st.success("Student information updated successfully!")
                                st.rerun()

                            if cancel_edit:
                                del st.session_state['editing_student']
                                st.rerun()
            else:
                st.info("No students registered yet.")

    elif page == "Access Codes":
        st.session_state.virtual_painter_active = False
        st.title("Access Codes Management")

        try:
            with get_mongodb_connection() as (_, access_codes_collection):
                # Display existing access codes
                codes = list(access_codes_collection.find())

                if codes:
                    for code in codes:
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.write(f"Code: {code['code']} (Created by: {code.get('educator_id', 'System')})")
                        with col2:
                            if st.button(f"Delete {code['code']}", key=f"del_code_{code['_id']}"):
                                access_codes_collection.delete_one({"_id": code["_id"]})
                                st.rerun()

                # Add new access code
                with st.form("add_code_form"):
                    new_code = st.text_input("New Access Code")
                    submit_code = st.form_submit_button("Add Code")
                    if submit_code and new_code:
                        # Check if code already exists
                        existing_code = access_codes_collection.find_one({"code": new_code})
                        if existing_code:
                            st.warning(f"Access code '{new_code}' already exists!")
                        else:
                            access_codes_collection.insert_one({
                                "code": new_code,
                                "created_at": time.time(),
                                "educator_id": "Admin"
                            })
                            st.rerun()
        except Exception as e:
            st.error(f"An error occurred while accessing the database: {str(e)}")
            st.info("Please try refreshing the page or contact support if the issue persists.")

    elif page == "Virtual Painter":
        st.session_state.virtual_painter_active = True
        st.title("Virtual Painter")
        run_virtual_painter()




if __name__ == "__main__":
    admin_portal()