from cvzone import HandTrackingModule
# HandTrackingModule.py
import cv2
import mediapipe as mp
import time
import streamlit as st
import numpy as np


class handDetector:
    def __init__(self, mode=False, maxHands=2, detectionCon=0.5, trackCon=0.5):
        self.results = None
        self.mode = mode
        self.maxHands = maxHands
        self.detectionCon = detectionCon
        self.trackCon = trackCon

        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(
            static_image_mode=self.mode,
            max_num_hands=self.maxHands,
            min_detection_confidence=self.detectionCon,
            min_tracking_confidence=self.trackCon
        )
        self.mpDraw = mp.solutions.drawing_utils
        self.tipIds = [4, 8, 12, 16, 20]

    def findHands(self, img, draw=True):
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.hands.process(imgRGB)

        if self.results.multi_hand_landmarks:
            for handLms in self.results.multi_hand_landmarks:
                if draw:
                    self.mpDraw.draw_landmarks(img, handLms,
                                               self.mpHands.HAND_CONNECTIONS)
        return img

    def findPosition(self, img, handNo=0, draw=True):
        self.lmList = []
        if self.results.multi_hand_landmarks:
            myHand = self.results.multi_hand_landmarks[handNo]
            for id, lm in enumerate(myHand.landmark):
                h, w, c = img.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                self.lmList.append([id, cx, cy])
                if draw:
                    cv2.circle(img, (cx, cy), 10, (255, 0, 255), cv2.FILLED)
        return self.lmList

    def fingersUp(self):
        fingers = []

        # Thumb
        if self.lmList[self.tipIds[0]][1] > self.lmList[self.tipIds[0] - 1][1]:
            fingers.append(1)
        else:
            fingers.append(0)

        # 4 Fingers
        for id in range(1, 5):
            if self.lmList[self.tipIds[id]][2] < self.lmList[self.tipIds[id] - 2][2]:  # Compare y-coordinates
                fingers.append(1)
            else:
                fingers.append(0)

        return fingers


def main():
    st.set_page_config(page_title="Hand Tracking App", page_icon="✋", layout="wide")
    
    # Sidebar configuration
    st.sidebar.title("Settings")
    detection_confidence = st.sidebar.slider("Detection Confidence", 0.0, 1.0, 0.5, 0.1)
    tracking_confidence = st.sidebar.slider("Tracking Confidence", 0.0, 1.0, 0.5, 0.1)
    max_hands = st.sidebar.selectbox("Maximum Hands", [1, 2], index=1)
    
    # Main content
    st.title("✋ Hand Tracking Application")
    st.markdown("---")
    
    # Create two columns for layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Create a placeholder for the video feed
        frame_placeholder = st.empty()
    
    with col2:
        st.subheader("Controls")
        start_button = st.button("Start Tracking", key="start")
        stop_button = st.button("Stop Tracking", key="stop")
        
        st.subheader("Statistics")
        fps_placeholder = st.empty()
        hands_detected_placeholder = st.empty()
        
        st.subheader("Instructions")
        st.markdown("""
        - Click 'Start Tracking' to begin
        - Show your hand to the camera
        - Use the sidebar to adjust settings
        - Click 'Stop Tracking' to end
        """)

    # Initialize session state
    if 'tracking' not in st.session_state:
        st.session_state.tracking = False

    # Initialize the detector with user settings
    detector = handDetector(
        mode=False,
        maxHands=max_hands,
        detectionCon=detection_confidence,
        trackCon=tracking_confidence
    )

    # Initialize webcam
    cap = cv2.VideoCapture(0)
    
    pTime = 0
    
    while cap.isOpened():
        if start_button:
            st.session_state.tracking = True
        
        if stop_button:
            st.session_state.tracking = False
            break
            
        if not st.session_state.tracking:
            continue

        success, img = cap.read()
        if not success:
            continue

        # Process the image
        img = detector.findHands(img)
        lmList = detector.findPosition(img)
        
        # Calculate FPS
        cTime = time.time()
        fps = 1 / (cTime - pTime)
        pTime = cTime
        
        # Update statistics
        fps_placeholder.metric("FPS", f"{int(fps)}")
        hands_detected = len(detector.results.multi_hand_landmarks) if detector.results.multi_hand_landmarks else 0
        hands_detected_placeholder.metric("Hands Detected", hands_detected)
        
        # Add FPS text to image
        cv2.putText(img, f"FPS: {int(fps)}", (10, 70), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 255), 3)
        
        # Convert the image to RGB for Streamlit
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Display the image in Streamlit
        frame_placeholder.image(img_rgb, channels="RGB", use_column_width=True)
        
        # Add a small delay to control the frame rate
        time.sleep(0.01)

    # Release resources
    cap.release()
    st.success("Tracking stopped. You can start again using the Start button.")


if __name__ == "__main__":
    main()
