import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import urllib.parse
import re
import os

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Sai Star Booking Manager", layout="wide")

# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# -----------------------------------------------------------------------------
EXPECTED_HEADERS = [
    "id", "booking_date", "start_time", "end_time", 
    "total_hours", "rate_per_hour", "total_charges", 
    "booked_by", "mobile_number", "advance_paid", "advance_mode", 
    "balance_paid", "balance_mode", 
    "remaining_due", "remarks"
]
PAYMENT_MODES = ["Cash", "Gpay", "Pending", "Cash+Gpay"]

def clean_phone_number(number):
    num_str = re.sub(r'\D', '', str(number))
    return f"91{num_str}" if len(num_str) == 10 else num_str

def convert_to_12h(time_str):
    try:
        return datetime.strptime(str(time_str)[:5], "%H:%M").strftime("%I:%M %p")
    except:
        return time_str

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

def format_wa_personal_msg(row_data):
    time_range = f"{convert_to_12h(row_data['start_time'])} to {convert_to_12h(row_data['end_time'])}"
    msg = (f"Hello {row_data['booked_by']},\n\n"
           f"This is from *Sai Star Ground*. Your booking is confirmed:\n"
           f"📅 *Date:* {pd.to_datetime(row_data['booking_date']).strftime('%d-%b-%Y')}\n"
           f"⏰ *Time:* {time_range}\n"
           f"💰 *Total Fees:* ₹{int(row_data['total_charges'])}\n"
           f"✅ *Advance:* ₹{int(row_data['advance_paid'])}\n"
           f"⏳ *Balance:* ₹{int(row_data['remaining_due'])}\n\n"
           f"See you! 🏏")
    return msg

# -----------------------------------------------------------------------------
# 3. DATA ENGINE (Targeting "Sheet1")
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        df.columns = [str(c).lower().strip() for c in df.columns]
        for col in EXPECTED_HEADERS:
            if col not in df.columns: df[col] = "" 
        
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        for col in ['rate_per_hour', 'total_charges', 'advance_paid', 'balance_paid', 'remaining_due']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        
        if not df.empty:
            df['start_time'] = df['start_time'].apply(lambda x: datetime.strptime(str(x)[:5], "%H:%M").strftime("%H:%M") if ":" in str(x) else "00:00")
            df['sort_key'] = pd.to_datetime(df['booking_date']).dt.strftime('%Y%m%d') + df['start_time'].str.replace(':', '')
            df['sort_key'] = pd.to_numeric(df['sort_key'], errors='coerce')
            df = df.sort_values(by='sort_key', ascending=True).reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Error loading Sheet1: {e}")
        return pd.DataFrame(columns=EXPECTED_HEADERS)

def save_data(df):
    if 'sort_key' in df.columns: 
        df = df.drop(columns=['sort_key'])
    conn.update(worksheet="Sheet1", data=df)

# -----------------------------------------------------------------------------
# 4. MAIN APP
# -----------------------------------------------------------------------------
def main():
    st.markdown("""<style>.block-container {padding-top: 1rem !important;} header {visibility: hidden;}</style>""", unsafe_allow_html=True)
    
    logo_file = "Sai_Star_logo__2_-removebg-preview.png"
    if os.path.exists(logo_file):
        st.image(logo_file, width=200)
    
    if 'edit_mode' not in st.session_state: st.session_state['edit_mode'] = False
    
    df = get_data()

    if st.session_state.get('edit_mode'):
        # --- EDIT MODE ---
        record = df[df['id'] == st.session_state['edit_id']].iloc[0]
        st.subheader("✏️ Edit Booking")
        with st.form("edit_form"):
            c1, c2, c3 = st.columns(3)
            e_date = c1.date_input("Date", value=pd.to_datetime(record['booking_date']))
            e_name = c2.text_input("Name", value=str(record['booked_by']))
            e_mob = c3.text_input("Mobile", value=str(record['mobile_number']))
            
            ts = get_time_slots(0, 23)
            e_start = st.selectbox("Start", ts, index=ts.index(record['start_time']) if record['start_time'] in ts else 0, format_func=convert_to_12h)
            e_end = st.selectbox("End", get_time_slots(0, 23, after_time=e_start), format_func=convert_to_12h)
            
            if st.form_submit_button("Save Changes"):
                idx = df.index[df['id'] == st.session_state['edit_id']][0]
                df.loc[idx, ['booking_date', 'booked_by', 'mobile_number', 'start_time', 'end_time']] = [e_date.strftime("%Y-%m-%d"), e_name, e_mob, e_start, e_end]
                save_data(df)
                st.session_state.edit_mode = False
                st.rerun()
            if st.form_submit_button("Cancel"):
                st.session_state.edit_mode = False
                st.rerun()

    else:
        # --- MAIN LIST VIEW ---
        with st.expander("➕ New Booking"):
            with st.form("new_b"):
                c1, c2 = st.columns(2)
                b_date = c1.date_input("Date")
                b_name = c2.text_input("Name")
                b_mob = st.text_input("Mobile")
                
                ts_start = get_time_slots(6, 23)
                b_start = st.selectbox("Start Time", ts_start, index=ts_start.index("20:00"))
                b_end = st.selectbox("End Time", get_time_slots(6, 23, after_time=b_start))
                
                if st.form_submit_button("Confirm"):
                    nid = 1 if df.empty else df['id'].max() + 1
                    new_row = pd.DataFrame([{"id": nid, "booking_date": b_date.strftime("%Y-%m-%d"), "start_time": b_start, "end_time": b_end, "booked_by": b_name, "mobile_number": b_mob}])
                    save_data(pd.concat([df, new_row]))
                    st.rerun()

        st.subheader("📅 Schedule")
        if not df.empty:
            # Display sorted upcoming bookings
            st.dataframe(df[["booking_date", "start_time", "end_time", "booked_by", "mobile_number"]], use_container_width=True, hide_index=True)
            
            # Simple Selection for Editing
            sel_id = st.selectbox("Select ID to Edit/Delete", df['id'].tolist())
            if st.button("Edit Selection"):
                st.session_state.edit_mode = True
                st.session_state.edit_id = sel_id
                st.rerun()

if __name__ == "__main__":
    main()
