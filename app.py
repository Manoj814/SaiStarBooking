import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import io
import os 
import urllib.parse 

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

def format_wa_group_msg(row_data):
    """Format for Group: Date#Day#Time#Name#Mobile#Fee#Advance#Balance#"""
    dt = pd.to_datetime(row_data['booking_date'])
    date_str = dt.strftime("%d/%m/%Y")
    day_str = dt.strftime("%A")
    time_range = f"{convert_to_12h(row_data['start_time'])} - {convert_to_12h(row_data['end_time'])}"
    
    msg = (
        f"{date_str}#{day_str}#{time_range}#{row_data['booked_by']}#\n"
        f"{row_data['mobile_number']}#₹{int(row_data['total_charges'])}#\n"
        f"Advance received: ₹{int(row_data['advance_paid'])}#Balance: ₹{int(row_data['remaining_due'])}#"
    )
    return msg

def format_wa_personal_msg(row_data):
    """Personal message for the customer"""
    time_range = f"{convert_to_12h(row_data['start_time'])} to {convert_to_12h(row_data['end_time'])}"
    msg = (
        f"Hello {row_data['booked_by']},\n\n"
        f"This is from *Sai Star Ground*. Your booking is confirmed for:\n"
        f"📅 *Date:* {pd.to_datetime(row_data['booking_date']).strftime('%d-%b-%Y')}\n"
        f"⏰ *Time:* {time_range}\n"
        f"💰 *Total Fees:* ₹{int(row_data['total_charges'])}\n"
        f"✅ *Advance:* ₹{int(row_data['advance_paid'])}\n"
        f"⏳ *Balance:* ₹{int(row_data['remaining_due'])}\n\n"
        f"See you at the ground! 🏏"
    )
    return msg

def init_session_state():
    if 'form_id' not in st.session_state: st.session_state['form_id'] = 0 
    if 'edit_mode' not in st.session_state: st.session_state['edit_mode'] = False
    if 'success_msg' not in st.session_state: st.session_state['success_msg'] = None
    if 'last_added_id' not in st.session_state: st.session_state['last_added_id'] = None

# --- DATA FUNCTIONS ---
def get_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        df.columns = [str(c).lower().strip() for c in df.columns]
        for col in EXPECTED_HEADERS:
            if col not in df.columns: df[col] = "" 
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        money_cols = ['rate_per_hour', 'total_charges', 'advance_paid', 'balance_paid', 'remaining_due']
        for col in money_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        df['mobile_number'] = df['mobile_number'].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
        return df
    except: return pd.DataFrame(columns=EXPECTED_HEADERS)

def save_data(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    conn.update(worksheet="Sheet1", data=df)

# -----------------------------------------------------------------------------
# 3. MAIN APP
# -----------------------------------------------------------------------------
def main():
    st.markdown("""<style>.block-container {padding-top: 1rem !important;} header {visibility: hidden;}</style>""", unsafe_allow_html=True)
    
    logo_file = "Sai_Star_logo__2_-removebg-preview.png"
    if os.path.exists(logo_file):
        c1, c2, c3 = st.columns([3, 2, 3]); c2.image(logo_file, use_container_width=True)
    else: st.title("🏏 Sai Star Booking Manager")
    
    init_session_state()
    df = get_data()
    if not df.empty: df['dt_obj'] = pd.to_datetime(df['booking_date']).dt.date

    # --- EDIT SCREEN ---
    if st.session_state['edit_mode']:
        record = df[df['id'] == st.session_state['edit_id']].iloc[0]
        st.subheader(f"✏️ Edit Booking")
        with st.form("edit_form"):
            c1, c2, c3 = st.columns(3)
            e_date = c1.date_input("Date", value=pd.to_datetime(record['booking_date']))
            e_name = c2.text_input("Name", value=record['booked_by'])
            e_mobile = c3.text_input("Mobile", value=record['mobile_number'])
            
            ts = get_time_slots()
            c4, c5, c6 = st.columns(3)
            e_start = c4.selectbox("Start", ts, index=ts.index(record['start_time']) if record['start_time'] in ts else 0, format_func=convert_to_12h)
            e_end = c5.selectbox("End", ts, index=ts.index(record['end_time']) if record['end_time'] in ts else 0, format_func=convert_to_12h)
            e_rate = c6.number_input("Rate", value=int(record['rate_per_hour']))
            
            c7, c8, c9 = st.columns(3)
            e_adv = c7.number_input("Advance", value=int(record['advance_paid']))
            e_bal = c8.number_input("Balance Paid", value=int(record['balance_paid']))
            e_mode = c9.selectbox("Mode", PAYMENT_MODES, index=PAYMENT_MODES.index(record['advance_mode']) if record['advance_mode'] in PAYMENT_MODES else 0)
            
            if st.form_submit_button("Save Changes", type="primary"):
                dur = (datetime.strptime(e_end, "%H:%M") - datetime.strptime(e_start, "%H:%M")).total_seconds() / 3600
                tot = int(dur * e_rate)
                idx = df.index[df['id'] == st.session_state['edit_id']][0]
                df.loc[idx, ['booking_date','booked_by','mobile_number','start_time','end_time','total_charges','advance_paid','balance_paid','remaining_due','advance_mode']] = [e_date.strftime("%Y-%m-%d"), e_name, e_mobile, e_start, e_end, tot, e_adv, e_bal, int(tot-e_adv-e_bal), e_mode]
                save_data(df); st.session_state.update({'edit_mode': False, 'success_msg': "Updated!"}); st.rerun()
            if st.form_submit_button("Cancel"): st.session_state['edit_mode'] = False; st.rerun()

    # --- MAIN SCREEN ---
    else:
        with st.expander("➕ Add New Booking"):
            with st.form("add_form"):
                fid = st.session_state['form_id']
                c1, c2, c3 = st.columns(3)
                b_date = c1.date_input("Date", key=f"d{fid}")
                b_name = c2.text_input("Name", key=f"n{fid}")
                b_mobile = c3.text_input("Mobile", key=f"m{fid}")
                
                ts = get_time_slots()
                c4, c5, c6 = st.columns(3)
                b_start = c4.selectbox("Start", ts, index=40, format_func=convert_to_12h, key=f"s{fid}")
                b_end = c5.selectbox("End", ts, index=44, format_func=convert_to_12h, key=f"e{fid}")
                b_rate = c6.number_input("Rate", value=1000, key=f"r{fid}")
                
                c7, c8 = st.columns(2)
                b_adv = c7.number_input("Advance", value=0, key=f"a{fid}")
                b_mode = c8.selectbox("Mode", PAYMENT_MODES, key=f"mo{fid}")
                
                if st.form_submit_button("Confirm Booking", type="primary"):
                    dur = (datetime.strptime(b_end, "%H:%M") - datetime.strptime(b_start, "%H:%M")).total_seconds() / 3600
                    tot, nid = int(dur * b_rate), 1 if df.empty else df['id'].max() + 1
                    new_row = pd.DataFrame([{"id": nid, "booking_date": b_date.strftime("%Y-%m-%d"), "start_time": b_start, "end_time": b_end, "booked_by": b_name, "mobile_number": b_mobile, "total_charges": tot, "advance_paid": b_adv, "remaining_due": tot-b_adv, "advance_mode": b_mode}])
                    save_data(pd.concat([df, new_row]))
                    st.session_state.update({'last_added_id': nid, 'success_msg': "Booking Added!", 'form_id': fid+1})
                    st.rerun()

        # Success Msg & Dual WhatsApp Buttons
        if st.session_state['success_msg']:
            st.success(st.session_state['success_msg'])
            if st.session_state['last_added_id']:
                last_rec = get_data().query(f"id == {st.session_state['last_added_id']}").iloc[0]
                wa_group = format_wa_group_msg(last_rec)
                wa_personal = format_wa_personal_msg(last_rec)
                
                col_a, col_b = st.columns(2)
                col_a.link_button("📢 Send to Group", f"https://wa.me/?text={urllib.parse.quote(wa_group)}", use_container_width=True)
                col_b.link_button(f"👤 Send to {last_rec['booked_by']}", f"https://wa.me/{last_rec['mobile_number']}?text={urllib.parse.quote(wa_personal)}", use_container_width=True)
            if st.button("Close Notifications"): st.session_state.update({'success_msg': None, 'last_added_id': None}); st.rerun()

        # Upcoming Grid
        st.subheader("📅 Upcoming Bookings")
        if not df.empty:
            today = datetime.now().date()
            future_df = df[df['dt_obj'] >= today].sort_values(['booking_date', 'start_time'])
            
            if not future_df.empty:
                # Share All Button
                all_msg = "🏏 *SAI STAR SCHEDULE* 🏏\n\n" + "\n---\n".join([format_wa_group_msg(row) for _, row in future_df.iterrows()])
                st.link_button("📋 Share Full List to Group", f"https://wa.me/?text={urllib.parse.quote(all_msg)}")
                
                # We use columns to show the "Quick Message" feature
                for _, row in future_df.iterrows():
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                        c1.markdown(f"**{pd.to_datetime(row['booking_date']).strftime('%d/%m')}** | {convert_to_12h(row['start_time'])}")
                        c2.markdown(f"**{row['booked_by']}**")
                        c3.markdown(f"Due: ₹{row['remaining_due']}")
                        
                        # Direct Chat Button
                        personal_msg = format_wa_personal_msg(row)
                        c4.link_button("📲 Chat", f"https://wa.me/{row['mobile_number']}?text={urllib.parse.quote(personal_msg)}")
                        
                        # Re-using select logic for editing
                        if c1.button("Edit", key=f"ed_{row['id']}"):
                            st.session_state.update({'edit_mode': True, 'edit_id': row['id']})
                            st.rerun()

        # History
        with st.expander("📜 History"):
            past_df = df[df['dt_obj'] < today].sort_values('booking_date', ascending=False)
            if not past_df.empty:
                st.dataframe(past_df, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
