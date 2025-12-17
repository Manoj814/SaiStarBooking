import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import io

# 1. Page Configuration (MUST be the first Streamlit command)
st.set_page_config(page_title="Cricket Turf Booking", layout="wide")

# 2. Define the Pop-up Function (MUST be outside main)
# Note: This requires Streamlit version 1.34+. 
# If you get an error like "no attribute dialog", update requirements.txt to streamlit>=1.34.0
@st.dialog("Booking Confirmation")
def show_modal(message):
    st.success(message)
    st.write("You can close this window now.")

# --- Constants & Helper Functions (Keep your existing ones here) ---
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

# ... (Include your other helper functions: get_time_slots, init_form_state, etc.) ...

# --- Main App ---
def main():
    # 3. Check for Success Message immediately at start of main
    if 'success_msg' in st.session_state:
        # Call the function defined above
        show_modal(st.session_state['success_msg'])
        del st.session_state['success_msg']

    st.title("🏏 Cricket Academy Booking Manager")
    
    # ... (Rest of your main function logic continues here) ...

     
    # 1. HANDLE RESET
    if st.session_state.get('trigger_reset', False):
        reset_form_state()
        st.session_state['trigger_reset'] = False 
    
    # 2. Initialize defaults
    init_form_state()
    
    # 3. Load Data
    df = get_data()

    # --- Section 1: New Booking ---
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
            
            # Updated Payment Section
            p1, p2, p3 = st.columns(3)
            adv_paid = p1.number_input("Advance Paid (₹)", step=100.0, key='f_adv')
            bal_paid = p2.number_input("Balance Paid Now (₹)", step=100.0, key='f_bal')
            # Updated options to include Cash+Gpay
            adv_mode = p3.selectbox("Payment Mode", PAYMENT_MODES, key='f_mode')
            
            # Added Remarks Field
            remarks = st.text_input("Remarks", placeholder="Optional notes (e.g. Regular Customer)", key='f_remarks')
            
            submitted = st.form_submit_button("✅ Confirm Booking", type="primary")

            if submitted:
                # ... save logic ...
                st.session_state['success_msg'] = f"✅ Booking Confirmed for {booked_by}!"
                st.rerun()
                b_date_str = b_date.strftime("%Y-%m-%d")
                
                if b_start >= b_end:
                    st.error("❌ End time must be after Start time.")
                elif check_overlap(df, b_date_str, b_start, b_end):
                    st.error(f"⚠️ Overlap detected on {b_date_str}!")
                else:
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
                        "balance_mode": adv_mode, # Assuming same mode if paid now
                        "remaining_due": remaining,
                        "remarks": remarks
                    }])
                    
                    updated_df = pd.concat([df, new_record], ignore_index=True)
                    save_data(updated_df)
                    
                    st.session_state['trigger_reset'] = True 
                    st.success(f"Booking Confirmed for {booked_by}!")
                    st.rerun()

    st.markdown("---")

    # --- Section 2: Data Splitting ---
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

    # --- Tabs Layout ---
    tab1, tab2, tab3 = st.tabs(["📅 Upcoming Bookings", "📜 Booking History", "✏️ Edit / Update"])

    # Define Column Config for nice display
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

    # --- TAB 1: FUTURE ---
    with tab1:
        if future_df.empty:
            st.info("No upcoming bookings found.")
        else:
            show_f = future_df.copy()
            show_f['formatted_start'] = show_f['start_time'].apply(convert_to_12h)
            show_f['formatted_end'] = show_f['end_time'].apply(convert_to_12h)
            show_f['total_charges'] = show_f['total_charges'].apply(lambda x: f"₹{x:,.0f}")
            show_f['remaining_due'] = show_f['remaining_due'].apply(lambda x: f"₹{x:,.0f}")

            st.dataframe(
                show_f,
                use_container_width=True,
                column_config=grid_config,
                column_order=visible_cols,
                hide_index=True
            )

    # --- TAB 2: PAST ---
    with tab2:
        if past_df.empty:
            st.info("No past booking history.")
        else:
            show_p = past_df.copy()
            show_p['formatted_start'] = show_p['start_time'].apply(convert_to_12h)
            show_p['formatted_end'] = show_p['end_time'].apply(convert_to_12h)
            show_p['total_charges'] = show_p['total_charges'].apply(lambda x: f"₹{x:,.0f}")
            show_p['remaining_due'] = show_p['remaining_due'].apply(lambda x: f"₹{x:,.0f}")

            st.dataframe(
                show_p,
                use_container_width=True,
                column_config=grid_config,
                column_order=visible_cols,
                hide_index=True
            )
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                past_df.drop(columns=['dt_obj'], errors='ignore').to_excel(writer, index=False, sheet_name='History')
            
            st.download_button(
                label="📥 Download History Excel",
                data=output.getvalue(),
                file_name=f"turf_history_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # --- TAB 3: EDIT (Combined) ---
    with tab3:
        if df.empty:
            st.write("No records available.")
        else:
            df['label'] = (
                df['booking_date'].astype(str) + " (" + 
                df['start_time'].astype(str) + ") - " + 
                df['booked_by'].astype(str)
            )
            id_to_label = dict(zip(df['id'], df['label']))

            if search_query:
                search_mask = (
                    df['booked_by'].str.contains(search_query, case=False, na=False) | 
                    df['booking_date'].astype(str).str.contains(search_query, case=False, na=False)
                )
                options = df[search_mask]['id'].tolist()
            else:
                options = df['id'].tolist()
                
            if not options:
                st.warning("No records match your search to edit.")
            else:
                edit_id = st.selectbox(
                    "Select Booking to Edit", 
                    options=options, 
                    format_func=lambda x: id_to_label.get(x, f"ID: {x}")
                )
                
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
                    except: s_idx, e_idx = 40, 42
                    
                    e_start = c_a.selectbox("Start", time_slots, index=s_idx, format_func=convert_to_12h, key='es')
                    e_end = c_b.selectbox("End", time_slots, index=e_idx, format_func=convert_to_12h, key='ee')
                    e_rate = c_a.number_input("Ground Fees", value=float(record['rate_per_hour']))
                    
                    st.divider()
                    st.write("**Payment & Remarks**")
                    pa, pb = st.columns(2)
                    e_adv = pa.number_input("Advance Paid", value=float(record['advance_paid']))
                    e_bal_paid = pb.number_input("Balance Amount Paid", value=float(record['balance_paid']))
                    
                    # Ensure the current mode is valid in our new list
                    curr_mode = record['advance_mode'] if record['advance_mode'] in PAYMENT_MODES else "Cash"
                    try:
                        mode_idx = PAYMENT_MODES.index(curr_mode)
                    except ValueError:
                        mode_idx = 0

                    e_mode = st.selectbox("Payment Mode", PAYMENT_MODES, index=mode_idx)
                    e_remarks = st.text_input("Remarks", value=str(record['remarks']))

                    upd_submit = st.form_submit_button("💾 Save Changes", type="primary")

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
                        df.at[idx, 'remarks'] = e_remarks # Update remarks
                        
                        save_data(df)
                        st.success("Updated Successfully!")
                        st.rerun()

if __name__ == "__main__":
    main()






