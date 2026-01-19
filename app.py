import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import io
import os 
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

PAYMENT_MODES = ["Cash", "UPI", "Gpay", "Pending"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def clean_phone_number(number):
    num_str = re.sub(r'\D', '', str(number))
    return f"91{num_str}" if len(num_str) == 10 else num_str

def convert_to_12h(time_str):
    try:
        # Standardize 20:30:00 or 20:30 to 08:30 PM
        return datetime.strptime(str(time_str)[:5], "%H:%M").strftime("%I:%M %p")
    except: return str(time_str)

# -----------------------------------------------------------------------------
# 3. DATA LOADING (FIXED FOR MATCHING COLUMN NAMES)
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name, expected_headers):
    try:
        df = conn.read(worksheet=sheet_name, ttl=0)
        if df.empty: return pd.DataFrame(columns=expected_headers)
        
        # Standardize column names to match Title Case in your Excel
        df.columns = [str(c).strip().title() for c in df.columns]
        
        # Ensure all expected headers exist
        for col in expected_headers:
            if col not in df.columns: df[col] = ""
        
        # Clean Active Status for Students
        if 'Active' in df.columns:
            df['Active'] = df['Active'].astype(str).str.upper().map({'TRUE': True, 'FALSE': False, '1': True, '0': False})
            
        return df
    except Exception as e:
        st.error(f"Error loading {sheet_name}: {e}")
        return pd.DataFrame(columns=expected_headers)

def save_data(sheet_name, df):
    # Standardize columns back to Sheet format
    conn.update(worksheet=sheet_name, data=df)

# -----------------------------------------------------------------------------
# 4. MODULE: BOOKING MANAGER
# -----------------------------------------------------------------------------
def booking_manager():
    st.header("🏏 Booking Manager")
    if 'edit_id' not in st.session_state: st.session_state.edit_id = None
    if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False

    df = load_data("Booking", BOOKING_HEADERS)

    # --- CHRONOLOGICAL SORTING ---
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        # Standardize 24h time string for sorting HH:MM
        df['_sort_time'] = df['Start Time'].astype(str).apply(lambda x: x[:5])
        df['sort_key'] = df['Date'].dt.strftime('%Y%m%d') + df['_sort_time'].str.replace(':', '')
        df['sort_key'] = pd.to_numeric(df['sort_key'], errors='coerce')
        df = df.sort_values(by='sort_key', ascending=True)

    # --- ADD NEW BOOKING ---
    with st.expander("➕ Add New Booking"):
        with st.form("new_booking_form"):
            c1, c2, c3 = st.columns(3)
            b_name = c1.text_input("Booked By")
            b_mob = c2.text_input("Mobile Number")
            b_date = c3.date_input("Date")
            
            c4, c5, c6 = st.columns(3)
            b_start = c4.selectbox("Start", [f"{h:02d}:{m:02d}" for h in range(6, 24) for m in [0, 30]], index=28) # 8:00 PM
            b_end = c5.selectbox("End", [f"{h:02d}:{m:02d}" for h in range(6, 24) for m in [0, 30]], index=30) # 9:00 PM
            b_rate = c6.number_input("Per Hour", value=1000)
            
            if st.form_submit_button("Confirm Booking", type="primary"):
                new_id = str(uuid.uuid4())[:8]
                new_row = pd.DataFrame([{"ID": new_id, "Booked By": b_name, "Mobile Number": b_mob, "Date": b_date.strftime("%Y-%m-%d"), "Start Time": b_start, "End Time": b_end, "Per Hour": b_rate, "Total Fee": b_rate, "Advance": 0, "Updated By": "Admin"}])
                save_data("Booking", pd.concat([df.drop(columns=['_sort_time', 'sort_key'], errors='ignore'), new_row], ignore_index=True))
                st.success("Booking Added!")
                st.rerun()

    # --- SCHEDULE GRID ---
    st.subheader("📅 Upcoming Schedule")
    if not df.empty:
        today = pd.to_datetime(datetime.now().date())
        upcoming = df[df['Date'] >= today].copy()
        
        if not upcoming.empty:
            upcoming['S.No'] = range(1, len(upcoming) + 1)
            upcoming['Time'] = upcoming['Start Time'].apply(convert_to_12h) + " - " + upcoming['End Time'].apply(convert_to_12h)
            
            st.dataframe(
                upcoming,
                column_order=["S.No", "Date", "Time", "Booked By", "Mobile Number", "Total Fee", "Advance"],
                use_container_width=True,
                hide_index=True
            )
        else: st.info("No upcoming bookings.")

# -----------------------------------------------------------------------------
# 5. MODULE: ACADEMY MANAGEMENT
# -----------------------------------------------------------------------------
def academy_management():
    st.header("🎓 Academy Management")
    if 'edit_student_id' not in st.session_state: st.session_state.edit_student_id = None
    
    tab1, tab2 = st.tabs(["👥 Student Profiles", "💰 Fee Payments"])
    students_df = load_data("Student Details", STUDENT_HEADERS)
    fees_df = load_data("Fees Payment", FEES_HEADERS)

    with tab1:
        if st.session_state.edit_student_id:
            # --- EDIT STUDENT ---
            record = students_df[students_df['ID'] == st.session_state.edit_student_id].iloc[0]
            if st.button("🔙 Back to List"): st.session_state.edit_student_id = None; st.rerun()
            
            with st.form("edit_s"):
                u_name = st.text_input("Name", value=record['Name'])
                u_mob = st.text_input("Mobile", value=record['Mobile Number'])
                u_active = st.checkbox("Active Student", value=record['Active'])
                u_fee = st.number_input("Monthly Fee", value=int(record['Coaching Fee']))
                
                if st.form_submit_button("Update"):
                    idx = students_df.index[students_df['ID'] == st.session_state.edit_student_id][0]
                    students_df.loc[idx, ['Name', 'Mobile Number', 'Active', 'Coaching Fee']] = [u_name, u_mob, u_active, u_fee]
                    save_data("Student Details", students_df)
                    st.session_state.edit_student_id = None; st.rerun()
        else:
            # --- STUDENT LIST ---
            with st.expander("➕ Register New Student"):
                with st.form("reg_s"):
                    n_name = st.text_input("Student Name")
                    n_mob = st.text_input("Mobile Number")
                    if st.form_submit_button("Register"):
                        new_id = str(uuid.uuid4())[:8]
                        new_s = pd.DataFrame([{"ID": new_id, "Name": n_name, "Mobile Number": n_mob, "DOJ": datetime.now().strftime("%Y-%m-%d"), "Active": True, "Coaching Fee": 3000}])
                        save_data("Student Details", pd.concat([students_df, new_s]))
                        st.success("Student Added!")
                        st.rerun()

            for _, row in students_df.iterrows():
                with st.container(border=True):
                    c_i, c_b = st.columns([4, 1])
                    status = "🟢" if row['Active'] else "🔴"
                    c_i.markdown(f"{status} **{row['Name']}** | {row['Mobile Number']}")
                    if col_b := c_b.button("Edit ✏️", key=f"s_{row['ID']}"):
                        st.session_state.edit_student_id = row['ID']
                        st.rerun()

    with tab2:
        # --- FEE COLLECTION ---
        active_list = students_df[students_df['Active'] == True]
        if not active_list.empty:
            with st.form("fee_pay"):
                s_name = st.selectbox("Select Student", active_list['Name'].tolist())
                s_data = active_list[active_list['Name'] == s_name].iloc[0]
                f_month = st.selectbox("Month", MONTHS, index=datetime.now().month-1)
                f_amt = st.number_input("Amount", value=int(s_data['Coaching Fee']))
                
                if st.form_submit_button("Record Payment"):
                    p_id = str(uuid.uuid4())[:8]
                    new_p = pd.DataFrame([{"ID": p_id, "Student": s_data['ID'], "Date": datetime.now().strftime("%Y-%m-%d"), "Month": f_month, "Year": 2026, "Amount": f_amt, "Payment Mode": "Gpay"}])
                    save_data("
