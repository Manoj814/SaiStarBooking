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

# Sidebar for Navigation
with st.sidebar:
    st.image("Sai_Star_logo__2_-removebg-preview.png", use_container_width=True)
    menu = st.radio("Navigation", ["🏏 Booking Manager", "🎓 Academy Management"])
    st.divider()
    st.caption("v2.0 - Student Management Integrated")

# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# -----------------------------------------------------------------------------
BOOKING_HEADERS = [
    "id", "booking_date", "start_time", "end_time", 
    "total_hours", "rate_per_hour", "total_charges", 
    "booked_by", "mobile_number", "advance_paid", "advance_mode", 
    "balance_paid", "balance_mode", 
    "remaining_due", "remarks"
]

STUDENT_HEADERS = [
    "ID", "Name", "Mobile Number", "DOJ", "DOB", "Student ID", 
    "Uniform Size", "Coaching Plan", "Coaching Fee", "Active", "Comments"
]

FEES_HEADERS = [
    "ID", "Student", "Date", "Month", "Year", "Amount", "Payment Mode", "Comments"
]

PAYMENT_MODES = ["Cash", "Gpay", "Pending", "Cash+Gpay"]
MONTHS = ["January", "February", "March", "April", "May", "June", 
          "July", "August", "September", "October", "November", "December"]

def clean_phone_number(number):
    num_str = re.sub(r'\D', '', str(number))
    if len(num_str) == 10: return f"91{num_str}"
    return num_str

def convert_to_12h(time_str):
    try: return datetime.strptime(time_str, "%H:%M").strftime("%I:%M %p")
    except: return time_str

def get_time_slots(start_h=0, end_h=23, after_time=None):
    slots = []
    start = datetime.strptime(f"{start_h:02d}:00", "%H:%M")
    end = datetime.strptime(f"{end_h:02d}:30", "%H:%M")
    current = start
    while current <= end:
        time_str = current.strftime("%H:%M")
        if after_time:
            if time_str > after_time: slots.append(time_str)
        else: slots.append(time_str)
        current += timedelta(minutes=30)
    return slots

# -----------------------------------------------------------------------------
# 3. DATA CONNECTION (GOOGLE SHEETS)
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def get_sheet_data(worksheet_name, headers):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df.empty: return pd.DataFrame(columns=headers)
        # Standardize columns to match headers exactly as in the sheet for gsheets update to work
        return df
    except:
        return pd.DataFrame(columns=headers)

def save_sheet_data(worksheet_name, df):
    conn.update(worksheet=worksheet_name, data=df)

# -----------------------------------------------------------------------------
# 4. BOOKING MANAGER MODULE
# -----------------------------------------------------------------------------
def booking_manager():
    st.markdown("""<style>.block-container {padding-top: 1rem !important;} header {visibility: hidden;}</style>""", unsafe_allow_html=True)
    
    # Init state
    if 'form_id' not in st.session_state: st.session_state['form_id'] = 0 
    if 'edit_mode' not in st.session_state: st.session_state['edit_mode'] = False
    
    df = get_sheet_data("Booking", BOOKING_HEADERS)
    df.columns = [str(c).lower().strip() for c in df.columns]

    # Pre-process sorting key
    if not df.empty:
        df['start_time'] = df['start_time'].astype(str).apply(lambda x: datetime.strptime(x, "%H:%M").strftime("%H:%M") if ":" in x else "00:00")
        df['sort_key'] = pd.to_datetime(df['booking_date']).dt.strftime('%Y%m%d') + df['start_time'].str.replace(':', '')
        df['sort_key'] = pd.to_numeric(df['sort_key'])
        df = df.sort_values(by='sort_key', ascending=True)

    if st.session_state.get('edit_mode'):
        # --- EDIT BOOKING ---
        record = df[df['id'] == st.session_state['edit_id']].iloc[0]
        st.subheader(f"✏️ Edit Booking: {record['booked_by']}")
        with st.form("edit_booking"):
            c1, c2, c3 = st.columns(3)
            e_date = c1.date_input("Date", value=pd.to_datetime(record['booking_date']))
            e_name = c2.text_input("Name", value=str(record['booked_by']))
            e_mobile = c3.text_input("Mobile", value=str(record['mobile_number']))
            
            ts = get_time_slots(0, 23)
            c4, c5, c6 = st.columns(3)
            e_start = c4.selectbox("Start", ts, index=ts.index(record['start_time']) if record['start_time'] in ts else 0, format_func=convert_to_12h)
            e_end = c5.selectbox("End", get_time_slots(0,23, after_time=e_start), format_func=convert_to_12h)
            e_rate = c6.number_input("Rate", value=int(record.get('rate_per_hour', 1000)))
            
            c7, c8, c9 = st.columns(3)
            e_adv = c7.number_input("Advance", value=int(record.get('advance_paid', 0)))
            e_bal = c8.number_input("Balance Paid", value=int(record.get('balance_paid', 0)))
            e_mode = c9.selectbox("Mode", PAYMENT_MODES, index=0)
            
            col_s, col_d, col_c = st.columns([1, 1, 3])
            if col_s.form_submit_button("Save", type="primary"):
                dur = (datetime.strptime(e_end, "%H:%M") - datetime.strptime(e_start, "%H:%M")).total_seconds() / 3600
                tot = int(dur * e_rate)
                idx = df.index[df['id'] == st.session_state['edit_id']][0]
                df.loc[idx, ['booking_date','booked_by','mobile_number','start_time','end_time','total_charges','advance_paid','balance_paid','remaining_due','advance_mode']] = [e_date.strftime("%Y-%m-%d"), e_name, e_mobile, e_start, e_end, tot, e_adv, e_bal, int(tot-e_adv-e_bal), e_mode]
                save_sheet_data("Booking", df.drop(columns=['sort_key'], errors='ignore'))
                st.session_state.edit_mode = False
                st.rerun()
            if col_d.form_submit_button("Delete"):
                save_sheet_data("Booking", df[df['id'] != st.session_state['edit_id']].drop(columns=['sort_key'], errors='ignore'))
                st.session_state.edit_mode = False
                st.rerun()
            if col_c.form_submit_button("Cancel"):
                st.session_state.edit_mode = False
                st.rerun()
    else:
        # --- ADD BOOKING ---
        with st.expander("➕ New Booking"):
            with st.form("new_booking", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                b_date = c1.date_input("Date")
                b_name = c2.text_input("Name")
                b_mobile = c3.text_input("Mobile")
                
                ts = get_time_slots(6, 23)
                c4, c5, c6 = st.columns(3)
                b_start = c4.selectbox("Start", ts, index=ts.index("20:00"))
                b_end = c5.selectbox("End", get_time_slots(6,23, after_time=b_start), index=1)
                b_rate = c6.number_input("Rate", value=1000)
                b_adv = st.number_input("Advance", value=0)
                
                if st.form_submit_button("Confirm", type="primary"):
                    dur = (datetime.strptime(b_end, "%H:%M") - datetime.strptime(b_start, "%H:%M")).total_seconds() / 3600
                    tot = int(dur * b_rate)
                    nid = str(uuid.uuid4())[:8]
                    new_row = pd.DataFrame([{"id": nid, "booking_date": b_date.strftime("%Y-%m-%d"), "start_time": b_start, "end_time": b_end, "booked_by": b_name, "mobile_number": b_mobile, "total_charges": tot, "advance_paid": b_adv, "remaining_due": tot-b_adv, "advance_mode": "Pending"}])
                    save_sheet_data("Booking", pd.concat([df.drop(columns=['sort_key'], errors='ignore'), new_row]))
                    st.success("Booking Added!")
                    st.rerun()

        st.subheader("📅 Schedule")
        if not df.empty:
            now_key = int(datetime.now().strftime('%Y%m%d%H%M'))
            future_df = df[df['sort_key'] >= now_key].copy()
            if not future_df.empty:
                future_df['S.No'] = range(1, len(future_df) + 1)
                future_df['Chat 📲'] = future_df.apply(lambda r: f"https://wa.me/{clean_phone_number(r['mobile_number'])}", axis=1)
                grid_cols = {"S.No": st.column_config.NumberColumn(width="small"), "total_charges": "Total", "advance_paid": "Adv", "remaining_due": "Due", "Chat 📲": st.column_config.LinkColumn()}
                ev = st.dataframe(future_df, column_config=grid_cols, column_order=["S.No", "booking_date", "start_time", "end_time", "booked_by", "total_charges", "remaining_due", "Chat 📲"], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
                if ev.selection.rows:
                    st.session_state.update({'edit_mode': True, 'edit_id': future_df.iloc[ev.selection.rows[0]]['id']})
                    st.rerun()

# -----------------------------------------------------------------------------
# 5. ACADEMY MANAGEMENT MODULE
# -----------------------------------------------------------------------------
def academy_management():
    st.header("🎓 Student & Academy Management")
    
    tab1, tab2, tab3 = st.tabs(["👥 Students", "💰 Fees Collection", "📜 Payment History"])
    
    # Load Data
    students_df = get_sheet_data("Student Details", STUDENT_HEADERS)
    fees_df = get_sheet_data("Fees Payment", FEES_HEADERS)
    plans_df = get_sheet_data("Coaching Plan", ["Plan", "Plan Fee"])

    # --- TAB 1: STUDENT PROFILES ---
    with tab1:
        st.subheader("Student Database")
        with st.expander("➕ Register New Student"):
            with st.form("new_student", clear_on_submit=True):
                c1, c2 = st.columns(2)
                s_name = c1.text_input("Full Name")
                s_mobile = c2.text_input("Mobile Number")
                c3, c4, c5 = st.columns(3)
                s_doj = c3.date_input("Date of Joining", value=datetime.now())
                s_dob = c4.date_input("Date of Birth", value=datetime(2010, 1, 1))
                s_size = c5.selectbox("Uniform Size", ["28", "30", "32", "34", "36", "38", "40"])
                
                c6, c7 = st.columns(2)
                s_plan = c6.selectbox("Coaching Plan", plans_df["Plan"].tolist() if not plans_df.empty else ["6 Days Weekly", "3 Days Weekly"])
                # Auto-fetch fee
                base_fee = 3000
                if not plans_df.empty:
                    base_fee = plans_df[plans_df["Plan"] == s_plan]["Plan Fee"].iloc[0]
                s_fee = c7.number_input("Monthly Fee", value=int(base_fee))
                
                if st.form_submit_button("Register Student", type="primary"):
                    new_id = str(uuid.uuid4())[:8]
                    new_student = pd.DataFrame([{
                        "ID": new_id, "Name": s_name, "Mobile Number": s_mobile,
                        "DOJ": s_doj.strftime("%Y-%m-%d"), "DOB": s_dob.strftime("%Y-%m-%d"),
                        "Uniform Size": s_size, "Coaching Plan": s_plan, 
                        "Coaching Fee": s_fee, "Active": True, "Comments": ""
                    }])
                    save_sheet_data("Student Details", pd.concat([students_df, new_student]))
                    st.success(f"Registered {s_name} successfully!")
                    st.rerun()

        if not students_df.empty:
            search = st.text_input("🔍 Search Student by Name", "").lower()
            disp_students = students_df[students_df['Name'].str.lower().contains(search)] if search else students_df
            st.dataframe(disp_students, use_container_width=True, hide_index=True)
        else:
            st.info("No students registered yet.")

    # --- TAB 2: FEES COLLECTION ---
    with tab2:
        st.subheader("Record Fee Payment")
        if students_df.empty:
            st.warning("Please add students first.")
        else:
            active_students = students_df[students_df['Active'] == True]
            with st.form("fee_collection", clear_on_submit=True):
                s_choice = st.selectbox("Select Student", active_students['Name'].tolist())
                s_row = active_students[active_students['Name'] == s_choice].iloc[0]
                
                c1, c2, c3 = st.columns(3)
                f_date = c1.date_input("Payment Date")
                f_month = c2.selectbox("For Month", MONTHS, index=datetime.now().month - 1)
                f_year = c3.selectbox("Year", [2024, 2025, 2026], index=2)
                
                c4, c5 = st.columns(2)
                f_amount = c4.number_input("Amount Paid", value=int(s_row['Coaching Fee']))
                f_mode = c5.selectbox("Payment Mode", ["Cash", "UPI", "Bank Transfer"])
                f_comm = st.text_input("Comments")
                
                if st.form_submit_button("Record Payment", type="primary"):
                    p_id = str(uuid.uuid4())[:8]
                    new_payment = pd.DataFrame([{
                        "ID": p_id, "Student": s_row['ID'], "Date": f_date.strftime("%Y-%m-%d"),
                        "Month": f_month, "Year": f_year, "Amount": f_amount,
                        "Payment Mode": f_mode, "Comments": f_comm
                    }])
                    save_sheet_data("Fees Payment", pd.concat([fees_df, new_payment]))
                    st.success(f"Payment of ₹{f_amount} recorded for {s_choice}")
                    st.rerun()

    # --- TAB 3: PAYMENT HISTORY ---
    with tab3:
        st.subheader("Recent Transactions")
        if not fees_df.empty and not students_df.empty:
            # Merge with student names for better display
            history = fees_df.merge(students_df[['ID', 'Name']], left_on='Student', right_on='ID', how='left')
            history = history.drop(columns=['Student', 'ID_y']).rename(columns={'ID_x': 'Receipt ID', 'Name': 'Student Name'})
            history = history.sort_values(by='Date', ascending=False)
            
            st.dataframe(history, use_container_width=True, hide_index=True)
            
            # Download as CSV
            csv = history.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Fee Report", csv, "fee_report.csv", "text/csv")
        else:
            st.info("No payment history found.")

# -----------------------------------------------------------------------------
# 6. MAIN EXECUTION
# -----------------------------------------------------------------------------
if menu == "🏏 Booking Manager":
    booking_manager()
else:
    academy_management()
