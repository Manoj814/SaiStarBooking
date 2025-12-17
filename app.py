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
# 2. HELPER FUNCTIONS
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

def init_form_state():
    defaults = {
        'f_date': datetime.now().date(),
        'f_name': "",
        'f_start': "20:00", 
        'f_end': "21:00",   
        'f_fees': 1000.0,
        'f_adv': 0.0,
        'f_bal': 0.0,
        'f_mode': "Cash",
        'f_remarks': "" 
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
    
    # --- NOTIFICATION BAR (Replaces Pop-ups) ---
    message_box = st.empty()

    # A. Success Logic (After Reload)
    if 'success_msg' in st.session_state:
        message_box.success(f"✅ {st.session_state['success_msg']}")
        del st.session_state['success_msg']
    
    # B. Reset Logic
    if st.session_state.get('trigger_reset', False):
        reset_form_state()
        st.session_state['trigger_reset'] = False 
    
    # C. Init
    init_form_state()
    df = get_data()

    # --- Section 1: Create Booking ---
    with st.expander("➕ Create New Booking", expanded=True):
        with st.form("add_booking_form", clear_on_submit=False):
            col_date, col_name = st.columns([1, 2])
            b_date = col_date.date_input("Date", key='f_date')
            booked_by = col_name.text_input("Booked By (Name)", key='f_name')
            
            time_slots = get_time_slots()
            try: s_idx, e_idx = time_slots.index(st.session_state['f_start']), time_slots.index(st.session_state['f_end'])
            except ValueError: s_idx, e_idx = 40, 42 

            c1, c2, c3 = st.columns(3)
            b_start = c1.selectbox("Start Time", time_slots, index=s_idx, format_func=convert_to_12h, key='f_start')
            b_end = c2.selectbox("End Time", time_slots, index=e_idx, format_func=convert_to_12h, key='f_end')
            rate = c3.number_input("Ground Fees (₹)", step=100.0, key='f_fees')
            
            st.markdown("---")
            st.caption("Payment Details")
            p1, p2, p3 = st.columns(3)
            adv_paid = p1.number_input("Advance Paid (₹)", step=100.0, key='f_adv')
            bal_paid = p2.number_input("Balance Paid Now (₹)", step=100.0, key='f_bal')
            adv_mode = p3.selectbox("Payment Mode", PAYMENT_MODES, key='f_mode')
            remarks = st.text_input("Remarks", placeholder="Optional notes", key='f_remarks')
            
            submitted = st.form_submit_button("✅ Confirm Booking", type="primary")

            if submitted:
                b_date_str = b_date.strftime("%Y-%m-%d")
                
                # --- VALIDATION (Send errors to the top message box) ---
                if b_start >= b_end:
                    message_box.error("❌ **Error:** End time must be after Start time.")
                elif check_overlap(df, b_date_str, b_start, b_end):
                    message_box.error(f"⚠️ **Overlap Detected:** A booking already exists on {b_date_str} in this slot.")
                else:
                    # Validated - Save
                    fmt = "%H:%M"
                    dur = (datetime.strptime(b_end, fmt) - datetime.strptime(b_start, fmt)).total_seconds() / 3600
                    total = dur * rate
                    remaining = total - adv_paid - bal_paid
                    
                    new_record = pd.DataFrame([{
                        "id": get_next_id(df),
                        "booking_date": b_date_str,
                        "start_time": b_start,
                        "end_time": b_end,
                        "total_hours": dur,
                        "rate_per_hour": rate,
                        "total_charges": total,
                        "booked_by": booked_by,
                        "advance_paid": adv_paid,
                        "advance_mode": adv_mode,
                        "balance_paid": bal_paid,
                        "balance_mode": adv_mode,
                        "remaining_due": remaining,
                        "remarks": remarks
                    }])
                    
                    updated_df = pd.concat([df, new_record], ignore_index=True)
                    save_data(updated_df)
                    
                    st.session_state['trigger_reset'] = True 
                    st.session_state['success_msg'] = f"Booking Confirmed for {booked_by}!"
                    st.rerun()

    st.markdown("---")

    # --- Section 2: Data Grid ---
    search_query = st.text_input("🔍 Search (Name or Date YYYY-MM-DD)", placeholder="Type name...")

    if not df.empty:
        df['dt_obj'] = pd.to_datetime(df['booking_date']).dt.date
        today = datetime.now().date()
        if search_query:
            filtered_df = df[
                df['booked_by'].str.contains(search_query, case=False, na=False) | 
                df['booking_date'].astype(str).str.contains(search_query, case=False, na=False)
            ]
        else:
            filtered_df = df
        future_df = filtered_df[filtered_df['dt_obj'] >= today].sort_values(by=['booking_date', 'start_time'], ascending=[True, True])
        past_df = filtered_df[filtered_df['dt_obj'] < today].sort_values(by=['booking_date', 'start_time'], ascending=[False, True])
    else:
        future_df = pd.DataFrame()
        past_df = pd.DataFrame()

    tab1, tab2, tab3 = st.tabs(["📅 Upcoming Bookings", "📜 Booking History", "✏️ Edit / Update"])
    
    grid_config = {
        "id": st.column_config.NumberColumn("ID", width="small"),
        "booking_date": "Date", 
        "formatted_start": "Start", 
        "formatted_end": "End", 
        "booked_by": "Name", 
        "total_charges": "Total",
        "remaining_due": "Due",
        "advance_mode": "Mode",
        "remarks": "Remarks"
    }
    visible_cols = ["id", "booking_date", "formatted_start", "formatted_end", "booked_by", "total_charges", "remaining_due", "advance_mode", "remarks"]

    with tab1:
        if future_df.empty: st.info("No upcoming bookings.")
        else:
            show_f = future_df.copy()
            show_f['formatted_start'] = show_f['start_time'].apply(convert_to_12h)
            show_f['formatted_end'] = show_f['end_time'].apply(convert_to_12h)
            show_f['total_charges'] = show_f['total_charges'].apply(lambda x: f"₹{x:,.0f}")
            show_f['remaining_due'] = show_f['remaining_due'].apply(lambda x: f"₹{x:,.0f}")
            st.dataframe(show_f, use_container_width=True, column_config=grid_config, column_order=visible_cols, hide_index=True)

    with tab2:
        if past_df.empty: st.info("No past history.")
        else:
            show_p = past_df.copy()
            show_p['formatted_start'] = show_p['start_time'].apply(convert_to_12h)
            show_p['formatted_end'] = show_p['end_time'].apply(convert_to_12h)
            show_p['total_charges'] = show_p['total_charges'].apply(lambda x: f"₹{x:,.0f}")
            show_p['remaining_due'] = show_p['remaining_due'].apply(lambda x: f"₹{x:,.0f}")
            st.dataframe(show_p, use_container_width=True, column_config=grid_config, column_order=visible_cols, hide_index=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                past_df.drop(columns=['dt_obj'], errors='ignore').to_excel(writer, index=False, sheet_name='History')
            st.download_button("📥 Download History Excel", output.getvalue(), f"turf_history_{datetime.now().strftime('%Y%m%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab3:
        if df.empty: st.write("No records.")
        else:
            df['label'] = df['booking_date'].astype(str) + " (" + df['start_time'].astype(str) + ") - " + df['booked_by'].astype(str)
            id_to_label = dict(zip(df['id'], df['label']))
            if search_query:
                search_mask = (df['booked_by'].str.contains(search_query, case=False, na=False) | df['booking_date'].astype(str).str.contains(search_query, case=False, na=False))
                options = df[search_mask]['id'].tolist()
            else:
                options = df['id'].tolist()
            if not options: st.warning("No records match.")
            else:
                edit_id = st.selectbox("Select Booking to Edit", options, format_func=lambda x: id_to_label.get(x, f"ID: {x}"))
                record = df[df['id'] == edit_id].iloc[0]
                with st.form("edit_form"):
                    st.subheader(f"Edit: {record['booked_by']}")
                    c_a, c_b = st.columns(2)
                    e_date = c_a.date_input("Date", datetime.strptime(str(record['booking_date']), '%Y-%m-%d'))
                    e_name = c_b.text_input("Name", value=record['booked_by'])
                    
                    time_slots = get_time_slots()
                    try: s_idx, e_idx = time_slots.index(record['start_time']), time_slots.index(record['end_time'])
                    except: s_idx, e_idx = 40, 42
                    
                    e_start = c_a.selectbox("Start", time_slots, index=s_idx, format_func=convert_to_12h, key='es')
                    e_end = c_b.selectbox("End", time_slots, index=e_idx, format_func=convert_to_12h, key='ee')
                    e_rate = c_a.number_input("Ground Fees", value=float(record['rate_per_hour']))
                    st.divider()
                    st.write("**Payment & Remarks**")
                    pa, pb = st.columns(2)
                    e_adv = pa.number_input("Advance Paid", value=float(record['advance_paid']))
                    e_bal_paid = pb.number_input("Balance Paid", value=float(record['balance_paid']))
                    curr_mode = record['advance_mode'] if record['advance_mode'] in PAYMENT_MODES else "Cash"
                    mode_idx = PAYMENT_MODES.index(curr_mode) if curr_mode in PAYMENT_MODES else 0
                    e_mode = st.selectbox("Payment Mode", PAYMENT_MODES, index=mode_idx)
                    e_remarks = st.text_input("Remarks", value=str(record['remarks']))

                    upd_submit = st.form_submit_button("💾 Save Changes", type="primary")

                if st.button("🗑️ Delete Booking", key='del_btn'):
                    df_new = df[df['id'] != edit_id]
                    save_data(df_new)
                    st.session_state['success_msg'] = "Record Deleted Successfully."
                    st.rerun()

                if upd_submit:
                    e_date_str = e_date.strftime("%Y-%m-%d")
                    # --- EDIT VALIDATION ---
                    if e_start >= e_end:
                        message_box.error("❌ **Error:** End time must be after Start time.")
                    elif check_overlap(df, e_date_str, e_start, e_end, exclude_id=edit_id):
                        message_box.error("⚠️ **Overlap Detected:** Please choose a different slot.")
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
                        st.session_state['success_msg'] = "Booking Updated Successfully!"
                        st.rerun()

if __name__ == "__main__":
    main()
