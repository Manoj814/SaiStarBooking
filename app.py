import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import urllib.parse 
import re 
import uuid

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & NAVIGATION
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Sai Star Management", layout="wide")

with st.sidebar:
    st.image("Sai_Star_logo__2_-removebg-preview.png", use_container_width=True)
    menu = st.radio("Navigation", ["🏏 Booking Manager", "🎓 Academy Management"])

# -----------------------------------------------------------------------------
# 2. CONSTANTS & HELPERS
# -----------------------------------------------------------------------------
# These will be matched regardless of capital letters
BOOKING_HEADERS = ["ID", "Booked By", "Mobile Number", "Date", "Start Time", "End Time", "Per Hour", "Total Fee", "Advance", "Advance Mode", "Final Payment", "Final Mode", "Updated By"]
STUDENT_HEADERS = ["ID", "Name", "Mobile Number", "DOJ", "DOB", "Student ID", "Uniform Size", "Coaching Plan", "Coaching Fee", "Active", "Comments"]

def clean_phone_number(number):
    num_str = re.sub(r'\D', '', str(number))
    return f"91{num_str}" if len(num_str) == 10 else num_str

# -----------------------------------------------------------------------------
# 3. ROBUST DATA LOADING (FIXED FOR KEYERROR)
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name, expected_headers):
    try:
        df = conn.read(worksheet=sheet_name, ttl=0)
        if df.empty:
            return pd.DataFrame(columns=expected_headers)
        
        # --- FIX: Standardize column names to Title Case ---
        # This converts "date" or "DATE" to "Date" to match our constants
        df.columns = [str(c).strip().title() for c in df.columns]
        
        # Ensure all expected headers exist
        for col in expected_headers:
            if col not in df.columns:
                df[col] = ""
        return df
    except Exception as e:
        st.error(f"Error loading '{sheet_name}': {e}")
        return pd.DataFrame(columns=expected_headers)

def save_data(sheet_name, df):
    # Ensure columns match sheet headers before saving
    conn.update(worksheet=sheet_name, data=df)

# -----------------------------------------------------------------------------
# 4. BOOKING MANAGER
# -----------------------------------------------------------------------------
def booking_manager():
    st.header("🏏 Booking Manager")
    
    # Load standardized data
    df = load_data("Booking", BOOKING_HEADERS)

    # --- ADD NEW BOOKING ---
    with st.expander("➕ Add New Booking"):
        with st.form("new_booking"):
            c1, c2, c3 = st.columns(3)
            b_name = c1.text_input("Booked By")
            b_mob = c2.text_input("Mobile Number")
            b_date = c3.date_input("Date")
            
            c4, c5, c6 = st.columns(3)
            b_start = c4.selectbox("Start Time", [f"{h:02d}:{m:02d}" for h in range(6, 24) for m in [0, 30]], index=28)
            b_end = c5.selectbox("End Time", [f"{h:02d}:{m:02d}" for h in range(6, 24) for m in [0, 30]], index=30)
            b_rate = c6.number_input("Per Hour", value=1000)
            
            if st.form_submit_button("Confirm Booking"):
                new_id = str(uuid.uuid4())[:8]
                new_row = pd.DataFrame([{
                    "ID": new_id, "Booked By": b_name, "Mobile Number": b_mob, 
                    "Date": b_date.strftime("%Y-%m-%d"), 
                    "Start Time": b_start, "End Time": b_end, 
                    "Per Hour": b_rate, "Total Fee": b_rate, 
                    "Advance": 0, "Updated By": "Admin"
                }])
                save_data("Booking", pd.concat([df, new_row], ignore_index=True))
                st.success("Booking Added!")
                st.rerun()

    # --- UPCOMING GRID ---
    st.subheader("📅 Schedule")
    if not df.empty:
        # Now 'Date' is guaranteed to exist because of standardizing in load_data
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        today = pd.to_datetime(datetime.now().date())
        upcoming = df[df['Date'] >= today].copy()
        
        if not upcoming.empty:
            upcoming = upcoming.sort_values(by=['Date', 'Start Time'])
            upcoming['Display Date'] = upcoming['Date'].dt.strftime('%d-%b-%Y')
            
            st.dataframe(
                upcoming,
                column_order=["Display Date", "Start Time", "End Time", "Booked By", "Mobile Number", "Total Fee"],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No upcoming bookings.")
    else:
        st.warning("Booking sheet is empty.")

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
if menu == "🏏 Booking Manager":
    booking_manager()
else:
    st.info("Navigate to Academy Management in Sidebar")
