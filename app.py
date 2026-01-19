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
# 2. CONSTANTS
# -----------------------------------------------------------------------------
BOOKING_HEADERS = ["ID", "Booked By", "Mobile Number", "Date", "Start Time", "End Time", "Per Hour", "Total Fee", "Advance", "Advance Mode", "Final Payment", "Final Mode", "Updated By"]
STUDENT_HEADERS = ["ID", "Name", "Mobile Number", "DOJ", "DOB", "Student ID", "Uniform Size", "Coaching Plan", "Coaching Fee", "Active", "Comments"]
FEES_HEADERS = ["ID", "Student", "Date", "Month", "Year", "Amount", "Payment Mode", "Comments"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def clean_phone(n):
    num = re.sub(r'\D', '', str(n))
    return f"91{num}" if len(num) == 10 else num

def convert_to_12h(time_str):
    try: return datetime.strptime(str(time_str)[:5], "%H:%M").strftime("%I:%M %p")
    except: return str(time_str)

# -----------------------------------------------------------------------------
# 3. DATA ENGINE
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(ws, headers):
    try:
        df = conn.read(worksheet=ws, ttl=0)
        if df.empty: return pd.DataFrame(columns=headers)
        # Standardize headers to Title Case for reliability
        df.columns = [str(c).strip().title() for c in df.columns]
        for h in headers:
            if h not in df.columns: df[h] = ""
        return df
    except: return pd.DataFrame(columns=headers)

def save_data(ws, df):
    conn.update(worksheet=ws, data=df)

# -----------------------------------------------------------------------------
# 4. BOOKING MANAGER
# -----------------------------------------------------------------------------
def booking_manager():
    st.header("🏏 Booking Manager")
    df = load_data("Booking", BOOKING_HEADERS)

    with st.expander("➕ Add New Booking"):
        with st.form("new_b"):
            c1, c2, c3 = st.columns(3)
            b_name = c1.text_input("Booked By")
            b_mob = c2.text_input("Mobile Number")
            b_date = c3.date_input("Date")
            
            c4, c5, c6 = st.columns(3)
            # Standardizing slot increments
            time_slots = [f"{h:02d}:{m:02d}" for h in range(6, 24) for m in [0, 30]]
            b_start = c4.selectbox("Start", time_slots, index=time_slots.index("20:30"))
            b_end = c5.selectbox("End", time_slots, index=time_slots.index("21:30"))
            b_rate = c6.number_input("Per Hour", value=1000)
            
            if st.form_submit_button("Confirm"):
                nid = str(uuid.uuid4())[:8]
                new_row = pd.DataFrame([{
                    "ID": nid, "Booked By": b_name, "Mobile Number": b_mob, 
                    "Date": b_date.strftime("%Y-%m-%d"), "Start Time": b_start, 
                    "End Time": b_end, "Per Hour": b_rate, "Total Fee": b_rate, "Advance": 0
                }])
                save_data("Booking", pd.concat([df, new_row], ignore_index=True))
                st.success("Booking Saved!")
                st.rerun()

    st.subheader("📅 Schedule")
    if not df.empty:
        # Standardize sorting key
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.sort_values(by=['Date', 'Start Time'], ascending=[True, True])
        
        upcoming = df[df['Date'].dt.date >= datetime.now().date()].copy()
        if not upcoming.empty:
            upcoming['S.No'] = range(1, len(upcoming) + 1)
            upcoming['Display Date'] = upcoming['Date'].dt.strftime('%d-%b-%Y')
            upcoming['Formatted Time'] = upcoming['Start Time'].apply(convert_to_12h) + " - " + upcoming['End Time'].apply(convert_to_12h)
            
            st.dataframe(
                upcoming, 
                column_order=["S.No", "Display Date", "Formatted Time", "Booked By", "Mobile Number", "Total Fee"], 
                use_container_width=True, hide_index=True
            )

# -----------------------------------------------------------------------------
# 5. ACADEMY MANAGEMENT
# -----------------------------------------------------------------------------
def academy_management():
    st.header("🎓 Academy Management")
    if 'edit_sid' not in st.session_state: st.session_state.edit_sid = None
    
    t1, t2 = st.tabs(["👥 Students", "💰 Fees"])
    s_df = load_data("Student Details", STUDENT_HEADERS)
    f_df = load_data("Fees Payment", FEES_HEADERS)

    with t1:
        if st.session_state.edit_sid:
            record = s_df[s_df['ID'] == st.session_state.edit_sid].iloc[0]
            if st.button("🔙 Back"): st.session_state.edit_sid = None; st.rerun()
            with st.form("edit_student"):
                u_name = st.text_input("Name", value=str(record['Name']))
                u_active = st.checkbox("Active", value=(str(record['Active']).upper() == 'TRUE'))
                if st.form_submit_button("Update"):
                    idx = s_df.index[s_df['ID'] == st.session_state.edit_sid][0]
                    s_df.loc[idx, ['Name', 'Active']] = [u_name, str(u_active).upper()]
                    save_data("Student Details", s_df)
                    st.session_state.edit_sid = None; st.rerun()
        else:
            with st.expander("➕ Register New Student"):
                with st.form("reg_s"):
                    n_name, n_mob = st.columns(2)
                    name = n_name.text_input("Name")
                    mob = n_mob.text_input("Mobile")
                    if st.form_submit_button("Register"):
                        nid = str(uuid.uuid4())[:8]
                        new_s = pd.DataFrame([{"ID": nid, "Name": name, "Mobile Number": mob, "Active": "TRUE", "Coaching Fee": 3000, "DOJ": datetime.now().strftime("%Y-%m-%d")}])
                        save_data("Student Details", pd.concat([s_df, new_s], ignore_index=True))
                        st.success("Registered!")
                        st.rerun()
            
            for _, row in s_df.iterrows():
                with st.container(border=True):
                    ci, cb = st.columns([4,1])
                    st_icon = "🟢" if str(row['Active']).upper() == 'TRUE' else "🔴"
                    ci.write(f"{st_icon} **{row['Name']}** | {row['Mobile Number']}")
                    if cb.button("Edit", key=str(row['ID'])):
                        st.session_state.edit_sid = row['ID']; st.rerun()

    with t2:
        active_s = s_df[s_df['Active'].astype(str).str.upper() == 'TRUE']
        if not active_s.empty:
            with st.form("fee_collection"):
                sel_name = st.selectbox("Student", active_s['Name'].tolist())
                sel_row = active_s[active_s['Name'] == sel_name].iloc[0]
                month = st.selectbox("Month", MONTHS, index=datetime.now().month-1)
                amt = st.number_input("Amount", value=int(sel_row['Coaching Fee']))
                if st.form_submit_button("Pay & Send Receipt"):
                    pid = str(uuid.uuid4())[:8]
                    new_p = pd.DataFrame([{"ID": pid, "Student": sel_row['ID'], "Date": datetime.now().strftime("%Y-%m-%d"), "Month": month, "Amount": amt}])
                    save_data("Fees Payment", pd.concat([f_df, new_p], ignore_index=True))
                    
                    # WhatsApp Text generation
                    wa_msg = f"🧾 *FEE RECEIPT*\nName: {sel_name}\nMonth: {month}\nAmount: ₹{amt}\nStatus: Paid. Thank you!"
                    wa_url = f"https://wa.me/{clean_phone(sel_row['Mobile Number'])}?text={urllib.parse.quote(wa_msg)}"
                    st.success("Payment Recorded!")
                    st.link_button("📲 Send WhatsApp Receipt", wa_url)

# -----------------------------------------------------------------------------
# 6. EXECUTION
# -----------------------------------------------------------------------------
if menu == "🏏 Booking Manager": booking_manager()
else: academy_management()
