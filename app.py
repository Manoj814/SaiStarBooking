import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import io
import os 

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Sai Star Booking Manager", layout="wide")

# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS & CONFIG
# -----------------------------------------------------------------------------
EXPECTED_HEADERS = [
    "id", "booking_date", "start_time", "end_time", 
    "total_hours", "rate_per_hour", "total_charges", 
    "booked_by", "mobile_number", "advance_paid", "advance_mode",  # Added mobile_number
    "balance_paid", "balance_mode", 
    "remaining_due", "remarks"
]
PAYMENT_MODES = ["Cash", "Gpay", "Pending", "Cash+Gpay"]

def convert_to_12h(time_str):
    try:
        return datetime.strptime(time_str, "%H:%M").strftime("%I:%M %p")
    except:
        return time_str

def get_time_slots():
    slots = []
    start = datetime.strptime("00:00", "%H:%M")
    end = datetime.strptime("23:30", "%H:%M")
    while start <= end:
        slots.append(start.strftime("%H:%M"))
        start += timedelta(minutes=30)
    return slots

def init_session_state():
    if 'form_id' not in st.session_state:
        st.session_state['form_id'] = 0 
    
    if 'expand_new' not in st.session_state:
        st.session_state['expand_new'] = False
        
    if 'edit_mode' not in st.session_state:
        st.session_state['edit_mode'] = False
        st.session_state['edit_id'] = None
        
    if 'success_msg' not in st.session_state:
        st.session_state['success_msg'] = None

# --- GOOGLE SHEETS FUNCTIONS ---
def get_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        if df.empty: return pd.DataFrame(columns=EXPECTED_HEADERS)
        df.columns = [str(c).lower().strip() for c in df.columns]
        for col in EXPECTED_HEADERS:
            if col not in df.columns: df[col] = "" 
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        cols_to_float = ['total_hours', 'rate_per_hour', 'total_charges', 'advance_paid', 'balance_paid', 'remaining_due']
        for col in cols_to_float:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        # Added mobile_number to text columns to preserve formatting
        text_cols = ['booked_by', 'mobile_number', 'advance_mode', 'balance_mode', 'remarks']
        for col in text_cols: df[col] = df[col].fillna("").astype(str)
        return df
    except Exception:
        return pd.DataFrame(columns=EXPECTED_HEADERS)

def save_data(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    conn.update(worksheet="Sheet1", data=df)

def check_overlap(df, date_str, start_str, end_str, exclude_id=None):
    if df.empty: return False
    day_bookings = df[df['booking_date'].astype(str) == str(date_str)]
    if exclude_id is not None:
        day_bookings = day_bookings[day_bookings['id'] != exclude_id]
    if day_bookings.empty: return False
    overlap = day_bookings[
        (day_bookings['start_time'] < end_str) & 
        (day_bookings['end_time'] > start_str)
    ]
    return not overlap.empty

def get_next_id(df):
    return 1 if df.empty else df['id'].max() + 1

# -----------------------------------------------------------------------------
# 3. MAIN APP
# -----------------------------------------------------------------------------
def main():
    # --- CSS ---
    st.markdown("""
        <style>
               .block-container {
                    padding-top: 0rem !important;
                    padding-bottom: 0rem !important;
                    padding-left: 2rem;
                    padding-right: 2rem;
                }
               header {visibility: hidden;} 
               div[data-testid="stVerticalBlock"] > div {
                    gap: 0.5rem;
               }
        </style>
        """, unsafe_allow_html=True)

    # --- LOGO ---
    logo_file = "Sai_Star_logo__2_-removebg-preview.png"
    if os.path.exists(logo_file):
        c1, c2, c3 = st.columns([3, 2, 3])
        with c2:
            st.image(logo_file, use_container_width=True)
    else:
        st.markdown("<h2 style='text-align: center;'>🏏 Sai Star Booking Manager</h2>", unsafe_allow_html=True)
    
    init_session_state()
    df = get_data()

    # --- PRE-PROCESS DATE ---
    if not df.empty:
        df['dt_obj'] = pd.to_datetime(df['booking_date']).dt.date
    # ------------------------

    # ---------------------------------------------------------
    # PART A: EDIT SCREEN (Only visible if a row is selected)
    # ---------------------------------------------------------
    if st.session_state['edit_mode'] and st.session_state['edit_id'] is not None:
        edit_id = st.session_state['edit_id']
        record = df[df['id'] == edit_id].iloc[0]
        
        st.subheader(f"✏️ Edit: {record['booked_by']}")
        
        with st.form("edit_form"):
            c1, c2, c3 = st.columns(3)
            e_date = c1.date_input("Date", value=datetime.strptime(str(record['booking_date']), '%Y-%m-%d'))
            e_name = c2.text_input("Booking Name", value=record['booked_by'])
            e_mobile = c3.text_input("Mobile No", value=str(record['mobile_number'])) # Added Mobile
            
            time_slots = get_time_slots()
            try: s_idx, e_idx = time_slots.index(record['start_time']), time_slots.index(record['end_time'])
            except: s_idx, e_idx = 40, 42
            
            c4, c5 = st.columns(2)
            e_start = c4.selectbox("Start", time_slots, index=s_idx, format_func=convert_to_12h)
            e_end = c5.selectbox("End", time_slots, index=e_idx, format_func=convert_to_12h)
            e_rate = st.number_input("Ground Fees", value=float(record['rate_per_hour']))
            
            st.divider()
            c6, c7, c8 = st.columns(3)
            e_adv = c6.number_input("Advance Paid", value=float(record['advance_paid']))
            e_bal_paid = c7.number_input("Balance Paid", value=float(record['balance_paid']))
            
            curr_mode = record['advance_mode'] if record['advance_mode'] in PAYMENT_MODES else "Cash"
            mode_idx = PAYMENT_MODES.index(curr_mode) if curr_mode in PAYMENT_MODES else 0
            e_mode = c8.selectbox("Payment Mode", PAYMENT_MODES, index=mode_idx)
            e_remarks = st.text_input("Remarks", value=str(record['remarks']))

            b1, b2, b3 = st.columns([1, 1, 4])
            cancel_btn = b1.form_submit_button("🔙 Cancel")
            del_btn = b2.form_submit_button("🗑️ Delete")
            save_btn = b3.form_submit_button("💾 Save Changes", type="primary")

            edit_msg_placeholder = st.empty()

            if cancel_btn:
                st.session_state['edit_mode'] = False
                st.session_state['edit_id'] = None
                st.rerun()

            if del_btn:
                df_new = df[df['id'] != edit_id]
                save_data(df_new)
                st.session_state['success_msg'] = "🗑️ Record Deleted Successfully"
                st.session_state['edit_mode'] = False
                st.session_state['edit_id'] = None
                st.rerun()

            if save_btn:
                e_date_str = e_date.strftime("%Y-%m-%d")
                if e_start >= e_end:
                    edit_msg_placeholder.error("❌ End time must be after Start time.")
                elif check_overlap(df, e_date_str, e_start, e_end, exclude_id=edit_id):
                    edit_msg_placeholder.error("⚠️ Overlap Detected!")
                else:
                    fmt = "%H:%M"
                    dur = (datetime.strptime(e_end, fmt) - datetime.strptime(e_start, fmt)).total_seconds() / 3600
                    tot = dur * e_rate
                    rem = tot - e_adv - e_bal_paid
                    
                    idx = df.index[df['id'] == edit_id][0]
                    df.at[idx, 'booking_date'] = e_date_str
                    df.at[idx, 'booked_by'] = e_name
                    df.at[idx, 'mobile_number'] = e_mobile # Save Mobile
                    df.at[idx, 'start_time'] = e_start
                    df.at[idx, 'end_time'] = e_end
                    df.at[idx, 'total_hours'] = dur
                    df.at[idx, 'rate_per_hour'] = e_rate
                    df.at[idx, 'total_charges'] = tot
                    df.at[idx, 'advance_paid'] = e_adv
                    df.at[idx, 'balance_paid'] = e_bal_paid
                    df.at[idx, 'advance_mode'] = e_mode
                    df.at[idx, 'remaining_due'] = rem
                    df.at[idx, 'remarks'] = e_remarks
                    
                    save_data(df)
                    st.session_state['success_msg'] = "💾 Changes Saved!"
                    st.session_state['edit_mode'] = False
                    st.session_state['edit_id'] = None
                    st.rerun()

    # ---------------------------------------------------------
    # PART B: MAIN GRID SCREEN (Visible if NOT editing)
    # ---------------------------------------------------------
    else:
        # 1. ADD NEW BOOKING
        with st.expander("➕ Add New Booking", expanded=st.session_state['expand_new']):
            with st.form("add_form", clear_on_submit=False):
                fid = st.session_state['form_id'] 
                
                c1, c2, c3 = st.columns([1, 2, 2])
                b_date = c1.date_input("Date", value=datetime.now().date(), key=f"date_{fid}")
                b_name = c2.text_input("Booking Name", key=f"name_{fid}")
                b_mobile = c3.text_input("Mobile No", key=f"mobile_{fid}") # Added Mobile Input
                
                time_slots = get_time_slots()
                c4, c5, c6 = st.columns(3)
                b_start = c4.selectbox("Start", time_slots, index=40, format_func=convert_to_12h, key=f"start_{fid}")
                b_end = c5.selectbox("End", time_slots, index=42, format_func=convert_to_12h, key=f"end_{fid}")
                b_rate = c6.number_input("Fees", step=100.0, value=1000.0, key=f"fees_{fid}")
                
                c7, c8, c9 = st.columns(3)
                b_adv = c7.number_input("Advance", step=100.0, key=f"adv_{fid}")
                b_bal = c8.number_input("Balance Paid", step=100.0, key=f"bal_{fid}")
                b_mode = c9.selectbox("Mode", PAYMENT_MODES, key=f"mode_{fid}")
                b_rem = st.text_input("Remarks", key=f"rem_{fid}")
                
                add_sub = st.form_submit_button("✅ Confirm Booking", type="primary")
                add_msg_placeholder = st.empty()
                
                if add_sub:
                    b_date_str = b_date.strftime("%Y-%m-%d")
                    if b_start >= b_end:
                        add_msg_placeholder.error("❌ End time must be after Start.")
                    elif check_overlap(df, b_date_str, b_start, b_end):
                        add_msg_placeholder.error("⚠️ Slot Overlap! Please check time.")
                    else:
                        fmt = "%H:%M"
                        dur = (datetime.strptime(b_end, fmt) - datetime.strptime(b_start, fmt)).total_seconds() / 3600
                        tot = dur * b_rate
                        rem = tot - b_adv - b_bal
                        
                        new_row = pd.DataFrame([{
                            "id": get_next_id(df), "booking_date": b_date_str,
                            "start_time": b_start, "end_time": b_end,
                            "total_hours": dur, "rate_per_hour": b_rate, "total_charges": tot,
                            "booked_by": b_name, "mobile_number": b_mobile, # Save Mobile
                            "advance_paid": b_adv, "advance_mode": b_mode,
                            "balance_paid": b_bal, "balance_mode": b_mode,
                            "remaining_due": rem, "remarks": b_rem
                        }])
                        save_data(pd.concat([df, new_row], ignore_index=True))
                        
                        st.session_state['form_id'] += 1
                        st.session_state['expand_new'] = False
                        st.session_state['success_msg'] = f"✅ Booking Added for {b_name}!"
                        st.rerun()

        # 2. SUCCESS MSG
        if st.session_state['success_msg']:
            st.success(st.session_state['success_msg'])
            st.session_state['success_msg'] = None

        # 3. GRID
        st.subheader("📅 Upcoming Bookings")
        
        if df.empty:
            st.info("No bookings found.")
        else:
            today = datetime.now().date()
            future_df = df[df['dt_obj'] >= today].sort_values(by=['booking_date', 'start_time'])
            
            if future_df.empty:
                st.info("No upcoming bookings.")
            else:
                st.caption("👆 **Click on any row to Edit**")
                
                display_df = future_df.copy()
                display_df['S.No'] = range(1, len(display_df) + 1)
                display_df['formatted_start'] = display_df['start_time'].apply(convert_to_12h)
                display_df['formatted_end'] = display_df['end_time'].apply(convert_to_12h)
                
                grid_cols = {
                    "S.No": st.column_config.NumberColumn("S.No", width="small"),
                    "booking_date": "Date",
                    "formatted_start": "Start",
                    "formatted_end": "End",
                    "booked_by": "Booking Name",
                    "total_charges": st.column_config.NumberColumn("Total", format="₹%d"),
                    "advance_paid": st.column_config.NumberColumn("Adv.", format="₹%d"), # Added Advance Column
                    "remaining_due": st.column_config.NumberColumn("Due", format="₹%d"),
                    "advance_mode": "Mode",
                    "remarks": "Remarks"
                }
                
                event = st.dataframe(
                    display_df,
                    column_config=grid_cols,
                    # Added 'advance_paid' to the column order
                    column_order=["S.No", "booking_date", "formatted_start", "formatted_end", "booked_by", "total_charges", "advance_paid", "remaining_due", "advance_mode", "remarks"],
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row"
                )

                if event.selection.rows:
                    selected_index = event.selection.rows[0]
                    selected_db_id = display_df.iloc[selected_index]['id']
                    st.session_state['edit_mode'] = True
                    st.session_state['edit_id'] = selected_db_id
                    st.rerun()

        # 4. HISTORY
        with st.expander("📜 View Booking History"):
            if df.empty:
                st.info("No past history.")
            else:
                past_df = df[df['dt_obj'] < today].sort_values(by=['booking_date', 'start_time'], ascending=False)
                if not past_df.empty:
                    past_df['S.No'] = range(1, len(past_df) + 1)
                    st.dataframe(
                        past_df,
                        column_order=["S.No", "booking_date", "start_time", "end_time", "booked_by", "mobile_number", "total_charges"],
                        hide_index=True,
                        use_container_width=True
                    )
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.drop(columns=['dt_obj'], errors='ignore').to_excel(writer, index=False)
                    st.download_button("📥 Download Full Excel", output.getvalue(), "bookings.xlsx")
                else:
                    st.info("No past history.")

if __name__ == "__main__":
    main()
