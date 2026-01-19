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
# 2. HELPER FUNCTIONS
# -----------------------------------------------------------------------------
STUDENT_HEADERS = ["ID", "Name", "Mobile Number", "DOJ", "DOB", "Student ID", "Uniform Size", "Coaching Plan", "Coaching Fee", "Active", "Comments"]
FEES_HEADERS = ["ID", "Student", "Date", "Month", "Year", "Amount", "Payment Mode", "Comments"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def clean_phone_number(number):
    num_str = re.sub(r'\D', '', str(number))
    return f"91{num_str}" if len(num_str) == 10 else num_str

def format_wa_student_welcome(name, sid):
    msg = (f"🏏 *Welcome to Sai Star Academy!* 🏏\n\n"
           f"Hello {name},\nYour registration is successful.\n"
           f"🆔 *Student ID:* {sid}\n\nWe look forward to seeing you at the crease!")
    return msg

def format_wa_fee_receipt(name, month, year, amount):
    msg = (f"🧾 *SAI STAR FEE RECEIPT* 🧾\n\n"
           f"Student: {name}\n"
           f"Period: {month} {year}\n"
           f"Amount Received: ₹{amount}\n\n"
           f"Thank you for the payment!")
    return msg

# -----------------------------------------------------------------------------
# 3. DATA CONNECTION
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def get_sheet_data(worksheet_name, headers):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        return df if not df.empty else pd.DataFrame(columns=headers)
    except: return pd.DataFrame(columns=headers)

def save_sheet_data(worksheet_name, df):
    conn.update(worksheet=worksheet_name, data=df)

# -----------------------------------------------------------------------------
# 4. ACADEMY MANAGEMENT MODULE
# -----------------------------------------------------------------------------
def academy_management():
    st.header("🎓 Student & Academy Management")
    
    # Init Session States for Editing
    if 'edit_student_id' not in st.session_state: st.session_state.edit_student_id = None
    
    tab1, tab2, tab3 = st.tabs(["👥 Students", "💰 Fees Collection", "📜 Payment History"])
    
    students_df = get_sheet_data("Student Details", STUDENT_HEADERS)
    fees_df = get_sheet_data("Fees Payment", FEES_HEADERS)
    plans_df = get_sheet_data("Coaching Plan", ["Plan", "Plan Fee"])

    # --- TAB 1: STUDENTS ---
    with tab1:
        # Edit View
        if st.session_state.edit_student_id:
            record = students_df[students_df['ID'] == st.session_state.edit_student_id].iloc[0]
            st.subheader(f"✏️ Editing: {record['Name']}")
            with st.form("edit_student_form"):
                col1, col2 = st.columns(2)
                u_name = col1.text_input("Name", value=record['Name'])
                u_mob = col2.text_input("Mobile", value=record['Mobile Number'])
                u_active = st.checkbox("Active Student", value=bool(record['Active']))
                u_plan = st.selectbox("Plan", plans_df["Plan"].tolist() if not plans_df.empty else ["6 Days", "3 Days"])
                u_fee = st.number_input("Fee", value=int(record['Coaching Fee']))
                
                c_save, c_cancel = st.columns([1,4])
                if c_save.form_submit_button("Update"):
                    idx = students_df.index[students_df['ID'] == st.session_state.edit_student_id][0]
                    students_df.loc[idx, ['Name', 'Mobile Number', 'Active', 'Coaching Plan', 'Coaching Fee']] = [u_name, u_mob, u_active, u_plan, u_fee]
                    save_sheet_data("Student Details", students_df)
                    st.session_state.edit_student_id = None
                    st.rerun()
                if c_cancel.form_submit_button("Cancel"):
                    st.session_state.edit_student_id = None
                    st.rerun()

        else:
            with st.expander("➕ Register New Student"):
                with st.form("new_student", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    s_name = c1.text_input("Full Name")
                    s_mobile = c2.text_input("Mobile Number")
                    s_id_proof = st.file_uploader("Upload ID Proof (Aadhar/Voter ID)", type=['png', 'jpg', 'jpeg', 'pdf'])
                    
                    c3, c4 = st.columns(2)
                    s_plan = c3.selectbox("Coaching Plan", plans_df["Plan"].tolist() if not plans_df.empty else ["6 Days", "3 Days"])
                    s_fee = c4.number_input("Monthly Fee", value=3000)
                    
                    if st.form_submit_button("Register Student"):
                        new_id = str(uuid.uuid4())[:8]
                        new_student = pd.DataFrame([{
                            "ID": new_id, "Name": s_name, "Mobile Number": s_mobile,
                            "DOJ": datetime.now().strftime("%Y-%m-%d"), "Active": True,
                            "Coaching Plan": s_plan, "Coaching Fee": s_fee, "Student ID": "File Uploaded" if s_id_proof else "No ID"
                        }])
                        save_sheet_data("Student Details", pd.concat([students_df, new_student]))
                        
                        # WhatsApp Link
                        wa_msg = format_wa_student_welcome(s_name, new_id)
                        wa_url = f"https://wa.me/{clean_phone_number(s_mobile)}?text={urllib.parse.quote(wa_msg)}"
                        st.success(f"Registered {s_name}!")
                        st.link_button("📲 Send Welcome WhatsApp", wa_url)

            st.subheader("Student Database")
            if not students_df.empty:
                # Add Edit Buttons to Grid
                for _, row in students_df.iterrows():
                    with st.container(border=True):
                        col_a, col_b, col_c = st.columns([3, 2, 1])
                        status = "🟢 Active" if row['Active'] else "🔴 Inactive"
                        col_a.markdown(f"**{row['Name']}** ({status})")
                        col_b.markdown(f"📞 {row['Mobile Number']}")
                        if col_c.button("Edit ✏️", key=f"edit_{row['ID']}"):
                            st.session_state.edit_student_id = row['ID']
                            st.rerun()

    # --- TAB 2: FEES COLLECTION ---
    with tab2:
        if not students_df.empty:
            active_list = students_df[students_df['Active'] == True]
            with st.form("fee_form", clear_on_submit=True):
                s_choice = st.selectbox("Select Student", active_list['Name'].tolist())
                s_row = active_list[active_list['Name'] == s_choice].iloc[0]
                
                c1, c2, c3 = st.columns(3)
                f_month = c1.selectbox("Month", MONTHS, index=datetime.now().month-1)
                f_year = c2.selectbox("Year", [2025, 2026], index=1)
                f_amount = c3.number_input("Amount", value=int(s_row['Coaching Fee']))
                
                if st.form_submit_button("Record Payment"):
                    p_id = str(uuid.uuid4())[:8]
                    new_pay = pd.DataFrame([{"ID": p_id, "Student": s_row['ID'], "Date": datetime.now().strftime("%Y-%m-%d"), "Month": f_month, "Year": f_year, "Amount": f_amount, "Payment Mode": "Cash/UPI"}])
                    save_sheet_data("Fees Payment", pd.concat([fees_df, new_pay]))
                    
                    wa_msg = format_wa_fee_receipt(s_choice, f_month, f_year, f_amount)
                    wa_url = f"https://wa.me/{clean_phone_number(s_row['Mobile Number'])}?text={urllib.parse.quote(wa_msg)}"
                    st.success("Payment Recorded!")
                    st.link_button("📲 Send WhatsApp Receipt", wa_url)

    # --- TAB 3: HISTORY ---
    with tab3:
        if not fees_df.empty:
            history = fees_df.merge(students_df[['ID', 'Name']], left_on='Student', right_on='ID', how='left')
            st.dataframe(history[['Date', 'Name', 'Month', 'Year', 'Amount']], use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# 5. EXECUTION
# -----------------------------------------------------------------------------
if menu == "🎓 Academy Management":
    academy_management()
else:
    # (Call your existing Booking Manager function here)
    st.info("Booking Manager Module")
