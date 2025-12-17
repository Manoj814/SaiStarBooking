import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import io

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & CONSTANTS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Cricket Turf Booking", layout="wide")

EXPECTED_HEADERS = [
    "id", "booking_date", "start_time", "end_time", 
    "total_hours", "rate_per_hour", "total_charges", 
    "booked_by", "advance_paid", "advance_mode", 
    "balance_paid", "balance_mode", 
    "remaining_due", "remarks"
]

PAYMENT_MODES = ["Cash", "Gpay", "Pending", "Cash+Gpay"]

# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# -----------------------------------------------------------------------------

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
        
        if df.empty:
            return pd.DataFrame(columns=EXPECTED_HEADERS)
            
        df.columns = [str(c).lower().strip() for c in df.columns]

        for col in EXPECTED_HEADERS:
            if col not in df.columns:
                df[col] = "" 

        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        
        cols_to_float = ['total_hours', 'rate_per_hour', 'total_charges', 'advance_paid', 'balance_paid', 'remaining_due']
        for col in cols_to_float:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        text_cols = ['booked_by', 'advance_mode', 'balance_mode', 'remarks']
        for col in text_cols:
             df[col] = df[col].fillna("").astype(str)

        return df
    except Exception as e:
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

    # --- MESSAGE CENTER (Top of Page) ---
    # This acts like a notification bar that is always visible at the top
    message_container = st.empty()

    # 1. Show Success Message from Session State (e.g., after reload)
    if 'success_msg' in st.session_state:
        message_container.success(f"✅ {st.session_state['success_msg']}")
        del st.session_state['success_msg']
    
    # 2. Reset Trigger
    if st.session_state.get('trigger_reset', False):
        reset_form_state()
        st.session_state['trigger_reset'] = False 
    
    # 3. Initialization
    init_form_state()
    df = get_data()

    # --- Section 1: Create Booking ---
    with st.expander("➕ Create New Booking", expanded=True):
        with st.form("add_booking_form", clear_on_submit=False):
            col_date, col_name = st.columns([1, 2])
            b_date = col_date.date_input("Date", key='f_date')
            booked_by = col_name.text_input("Booked By (Name)", key='f_name')
            
            time_slots = get_time_slots()
            try:
                s_idx = time_slots.index(st.session_state['f_start'])
                e_idx = time_slots.index(st.session_state['f_end'])
            except ValueError:
                s_idx, e_idx = 40, 42 

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
                
                # --- VALIDATION (Display Errors at Top) ---
                if b_start >= b_end:
                    message_container.error("❌ **Error:** End time must be after Start time.")
                
                elif check_overlap(df, b_date_str, b_start, b_end):
                    message_container.error(f"⚠️ **Overlap Detected:** A booking already exists on {b_date_str} during these hours.")
                
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
        today = datetime.now().
