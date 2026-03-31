import sys
import cv2
import numpy as np
import pyautogui
from PyQt6.QtWidgets import QApplication, QWidget, QTextEdit, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
import ctypes

class InterviewAssistant(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.make_invisible_to_capture()

    def initUI(self):
        self.setWindowTitle('Assistant')
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 100, 400, 300)

        self.layout = QVBoxLayout()
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setStyleSheet("background-color: rgba(0, 0, 0, 150); color: white; border-radius: 10px;")
        self.layout.addWidget(self.text_area)
        self.setLayout(self.layout)

    def make_invisible_to_capture(self):
        # This works on Windows 10+
        hwnd = self.winId().__int__()
        # WDA_EXCLUDEFROMCAPTURE = 0x00000011
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = InterviewAssistant()
    ex.show()
    sys.exit(app.exec())
