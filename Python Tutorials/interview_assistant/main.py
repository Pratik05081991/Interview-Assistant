"""
Real-Time AI Interview Assistant
Entry point — run this file to start the application.
"""

import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import InterviewAssistantApp

if __name__ == "__main__":
    app = InterviewAssistantApp()
    app.run()
