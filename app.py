import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import urllib.parse 
import re 
import uuid

# -----------------------------------------------------------------------------
# 1. NAVIGATION & CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Sai Star Management", layout="wide")

with st.sidebar:
    st.image("Sai_Star_logo__2_-removebg-preview.png", use_container_width=True)
    menu = st.radio("Navigation", ["🏏 Booking Manager", "🎓 Academy Management"])

# -----------------------------------------------------------------------------
# 2. CONSTANTS & HELPERS
# -----------------------------------------------------------------------------
STUDENT_HEADERS = ["ID", "Name", "Mobile Number", "DOJ", "DOB", "Student ID", "Uniform Size", "Coaching Plan", "Coaching Fee", "Active", "Comments"]
FEES_HEADERS = ["ID", "Student", "Date", "Month", "Year", "Amount", "Payment Mode", "Comments"]
SIZES = ["28", "30", "32", "34", "36", "38", "40", "42"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def clean_phone_number(number):
    num_str = re.sub(r'\D', '', str(number))
    return f"91{num_str}" if len(num_str) == 10 else num_str

# -----------------------------------------------------------------------------
# 3. DATA PERSISTENCE
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def get_sheet_data(worksheet_name, headers):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df.empty: return pd.DataFrame(columns=headers)
        # Standardize 'Active' column to boolean to prevent IndexErrors
        if 'Active' in df.columns:
            df['Active'] = df['Active'].astype(str).str.upper().map({'TRUE': True, 'FALSE': False, '1': True, '0': False})
        return df
    except: return pd.DataFrame(columns=headers)

def save_sheet_data(worksheet_name, df):
    # Remove helper columns before saving
    cols_to_save = [c for c in df.columns if not c.startswith('_')]
    conn.update(worksheet=worksheet_name, data=df[cols_to_save])

# -----------------------------------------------------------------------------
# 4. ACADEMY MANAGEMENT MODULE
# -----------------------------------------------------------------------------
def academy_management():
    st.header("🎓 Academy Management")
    
    if 'edit_student_id' not in st.session_state: st.session_state.edit_student_id = None
    
    tab1, tab2, tab3 = st.tabs(["👥 Student Database", "💰 Fees Collection", "📜 History"])
    
    students_df = get_sheet_data("Student Details", STUDENT_HEADERS)
    fees_df = get_sheet_data("Fees Payment", FEES_HEADERS)
    plans_df = get_sheet_data("Coaching Plan", ["Plan", "Plan Fee"])

    with tab1:
        # A. EDIT SCREEN (With Safety Checks)
        if st.session_state.edit_student_id:
            record_set = students_df[students_df['ID'] == st.session_state.edit_student_id]
            
            if record_set.empty:
                st.error("⚠️ Error: Student record not found or ID has changed.")
                if st.button("Return to List"):
                    st.session_state.edit_student_id = None
                    st.rerun()
            else:
                record = record_set.iloc[0]
                st.subheader(f"✏️ Editing Student: {record['Name']}")
                
                if st.button("🔙 Back to Student List"):
                    st.session_state.edit_student_id = None
                    st.rerun()

                with st.form("full_edit_student"):
                    c1, c2 = st.columns(2)
                    u_name = c1.text_input("Name", value=str(record['Name']))
                    u_mob = c2.text_input("Mobile Number", value=str(record['Mobile Number']))
                    
                    c3, c4, c5 = st.columns(3)
                    # Use try/except for date conversion safety
                    try: def_doj = pd.to_datetime(record['DOJ'])
                    except: def_doj = datetime.now()
                    try: def_dob = pd.to_datetime(record['DOB'])
                    except: def_dob = datetime.now()

                    u_doj = c3.date_input("Date of Joining", value=def_doj)
                    u_dob = c4.date_input("Date of Birth", value=def_dob)
                    
                    # Safe Indexing for Size
                    cur_size = str(record['Uniform Size'])
                    size_idx = SIZES.index(cur_size) if cur_size in SIZES else 0
                    u_size = c5.selectbox("Uniform Size", SIZES, index=size_idx)
                    
                    c6, c7, c8 = st.columns(3)
                    plan_list = plans_df["Plan"].tolist() if not plans_df.empty else ["6 Days Weekly", "3 Days Weekly"]
                    cur_plan = str(record['Coaching Plan'])
                    plan_idx = plan_list.index(cur_plan) if cur_plan in plan_list else 0
                    
                    u_plan = c6.selectbox("Coaching Plan", plan_list, index=plan_idx)
                    u_fee = c7.number_input("Monthly Fee", value=int(record['Coaching Fee']))
                    
                    # Safe Status logic
                    is_active = record['Active']
                    u_active = c8.selectbox("Status", ["Active", "Inactive"], index=0 if is_active else 1)
                    
                    u_comm = st.text_area("Comments", value=str(record['Comments']))

                    if st.form_submit_button("💾 Save Changes", type="primary"):
                        idx = students_df.index[students_df['ID'] == st.session_state.edit_student_id][0]
                        students_df.loc[idx, STUDENT_HEADERS[1:]] = [
                            u_name, u_mob, u_doj.strftime("%Y-%m-%d"), u_dob.strftime("%Y-%m-%d"), 
                            record['Student ID'], u_size, u_plan, u_fee, (u_active == "Active"), u_comm
                        ]
                        save_sheet_data("Student Details", students_df)
                        st.success("Record Updated!")
                        st.session_state.edit_student_id = None
                        st.rerun()

        # B. LIST VIEW
        else:
            # ... (Rest of Register New Student expander stays the same) ...
            st.subheader("Student List")
            if not students_df.empty:
                for _, row in students_df.iterrows():
                    with st.container(border=True):
                        c_info, c_btn = st.columns([4, 1])
                        status = "🟢" if row['Active'] else "🔴"
                        c_info.markdown(f"{status} **{row['Name']}** | {row['Mobile Number']}")
                        if c_btn.button("Edit ✏️", key=f"btn_{row['ID']}"):
                            st.session_state.edit_student_id = row['ID']
                            st.rerun()

    # --- TAB 2: FEES COLLECTION (With WhatsApp Logic) ---
    with tab2:
        if not students_df.empty:
            active_list = students_df[students_df['Active'] == True]
            with st.form("fee_payment"):
                s_name = st.selectbox("Select Student", active_list['Name'].tolist())
                s_data = active_list[active_list['Name'] == s_name].iloc[0]
                
                cc1, cc2, cc3 = st.columns(3)
                f_amount = cc1.number_input("Amount", value=int(s_data['Coaching Fee']))
                f_month = cc2.selectbox("Month", MONTHS, index=datetime.now().month - 1)
                f_date = cc3.date_input("Date")
                
                if st.form_submit_button("Record Payment & Generate WhatsApp"):
                    p_id = str(uuid.uuid4())[:8]
                    new_pay = pd.DataFrame([{
                        "ID": p_id, "Student": s_data['ID'], "Date": f_date.strftime("%Y-%m-%d"),
                        "Month": f_month, "Year": datetime.now().year, "Amount": f_amount,
                        "Payment Mode": "Cash/UPI", "Comments": ""
                    }])
                    save_sheet_data("Fees Payment", pd.concat([fees_df, new_pay]))
                    
                    # Generate WhatsApp Link
                    wa_msg = f"🧾 *SAI STAR RECEIPT*\nStudent: {s_name}\nMonth: {f_month}\nAmount: ₹{f_amount}\nStatus: Paid. Thank you!"
                    wa_url = f"https://wa.me/{clean_phone_number(s_data['Mobile Number'])}?text={urllib.parse.quote(wa_msg)}"
                    st.success("Payment Recorded!")
                    st.link_button("📲 Send WhatsApp Receipt", wa_url)

if __name__ == "__main__":
    if menu == "🎓 Academy Management":
        academy_management()
    else:
        st.info("Booking Manager Screen")
