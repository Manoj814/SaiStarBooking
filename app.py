import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import io

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cricket Turf Booking", layout="wide")

# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS & CONFIG
# -----------------------------------------------------------------------------
EXPECTED_HEADERS = [
    "id", "booking_date", "start_time", "end_time", 
    "total_hours", "rate_per_hour", "total_charges", 
    "booked_by", "advance_paid", "advance_mode", 
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
    # Form defaults
    defaults = {
        'f_date': datetime.now().date(),
        'f_name': "",
        'f_start': "20:00", 'f_end': "21:00",
        'f_fees': 1000.0, 'f_adv': 0.0, 'f_bal': 0.0,
        'f_mode': "Cash", 'f_remarks': "",
        # App State
        'expand_new': False,       # Controls if "Add New" is open/closed
        'edit_mode': False,        # Controls if we are editing
        'edit_id': None,           # ID being edited
        'success_msg': None        # Message to show after reload
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

def reset_form_state():
    st.session_state['f_date'] = datetime.now().date()
    st.session_state['f_name'] = ""
    st.session_state['f_start'] = "20:00"
    st.session_state['f_end'] = "21:00"
    st.session_state['f_fees'] = 1000.0
    st.session_state['f_adv'] = 0.0
    st.session_state['f_bal'] = 0.0
    st.session_state['f_mode'] = "Cash"
    st.session_state['f_remarks'] = ""

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
        text_cols = ['booked_by', 'advance_mode', 'balance_mode', 'remarks']
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
    st.title("🏏 Cricket Academy Booking Manager")
    
    # Init State
    init_session_state()
    
    # Message Bar
    msg_box = st.empty()
    if st.session_state['success_msg']:
        msg_box.success(st.session_state['success_msg'])
        st.session_state['success_msg'] = None # Clear after showing

    # Load Data
    df = get_data()

    # ---------------------------------------------------------
    # PART A: EDIT SCREEN (Only visible if a row is selected)
    # ---------------------------------------------------------
    if st.session_state['edit_mode'] and st.session_state['edit_id'] is not None:
        edit_id = st.session_state['edit_id']
        record = df[df['id'] == edit_id].iloc[0]
        
        st.subheader(f"✏️ Editing Booking: {record['booked_by']}")
        
        with st.form("edit_form"):
            c1, c2 = st.columns(2)
            e_date = c1.date_input("Date", datetime.strptime(str(record['booking_date']), '%Y-%m-%d'))
            e_name = c2.text_input("Name", value=record['booked_by'])
            
            time_slots = get_time_slots()
            try: s_idx, e_idx = time_slots.index(record['start_time']), time_slots.index(record['end_time'])
            except: s_idx, e_idx = 40, 42
            
            c3, c4 = st.columns(2)
            e_start = c3.selectbox("Start", time_slots, index=s_idx, format_func=convert_to_12h)
            e_end = c4.selectbox("End", time_slots, index=e_idx, format_func=convert_to_12h)
            e_rate = st.number_input("Ground Fees", value=float(record['rate_per_hour']))
            
            st.divider()
            c5, c6, c7 = st.columns(3)
            e_adv = c5.number_input("Advance Paid", value=float(record['advance_paid']))
            e_bal_paid = c6.number_input("Balance Paid", value=float(record['balance_paid']))
            
            curr_mode = record['advance_mode'] if record['advance_mode'] in PAYMENT_MODES else "Cash"
            mode_idx = PAYMENT_MODES.index(curr_mode) if curr_mode in PAYMENT_MODES else 0
            e_mode = c7.selectbox("Payment Mode", PAYMENT_MODES, index=mode_idx)
            e_remarks = st.text_input("Remarks", value=str(record['remarks']))

            b1, b2, b3 = st.columns([1, 1, 4])
            cancel_btn = b1.form_submit_button("🔙 Cancel")
            del_btn = b2.form_submit_button("🗑️ Delete")
            save_btn = b3.form_submit_button("💾 Save Changes", type="primary")

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
                    st.error("❌ End time must be after Start time.")
                elif check_overlap(df, e_date_str, e_start, e_end, exclude_id=edit_id):
                    st.error("⚠️ Overlap Detected!")
                else:
                    fmt = "%H:%M"
                    dur = (datetime.strptime(e_end, fmt) - datetime.strptime(e_start, fmt)).total_seconds() / 3600
                    tot = dur * e_rate
                    rem = tot - e_adv - e_bal_paid
                    
                    idx = df.index[df['id'] == edit_id][0]
                    df.at[idx, 'booking_date'] = e_date_str
                    df.at[idx, 'booked_by'] = e_name
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
        # 1. ADD NEW BOOKING (Collapsed by default)
        with st.expander("➕ Add New Booking", expanded=st.session_state['expand_new']):
            with st.form("add_form", clear_on_submit=False):
                c1, c2 = st.columns([1, 2])
                b_date = c1.date_input("Date", key='f_date')
                b_name = c2.text_input("Name", key='f_name')
                
                time_slots = get_time_slots()
                c3, c4, c5 = st.columns(3)
                b_start = c3.selectbox("Start", time_slots, format_func=convert_to_12h, key='f_start')
                b_end = c4.selectbox("End", time_slots, format_func=convert_to_12h, key='f_end')
                b_rate = c5.number_input("Fees", step=100.0, key='f_fees')
                
                c6, c7, c8 = st.columns(3)
                b_adv = c6.number_input("Advance", step=100.0, key='f_adv')
                b_bal = c7.number_input("Balance Paid", step=100.0, key='f_bal')
                b_mode = c8.selectbox("Mode", PAYMENT_MODES, key='f_mode')
                b_rem = st.text_input("Remarks", key='f_remarks')
                
                add_sub = st.form_submit_button("✅ Confirm Booking", type="primary")
                
                if add_sub:
                    b_date_str = b_date.strftime("%Y-%m-%d")
                    if b_start >= b_end:
                        st.error("Error: End time must be after Start.")
                    elif check_overlap(df, b_date_str, b_start, b_end):
                        st.error("Error: Slot Overlap!")
                    else:
                        fmt = "%H:%M"
                        dur = (datetime.strptime(b_end, fmt) - datetime.strptime(b_start, fmt)).total_seconds() / 3600
                        tot = dur * b_rate
                        rem = tot - b_adv - b_bal
                        
                        new_row = pd.DataFrame([{
                            "id": get_next_id(df), "booking_date": b_date_str,
                            "start_time": b_start, "end_time": b_end,
                            "total_hours": dur, "rate_per_hour": b_rate, "total_charges": tot,
                            "booked_by": b_name, "advance_paid": b_adv, "advance_mode": b_mode,
                            "balance_paid": b_bal, "balance_mode": b_mode,
                            "remaining_due": rem, "remarks": b_rem
                        }])
                        save_data(pd.concat([df, new_row], ignore_index=True))
                        
                        # Reset form and collapse expander
                        reset_form_state()
                        st.session_state['expand_new'] = False
                        st.session_state['success_msg'] = f"✅ Added booking for {b_name}"
                        st.rerun()

        st.markdown("---")

        # 2. UPCOMING BOOKINGS GRID
        st.subheader("📅 Upcoming Bookings")
        
        if df.empty:
            st.info("No bookings found.")
        else:
            # Prepare Data
            df['dt_obj'] = pd.to_datetime(df['booking_date']).dt.date
            today = datetime.now().date()
            
            # Filter Future
            future_df = df[df['dt_obj'] >= today].sort_values(by=['booking_date', 'start_time'])
            
            if future_df.empty:
                st.info("No upcoming bookings.")
            else:
                st.caption("👆 **Click on any row to Edit or Delete**")
                
                # Format for Display
                display_df = future_df.copy()
                display_df['S.No'] = range(1, len(display_df) + 1) # Generate Serial Numbers 1, 2, 3...
                display_df['formatted_start'] = display_df['start_time'].apply(convert_to_12h)
                display_df['formatted_end'] = display_df['end_time'].apply(convert_to_12h)
                
                # Configure Columns
                grid_cols = {
                    "S.No": st.column_config.NumberColumn("S.No", width="small"),
                    "booking_date": "Date",
                    "formatted_start": "Start",
                    "formatted_end": "End",
                    "booked_by": "Name",
                    "total_charges": st.column_config.NumberColumn("Total", format="₹%d"),
                    "remaining_due": st.column_config.NumberColumn("Due", format="₹%d"),
                    "advance_mode": "Mode",
                    "remarks": "Remarks"
                }
                
                # Show Grid with Selection
                event = st.dataframe(
                    display_df,
                    column_config=grid_cols,
                    column_order=["S.No", "booking_date", "formatted_start", "formatted_end", "booked_by", "total_charges", "remaining_due", "advance_mode", "remarks"],
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",           # Make row selection trigger a rerun
                    selection_mode="single-row"  # Only allow one row
                )

                # Handle Selection
                if event.selection.rows:
                    selected_index = event.selection.rows[0]
                    # Get the actual Database ID (not the S.No)
                    selected_db_id = display_df.iloc[selected_index]['id']
                    
                    # Set State to Edit Mode
                    st.session_state['edit_mode'] = True
                    st.session_state['edit_id'] = selected_db_id
                    st.rerun()

        # 3. PAST HISTORY (Read Only)
        with st.expander("📜 View Booking History"):
            past_df = df[df['dt_obj'] < today].sort_values(by=['booking_date', 'start_time'], ascending=False)
            if not past_df.empty:
                past_df['S.No'] = range(1, len(past_df) + 1)
                st.dataframe(
                    past_df,
                    column_order=["S.No", "booking_date", "start_time", "end_time", "booked_by", "total_charges"],
                    hide_index=True,
                    use_container_width=True
                )
                
                # Excel Download
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.drop(columns=['dt_obj'], errors='ignore').to_excel(writer, index=False)
                st.download_button("📥 Download Full Excel", output.getvalue(), "bookings.xlsx")
            else:
                st.info("No past history.")

if __name__ == "__main__":
    main()
