import pyodbc
from shift_engine import DEFAULT_SHIFTS

SERVER_NAME = r".\SQLEXPRESS"
DB_NAME = "HR_Management"
CONN_STR_MASTER = f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SERVER_NAME};DATABASE=master;Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;"
CONN_STR_APP = f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SERVER_NAME};DATABASE={DB_NAME};Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;"






def get_connection(use_app_db=True):
    try:
        conn_str = CONN_STR_APP if use_app_db else CONN_STR_MASTER
        return pyodbc.connect(conn_str, autocommit=True)
    except Exception as e:
        print(f"SQL Server Connection Error: {e}")
        return None


def init_db():
    """Ensure Database and Tables exist in SQL Server"""
    # 1. Create DB if not exists
    conn_master = get_connection(use_app_db=False)
    if conn_master:
        cursor = conn_master.cursor()
        cursor.execute("SELECT database_id FROM sys.databases WHERE name = ?", (DB_NAME,))
        if not cursor.fetchone():
            print(f"Creating database {DB_NAME} in SQL Server...")
            cursor.execute(f"CREATE DATABASE [{DB_NAME}]")
        conn_master.close()

    # 2. Create Tables
    conn = get_connection(use_app_db=True)
    if not conn:
        print("Failed to connect to HR_Management database.")
        return False

    cursor = conn.cursor()

    # Employees Table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Employees' AND xtype='U')
        CREATE TABLE Employees (
            id NVARCHAR(50) PRIMARY KEY,
            name NVARCHAR(150) NOT NULL,
            department NVARCHAR(100),
            role NVARCHAR(100),
            base_salary DECIMAL(18,2),
            shift_id NVARCHAR(50),
            annual_leave_quota DECIMAL(5,2) DEFAULT 24.0,
            join_date VARCHAR(20),
            status NVARCHAR(20) DEFAULT 'Active',
            initial_leaves_taken DECIMAL(5,2) DEFAULT 0.0
        )
    """)
    
    # Add column if table existed previously without annual_leave_quota, status, or initial_leaves_taken
    cursor.execute("""
        IF EXISTS (SELECT * FROM sysobjects WHERE name='Employees' AND xtype='U')
        AND NOT EXISTS (SELECT * FROM syscolumns WHERE id = OBJECT_ID('Employees') AND name = 'annual_leave_quota')
        ALTER TABLE Employees ADD annual_leave_quota DECIMAL(5,2) DEFAULT 24.0 WITH VALUES
    """)

    cursor.execute("""
        IF EXISTS (SELECT * FROM sysobjects WHERE name='Employees' AND xtype='U')
        AND NOT EXISTS (SELECT * FROM syscolumns WHERE id = OBJECT_ID('Employees') AND name = 'status')
        ALTER TABLE Employees ADD status NVARCHAR(20) DEFAULT 'Active' WITH VALUES
    """)

    cursor.execute("""
        IF EXISTS (SELECT * FROM sysobjects WHERE name='Employees' AND xtype='U')
        AND NOT EXISTS (SELECT * FROM syscolumns WHERE id = OBJECT_ID('Employees') AND name = 'initial_leaves_taken')
        ALTER TABLE Employees ADD initial_leaves_taken DECIMAL(5,2) DEFAULT 0.0 WITH VALUES
    """)


    # Shifts Table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Shifts' AND xtype='U')
        CREATE TABLE Shifts (
            id NVARCHAR(50) PRIMARY KEY,
            name NVARCHAR(100) NOT NULL,
            start_time VARCHAR(10),
            end_time VARCHAR(10),
            grace_minutes INT
        )
    """)

    # Attendance Table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Attendance' AND xtype='U')
        CREATE TABLE Attendance (
            id INT IDENTITY(1,1) PRIMARY KEY,
            emp_id NVARCHAR(50),
            emp_name NVARCHAR(150),
            date VARCHAR(20),
            check_in VARCHAR(20),
            check_out VARCHAR(20),
            shift_name NVARCHAR(100),
            shift_id NVARCHAR(50),
            status NVARCHAR(50),
            late_minutes INT,
            early_minutes INT,
            hours_worked DECIMAL(10,2),
            penalty_days DECIMAL(5,2),
            remarks NVARCHAR(255),
            CONSTRAINT UQ_Emp_Date UNIQUE (emp_id, date)
        )
    """)

    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='IX_Attendance_Date')
        CREATE INDEX IX_Attendance_Date ON Attendance (date DESC, emp_id);
    """)


    # Leaves Table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Leaves' AND xtype='U')
        CREATE TABLE Leaves (
            id NVARCHAR(50) PRIMARY KEY,
            emp_id NVARCHAR(50),
            emp_name NVARCHAR(150),
            shift_id NVARCHAR(50),
            from_date VARCHAR(20),
            to_date VARCHAR(20),
            leave_type NVARCHAR(50),
            deduction_value DECIMAL(5,2),
            reason NVARCHAR(255),
            status NVARCHAR(50)
        )
    """)

    # AuditLogs Table
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AuditLogs' AND xtype='U')
        CREATE TABLE AuditLogs (
            id INT IDENTITY(1,1) PRIMARY KEY,
            timestamp DATETIME DEFAULT GETDATE(),
            action NVARCHAR(100) NOT NULL,
            details NVARCHAR(500),
            performed_by NVARCHAR(100) DEFAULT 'System Admin'
        )
    """)

    # Seed Default Shifts ONLY on brand new database installation
    cursor.execute("SELECT COUNT(*) FROM Shifts")
    shifts_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Employees")
    emps_count = cursor.fetchone()[0]

    if shifts_count == 0 and emps_count == 0:
        for s_id, s in DEFAULT_SHIFTS.items():
            cursor.execute(
                "INSERT INTO Shifts (id, name, start_time, end_time, grace_minutes) VALUES (?, ?, ?, ?, ?)",
                (s["id"], s["name"], s["start_time"], s["end_time"], s["grace_minutes"])
            )

    conn.close()

    print("MS SQL Server database initialized successfully!")
    return True


def fetch_all_data_sql():
    conn = get_connection(use_app_db=True)
    if not conn:
        return None

    cursor = conn.cursor()

    # Fetch Employees
    cursor.execute("SELECT id, name, department, role, base_salary, shift_id, annual_leave_quota, join_date, status, initial_leaves_taken FROM Employees")
    employees = []
    for row in cursor.fetchall():
        employees.append({
            "id": str(row[0]),
            "name": row[1],
            "department": row[2],
            "role": row[3],
            "base_salary": float(row[4]),
            "shift_id": row[5],
            "annual_leave_quota": float(row[6]) if row[6] is not None else 24.0,
            "join_date": row[7],
            "status": row[8] if len(row) > 8 and row[8] else "Active",
            "initial_leaves_taken": float(row[9]) if len(row) > 9 and row[9] is not None else 0.0
        })

    # Fetch Shifts
    cursor.execute("SELECT id, name, start_time, end_time, grace_minutes FROM Shifts")
    shifts = {}
    for row in cursor.fetchall():
        shifts[row[0]] = {
            "id": row[0],
            "name": row[1],
            "start_time": row[2],
            "end_time": row[3],
            "grace_minutes": row[4]
        }

    # Fetch Attendance (Most recent 2000 records ordered by date DESC)
    cursor.execute("SELECT TOP 2000 emp_id, emp_name, date, check_in, check_out, shift_name, shift_id, status, late_minutes, early_minutes, hours_worked, penalty_days, remarks FROM Attendance ORDER BY date DESC, id DESC")
    attendance = []
    for row in cursor.fetchall():
        attendance.append({
            "emp_id": str(row[0]),
            "emp_name": row[1],
            "date": row[2],
            "check_in": row[3],
            "check_out": row[4],
            "shift_name": row[5],
            "shift_id": row[6],
            "status": row[7],
            "late_minutes": row[8],
            "early_minutes": row[9],
            "hours_worked": float(row[10]) if row[10] is not None else 0.0,
            "penalty_days": float(row[11]) if row[11] is not None else 0.0,
            "remarks": row[12]
        })



    # Fetch Leaves
    cursor.execute("SELECT id, emp_id, emp_name, shift_id, from_date, to_date, leave_type, deduction_value, reason, status FROM Leaves")
    leaves = []
    for row in cursor.fetchall():
        leaves.append({
            "id": row[0],
            "emp_id": str(row[1]),
            "emp_name": row[2],
            "shift_id": row[3],
            "from_date": row[4],
            "to_date": row[5],
            "leave_type": row[6],
            "deduction_value": float(row[7]) if row[7] is not None else 1.0,
            "reason": row[8],
            "status": row[9]
        })

    conn.close()

    return {
        "employees": employees,
        "shifts": shifts,
        "attendance": attendance,
        "leaves": leaves,
        "payroll": []
    }



import json
import os
import datetime

def sync_hr_data_json(all_data=None):
    """Syncs SQL Server state into hr_data.json if present to keep fallback in sync"""
    try:
        if not all_data:
            all_data = fetch_all_data_sql()
        if all_data and os.path.exists("hr_data.json"):
            with open("hr_data.json", "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to sync hr_data.json: {e}")


def cleanup_invalid_overnight_attendance_sql():
    """
    Cleans up bogus attendance entries created for today's date where a 4:00 AM check-out
    was falsely saved as a check-in for an overnight shift.
    """
    conn = get_connection(use_app_db=True)
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        # Find overnight shifts
        cursor.execute("SELECT id, start_time, end_time FROM Shifts")
        shifts = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        overnight_shift_ids = set()
        for s_id, (st, et) in shifts.items():
            if st and et:
                st_h = int(st.split(":")[0])
                et_h = int(et.split(":")[0])
                if et_h < st_h:
                    overnight_shift_ids.add(s_id)

        if overnight_shift_ids:
            placeholders = ",".join(f"'{s}'" for s in overnight_shift_ids)
            # Delete records where shift is overnight, check_in is morning (< 12:00) and check_out is NULL/None
            sql = f"""
                DELETE FROM Attendance 
                WHERE shift_id IN ({placeholders}) 
                AND check_in IS NOT NULL 
                AND CAST(SUBSTRING(check_in, 1, 2) AS INT) < 12 
                AND (check_out IS NULL OR check_out = '' OR check_out = '--:--')
            """
            cursor.execute(sql)
        conn.close()
        return True
    except Exception as e:
        print(f"Cleanup Error: {e}")
        if conn:
            conn.close()
        return False


def save_employee_sql(emp_obj, preserve_existing=False):
    conn = get_connection(use_app_db=True)
    if not conn:
        return False
    cursor = conn.cursor()

    emp_id = str(emp_obj['id']).strip()
    cursor.execute("SELECT name, department, role, base_salary, shift_id, annual_leave_quota, join_date, status, initial_leaves_taken FROM Employees WHERE id = ?", (emp_id,))
    existing_row = cursor.fetchone()

    if existing_row:
        if preserve_existing:
            name = existing_row[0]
            department = existing_row[1] or 'General'
            role = existing_row[2] or 'Staff'
            base_salary = float(existing_row[3]) if existing_row[3] is not None else 50000.0
            shift_id = existing_row[4] or 'S5'
            annual_quota = float(existing_row[5]) if existing_row[5] is not None else 24.0
            join_date = existing_row[6] or datetime.date.today().strftime('%Y-%m-%d')
            emp_status = existing_row[7] or 'Active'
            initial_leaves = float(existing_row[8]) if existing_row[8] is not None else 0.0
        else:
            name = emp_obj.get('name') if (emp_obj.get('name') and str(emp_obj.get('name')).strip()) else existing_row[0]
            department = emp_obj.get('department') if (emp_obj.get('department') and str(emp_obj.get('department')).strip()) else (existing_row[1] or 'General')
            role = emp_obj.get('role') if (emp_obj.get('role') and str(emp_obj.get('role')).strip()) else (existing_row[2] or 'Staff')
            base_salary = float(emp_obj.get('base_salary')) if emp_obj.get('base_salary') is not None else float(existing_row[3] or 50000.0)
            shift_id = emp_obj.get('shift_id') if emp_obj.get('shift_id') else (existing_row[4] or 'S5')
            annual_quota = float(emp_obj.get('annual_leave_quota')) if emp_obj.get('annual_leave_quota') is not None else float(existing_row[5] or 24.0)
            join_date = emp_obj.get('join_date') if emp_obj.get('join_date') else (existing_row[6] or datetime.date.today().strftime('%Y-%m-%d'))
            emp_status = emp_obj.get('status') if emp_obj.get('status') else (existing_row[7] or 'Active')
            initial_leaves = float(emp_obj.get('initial_leaves_taken')) if emp_obj.get('initial_leaves_taken') is not None else float(existing_row[8] or 0.0)
    else:
        name = emp_obj.get('name', f"Emp-{emp_id}")
        department = emp_obj.get('department', 'General')
        role = emp_obj.get('role', 'Staff')
        base_salary = float(emp_obj.get('base_salary', 50000.0))
        shift_id = emp_obj.get('shift_id', 'S5')
        annual_quota = float(emp_obj.get('annual_leave_quota', 24.0))
        join_date = emp_obj.get('join_date', datetime.date.today().strftime('%Y-%m-%d'))
        emp_status = emp_obj.get('status', 'Active')
        initial_leaves = float(emp_obj.get('initial_leaves_taken', 0.0))

    cursor.execute("""
        IF EXISTS (SELECT 1 FROM Employees WHERE id = ?)
            UPDATE Employees SET name=?, department=?, role=?, base_salary=?, shift_id=?, annual_leave_quota=?, join_date=?, status=?, initial_leaves_taken=? WHERE id=?
        ELSE
            INSERT INTO Employees (id, name, department, role, base_salary, shift_id, annual_leave_quota, join_date, status, initial_leaves_taken) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        emp_id, name, department, role, base_salary, shift_id, annual_quota, join_date, emp_status, initial_leaves, emp_id,
        emp_id, name, department, role, base_salary, shift_id, annual_quota, join_date, emp_status, initial_leaves
    ))
    conn.close()

    # Mirror changes to hr_data.json fallback file
    sync_hr_data_json()
    return True




def delete_employee_sql(emp_id):
    conn = get_connection(use_app_db=True)
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Employees WHERE id = ?", (emp_id,))
    conn.close()
    return True


def save_attendance_batch_sql(attendance_entries, is_manual=False):
    if not attendance_entries:
        return True

    conn = get_connection(use_app_db=True)
    if not conn:
        return False
    cursor = conn.cursor()

    try:
        if not is_manual:
            # Only protect manual entries if check_out is already filled
            cursor.execute("SELECT emp_id, date FROM Attendance WHERE remarks LIKE '%Manual%' AND check_out IS NOT NULL AND check_out != '' AND check_out != '--:--'")
            manual_keys = {(str(row[0]).strip(), str(row[1]).strip()) for row in cursor.fetchall()}
            attendance_entries = [
                att for att in attendance_entries 
                if (str(att['emp_id']).strip(), str(att['date']).strip()) not in manual_keys
            ]

        if not attendance_entries:
            conn.close()
            return True

        merge_sql = """
            MERGE Attendance AS target
            USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)) 
            AS source (emp_id, emp_name, date, check_in, check_out, shift_name, shift_id, status, late_minutes, early_minutes, hours_worked, penalty_days, remarks)
            ON target.emp_id = source.emp_id AND target.date = source.date
            WHEN MATCHED THEN
                UPDATE SET 
                    target.emp_name = source.emp_name,
                    target.check_in = source.check_in,
                    target.check_out = source.check_out,
                    target.shift_name = source.shift_name,
                    target.shift_id = source.shift_id,
                    target.status = source.status,
                    target.late_minutes = source.late_minutes,
                    target.early_minutes = source.early_minutes,
                    target.hours_worked = source.hours_worked,
                    target.penalty_days = source.penalty_days,
                    target.remarks = source.remarks
            WHEN NOT MATCHED THEN
                INSERT (emp_id, emp_name, date, check_in, check_out, shift_name, shift_id, status, late_minutes, early_minutes, hours_worked, penalty_days, remarks)
                VALUES (source.emp_id, source.emp_name, source.date, source.check_in, source.check_out, source.shift_name, source.shift_id, source.status, source.late_minutes, source.early_minutes, source.hours_worked, source.penalty_days, source.remarks);
        """

        params = [
            (
                str(att['emp_id']).strip(),
                att['emp_name'],
                str(att['date']).strip(),
                att.get('check_in'),
                att.get('check_out'),
                att.get('shift_name', 'Standard'),
                att.get('shift_id', 'S5'),
                att.get('status', 'On Time'),
                int(att.get('late_minutes', 0)),
                int(att.get('early_minutes', 0)),
                float(att.get('hours_worked', 0.0)),
                float(att.get('penalty_days', 0.0)),
                att.get('remarks', '')
            )
            for att in attendance_entries
        ]

        cursor.fast_executemany = True
        cursor.executemany(merge_sql, params)
        conn.close()
        return True
    except Exception as e:
        print(f"Batch Save Error: {e}")
        # Fallback to single row loop if fast_executemany encounters driver issue
        try:
            for att in attendance_entries:
                cursor.execute("""
                    IF EXISTS (SELECT 1 FROM Attendance WHERE emp_id = ? AND date = ?)
                        UPDATE Attendance SET emp_name=?, check_in=?, check_out=?, shift_name=?, shift_id=?, status=?, late_minutes=?, early_minutes=?, hours_worked=?, penalty_days=?, remarks=? WHERE emp_id=? AND date=?
                    ELSE
                        INSERT INTO Attendance (emp_id, emp_name, date, check_in, check_out, shift_name, shift_id, status, late_minutes, early_minutes, hours_worked, penalty_days, remarks)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    att['emp_id'], att['date'],
                    att['emp_name'], att['check_in'], att['check_out'], att['shift_name'], att['shift_id'], att['status'], att['late_minutes'], att['early_minutes'], att['hours_worked'], att['penalty_days'], att['remarks'], att['emp_id'], att['date'],
                    att['emp_id'], att['emp_name'], att['date'], att['check_in'], att['check_out'], att['shift_name'], att['shift_id'], att['status'], att['late_minutes'], att['early_minutes'], att['hours_worked'], att['penalty_days'], att['remarks']
                ))
            conn.close()
            return True
        except Exception:
            conn.close()
            return False




def save_leave_sql(leave_obj):
    conn = get_connection(use_app_db=True)
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("""
        IF EXISTS (SELECT 1 FROM Leaves WHERE id = ?)
            UPDATE Leaves SET emp_id=?, emp_name=?, shift_id=?, from_date=?, to_date=?, leave_type=?, deduction_value=?, reason=?, status=? WHERE id=?
        ELSE
            INSERT INTO Leaves (id, emp_id, emp_name, shift_id, from_date, to_date, leave_type, deduction_value, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        leave_obj['id'], leave_obj['emp_id'], leave_obj['emp_name'], leave_obj['shift_id'], leave_obj['from_date'], leave_obj['to_date'], leave_obj['leave_type'], leave_obj['deduction_value'], leave_obj['reason'], leave_obj['status'], leave_obj['id'],
        leave_obj['id'], leave_obj['emp_id'], leave_obj['emp_name'], leave_obj['shift_id'], leave_obj['from_date'], leave_obj['to_date'], leave_obj['leave_type'], leave_obj['deduction_value'], leave_obj['reason'], leave_obj['status']
    ))
    conn.close()
    return True


def delete_leave_sql(leave_id):
    conn = get_connection(use_app_db=True)
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Leaves WHERE id = ?", (leave_id,))
    conn.close()
    return True


def recalculate_attendance_for_shift_sql(target_shift_id=None):
    from shift_engine import calculate_punch_status, DEFAULT_SHIFTS
    conn = get_connection(use_app_db=True)
    if not conn:
        return False
    try:
        cursor = conn.cursor()

        # Fetch employees
        cursor.execute("SELECT id, shift_id FROM Employees")
        emp_shifts = {str(row[0]).strip(): (row[1] or 'S5') for row in cursor.fetchall()}

        # Fetch shifts
        cursor.execute("SELECT id, name, start_time, end_time, grace_minutes FROM Shifts")
        shifts = {}
        for row in cursor.fetchall():
            shifts[row[0]] = {
                "id": row[0],
                "name": row[1],
                "start_time": row[2],
                "end_time": row[3],
                "grace_minutes": row[4]
            }

        # Fetch attendance records
        if target_shift_id:
            cursor.execute("SELECT id, emp_id, check_in, check_out, shift_id FROM Attendance WHERE shift_id = ?", (target_shift_id,))
        else:
            cursor.execute("SELECT id, emp_id, check_in, check_out, shift_id FROM Attendance")

        att_rows = cursor.fetchall()
        for row in att_rows:
            att_id, emp_id, cin, cout, cur_s_id = row[0], str(row[1]).strip(), row[2], row[3], row[4]
            emp_s_id = emp_shifts.get(emp_id, cur_s_id)
            shift = shifts.get(emp_s_id, shifts.get(cur_s_id, DEFAULT_SHIFTS.get('S5')))

            if shift and cin and cin != '--:--':
                res = calculate_punch_status(shift, cin, cout)
                cursor.execute("""
                    UPDATE Attendance 
                    SET shift_name=?, shift_id=?, status=?, late_minutes=?, early_minutes=?, hours_worked=?, penalty_days=?, remarks=? 
                    WHERE id=?
                """, (
                    shift['name'], shift['id'], res['status'], res['late_minutes'], res['early_minutes'], res['hours_worked'], res['penalty_days'], res['remarks'], att_id
                ))
        conn.close()
        return True
    except Exception as e:
        print(f"Recalculate error: {e}")
        if conn:
            conn.close()
        return False


def save_shift_sql(shift_obj):
    conn = get_connection(use_app_db=True)
    if not conn:
        return False
    cursor = conn.cursor()
    s_id = str(shift_obj['id']).strip().upper()
    name = shift_obj.get('name', f"Shift {s_id}")
    start_time = str(shift_obj.get('start_time', '09:00')).strip()
    end_time = str(shift_obj.get('end_time', '17:00')).strip()
    grace_minutes = int(shift_obj.get('grace_minutes', 15))

    cursor.execute("""
        IF EXISTS (SELECT 1 FROM Shifts WHERE id = ?)
            UPDATE Shifts SET name=?, start_time=?, end_time=?, grace_minutes=? WHERE id=?
        ELSE
            INSERT INTO Shifts (id, name, start_time, end_time, grace_minutes) VALUES (?, ?, ?, ?, ?)
    """, (
        s_id,
        name, start_time, end_time, grace_minutes, s_id,
        s_id, name, start_time, end_time, grace_minutes
    ))
    conn.close()

    # Automatically recalculate existing attendance logs for this shift
    recalculate_attendance_for_shift_sql(s_id)
    return True



def delete_shift_sql(shift_id):
    conn = get_connection(use_app_db=True)
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Shifts WHERE id = ?", (shift_id,))
    conn.close()
    return True


def log_audit_event_sql(action, details, performed_by="System Admin"):
    conn = get_connection(use_app_db=True)
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO AuditLogs (action, details, performed_by) VALUES (?, ?, ?)",
            (str(action)[:100], str(details)[:500], str(performed_by)[:100])
        )
        conn.close()
        return True
    except Exception as e:
        print(f"Audit log error: {e}")
        if conn:
            conn.close()
        return False


def fetch_audit_logs_sql(limit=200):
    conn = get_connection(use_app_db=True)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT TOP {limit} id, CONVERT(VARCHAR(20), timestamp, 120) AS ts, action, details, performed_by FROM AuditLogs ORDER BY id DESC")
        logs = []
        for row in cursor.fetchall():
            logs.append({
                "id": row[0],
                "timestamp": str(row[1]),
                "action": row[2],
                "details": row[3],
                "performed_by": row[4]
            })
        conn.close()
        return logs
    except Exception as e:
        print(f"Fetch audit log error: {e}")
        if conn:
            conn.close()
        return []



