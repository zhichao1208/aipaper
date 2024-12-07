import streamlit as st
import os
import json
import time
from datetime import datetime
from nlm_client import NotebookLMClient
from podbean_client import PodbeanClient
from cloudinary_storage import CloudStorage

# Page config
st.set_page_config(
    page_title="AI Paper+",
    page_icon="📚",
    layout="centered"
)

# Initialize session state variables
if 'should_stop_check' not in st.session_state:
    st.session_state.should_stop_check = False

# Status mapping
status_mapping = {
    "unknown": "⏳ Unknown Status",
    "pending": "⏳ Pending",
    "processing": "🔄 Processing",
    "completed": "✅ Completed",
    "failed": "❌ Failed",
    "error": "❌ Error"
}
