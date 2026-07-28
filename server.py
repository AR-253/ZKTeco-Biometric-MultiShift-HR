import os
import json
import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from biometric_parser import parse_biometric_excel
from shift_engine import DEFAULT_SHIFTS, calculate_punch_status
import db_sqlserver

app = Flask(__name__, static_folder=".")
CORS(app)

# Initialize database schema on startup
try:
    db_sqlserver.init_db()
except Exception as e:
    print(f"DB Init Warning: {e}")


def load_data():
    sql_data = db_sqlserver.fetch_all_data_sql()
    if sql_data:
        return sql_data
    
    # Fallback to JSON if SQL server unreachable
    if os.path.exists("hr_data.json"):
        try:
            with open("hr_data.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"employees": [], "shifts": DEFAULT_SHIFTS, "attendance": [], "leaves": [], "payroll": []}




# API ROUTES (Must be defined BEFORE static catch-all)

@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/data', methods=['GET'])
def get_all_data():
    data = load_data()
    return jsonify(data)


@app.route('/api/employees', methods=['POST'])
def save_employee():
    req = request.json
    emp_id = str(req.get('id', '')).strip()
    if not emp_id:
        return jsonify({'error': 'Employee ID is required'}), 400

    emp_obj = {
        'id': emp_id,
        'name': req.get('name', ''),
        'department': req.get('department', 'General'),
        'role': req.get('role', 'Staff'),
        'base_salary': float(req.get('base_salary', 50000)),
        'shift_id': req.get('shift_id') if req.get('shift_id') is not None else None,
        'annual_leave_quota': float(req.get('annual_leave_quota', 24.0)),
        'status': req.get('status') if req.get('status') is not None else None,
        'initial_leaves_taken': float(req.get('initial_leaves_taken', 0.0)),
        'join_date': req.get('join_date', datetime.date.today().strftime('%Y-%m-%d'))
    }

    db_sqlserver.save_employee_sql(emp_obj)
    return jsonify({'success': True, 'employee': emp_obj})


@app.route('/api/employees/<emp_id>', methods=['DELETE'])
def delete_employee(emp_id):
    db_sqlserver.delete_employee_sql(emp_id)
    return jsonify({'success': True})


@app.route('/api/shifts', methods=['POST'])
def save_custom_shift():
    req = request.json
    s_id = str(req.get('id', '')).strip().upper()
    if not s_id:
        s_id = f"S{len(load_data().get('shifts', {})) + 1}"

    shift_obj = {
        'id': s_id,
        'name': req.get('name', f"Shift {s_id}"),
        'start_time': req.get('start_time', '09:00'),
        'end_time': req.get('end_time', '17:00'),
        'grace_minutes': int(req.get('grace_minutes', 15))
    }

    db_sqlserver.save_shift_sql(shift_obj)

    # Re-evaluate biometric attendance logs with updated shift rules
    try:
        import zk_connect
        zk_connect.sync_zkteco_logs()
    except Exception as e:
        print(f"Post-shift-save error: {e}")

    log_audit_event_sql("Edit Shift", f"Updated shift {s_id} timing: {shift_obj['start_time']} - {shift_obj['end_time']}")

    return jsonify({'success': True, 'shift': shift_obj})


@app.route('/api/shifts/<shift_id>', methods=['DELETE'])
def delete_shift(shift_id):
    db_sqlserver.delete_shift_sql(shift_id)
    return jsonify({'success': True})



import threading

@app.route('/api/zkteco/sync', methods=['POST'])
def sync_zkteco():
    import zk_connect
    import threading
    req = request.json or {}
    ip = req.get('ip', '192.168.18.25')
    port = int(req.get('port', 4370))

    # Run sync asynchronously in a background thread for instant (<10ms) HTTP response
    t = threading.Thread(target=zk_connect.sync_zkteco_logs, kwargs={'ip': ip, 'port': port}, daemon=True)
    t.start()

    try:
        db_sqlserver.log_audit_event_sql("ZKTeco Sync", f"Initiated live biometric sync with ZKTeco device at {ip}:{port}")
    except Exception:
        pass

    return jsonify({
        'success': True,
        'message': 'Biometric Sync initiated! New punches are being fetched in background and will render on screen.'
    })



@app.route('/api/zkteco/sync-time', methods=['POST'])
def sync_zkteco_time_route():
    import zk_connect
    req = request.json or {}
    ip = req.get('ip', '192.168.18.25')
    port = int(req.get('port', 4370))

    res = zk_connect.sync_zkteco_time(ip=ip, port=port)
    if res.get('success'):
        return jsonify(res)
    else:
        return jsonify(res), 500




@app.route('/api/biometric/upload', methods=['POST'])
def upload_biometric_log():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'Empty file'}), 400

    data = load_data()
    employees_map = {str(e['id']): e for e in data['employees']}
    shifts_map = data.get('shifts', DEFAULT_SHIFTS)

    parsed = parse_biometric_excel(file, employees_map=employees_map, shifts_map=shifts_map)
    if not parsed['success']:
        return jsonify({'error': f"Failed to parse log file: {parsed.get('error')}"}), 400

    batch_attendance = []

    for rec in parsed['records']:
        emp_id = str(rec['emp_id'])
        date_str = rec['date']
        check_in = rec.get('check_in')
        check_out = rec.get('check_out')

        emp = employees_map.get(emp_id)
        shift_id = emp.get('shift_id', 'S5') if emp else 'S5'
        shift = shifts_map.get(shift_id, DEFAULT_SHIFTS['S5'])

        evaluation = calculate_punch_status(shift, check_in, check_out)

        att_entry = {
            'emp_id': emp_id,
            'emp_name': emp.get('name') if emp else rec.get('name', f"Emp {emp_id}"),
            'date': date_str,
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

    db_sqlserver.save_attendance_batch_sql(batch_attendance)
    db_sqlserver.cleanup_invalid_overnight_attendance_sql()

    return jsonify({
        'success': True,
        'message': f"Successfully saved {len(batch_attendance)} attendance records into MS SQL Server database!",
        'records_count': len(batch_attendance)
    })


@app.route('/api/attendance/manual', methods=['POST'])
def add_manual_attendance():
    data = load_data()
    req = request.json
    emp_id = str(req.get('emp_id')).strip()
    date_str = req.get('date', datetime.date.today().strftime('%Y-%m-%d'))
    check_in = req.get('check_in')
    check_out = req.get('check_out')

    emp = next((e for e in data['employees'] if str(e['id']) == emp_id), None)
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404

    shift_id = emp.get('shift_id', 'S5')
    shifts_map = data.get('shifts', DEFAULT_SHIFTS)
    shift = shifts_map.get(shift_id, DEFAULT_SHIFTS['S5'])

    evaluation = calculate_punch_status(shift, check_in, check_out)

    remarks_val = evaluation['remarks'] if evaluation['remarks'] else 'Manual Entry'
    if 'Manual' not in remarks_val:
        remarks_val = f"{remarks_val} (Manual)"

    att_entry = {
        'emp_id': emp_id,
        'emp_name': emp['name'],
        'date': date_str,
        'check_in': check_in,
        'check_out': check_out,
        'shift_name': shift['name'],
        'shift_id': shift_id,
        'status': evaluation['status'],
        'late_minutes': evaluation['late_minutes'],
        'early_minutes': evaluation['early_minutes'],
        'hours_worked': evaluation['hours_worked'],
        'penalty_days': evaluation['penalty_days'],
        'remarks': remarks_val
    }

    db_sqlserver.save_attendance_batch_sql([att_entry], is_manual=True)


    return jsonify({'success': True, 'entry': att_entry})


@app.route('/api/leaves', methods=['POST'])
def add_leave():
    data = load_data()
    req = request.json
    emp_id = str(req.get('emp_id')).strip()
    emp = next((e for e in data['employees'] if str(e['id']) == emp_id), None)
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404

    leave_type = req.get('leave_type', 'Full')
    deduction_value = 1.0 if leave_type == 'Full' else (0.5 if leave_type == 'Half' else 0.25)
    existing_id = req.get('id')
    leave_id = existing_id if existing_id else f"L-{int(datetime.datetime.now().timestamp())}"

    leave_entry = {
        'id': leave_id,
        'emp_id': emp_id,
        'emp_name': emp['name'],
        'shift_id': emp.get('shift_id', 'S5'),
        'from_date': req.get('from_date'),
        'to_date': req.get('to_date'),
        'leave_type': leave_type,
        'deduction_value': deduction_value,
        'reason': req.get('reason', ''),
        'status': req.get('status', 'Approved')
    }

    db_sqlserver.save_leave_sql(leave_entry)

    return jsonify({'success': True, 'leave': leave_entry})


@app.route('/api/leaves/<leave_id>', methods=['DELETE'])
def delete_leave(leave_id):
    db_sqlserver.delete_leave_sql(leave_id)
    return jsonify({'success': True})


@app.route('/api/payroll/calculate', methods=['GET'])
def calculate_payroll():
    data = load_data()
    month_str = request.args.get('month', datetime.date.today().strftime('%Y-%m'))
    status_filter = request.args.get('status', 'Active')
    year_str = month_str.split('-')[0] # e.g. '2026'
    
    payroll_summary = []

    for emp in data['employees']:
        if status_filter == 'Active' and emp.get('status', 'Active') != 'Active':
            continue

        emp_id = str(emp['id'])
        base = float(emp.get('base_salary', 50000))
        daily_rate = base / 30.0
        annual_quota = float(emp.get('annual_leave_quota', 24.0))

        # YTD Attendance penalties up to selected month in current calendar year
        ytd_atts = [a for a in data.get('attendance', []) if str(a['emp_id']) == emp_id and a['date'].startswith(year_str) and a['date'][:7] <= month_str]
        ytd_shift_penalty = sum(a.get('penalty_days', 0) for a in ytd_atts)

        # YTD Approved leaves up to selected month in current calendar year (Only Approved)
        ytd_leaves = [l for l in data.get('leaves', []) if str(l['emp_id']) == emp_id and l.get('from_date', '').startswith(year_str) and l.get('from_date', '')[:7] <= month_str and l.get('status', 'Approved') == 'Approved']
        ytd_leave_penalty = sum(l.get('deduction_value', 1.0) for l in ytd_leaves)

        initial_used = float(emp.get('initial_leaves_taken', 0.0))
        total_ytd_used = round(initial_used + ytd_shift_penalty + ytd_leave_penalty, 2)

        # YTD used PRIOR to current month
        prior_atts = [a for a in data.get('attendance', []) if str(a['emp_id']) == emp_id and a['date'].startswith(year_str) and a['date'][:7] < month_str]
        prior_leaves = [l for l in data.get('leaves', []) if str(l['emp_id']) == emp_id and l.get('from_date', '').startswith(year_str) and l.get('from_date', '')[:7] < month_str and l.get('status', 'Approved') == 'Approved']
        prior_used = initial_used + sum(a.get('penalty_days', 0) for a in prior_atts) + sum(l.get('deduction_value', 1.0) for l in prior_leaves)

        prior_billed_days = max(0.0, prior_used - annual_quota)

        # Total excess days above quota so far
        total_excess = max(0.0, total_ytd_used - annual_quota)

        # Chargeable days FOR THIS MONTH ONLY
        chargeable_days = round(max(0.0, total_excess - prior_billed_days), 2)
        quota_remaining = round(max(0.0, annual_quota - total_ytd_used), 2)

        deduction_amount = round(chargeable_days * daily_rate, 2)
        net_salary = round(max(0, base - deduction_amount), 2)

        payroll_summary.append({
            'emp_id': emp_id,
            'emp_name': emp['name'],
            'department': emp.get('department'),
            'base_salary': base,
            'daily_rate': round(daily_rate, 2),
            'annual_quota': annual_quota,
            'initial_leaves_taken': initial_used,
            'biometric_penalty': round(ytd_shift_penalty + ytd_leave_penalty, 2),
            'total_ytd_used': round(total_ytd_used, 2),
            'quota_remaining': quota_remaining,
            'chargeable_days': chargeable_days,
            'deduction_amount': deduction_amount,
            'net_salary': net_salary,
            'month': month_str
        })

    return jsonify({'month': month_str, 'payroll': payroll_summary})


@app.route('/api/audit-logs', methods=['GET', 'POST'])
def handle_audit_logs():
    if request.method == 'POST':
        req = request.json or {}
        action = req.get('action', 'User Action')
        details = req.get('details', '')
        by = req.get('performed_by', 'System Admin')
        db_sqlserver.log_audit_event_sql(action, details, by)
        return jsonify({'success': True})
    else:
        limit = int(request.args.get('limit', 200))
        logs = db_sqlserver.fetch_audit_logs_sql(limit=limit)
        return jsonify({'success': True, 'logs': logs})



# STATIC FILES CATCH-ALL (Must be at the very bottom)
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/<path:path>')
def static_files(path):
    if os.path.exists(path):
        return send_from_directory('.', path)
    return send_from_directory('.', 'index.html')


if __name__ == '__main__':
    print("Starting HR & Biometric System (Connected to MS SQL Server) on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)


