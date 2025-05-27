# VirtualPainterEduc.py
import streamlit as st
import cv2
import numpy as np
import os
import time
import HandTrackingModule as htm
from KeyboardInput import KeyboardInput
import keyboard
from collections import deque


def run_virtual_painter():
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

    # Variables
    brushSize = 10
    eraserSize = 100
    fps = 50
    time_per_frame = 5.0 / fps

    # Load header images
    folderPath = 'header'
    myList = sorted(os.listdir(folderPath))
    overlayList = [cv2.imread(f"{folderPath}/{imPath}") for imPath in myList]

    # Load guide images (resized to 1280x595)
    folderPath = 'guide'
    myList = sorted(os.listdir(folderPath))
    guideList = []
    for imPath in myList:
        img = cv2.imread(f"{folderPath}/{imPath}")
        if img is not None:
            # Resize guide images to fit below header (1280x595)
            img = cv2.resize(img, (1280, 595))
            guideList.append(img)

    # Default images
    header = overlayList[0]
    current_guide_index = 0  # Track current guide index
    current_guide = None  # Initially no guide shown
    show_guide = False  # Track guide visibility state

    # Swipe detection variables
    swipe_threshold = 50  # Minimum horizontal movement to consider a swipe
    swipe_start_x = None  # To track where swipe started
    swipe_active = False  # To track if swipe is in progress

    # Default drawing color
    drawColor = (255, 0, 255)

    # Previous points
    xp, yp = 0, 0

    # Create Image Canvas
    imgCanvas = np.zeros((720, 1280, 3), np.uint8)

    # Undo/Redo Stack - now stores both canvas and text state
    undoStack = []
    redoStack = []

    # Create keyboard input handler
    keyboard_input = KeyboardInput()
    last_time = time.time()

    def handle_keyboard_events():
        if keyboard_input.active:
            if keyboard.is_pressed('enter'):
                keyboard_input.process_key_input(13)  # Enter key
            elif keyboard.is_pressed('backspace'):
                keyboard_input.process_key_input(8)  # Backspace
            elif keyboard.is_pressed('esc'):
                keyboard_input.active = False
            elif keyboard.is_pressed('caps lock'):
                # Toggle caps lock state
                keyboard_input.caps_lock = not getattr(keyboard_input, 'caps_lock', False)
            else:
                shift_pressed = keyboard.is_pressed('shift')
                caps_lock_active = getattr(keyboard_input, 'caps_lock', False)

                # First check numbers (they shouldn't be affected by caps lock)
                for num in '0123456789':
                    if keyboard.is_pressed(num):
                        if shift_pressed:
                            # Shift + number gives the special character
                            shift_num_map = {
                                '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
                                '6': '^', '7': '&', '8': '*', '9': '(', '0': ')'
                            }
                            char = shift_num_map[num]
                            keyboard_input.process_key_input(ord(char))
                        else:
                            # Regular number
                            keyboard_input.process_key_input(ord(num))
                        return

                # Then check letters (affected by both shift and caps lock)
                for letter in 'abcdefghijklmnopqrstuvwxyz':
                    if keyboard.is_pressed(letter):
                        if shift_pressed ^ caps_lock_active:  # XOR - uppercase if either is true
                            keyboard_input.process_key_input(ord(letter.upper()))
                        else:
                            keyboard_input.process_key_input(ord(letter.lower()))
                        return

                # Then check other special characters (space, punctuation, etc.)
                special_chars = {
                    'space': ' ',
                    'tab': '\t',
                    '-': '-', '=': '=',
                    '[': '[', ']': ']', '\\': '\\',
                    ';': ';', "'": "'",
                    ',': ',', '.': '.', '/': '/',
                    '`': '`'
                }

                # Shifted versions of special characters
                shifted_special_chars = {
                    '-': '_', '=': '+',
                    '[': '{', ']': '}', '\\': '|',
                    ';': ':', "'": '"',
                    ',': '<', '.': '>', '/': '?',
                    '`': '~'
                }

                for char in special_chars:
                    if keyboard.is_pressed(char):
                        if shift_pressed and char in shifted_special_chars:
                            keyboard_input.process_key_input(ord(shifted_special_chars[char]))
                        else:
                            keyboard_input.process_key_input(ord(special_chars[char]))
                        return

    # Function to save current state (both canvas and text)
    def save_state():
        return {
            'canvas': imgCanvas.copy(),
            'text_objects': list(keyboard_input.text_objects)  # Convert deque to list for proper copying
        }

    # Function to restore state (both canvas and text)
    def restore_state(state):
        nonlocal imgCanvas
        imgCanvas = state['canvas'].copy()
        keyboard_input.text_objects = deque(state['text_objects'], maxlen=20)  # Convert back to deque

    # Function to save the canvas
    def save_canvas():
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(os.path.expanduser("~"), "Pictures", f"saved_painting_{timestamp}.png")

        # Create a copy of the canvas to draw text on
        saved_img = imgCanvas.copy()

        # Draw all text objects onto the saved image
        for obj in keyboard_input.text_objects:
            cv2.putText(
                saved_img,
                obj['text'],
                obj['position'],
                obj['font'],
                obj['scale'],
                obj['color'],
                obj['thickness'] + 2
            )

            # Then draw main text
            cv2.putText(
                saved_img,
                obj['text'],
                obj['position'],
                obj['font'],
                obj['scale'],
                obj['color'],
                obj['thickness']
            )

        cv2.imwrite(save_path, saved_img)
        st.success(f"Canvas Saved at {save_path}")

    # Function to interpolate points
    def interpolate_points(x1, y1, x2, y2, num_points=10):
        points = []
        for i in range(num_points):
            x = int(x1 + (x2 - x1) * (i / num_points))
            y = int(y1 + (y2 - y1) * (i / num_points))
            points.append((x, y))
        return points

    # Streamlit app
    st.title("Beyond The Brush - Virtual Painter")

    # Camera input
    run = st.checkbox('Run', value=True)
    FRAME_WINDOW = st.image([])

    # Add camera loading state
    if 'camera_initialized' not in st.session_state:
        st.session_state.camera_initialized = False

    # Show loading spinner while initializing camera
    if not st.session_state.camera_initialized:
        with st.spinner('Initializing camera...'):
            try:
                if 'cap' not in st.session_state:
                    st.session_state.cap = cv2.VideoCapture(0)
                    if not st.session_state.cap.isOpened():
                        st.error('Failed to initialize camera. Please check your camera connection.')
                        st.stop()

                    # Set camera properties
                    st.session_state.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    st.session_state.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    st.session_state.camera_initialized = True
            except Exception as e:
                st.error(f'Error initializing camera: {str(e)}')
                st.stop()
            time.sleep(1)  # Brief pause to show loading state

    cap = st.session_state.cap

    # Assigning Detector
    detector = htm.handDetector(detectionCon=0.85)

    try:
        while run:
            start_time = time.time()

            # 1. Import Image
            success, img = cap.read()
            if not success:
                continue

            img = cv2.flip(img, 1)

            # 2. Find Hand Landmarks
            img = detector.findHands(img, draw=False)
            lmList = detector.findPosition(img, draw=False)

            # Draw black outline (thicker)
            cv2.putText(img, "Selection Mode - Two Fingers Up", (50, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)  # Black with thickness 4

            # Draw main white text (thinner)
            cv2.putText(img, "Selection Mode - Two Fingers Up", (50, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)  # White with thickness 2

            if len(lmList) != 0:
                # Tip of index and middle fingers
                x1, y1 = lmList[8][1:]
                x2, y2 = lmList[12][1:]

                # 3. Check which fingers are up
                fingers = detector.fingersUp()

                # 4. Selection Mode - Two Fingers Up
                if fingers[1] and fingers[2]:
                    xp, yp = 0, 0  # Reset points
                    swipe_start_x = None  # Reset swipe tracking when in selection mode

                    # Detecting selection based on X coordinate
                    if y1 < 125:  # Ensure the selection is within the header area
                        if 0 < x1 < 128:  # Save
                            header = overlayList[1]
                            save_canvas()
                            show_guide = False

                        elif 128 < x1 < 256:  # Pink
                            header = overlayList[2]
                            drawColor = (255, 0, 255)  # Pink
                            show_guide = False
                            keyboard_input.active = False  # Close keyboard input if open

                        elif 256 < x1 < 384:  # Blue
                            header = overlayList[3]
                            drawColor = (255, 0, 0)  # Blue
                            show_guide = False
                            keyboard_input.active = False  # Close keyboard input if open

                        elif 384 < x1 < 512:  # Green
                            header = overlayList[4]
                            drawColor = (0, 255, 0)  # Green
                            show_guide = False
                            keyboard_input.active = False  # Close keyboard input if open

                        elif 512 < x1 < 640:  # Yellow
                            header = overlayList[5]
                            drawColor = (0, 255, 255)  # Yellow
                            show_guide = False
                            keyboard_input.active = False  # Close keyboard input if open

                        elif 640 < x1 < 768:  # Eraser
                            header = overlayList[6]
                            drawColor = (0, 0, 0)  # Eraser
                            show_guide = False
                            keyboard_input.active = False  # Close keyboard input if open
                            # Delete selected text if any
                            keyboard_input.delete_selected()

                        # Undo/Redo handling with global state
                        elif 768 < x1 < 896:  # Undo
                            header = overlayList[7]
                            if len(undoStack) > 0:
                                redoStack.append(save_state())
                                state = undoStack.pop()
                                restore_state(state)
                                show_guide = False

                        elif 896 < x1 < 1024:  # Redo
                            header = overlayList[8]
                            if len(redoStack) > 0:
                                undoStack.append(save_state())
                                state = redoStack.pop()
                                restore_state(state)
                                show_guide = False

                        elif 1024 < x1 < 1152:  # Guide
                            header = overlayList[9]
                            # Toggle guide display
                            show_guide = True  # Always show guide when selected
                            current_guide_index = 0  # Reset to first guide
                            current_guide = guideList[current_guide_index]  # Show first guide image
                            keyboard_input.active = False  # Close keyboard input if open

                        elif 1155 < x1 < 1280:
                            if not keyboard_input.active:
                                keyboard_input.active = True
                            header = overlayList[10]
                            show_guide = False

                        # Brush/Eraser size controls
                        elif 1155 < x1 < 1280 and y1 > 650:  # Bottom right area
                            if x1 < 1200:  # Left side - decrease size
                                if drawColor == (0, 0, 0):  # Eraser
                                    eraserSize = max(10, eraserSize - 5)
                                else:  # Brush
                                    brushSize = max(1, brushSize - 1)
                            else:  # Right side - increase size
                                if drawColor == (0, 0, 0):  # Eraser
                                    eraserSize = min(200, eraserSize + 5)
                                else:  # Brush
                                    brushSize = min(50, brushSize + 1)
                            st.toast(
                                f"{'Eraser' if drawColor == (0, 0, 0) else 'Brush'} size: {eraserSize if drawColor == (0, 0, 0) else brushSize}")

                    # Show selection rectangle
                    cv2.rectangle(img, (x1, y1 - 25), (x2, y2 + 25), drawColor, cv2.FILLED)

                # ==================== HAND GESTURE LOGIC ====================
                # GUIDE NAVIGATION MODE - One index finger, guide visible, keyboard not active
                if fingers[1] and not fingers[2] and show_guide and not keyboard_input.active:
                    # Start or continue swipe gesture
                    if swipe_start_x is None:
                        swipe_start_x = x1
                        swipe_active = True
                    else:
                        delta_x = x1 - swipe_start_x
                        if abs(delta_x) > swipe_threshold and swipe_active:
                            if delta_x > 0:
                                # Swipe right - previous guide
                                current_guide_index = max(0, current_guide_index - 1)
                            else:
                                # Swipe left - next guide
                                current_guide_index = min(len(guideList) - 1, current_guide_index + 1)

                            current_guide = guideList[current_guide_index]
                            st.toast(f"Guide {current_guide_index + 1}/{len(guideList)}")
                            swipe_active = False  # avoid rapid multiple swipes

                    # Visual feedback
                    cv2.circle(img, (x1, y1), 15, (0, 255, 0), cv2.FILLED)

                # DRAWING MODE - One index finger, guide hidden, keyboard not active
                elif fingers[1] and not fingers[2] and not show_guide and not keyboard_input.active:
                    swipe_start_x = None  # cancel swipe tracking when drawing

                    # Eraser: Check for overlapping with existing text
                    if drawColor == (0, 0, 0):
                        for i, obj in enumerate(reversed(keyboard_input.text_objects)):
                            idx = len(keyboard_input.text_objects) - 1 - i
                            text_size = cv2.getTextSize(obj['text'], obj['font'], obj['scale'], obj['thickness'])[0]

                            x_text, y_text = obj['position']
                            if (x_text <= x1 <= x_text + text_size[0] and
                                    y_text - text_size[1] <= y1 <= y_text):
                                del keyboard_input.text_objects[idx]
                                break

                    # Visual feedback
                    cv2.circle(img, (x1, y1), 15, drawColor, cv2.FILLED)

                    if xp == 0 and yp == 0:
                        xp, yp = x1, y1

                    # Smooth drawing
                    points = interpolate_points(xp, yp, x1, y1)
                    for point in points:
                        if drawColor == (0, 0, 0):  # eraser
                            cv2.line(img, (xp, yp), point, drawColor, eraserSize)
                            cv2.line(imgCanvas, (xp, yp), point, drawColor, eraserSize)
                        else:
                            cv2.line(img, (xp, yp), point, drawColor, brushSize)
                            cv2.line(imgCanvas, (xp, yp), point, drawColor, brushSize)
                        xp, yp = point

                    # Update undo/redo stacks
                    undoStack.append(save_state())
                    redoStack.clear()

                # TEXT DRAGGING MODE - Two fingers, keyboard active
                elif keyboard_input.active and fingers[1] and fingers[2]:
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2

                    if not keyboard_input.dragging:
                        if keyboard_input.text or keyboard_input.cursor_visible:
                            keyboard_input.check_drag_start(center_x, center_y)
                    else:
                        keyboard_input.update_drag(center_x, center_y)
                        # Save state after text movement
                        undoStack.append(save_state())
                        redoStack.clear()

                    # Visual feedback
                    cv2.circle(img, (center_x, center_y), 15, (0, 255, 255), cv2.FILLED)

                else:
                    # Reset states when fingers not up or mode not active
                    xp, yp = 0, 0
                    swipe_start_x = None
                    swipe_active = False
                    if keyboard_input.dragging:
                        keyboard_input.end_drag()

            else:
                # No hand detected: reset everything
                swipe_start_x = None
                swipe_active = False
                if keyboard_input.dragging:
                    keyboard_input.end_drag()

            # Handle keyboard input
            handle_keyboard_events()  # Add this line
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time
            keyboard_input.update(dt)

            # 8. Convert Canvas to Grayscale and Invert
            imgGray = cv2.cvtColor(imgCanvas, cv2.COLOR_BGR2GRAY)
            _, imgInv = cv2.threshold(imgGray, 50, 255, cv2.THRESH_BINARY_INV)
            imgInv = cv2.cvtColor(imgInv, cv2.COLOR_GRAY2BGR)
            img = cv2.bitwise_and(img, imgInv)
            img = cv2.bitwise_or(img, imgCanvas)

            # 9. Set Header Image
            img[0:125, 0:1280] = header

            # 10. Draw keyboard text and placeholder
            if keyboard_input.active:
                # Draw semi-transparent typing area background
                typing_area = np.zeros((100, 1280, 3), dtype=np.uint8)
                typing_area[:] = (50, 50, 50)  # Dark gray background
                img[620:720, 0:1280] = cv2.addWeighted(img[620:720, 0:1280], 0.7, typing_area, 0.3, 0)

                keyboard_input.draw(img)

                # Draw instruction text
                instruction_text = "Press Enter to confirm text, ESC to cancel"
                cv2.putText(img, instruction_text, (20, 700),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            else:
                # Draw existing text objects even when keyboard is inactive
                keyboard_input.draw(img)

            # 11. Display Guide Image if active
            if show_guide and current_guide is not None:
                # Create a composite image that preserves the drawing canvas
                guide_area = img[125:720, 0:1280].copy()
                # Blend the guide with the current camera feed (50% opacity)
                blended_guide = cv2.addWeighted(current_guide, 0.3, guide_area, 0.3, 0)
                # Put the blended guide back
                img[125:720, 0:1280] = blended_guide

                # Display guide navigation instructions
                cv2.putText(img, "", (50, 150),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(img, f"Guide {current_guide_index + 1}/{len(guideList)}", (1100, 150),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Display the image in Streamlit
            FRAME_WINDOW.image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

            # Maintain 60 FPS
            elapsed_time = time.time() - start_time
            if elapsed_time < time_per_frame:
                time.sleep(time_per_frame - elapsed_time)

    finally:
        # Ensure camera is released when the loop ends
        if 'cap' in st.session_state:
            st.session_state.cap.release()
            del st.session_state.cap
        if 'camera_initialized' in st.session_state:
            del st.session_state.camera_initialized


if __name__ == "__main__":
    run_virtual_painter()