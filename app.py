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
PAYMENT_MODES = ["Cash", "UPI", "Bank Transfer"]
SIZES = ["28", "30", "32", "34", "36", "38", "40", "42"]

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
        return df if not df.empty else pd.DataFrame(columns=headers)
    except: return pd.DataFrame(columns=headers)

def save_sheet_data(worksheet_name, df):
    conn.update(worksheet=worksheet_name, data=df)

# -----------------------------------------------------------------------------
# 4. ACADEMY MANAGEMENT MODULE
# -----------------------------------------------------------------------------
def academy_management():
    st.header("🎓 Academy Management")
    
    # Session State for View Control
    if 'edit_student_id' not in st.session_state: st.session_state.edit_student_id = None
    
    tab1, tab2, tab3 = st.tabs(["👥 Student Database", "💰 Fees Collection", "📜 History"])
    
    # Load Data
    students_df = get_sheet_data("Student Details", STUDENT_HEADERS)
    fees_df = get_sheet_data("Fees Payment", FEES_HEADERS)
    plans_df = get_sheet_data("Coaching Plan", ["Plan", "Plan Fee"])

    # --- TAB 1: STUDENTS ---
    with tab1:
        # A. EDIT SCREEN
        if st.session_state.edit_student_id:
            record_set = students_df[students_df['ID'] == st.session_state.edit_student_id]
            
            if not record_set.empty:
                record = record_set.iloc[0]
                st.subheader(f"✏️ Editing Student: {record['Name']}")
                
                # Back Button (Important)
                if st.button("🔙 Back to Student List"):
                    st.session_state.edit_student_id = None
                    st.rerun()

                with st.form("full_edit_student"):
                    c1, c2 = st.columns(2)
                    u_name = c1.text_input("Name", value=str(record['Name']))
                    u_mob = c2.text_input("Mobile Number", value=str(record['Mobile Number']))
                    
                    c3, c4, c5 = st.columns(3)
                    u_doj = c3.date_input("Date of Joining", value=pd.to_datetime(record['DOJ']))
                    u_dob = c4.date_input("Date of Birth", value=pd.to_datetime(record['DOB']))
                    u_size = c5.selectbox("Uniform Size", SIZES, index=SIZES.index(str(record['Uniform Size'])) if str(record['Uniform Size']) in SIZES else 0)
                    
                    c6, c7, c8 = st.columns(3)
                    plan_list = plans_df["Plan"].tolist() if not plans_df.empty else ["6 Days Weekly", "3 Days Weekly"]
                    u_plan = c6.selectbox("Coaching Plan", plan_list, index=plan_list.index(record['Coaching Plan']) if record['Coaching Plan'] in plan_list else 0)
                    u_fee = c7.number_input("Monthly Fee", value=int(record['Coaching Fee']))
                    u_active = c8.selectbox("Status", ["Active", "Inactive"], index=0 if record['Active'] == True or str(record['Active']).lower() == 'true' else 1)
                    
                    u_comm = st.text_area("Comments", value=str(record['Comments']))

                    # Action Buttons
                    col_save, col_del = st.columns([1, 5])
                    if col_save.form_submit_button("💾 Save Changes", type="primary"):
                        idx = students_df.index[students_df['ID'] == st.session_state.edit_student_id][0]
                        students_df.loc[idx, STUDENT_HEADERS[1:]] = [
                            u_name, u_mob, u_doj.strftime("%Y-%m-%d"), u_dob.strftime("%Y-%m-%d"), 
                            record['Student ID'], u_size, u_plan, u_fee, (u_active == "Active"), u_comm
                        ]
                        save_sheet_data("Student Details", students_df)
                        st.success("Record Updated!")
                        st.session_state.edit_student_id = None
                        st.rerun()
            else:
                st.error("Student Record not found.")
                st.session_state.edit_student_id = None

        # B. LIST VIEW
        else:
            with st.expander("➕ Register New Student"):
                with st.form("new_student_form", clear_on_submit=True):
                    nc1, nc2 = st.columns(2)
                    n_name = nc1.text_input("Full Name")
                    n_mob = nc2.text_input("Mobile Number")
                    
                    nc3, nc4, nc5 = st.columns(3)
                    n_doj = nc3.date_input("DOJ", value=datetime.now())
                    n_dob = nc4.date_input("DOB", value=datetime(2010, 1, 1))
                    n_size = nc5.selectbox("Uniform Size", SIZES)
                    
                    if st.form_submit_button("Register"):
                        new_id = str(uuid.uuid4())[:8]
                        new_row = pd.DataFrame([{
                            "ID": new_id, "Name": n_name, "Mobile Number": n_mob,
                            "DOJ": n_doj.strftime("%Y-%m-%d"), "DOB": n_dob.strftime("%Y-%m-%d"),
                            "Student ID": "Pending", "Uniform Size": n_size,
                            "Coaching Plan": "6 Days Weekly", "Coaching Fee": 3000,
                            "Active": True, "Comments": ""
                        }])
                        save_sheet_data("Student Details", pd.concat([students_df, new_row]))
                        st.success("Student Added!")
                        st.rerun()

            st.subheader("Active & Inactive Students")
            if not students_df.empty:
                # Add a search filter
                search = st.text_input("🔍 Search by Name", "")
                filtered_df = students_df[students_df['Name'].str.contains(search, case=False)] if search else students_df
                
                # Table with Edit Buttons
                for _, row in filtered_df.iterrows():
                    with st.container(border=True):
                        c_info, c_status, c_btn = st.columns([3, 1, 1])
                        c_info.markdown(f"**{row['Name']}** \n📞 {row['Mobile Number']} | 📅 DOJ: {row['DOJ']}")
                        
                        status_color = "🟢" if str(row['Active']).lower() == 'true' or row['Active'] == True else "🔴"
                        status_text = "Active" if status_color == "🟢" else "Inactive"
                        c_status.markdown(f"{status_color} {status_text}")
                        
                        if c_btn.button("Edit ✏️", key=f"btn_{row['ID']}"):
                            st.session_state.edit_student_id = row['ID']
                            st.rerun()
            else:
                st.info("No students found.")

    # --- TAB 2: FEES ---
    with tab2:
        if not students_df.empty:
            active_list = students_df[students_df['Active'].astype(str).str.lower() == 'true']
            with st.form("fee_payment"):
                s_name = st.selectbox("Select Student", active_list['Name'].tolist())
                s_data = active_list[active_list['Name'] == s_name].iloc[0]
                
                cc1, cc2, cc3 = st.columns(3)
                f_amount = cc1.number_input("Amount", value=int(s_data['Coaching Fee']))
                f_mode = cc2.selectbox("Mode", PAYMENT_MODES)
                f_date = cc3.date_input("Date")
                
                if st.form_submit_button("Record Payment"):
                    # Payment Logic Here
                    st.success("Payment Recorded!")

if __name__ == "__main__":
    if menu == "🎓 Academy Management":
        academy_management()
    else:
        st.info("Booking Manager Screen")
