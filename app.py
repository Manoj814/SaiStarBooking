import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import io

# --- Configuration ---
st.set_page_config(page_title="Cricket Turf Booking", layout="wide")

# --- Constants ---
EXPECTED_HEADERS = [
    "id", "booking_date", "start_time", "end_time", 
    "total_hours", "rate_per_hour", "total_charges", 
    "booked_by", "advance_paid", "advance_mode", 
    "balance_paid", "balance_mode", # New/Renamed fields
    "remaining_due" # Calculated final pending
]

# --- Database Functions ---

def get_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        if df.empty or len(df.columns) < len(EXPECTED_HEADERS):
            return pd.DataFrame(columns=EXPECTED_HEADERS)
            
        # Type conversion
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        cols_to_float = ['total_hours', 'rate_per_hour', 'total_charges', 'advance_paid', 'balance_paid', 'remaining_due']
        for col in cols_to_float:
            # Check if col exists (for backward compatibility), if not create it with 0.0
            if col not in df.columns:
                df[col] = 0.0
            else:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        return df
    except Exception:
        return pd.DataFrame(columns=EXPECTED_HEADERS)

def save_data(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    conn.update(worksheet="Sheet1", data=df)

def check_overlap(df, date_str, start_str, end_str, exclude_id=None):
    if df.empty:
        return False
    
    # Ensure date comparison works by converting to string
    day_bookings = df[df['booking_date'].astype(str) == str(date_str)]
    
    if exclude_id is not None:
        day_bookings = day_bookings[day_bookings['id'] != exclude_id]
        
    if day_bookings.empty:
        return False
        
    overlap = day_bookings[
        (day_bookings['start_time'] < end_str) & 
        (day_bookings['end_time'] > start_str)
    ]
    return not overlap.empty

def get_next_id(df):
    if df.empty:
        return 1
    return df['id'].max() + 1

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
    st.title("🏏 Cricket Academy Booking Manager")

    # Load Data
    df = get_data()

    # --- Section 1: New Booking (Expander for Mobile Stability) ---
    # We use st.expander instead of sidebar so it doesn't close on interaction
    with st.expander("➕ Create New Booking", expanded=False):
        with st.form("add_booking_form", clear_on_submit=True):
            col_date, col_name = st.columns([1, 2])
            b_date = col_date.date_input("Date", datetime.now())
            booked_by = col_name.text_input("Booked By (Name)")
            
            time_slots = get_time_slots()
            s_idx = time_slots.index("06:00") if "06:00" in time_slots else 0
            e_idx = time_slots.index("07:00") if "07:00" in time_slots else 1
            
            c1, c2, c3 = st.columns(3)
            b_start = c1.selectbox("Start Time", time_slots, index=s_idx)
            b_end = c2.selectbox("End Time", time_slots, index=e_idx)
            rate = c3.number_input("Rate/Hr (₹)", value=1000, step=100)
            
            st.markdown("---")
            st.caption("Payment Details")
            p1, p2, p3 = st.columns(3)
            adv_paid = p1.number_input("Advance Paid (₹)", value=0, step=100)
            bal_paid = p2.number_input("Balance Paid Now (₹)", value=0, step=100, help="If they pay the remaining amount immediately")
            
            adv_mode = p3.radio("Payment Mode", ["Cash", "GPay", "Pending"], horizontal=True)
            
            submitted = st.form_submit_button("✅ Confirm Booking", type="primary")

            if submitted:
                b_date_str = b_date.strftime("%Y-%m-%d")
                
                if b_start >= b_end:
                    st.error("Error: End time must be after Start time.")
                elif check_overlap(df, b_date_str, b_start, b_end):
                    st.error(f"⚠️ Overlap! Ground already booked on {b_date_str} ({b_start}-{b_end})")
                else:
                    # Calculations
                    fmt = "%H:%M"
                    dur = (datetime.strptime(b_end, fmt) - datetime.strptime(b_start, fmt)).total_seconds() / 3600
                    total = dur * rate
                    # Logic: Total - Advance - BalancePaidNow = Remaining Due
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
                        "balance_paid": bal_paid, # New field
                        "balance_mode": adv_mode, # Assuming same mode for simplicity, or "Pending"
                        "remaining_due": remaining
                    }])
                    
                    updated_df = pd.concat([df, new_record], ignore_index=True)
                    save_data(updated_df)
                    st.success(f"Booking Confirmed for {booked_by}!")
                    st.rerun() # Refresh to show in table immediately

    st.markdown("---")

    # --- Section 2: View, Search & Download ---
    
    # Search Bar
    search_query = st.text_input("🔍 Search Bookings (Name or Date YYYY-MM-DD)", placeholder="Type name or date...")

    # Filter Data based on Search
    if not df.empty:
        # Sort desc
        display_df = df.sort_values(by=['booking_date', 'start_time'], ascending=[False, True])
        
        if search_query:
            display_df = display_df[
                display_df['booked_by'].str.contains(search_query, case=False, na=False) | 
                display_df['booking_date'].astype(str).str.contains(search_query, case=False, na=False)
            ]
    else:
        display_df = pd.DataFrame()

    # Stats Row
    if not display_df.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Records Found", len(display_df))
        c2.metric("Total Revenue", f"₹{display_df['total_charges'].sum():,.0f}")
        c3.metric("Total Collected", f"₹{(display_df['advance_paid'].sum() + display_df['balance_paid'].sum()):,.0f}")
        c4.metric("Outstanding Due", f"₹{display_df['remaining_due'].sum():,.0f}", delta_color="inverse")

        # Excel Download Button
        # We use BytesIO to create a file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            display_df.to_excel(writer, index=False, sheet_name='Bookings')
        excel_data = output.getvalue()

        st.download_button(
            label="📥 Download Excel Grid",
            data=excel_data,
            file_name=f"turf_bookings_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    tab1, tab2 = st.tabs(["📅 Schedule Table", "✏️ Edit / Update Payment"])

    with tab1:
        if display_df.empty:
            st.info("No bookings found matching your criteria.")
        else:
            # Visual formatting
            show_df = display_df.copy()
            show_df['booking_date'] = pd.to_datetime(show_df['booking_date']).dt.strftime('%Y-%m-%d')
            show_df['total_charges'] = show_df['total_charges'].apply(lambda x: f"₹{x:,.0f}")
            show_df['remaining_due'] = show_df['remaining_due'].apply(lambda x: f"₹{x:,.0f}")
            
            st.dataframe(
                show_df,
                use_container_width=True,
                column_config={
                    "id": "ID", "booking_date": "Date", "start_time": "Start",
                    "end_time": "End", "booked_by": "Name",
                    "total_hours": "Hrs", "advance_paid": "Adv",
                    "balance_paid": "Bal Paid",
                    "remaining_due": "Due"
                },
                hide_index=True
            )

    with tab2:
        if df.empty:
            st.write("No records available.")
        else:
            # Edit Dropdown
            df['label'] = df['id'].astype(str) + " | " + df['booking_date'].astype(str) + " (" + df['start_time'] + ") - " + df['booked_by']
            
            # Filter dropdown if search is active, otherwise show all
            if search_query:
                options = df[df['id'].isin(display_df['id'])]['id']
            else:
                options = df['id']
                
            if options.empty:
                st.warning("No records match search.")
            else:
                edit_id = st.selectbox("Select Booking to Edit", options=options, format_func=lambda x: df[df['id'] == x]['label'].values[0])
                
                # Get Record
                record = df[df['id'] == edit_id].iloc[0]
                
                with st.form("edit_form"):
                    st.subheader(f"Edit: {record['booked_by']}")
                    
                    c_a, c_b = st.columns(2)
                    e_date = c_a.date_input("Date", datetime.strptime(str(record['booking_date']), '%Y-%m-%d'))
                    e_name = c_b.text_input("Name", value=record['booked_by'])
                    
                    time_slots = get_time_slots()
                    try:
                        s_idx = time_slots.index(record['start_time'])
                        e_idx = time_slots.index(record['end_time'])
                    except: s_idx, e_idx = 0, 1
                    
                    e_start = c_a.selectbox("Start", time_slots, index=s_idx, key='es')
                    e_end = c_b.selectbox("End", time_slots, index=e_idx, key='ee')
                    e_rate = c_a.number_input("Rate", value=float(record['rate_per_hour']))
                    
                    st.divider()
                    st.write("**Payment Status Update**")
                    pa, pb = st.columns(2)
                    e_adv = pa.number_input("Advance Paid", value=float(record['advance_paid']))
                    e_bal_paid = pb.number_input("Balance Amount Paid", value=float(record['balance_paid']))
                    
                    e_mode = st.radio("Payment Mode", ["Cash", "GPay", "Pending"], horizontal=True, index=0)

                    upd_submit = st.form_submit_button("💾 Save Changes", type="primary")

                # Delete Button
                if st.button("🗑️ Delete Booking", key='del_btn'):
                    df_new = df[df['id'] != edit_id]
                    save_data(df_new)
                    st.success("Record Deleted.")
                    st.rerun()

                if upd_submit:
                    e_date_str = e_date.strftime("%Y-%m-%d")
                    if e_start >= e_end:
                        st.error("End Time Error")
                    elif check_overlap(df, e_date_str, e_start, e_end, exclude_id=edit_id):
                        st.error("Overlap Detected!")
                    else:
                        fmt = "%H:%M"
                        dur = (datetime.strptime(e_end, fmt) - datetime.strptime(e_start, fmt)).total_seconds() / 3600
                        tot = dur * e_rate
                        rem = tot - e_adv - e_bal_paid
                        
                        # Update
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
                        
                        save_data(df)
                        st.success("Updated Successfully!")
                        st.rerun()

if __name__ == "__main__":
    main()
