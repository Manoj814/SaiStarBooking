import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import io
import os 
import urllib.parse 
import re 

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
    if len(num_str) == 10:
        return f"91{num_str}"
    return num_str

def convert_to_12h(time_str):
    try:
        return datetime.strptime(time_str, "%H:%M").strftime("%I:%M %p")
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
            if time_str > after_time:
                slots.append(time_str)
        else:
            slots.append(time_str)
        current += timedelta(minutes=30)
    return slots

def format_wa_group_msg(row_data):
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
    time_range = f"{convert_to_12h(row_data['start_time'])} to {convert_to_12h(row_data['end_time'])}"
    msg = (
        f"Hello {row_data['booked_by']},\n\n"
        f"This is from *Sai Star Ground*. Your booking is confirmed:\n"
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
    if 'edit_id' not in st.session_state: st.session_state['edit_id'] = None
    if 'success_msg' not in st.session_state: st.session_state['success_msg'] = None
    if 'last_added_id' not in st.session_state: st.session_state['last_added_id'] = None

# --- UPDATED DATA FUNCTION WITH AUTOMATIC SORTING LOGIC ---
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
        
        # --- NEW SORTING CONVERSION ---
        if not df.empty:
            # Create a true date object
            df['dt_obj'] = pd.to_datetime(df['booking_date']).dt.date
            # Create a true time object for sorting (HH:MM:SS)
            df['sort_time'] = pd.to_datetime(df['start_time'], format='%H:%M').dt.time
            # Sort the entire dataframe globally by Date then Time
            df = df.sort_values(by=['dt_obj', 'sort_time'], ascending=[True, True])
        
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
    
    init_session_state()
    df = get_data()

    # --- EDIT SCREEN ---
    if st.session_state['edit_mode']:
        record = df[df['id'] == st.session_state['edit_id']].iloc[0]
        st.subheader(f"✏️ Edit Booking")
        with st.form("edit_form"):
            c1, c2, c3 = st.columns(3)
            e_date = c1.date_input("Date", value=pd.to_datetime(record['booking_date']))
            e_name = c2.text_input("Name", value=str(record['booked_by']))
            e_mobile = c3.text_input("Mobile", value=str(record['mobile_number']))
            
            ts = get_time_slots(0, 23)
            c4, c5, c6 = st.columns(3)
            e_start = c4.selectbox("Start Time", ts, index=ts.index(record['start_time']) if record['start_time'] in ts else 0, format_func=convert_to_12h)
            end_ts_edit = get_time_slots(0, 23, after_time=e_start)
            e_end = c5.selectbox("End Time", end_ts_edit, index=end_ts_edit.index(record['end_time']) if record['end_time'] in end_ts_edit else 0, format_func=convert_to_12h)
            e_rate = c6.number_input("Rate per Hour", value=int(record['rate_per_hour']))
            
            c7, c8, c9 = st.columns(3)
            e_adv = c7.number_input("Advance Amount", value=int(record['advance_paid']))
            e_bal = c8.number_input("Balance Paid", value=int(record['balance_paid']))
            e_mode = c9.selectbox("Mode", PAYMENT_MODES, index=PAYMENT_MODES.index(record['advance_mode']) if record['advance_mode'] in PAYMENT_MODES else 0)
            
            col_save, col_del, col_can = st.columns([1, 1, 3])
            if col_save.form_submit_button("💾 Save", type="primary"):
                dur = (datetime.strptime(e_end, "%H:%M") - datetime.strptime(e_start, "%H:%M")).total_seconds() / 3600
                tot = int(dur * e_rate)
                idx = df.index[df['id'] == st.session_state['edit_id']][0]
                df.loc[idx, ['booking_date','booked_by','mobile_number','start_time','end_time','total_hours','rate_per_hour','total_charges','advance_paid','balance_paid','remaining_due','advance_mode']] = [
                    e_date.strftime("%Y-%m-%d"), e_name, e_mobile, e_start, e_end, dur, int(e_rate), tot, int(e_adv), int(e_bal), int(tot-e_adv-e_bal), e_mode
                ]
                save_data(df); st.session_state.update({'edit_mode': False, 'success_msg': "✅ Updated!"}); st.rerun()
            if col_del.form_submit_button("🗑️ Delete"):
                df = df[df['id'] != st.session_state['edit_id']]
                save_data(df); st.session_state.update({'edit_mode': False, 'success_msg': "🗑️ Deleted!"}); st.rerun()
            if col_can.form_submit_button("Cancel"):
                st.session_state['edit_mode'] = False; st.rerun()

    # --- MAIN SCREEN ---
    else:
        with st.expander("➕ Add New Booking"):
            fid = st.session_state['form_id']
            c1, c2, c3 = st.columns(3)
            b_date = c1.date_input("Date", key=f"d{fid}")
            b_name = c2.text_input("Name", key=f"n{fid}")
            b_mobile = c3.text_input("Mobile", key=f"m{fid}")
            
            ts_start = get_time_slots(6, 23)
            c4, c5, c6 = st.columns(3)
            b_start = c4.selectbox("Start", ts_start, index=ts_start.index("20:00"), format_func=convert_to_12h, key=f"s{fid}")
            ts_end = get_time_slots(6, 23, after_time=b_start)
            
            e_def = "21:00" if b_start == "20:00" else ("22:30" if b_start == "21:00" else None)
            e_idx = ts_end.index(e_def) if e_def in ts_end else 0
            
            b_end = c5.selectbox("End", ts_end, index=e_idx, format_func=convert_to_12h, key=f"e{fid}")
            b_rate = c6.number_input("Rate", value=1000, key=f"r{fid}")
            
            c7, c8 = st.columns(2)
            b_adv = c7.number_input("Advance", value=0, key=f"a{fid}")
            b_mode = c8.selectbox("Mode", PAYMENT_MODES, key=f"mo{fid}")
            
            if st.button("Confirm Booking", type="primary"):
                dur = (datetime.strptime(b_end, "%H:%M") - datetime.strptime(b_start, "%H:%M")).total_seconds() / 3600
                tot = int(dur * b_rate)
                nid = 1 if df.empty else df['id'].max() + 1
                new_row = pd.DataFrame([{"id": nid, "booking_date": b_date.strftime("%Y-%m-%d"), "start_time": b_start, "end_time": b_end, "total_hours": dur, "rate_per_hour": int(b_rate), "booked_by": b_name, "mobile_number": b_mobile, "total_charges": tot, "advance_paid": b_adv, "remaining_due": tot-b_adv, "advance_mode": b_mode}])
                save_data(pd.concat([df, new_row]))
                st.session_state.update({'last_added_id': nid, 'success_msg': "✅ Added!", 'form_id': fid+1})
                st.rerun()

        if st.session_state['success_msg']:
            st.success(st.session_state['success_msg'])
            if st.session_state['last_added_id']:
                current_df = get_data() # This fetches freshly sorted data
                try:
                    last = current_df.query(f"id == {st.session_state['last_added_id']}").iloc[0]
                    ca, cb = st.columns(2)
                    ca.link_button("📢 Group WhatsApp", f"https://wa.me/?text={urllib.parse.quote(format_wa_group_msg(last))}")
                    cb.link_button(f"👤 Message {last['booked_by']}", f"https://wa.me/{clean_phone_number(last['mobile_number'])}?text={urllib.parse.quote(format_wa_personal_msg(last))}")
                except: pass
            if st.button("Close Notifications"): st.session_state.update({'success_msg': None, 'last_added_id': None}); st.rerun()

        st.subheader("📅 Upcoming Bookings")
        if not df.empty:
            today = datetime.now().date()
            # Since df is sorted in get_data, we just filter it
            future_df = df[df['dt_obj'] >= today]
            
            if not future_df.empty:
                all_msg = "🏏 *SCHEDULE* 🏏\n\n" + "\n---\n".join([format_wa_group_msg(row) for _, row in future_df.iterrows()])
                st.link_button("📋 Share Full Schedule", f"https://wa.me/?text={urllib.parse.quote(all_msg)}")
                
                # Re-calculate S.No based on current filtered view
                future_df = future_df.copy()
                future_df['S.No'] = range(1, len(future_df) + 1)
                future_df['formatted_start'] = future_df['start_time'].apply(convert_to_12h)
                future_df['formatted_end'] = future_df['end_time'].apply(convert_to_12h)
                future_df['wa_link'] = future_df.apply(lambda r: f"https://wa.me/{clean_phone_number(r['mobile_number'])}?text={urllib.parse.quote(format_wa_personal_msg(r))}", axis=1)

                grid_cols = {
                    "S.No": st.column_config.NumberColumn("S.No", width="small"),
                    "booking_date": "Date", "formatted_start": "Start", "formatted_end": "End",
                    "booked_by": "Name", "mobile_number": "Mobile",
                    "total_charges": st.column_config.NumberColumn("Total", format="₹%d"),
                    "advance_paid": st.column_config.NumberColumn("Adv. Paid", format="₹%d"),
                    "remaining_due": st.column_config.NumberColumn("Due", format="₹%d"),
                    "wa_link": st.column_config.LinkColumn("WhatsApp", display_text="Chat 📲")
                }

                ev = st.dataframe(
                    future_df, 
                    column_config=grid_cols, 
                    column_order=["S.No", "booking_date", "formatted_start", "formatted_end", "booked_by", "mobile_number", "total_charges", "advance_paid", "remaining_due", "wa_link"], 
                    use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="u_grid"
                )
                if ev.selection.rows:
                    st.session_state.update({'edit_mode': True, 'edit_id': future_df.iloc[ev.selection.rows[0]]['id']})
                    st.rerun()
            else: st.info("No bookings.")

        with st.expander("📜 History"):
            past_df = df[df['dt_obj'] < today].sort_values(by=['dt_obj', 'sort_time'], ascending=[False, False])
            if not past_df.empty:
                st.dataframe(past_df, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
