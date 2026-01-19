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
    st.divider()

# -----------------------------------------------------------------------------
# 2. CONSTANTS & HELPERS
# -----------------------------------------------------------------------------
BOOKING_HEADERS = ["ID", "Booked By", "Mobile Number", "Date", "Start Time", "End Time", "Per Hour", "Total Fee", "Advance", "Advance Mode", "Final Payment", "Final Mode", "Updated By"]
STUDENT_HEADERS = ["ID", "Name", "Mobile Number", "DOJ", "DOB", "Student ID", "Uniform Size", "Coaching Plan", "Coaching Fee", "Active", "Comments"]
FEES_HEADERS = ["ID", "Student", "Date", "Month", "Year", "Amount", "Payment Mode", "Comments"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def clean_phone_number(number):
    num_str = re.sub(r'\D', '', str(number))
    return f"91{num_str}" if len(num_str) == 10 else num_str

def convert_to_12h(time_str):
    try: return datetime.strptime(str(time_str)[:5], "%H:%M").strftime("%I:%M %p")
    except: return str(time_str)

# -----------------------------------------------------------------------------
# 3. ROBUST DATA LOADING
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name, expected_headers):
    try:
        df = conn.read(worksheet=sheet_name, ttl=0)
        if df.empty: return pd.DataFrame(columns=expected_headers)
        
        # Standardize headers to Title Case to prevent KeyErrors
        df.columns = [str(c).strip().title() for c in df.columns]
        
        for col in expected_headers:
            if col not in df.columns: df[col] = ""
            
        # Clean Academy Active status
        if 'Active' in df.columns:
            df['Active'] = df['Active'].astype(str).str.upper().map({'TRUE': True, 'FALSE': False, '1': True, '0': False})
            
        return df
    except Exception as e:
        st.error(f"Error loading {sheet_name}: {e}")
        return pd.DataFrame(columns=expected_headers)

def save_data(sheet_name, df):
    conn.update(worksheet=sheet_name, data=df)

# -----------------------------------------------------------------------------
# 4. BOOKING MANAGER
# -----------------------------------------------------------------------------
def booking_manager():
    st.header("🏏 Booking Manager")
    df = load_data("Booking", BOOKING_HEADERS)

    # Add New Booking Form
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
            
            if st.form_submit_button("Confirm"):
                new_id = str(uuid.uuid4())[:8]
                new_row = pd.DataFrame([{"ID": new_id, "Booked By": b_name, "Mobile Number": b_mob, "Date": b_date.strftime("%Y-%m-%d"), "Start Time": b_start, "End Time": b_end, "Per Hour": b_rate, "Total Fee": b_rate, "Advance": 0}])
                save_data("Booking", pd.concat([df, new_row]))
                st.rerun()

    # Schedule Table
    st.subheader("📅 Schedule")
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        # Sort by Date and Time
        df = df.sort_values(by=['Date', 'Start Time'], ascending=[True, True])
        
        today = pd.to_datetime(datetime.now().date())
        upcoming = df[df['Date'] >= today].copy()
        
        if not upcoming.empty:
            upcoming['Display Date'] = upcoming['Date'].dt.strftime('%d-%b-%Y')
            st.dataframe(upcoming, column_order=["Display Date", "Start Time", "End Time", "Booked By", "Mobile Number", "Total Fee"], use_container_width=True, hide_index=True)
        else: st.info("No upcoming bookings.")

# -----------------------------------------------------------------------------
# 5. ACADEMY MANAGEMENT
# -----------------------------------------------------------------------------
def academy_management():
    st.header("🎓 Academy Management")
    if 'edit_student_id' not in st.session_state: st.session_state.edit_student_id = None
    
    tab1, tab2 = st.tabs(["👥 Students", "💰 Fees"])
    students_df = load_data("Student Details", STUDENT_HEADERS)
    fees_df = load_data("Fees Payment", FEES_HEADERS)

    with tab1:
        if st.session_state.edit_student_id:
            # Edit Mode
            record = students_df[students_df['ID'] == st.session_state.edit_student_id].iloc[0]
            if st.button("🔙 Back"): st.session_state.edit_student_id = None; st.rerun()
            with st.form("edit_s"):
                u_name = st.text_input("Name", value=record['Name'])
                u_active = st.checkbox("Active", value=record['Active'])
                if st.form_submit_button("Update"):
                    idx = students_df.index[students_df['ID'] == st.session_state.edit_student_id][0]
                    students_df.loc[idx, ['Name', 'Active']] = [u_name, u_active]
                    save_data("Student Details", students_df)
                    st.session_state.edit_student_id = None; st.rerun()
        else:
            # List Mode
            for _, row in students_df.iterrows():
                with st.container(border=True):
                    c_i, c_b = st.columns([4,1])
                    c_i.write(f"**{row['Name']}** | {row['Mobile Number']}")
                    if c_b.button("Edit ✏️", key=row['ID']):
                        st.session_state.edit_student_id = row['ID']; st.rerun()

    with tab2:
        # Fee logic here
        st.info("Fee Collection Module Ready.")

# -----------------------------------------------------------------------------
# 6. EXECUTION
# -----------------------------------------------------------------------------
if menu == "🏏 Booking Manager": booking_manager()
else: academy_management()
