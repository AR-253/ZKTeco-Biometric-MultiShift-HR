import os
import datetime
from zk import ZK
import db_sqlserver
from shift_engine import DEFAULT_SHIFTS, calculate_punch_status, get_work_date

ZK_MACHINE_IP = "192.168.18.25"
ZK_MACHINE_PORT = 4370


def sync_zkteco_logs(ip=ZK_MACHINE_IP, port=ZK_MACHINE_PORT):
    """
    Connects live to ZKTeco MB360 machine at 192.168.18.25:4370 over the network.
    Fetches machine users & attendance logs, evaluates shift rules, and syncs to MS SQL Server.
    """
    zk = ZK(ip, port=port, timeout=4, password=0, force_udp=False, ommit_ping=True)
    conn = None
    try:
        print(f"Connecting to ZKTeco device at {ip}:{port}...")
        conn = zk.connect()

        # Disable device temporarily for safe data read
        try:
            conn.disable_device()
        except Exception:
            pass

        # 1. Fetch Users
        users = conn.get_users()
        print(f"Fetched {len(users)} registered users from ZKTeco MB360.")

        # 2. Fetch Attendance Logs
        attendance_logs = conn.get_attendance()
        print(f"Fetched {len(attendance_logs)} raw attendance log punches from ZKTeco device!")

        # Re-enable device immediately
        try:
            conn.enable_device()
        except Exception:
            pass
        conn.disconnect()
        conn = None

        if not attendance_logs:
            return {"success": True, "message": "Connected to ZKTeco device, but no attendance records were found.", "count": 0}

        # Sync ZKTeco Users to SQL Server Employees table ONLY IF MISSING (preserves existing shift, role, status)
        db_data = db_sqlserver.fetch_all_data_sql() or {"employees": [], "shifts": DEFAULT_SHIFTS}
        existing_emp_ids = {str(e['id']): e for e in db_data['employees']}

        for u in users:
            u_id = str(u.user_id).strip()
            u_name = str(u.name).strip() if u.name else f"Employee-{u_id}"
            if u_id not in existing_emp_ids:
                emp_obj = {
                    'id': u_id,
                    'name': u_name,
                    'department': 'General',
                    'role': 'Staff',
                    'base_salary': 60000.0,
                    'shift_id': 'S5',
                    'annual_leave_quota': 24.0,
                    'status': 'Active',
                    'join_date': datetime.date.today().strftime('%Y-%m-%d')
                }
                db_sqlserver.save_employee_sql(emp_obj, preserve_existing=True)
                existing_emp_ids[u_id] = emp_obj

        # Refresh employee and shift maps
        db_data = db_sqlserver.fetch_all_data_sql()
        employees_map = {str(e['id']): e for e in db_data['employees']}
        shifts_map = db_data.get('shifts', DEFAULT_SHIFTS)

        # Group punches by (emp_id, work_date) considering overnight shifts
        punches_by_emp_date = {}

        for att in attendance_logs:
            dt = att.timestamp
            user_id = str(att.user_id)

            emp = employees_map.get(user_id)
            shift_id = emp.get('shift_id', 'S5') if emp else 'S5'
            shift = shifts_map.get(shift_id, DEFAULT_SHIFTS['S5'])

            work_date_str = get_work_date(dt, shift)
            time_str = dt.strftime("%H:%M")

            key = (user_id, work_date_str)
            if key not in punches_by_emp_date:
                punches_by_emp_date[key] = []
            punches_by_emp_date[key].append({
                "dt": dt,
                "time_str": time_str,
                "cal_date": dt.strftime("%Y-%m-%d")
            })

        batch_attendance = []

        for (emp_id, work_date_str), punch_items in punches_by_emp_date.items():
            emp = employees_map.get(emp_id)
            shift_id = emp.get('shift_id', 'S5') if emp else 'S5'
            shift = shifts_map.get(shift_id, DEFAULT_SHIFTS['S5'])

            start_h = int(shift.get('start_time', '09:00').split(':')[0])
            end_h = int(shift.get('end_time', '17:00').split(':')[0])
            is_overnight = end_h < start_h

            sorted_items = sorted(punch_items, key=lambda x: x["dt"])

            check_in = None
            check_out = None

            if is_overnight:
                # Separate evening punches (cal_date == work_date or time >= 12:00) vs morning punches
                eve_punches = [p for p in sorted_items if p["cal_date"] == work_date_str or int(p["time_str"].split(':')[0]) >= 12]
                morn_punches = [p for p in sorted_items if p["cal_date"] != work_date_str and int(p["time_str"].split(':')[0]) < 12]

                if eve_punches:
                    check_in = eve_punches[0]["time_str"]
                if morn_punches:
                    check_out = morn_punches[-1]["time_str"]
                elif len(eve_punches) > 1:
                    # Both punches in evening
                    t_last = eve_punches[-1]["time_str"]
                    in_h, in_m = map(int, check_in.split(':'))
                    t_h, t_m = map(int, t_last.split(':'))
                    if (t_h * 60 + t_m) - (in_h * 60 + in_m) >= 10:
                        check_out = t_last
            else:
                # Standard daytime shift
                sorted_times = [p["time_str"] for p in sorted_items]
                check_in = sorted_times[0] if sorted_times else None
                if check_in and len(sorted_times) > 1:
                    in_h, in_m = map(int, check_in.split(':'))
                    in_total_mins = in_h * 60 + in_m
                    for t in reversed(sorted_times):
                        t_h, t_m = map(int, t.split(':'))
                        t_total_mins = t_h * 60 + t_m
                        if t_total_mins < in_total_mins:
                            t_total_mins += 24 * 60
                        if (t_total_mins - in_total_mins) >= 10:
                            check_out = t
                            break

            evaluation = calculate_punch_status(shift, check_in, check_out)

            att_entry = {
                'emp_id': emp_id,
                'emp_name': emp.get('name') if emp else f"Emp-{emp_id}",
                'date': work_date_str,
                'check_in': check_in,
                'check_out': check_out,
                'shift_name': shift.get('name', 'Standard'),
                'shift_id': shift_id,
                'status': evaluation['status'],
                'late_minutes': evaluation['late_minutes'],
                'early_minutes': evaluation['early_minutes'],
                'hours_worked': evaluation['hours_worked'],
                'penalty_days': evaluation['penalty_days'],
                'remarks': evaluation['remarks']
            }
            batch_attendance.append(att_entry)

        # Bulk save into MS SQL Server
        db_sqlserver.save_attendance_batch_sql(batch_attendance)

        # Clean up any bad overnight rows created previously for today's morning check-in
        db_sqlserver.cleanup_invalid_overnight_attendance_sql()

        return {
            "success": True,
            "message": f"Successfully synced {len(batch_attendance)} attendance records & {len(users)} users live from ZKTeco MB360 ({ip}) into MS SQL Server!",
            "users_count": len(users),
            "records_count": len(batch_attendance)
        }

    except Exception as e:
        if conn:
            try:
                conn.enable_device()
                conn.disconnect()
            except Exception:
                pass
        return {"success": False, "error": f"Connection error with ZKTeco machine at {ip}:{port}: {str(e)}"}


def sync_zkteco_time(ip=ZK_MACHINE_IP, port=ZK_MACHINE_PORT):
    """
    Connects to ZKTeco MB360 machine at 192.168.18.25:4370 and calibrates the hardware clock to match current PC time.
    Fixes AM/PM and date misalignments on the biometric terminal.
    """
    zk = ZK(ip, port=port, timeout=4, password=0, force_udp=False, ommit_ping=True)
    conn = None
    try:
        conn = zk.connect()
        now = datetime.datetime.now()
        conn.set_time(now)
        conn.disconnect()
        return {"success": True, "message": f"ZKTeco machine clock successfully calibrated to PC time: {now.strftime('%Y-%m-%d %I:%M:%S %p')}"}
    except Exception as e:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass
        return {"success": False, "error": f"Failed to sync machine clock: {str(e)}"}

