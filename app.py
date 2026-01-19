import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import urllib.parse 
import re 
import uuid

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Sai Star Management", layout="wide")

with st.sidebar:
    st.image("Sai_Star_logo__2_-removebg-preview.png", use_container_width=True)
    menu = st.radio("Navigation", ["🏏 Booking Manager", "🎓 Academy Management"])

# -----------------------------------------------------------------------------
# 2. CONSTANTS & HELPERS
# -----------------------------------------------------------------------------
# These now match your EXACT Excel column names
BOOKING_HEADERS = ["ID", "Booked By", "Mobile Number", "Date", "Start Time", "End Time", "Per Hour", "Total Fee", "Advance", "Advance Mode", "Final Payment", "Final Mode", "Updated By"]
STUDENT_HEADERS = ["ID", "Name", "Mobile Number", "DOJ", "DOB", "Student ID", "Uniform Size", "Coaching Plan", "Coaching Fee", "Active", "Comments"]

def clean_phone_number(number):
    num_str = re.sub(r'\D', '', str(number))
    return f"91{num_str}" if len(num_str) == 10 else num_str

def convert_to_12h(time_str):
    try:
        # Handles cases like '20:30:00' or '20:30'
        return datetime.strptime(str(time_range)[:5], "%H:%M").strftime("%I:%M %p")
    except: return str(time_str)

# -----------------------------------------------------------------------------
# 3. ROBUST DATA LOADING
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name, expected_headers):
    try:
        df = conn.read(worksheet=sheet_name, ttl=0)
        if df.empty:
            return pd.DataFrame(columns=expected_headers)
        
        # Ensure all expected headers exist (prevents KeyErrors)
        for col in expected_headers:
            if col not in df.columns:
                df[col] = ""
        return df
    except Exception as e:
        st.error(f"Error loading '{sheet_name}': {e}")
        return pd.DataFrame(columns=expected_headers)

# -----------------------------------------------------------------------------
# 4. BOOKING MANAGER
# -----------------------------------------------------------------------------
def booking_manager():
    st.header("🏏 Booking Manager")
    
    df = load_data("Booking", BOOKING_HEADERS)

    # --- 1. ADD NEW BOOKING ---
    with st.expander("➕ Add New Booking"):
        with st.form("new_booking_form"):
            c1, c2, c3 = st.columns(3)
            b_name = c1.text_input("Booked By")
            b_mob = c2.text_input("Mobile Number")
            b_date = c3.date_input("Date")
            
            c4, c5, c6 = st.columns(3)
            b_start = c4.time_input("Start Time", value=datetime.strptime("20:30", "%H:%M"))
            b_end = c5.time_input("End Time", value=datetime.strptime("21:30", "%H:%M"))
            b_rate = c6.number_input("Per Hour Fee", value=1000)
            
            if st.form_submit_button("Confirm Booking"):
                new_id = str(uuid.uuid4())[:8]
                new_row = pd.DataFrame([{
                    "ID": new_id, "Booked By": b_name, "Mobile Number": b_mob,
                    "Date": b_date.strftime("%Y-%m-%d"), 
                    "Start Time": b_start.strftime("%H:%M:%S"),
                    "End Time": b_end.strftime("%H:%M:%S"),
                    "Per Hour": b_rate, "Total Fee": b_rate, # Simplified for now
                    "Advance": 0, "Advance Mode": "Cash", "Updated By": "Admin"
                }])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(worksheet="Booking", data=updated_df)
                st.success("Booking Saved!")
                st.rerun()

    # --- 2. UPCOMING GRID ---
    st.subheader("📅 Schedule")
    if not df.empty:
        # Filter for upcoming
        df['Date'] = pd.to_datetime(df['Date'])
        today = pd.to_datetime(datetime.now().date())
        upcoming = df[df['Date'] >= today].copy()
        
        if upcoming.empty:
            st.info("No upcoming bookings found.")
        else:
            # Sort by Date and Time
            upcoming = upcoming.sort_values(by=['Date', 'Start Time'])
            
            # Formatting for display
            display_df = upcoming.copy()
            display_df['Date'] = display_df['Date'].dt.strftime('%d-%b-%Y')
            
            st.dataframe(
                display_df,
                column_order=["Date", "Start Time", "End Time", "Booked By", "Mobile Number", "Total Fee", "Advance"],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.warning("The 'Booking' sheet is empty. Add a booking above to see it here.")

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
if menu == "🏏 Booking Manager":
    booking_manager()
else:
    st.info("Academy Management Screen is active. Select 'Booking Manager' in sidebar.")
