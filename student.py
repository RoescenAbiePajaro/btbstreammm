import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import os
import time
from copy import deepcopy
from VirtualPainter import run_virtuals_painter  # Fixed typo in import

st.set_page_config(layout="wide")

# Initialize session state for Virtual Painter if not exists
if 'virtuals_painter_active' not in st.session_state:  # Fixed variable name
    st.session_state.virtuals_painter_active = False

def init_session_state():
    """Initialize session state variables"""
    if 'current_color' not in st.session_state:
        st.session_state.current_color = "#000000"
    if 'line_width' not in st.session_state:
        st.session_state.line_width = 5
    if 'drawing_mode' not in st.session_state:
        st.session_state.drawing_mode = "freedraw"
    if 'eraser_width' not in st.session_state:
        st.session_state.eraser_width = 20
    if 'undo_stack' not in st.session_state:
        st.session_state.undo_stack = []
    if 'redo_stack' not in st.session_state:
        st.session_state.redo_stack = []
    if 'canvas_data' not in st.session_state:
        st.session_state.canvas_data = None
    if 'clear_canvas' not in st.session_state:
        st.session_state.clear_canvas = False

def clear_session_state():
    """Clear all session state variables and release resources"""
    # Don't clear authentication state
    auth_state = st.session_state.get('authenticated')
    user_type = st.session_state.get('user_type')

    # Clear all other session state variables except authentication
    for key in list(st.session_state.keys()):
        if key not in ['authenticated', 'user_type']:
            del st.session_state[key]

    # Restore authentication state
    if auth_state:
        st.session_state.authenticated = auth_state
    if user_type:
        st.session_state.user_type = user_type

def push_to_undo_stack(canvas_data):
    """Push current state to undo stack and clear redo stack"""
    if canvas_data is not None:
        # Limit undo stack size to prevent memory issues
        if len(st.session_state.undo_stack) >= 20:
            st.session_state.undo_stack.pop(0)
        st.session_state.undo_stack.append(deepcopy(canvas_data))
        st.session_state.redo_stack = []

def student_portal():
    """Main entry point for the student portal"""
    # Check authentication state
    if not st.session_state.get('authenticated') or st.session_state.get('user_type') != 'student':
        st.error("Access denied. Please login as a student.")
        st.stop()

    # Initialize session state for navigation if not exists
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Drawing"

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Drawing", "Virtual Painter"])

    # Update current page in session state
    st.session_state.current_page = page

    # Clear virtual painter state when switching to other pages
    if page != "Virtual Painter" and st.session_state.get('virtuals_painter_active'):  # Fixed variable name
        clear_session_state()
        st.session_state.virtuals_painter_active = False  # Fixed variable name
        st.rerun()

    # Debug information
    st.sidebar.write(f"Current page: {page}")

    # Add logout button at the bottom of sidebar
    st.sidebar.markdown("---")  # Add a separator
    if st.sidebar.button("Logout", key="student_portal_logout"):
        # Release camera if it exists
        if 'camera' in st.session_state:
            st.session_state.camera.release()  # Turn off camera
            del st.session_state.camera  # Clean up the session

        # Clear all session state including authentication
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    if page == "Drawing":
        st.session_state.virtuals_painter_active = False  # Fixed variable name
        st.title("Drawing Mode")
        main()  # Call main function for drawing page
    elif page == "Virtual Painter":
        st.session_state.virtuals_painter_active = True  # Fixed variable name
        st.title("Virtual Painter")
        run_virtuals_painter()  # Fixed function name

def main():
    # Initialize session state
    init_session_state()

    st.title("Canvas Drawing Mode")

    # Sidebar for controls
    with st.sidebar:
        st.header("Drawing Controls")

        # Tool selection
        tool = st.radio(
            "Tool:",
            ("Draw", "Eraser"),
            index=0,
            key="tool_selector"
        )

        # Update drawing mode based on selection
        if tool == "Draw":
            st.session_state.drawing_mode = "freedraw"
        elif tool == "Eraser":
            st.session_state.drawing_mode = "freedraw"  # Eraser still uses freedraw to erase
        else:
            st.session_state.drawing_mode = "freedraw"

        # Color picker (only show when in draw mode)
        if tool == "Draw":
            st.session_state.current_color = st.color_picker(
                "Brush Color",
                st.session_state.current_color,
                key="brush_picker"
            )
        elif tool == "Eraser":
            st.session_state.eraser_width = st.slider(
                "Eraser Size",
                min_value=10,
                max_value=100,
                value=20,
                key="eraser_slider"
            )

        # Line width slider
        st.session_state.line_width = st.slider(
            "Line Width",
            min_value=1,
            max_value=50,
            value=st.session_state.line_width,
            key="line_slider"
        )

        # Determine stroke parameters based on tool
        if tool == "Eraser":
            stroke_color = "#FFFFFF"  # Erase with white
            stroke_width = st.session_state.eraser_width
        else:
            stroke_color = st.session_state.current_color
            stroke_width = st.session_state.line_width

    # Create the canvas
    canvas_result = st_canvas(
        fill_color="rgba(255, 255, 255, 0)",  # Transparent
        stroke_width=stroke_width,
        stroke_color=stroke_color,
        background_color="white",
        width=1220,
        height=720,
        drawing_mode=st.session_state.drawing_mode,
        key="canvas",
        initial_drawing=None if st.session_state.get('clear_canvas', False) else None,
        display_toolbar=True,
        update_streamlit=True
    )

    # Handle canvas data changes
    if canvas_result.json_data is not None:
        if st.session_state.canvas_data != canvas_result.json_data:
            # Only push to undo stack if there's a significant change
            if st.session_state.canvas_data is not None:
                push_to_undo_stack(st.session_state.canvas_data)
            # Update current state
            st.session_state.canvas_data = deepcopy(canvas_result.json_data)

    # Reset clear canvas flag
    if st.session_state.get('clear_canvas', False):
        st.session_state.clear_canvas = False

    # Save button
    if st.button("Save Drawing"):
        if canvas_result.image_data is not None:
            # Convert the canvas data to an image
            image = Image.fromarray(canvas_result.image_data.astype('uint8'))

            # Generate timestamp for filename
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(os.path.expanduser("~"), "Pictures", f"drawing_{timestamp}.png")

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Save the image
            image.save(save_path)
            st.success(f"Drawing saved at {save_path}")

if __name__ == "__main__":
    student_portal()