import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta, time

# --- Configuration & Setup ---
st.set_page_config(page_title="Cricket Turf Booking", layout="wide")
DB_FILE = 'turf_bookings.db'

# --- Database Functions ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_date TEXT,
            start_time TEXT,
            end_time TEXT,
            total_hours REAL,
            rate_per_hour REAL,
            total_charges REAL,
            booked_by TEXT,
            advance_paid REAL,
            advance_mode TEXT,
            pending_amount REAL,
            pending_mode TEXT
        )
    ''')
    conn.commit()
    conn.close()

def check_overlap(date_str, start_str, end_str, exclude_id=None):
    """
    Checks if the time slot overlaps with existing bookings.
    exclude_id is used when Editing (to ignore the record currently being edited).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Logic: New Start < Existing End AND New End > Existing Start
    query = '''
        SELECT count(*) FROM bookings 
        WHERE booking_date = ? 
        AND start_time < ? 
        AND end_time > ?
    '''
    params = [date_str, end_str, start_str]
    
    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)
        
    c.execute(query, tuple(params))
    count = c.fetchone()[0]
    conn.close()
    return count > 0

def add_booking(data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO bookings (booking_date, start_time, end_time, total_hours, 
                              rate_per_hour, total_charges, booked_by, 
                              advance_paid, advance_mode, pending_amount, pending_mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', data)
    conn.commit()
    conn.close()

def update_booking(booking_id, data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Unpack data (excluding ID)
    (b_date, b_start, b_end, duration, rate, total, booked_by, adv, adv_mode, pend, pend_mode) = data
    
    c.execute('''
        UPDATE bookings 
        SET booking_date=?, start_time=?, end_time=?, total_hours=?, 
            rate_per_hour=?, total_charges=?, booked_by=?, 
            advance_paid=?, advance_mode=?, pending_amount=?, pending_mode=?
        WHERE id=?
    ''', (*data, booking_id))
    conn.commit()
    conn.close()

def delete_booking(booking_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()

def get_all_bookings():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM bookings ORDER BY booking_date DESC, start_time ASC", conn)
    conn.close()
    return df

def get_booking_by_id(booking_id):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM bookings WHERE id = ?", conn, params=(booking_id,))
    conn.close()
    return df.iloc[0] if not df.empty else None

# --- Helper: Generate 30 min slots ---
def get_time_slots():
    slots = []
    start = datetime.strptime("00:00", "%H:%M")
    end = datetime.strptime("23:30", "%H:%M")
    while start <= end:
        slots.append(start.strftime("%H:%M"))
        start += timedelta(minutes=30)
    return slots

# --- Main App ---
def main():
    init_db()
    st.title("🏏 Cricket Academy Booking Manager")

    # --- Sidebar: Add New Booking ---
    with st.sidebar:
        st.header("➕ New Booking")
        
        with st.form("add_booking_form", clear_on_submit=True):
            b_date = st.date_input("Date", datetime.now())
            
            time_slots = get_time_slots()
            # Default indices
            s_idx = time_slots.index("06:00") if "06:00" in time_slots else 0
            e_idx = time_slots.index("07:00") if "07:00" in time_slots else 1
            
            c1, c2 = st.columns(2)
            b_start = c1.selectbox("Start", time_slots, index=s_idx)
            b_end = c2.selectbox("End", time_slots, index=e_idx)
            
            rate = st.number_input("Rate/Hr (₹)", value=1000, step=100)
            booked_by = st.text_input("Booked By")
            
            st.divider()
            adv_paid = st.number_input("Advance (₹)", value=0, step=100)
            adv_mode = st.radio("Adv. Mode", ["Cash", "GPay"], horizontal=True)
            pending_mode = st.selectbox("Pending Mode", ["Cash", "GPay", "Pending"])
            
            submitted = st.form_submit_button("Confirm Booking")

            if submitted:
                # Validation & Calc
                if b_start >= b_end:
                    st.error("End time must be after Start time.")
                elif check_overlap(b_date, b_start, b_end):
                    st.error(f"⚠️ Overlap detected on {b_date} ({b_start}-{b_end})")
                else:
                    fmt = "%H:%M"
                    dur = (datetime.strptime(b_end, fmt) - datetime.strptime(b_start, fmt)).total_seconds() / 3600
                    total = dur * rate
                    pend = total - adv_paid
                    
                    add_booking((b_date, b_start, b_end, dur, rate, total, booked_by, adv_paid, adv_mode, pend, pending_mode))
                    st.success("Booking Added!")
                    st.rerun()

    # --- Main Area ---
    df = get_all_bookings()
    
    # Stats
    if not df.empty:
        total_rev = df['total_charges'].sum()
        pending_rev = df['pending_amount'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Bookings", len(df))
        c2.metric("Total Revenue", f"₹{total_rev:,.0f}")
        c3.metric("Pending Collection", f"₹{pending_rev:,.0f}")
    
    st.divider()
    
    tab1, tab2 = st.tabs(["📅 Schedule View", "✏️ Edit / Delete"])
    
    # --- Tab 1: Table View ---
    with tab1:
        if df.empty:
            st.info("No bookings yet.")
        else:
            display_df = df.copy()
            # Beautify for display
            display_df['total_charges'] = display_df['total_charges'].map('₹{:,.0f}'.format)
            display_df['pending_amount'] = display_df['pending_amount'].map('₹{:,.0f}'.format)
            display_df['booking_date'] = pd.to_datetime(display_df['booking_date']).dt.strftime('%Y-%m-%d')
            
            st.dataframe(
                display_df, 
                use_container_width=True,
                column_config={
                    "id": "ID", "booking_date": "Date", "start_time": "Start",
                    "end_time": "End", "total_hours": "Hrs", "booked_by": "Name",
                    "advance_paid": "Adv", "pending_amount": "Pending"
                },
                hide_index=True
            )

    # --- Tab 2: Edit / Delete ---
    with tab2:
        if df.empty:
            st.write("No records to edit.")
        else:
            # 1. Select Record
            df['label'] = df['booking_date'].astype(str) + " | " + df['start_time'] + " - " + df['booked_by']
            edit_id = st.selectbox("Select Booking to Edit/Delete", options=df['id'], format_func=lambda x: df[df['id'] == x]['label'].values[0])
            
            # 2. Get Current Data
            record = get_booking_by_id(edit_id)
            
            if record is not None:
                st.subheader(f"Editing Booking #{edit_id} - {record['booked_by']}")
                
                with st.form("edit_form"):
                    col_a, col_b = st.columns(2)
                    
                    # Pre-fill Date
                    e_date = col_a.date_input("Date", datetime.strptime(record['booking_date'], '%Y-%m-%d'))
                    
                    # Pre-fill Time
                    time_slots = get_time_slots()
                    try:
                        s_idx = time_slots.index(record['start_time'])
                        e_idx = time_slots.index(record['end_time'])
                    except:
                        s_idx, e_idx = 0, 1
                        
                    e_start = col_a.selectbox("Start", time_slots, index=s_idx, key='e_start')
                    e_end = col_b.selectbox("End", time_slots, index=e_idx, key='e_end')
                    
                    e_rate = col_a.number_input("Rate/Hr", value=float(record['rate_per_hour']))
                    e_name = col_b.text_input("Booked By", value=record['booked_by'])
                    
                    st.markdown("---")
                    e_adv = col_a.number_input("Advance Paid", value=float(record['advance_paid']))
                    
                    # Map radio index
                    adv_opts = ["Cash", "GPay"]
                    adv_idx = adv_opts.index(record['advance_mode']) if record['advance_mode'] in adv_opts else 0
                    e_adv_mode = col_b.radio("Adv Mode", adv_opts, index=adv_idx, horizontal=True)
                    
                    # Map pending index
                    pen_opts = ["Cash", "GPay", "Pending"]
                    pen_idx = pen_opts.index(record['pending_mode']) if record['pending_mode'] in pen_opts else 2
                    e_pen_mode = st.selectbox("Pending Bal. Mode", pen_opts, index=pen_idx)
                    
                    c_upd, c_del = st.columns([1,1])
                    update_btn = c_upd.form_submit_button("💾 Update Record", type="primary")
                    # Note: Delete inside a form is tricky, so we do it outside or use a trick.
                    # Ideally separate forms, but for simplicity, we focus on Update here.
                
                # Delete Button (Outside form to avoid validation clashes)
                if st.button("🗑️ Delete This Record"):
                    delete_booking(edit_id)
                    st.success("Deleted!")
                    st.rerun()

                if update_btn:
                    # Logic
                    if e_start >= e_end:
                        st.error("End time must be after Start time.")
                    # Check overlap EXCLUDING current ID
                    elif check_overlap(e_date, e_start, e_end, exclude_id=edit_id):
                        st.error("⚠️ Overlap with another booking!")
                    else:
                        fmt = "%H:%M"
                        dur = (datetime.strptime(e_end, fmt) - datetime.strptime(e_start, fmt)).total_seconds() / 3600
                        tot = dur * e_rate
                        pen = tot - e_adv
                        
                        update_booking(edit_id, (e_date, e_start, e_end, dur, e_rate, tot, e_name, e_adv, e_adv_mode, pen, e_pen_mode))
                        st.success("Record Updated Successfully!")
                        st.rerun()

if __name__ == "__main__":
    main()