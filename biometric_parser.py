import os
import datetime
import pandas as pd


def normalize_col_name(col):
    return str(col).strip().lower().replace(" ", "_").replace("-", "_").replace(".", "")


def load_dataframe_multi_encoding(source):
    """
    Attempts to load a DataFrame from Excel, CSV, or TXT with multi-encoding and multi-separator fallback.
    """
    # 1. Try Excel read (xlsx, xls)
    try:
        if hasattr(source, 'seek'):
            source.seek(0)
        return pd.read_excel(source)
    except Exception:
        pass

    try:
        if hasattr(source, 'seek'):
            source.seek(0)
        return pd.read_excel(source, engine='xlrd')
    except Exception:
        pass

    # 2. Try CSV/TXT with various encodings & separators
    encodings = ['utf-8', 'latin1', 'cp1252', 'utf-16', 'utf-16le', 'iso-8859-1', 'gbk']
    separators = [',', '\t', ';', r'\s+']

    for enc in encodings:
        for sep in separators:
            try:
                if hasattr(source, 'seek'):
                    source.seek(0)
                df = pd.read_csv(source, encoding=enc, sep=sep, engine='python', on_bad_lines='skip')
                if len(df.columns) >= 2 and len(df) > 0:
                    return df
            except Exception:
                continue

    # 3. Fallback: read bytes directly
    if hasattr(source, 'read'):
        if hasattr(source, 'seek'):
            source.seek(0)
        content_bytes = source.read()
    elif isinstance(source, bytes):
        content_bytes = source
    else:
        with open(source, 'rb') as f:
            content_bytes = f.read()

    for enc in encodings:
        try:
            text = content_bytes.decode(enc)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            data = [line.split() for line in lines if len(line.split()) >= 2]
            if data:
                headers = [f"col_{i}" for i in range(len(data[0]))]
                return pd.DataFrame(data, columns=headers[:len(data[0])])
        except Exception:
            continue

    raise ValueError("Could not parse file with any supported Excel or text file format.")


from shift_engine import DEFAULT_SHIFTS, get_work_date

def parse_biometric_excel(filepath_or_bytes, employees_map=None, shifts_map=None):
    """
    Parses biometric logs from .xls, .xlsx, .csv, .txt, or .dat files exported from ZKTeco or any thumb machine.
    """
    try:
        df = load_dataframe_multi_encoding(filepath_or_bytes)

        # 1. Skip report title rows if headers are on line 2, 3, or 4
        for idx in range(min(10, len(df))):
            row_str_values = [normalize_col_name(val) for val in df.iloc[idx].values]
            if any(k in row_str_values for k in ['ac_no', 'id', 'emp_id', 'userid', 'no', 'stime', 'time', 'name']):
                df.columns = df.iloc[idx]
                df = df.iloc[idx + 1:].reset_index(drop=True)
                break

        # 2. Normalize column mapping
        col_map = {normalize_col_name(col): col for col in df.columns}
        
        emp_id_col = None
        for key in ['ac_no', 'acno', 'emp_id', 'employee_id', 'id', 'userid', 'user_id', 'id_no', 'pin', 'no', 'no.', 'badgenumber', 'enrollnumber', 'enroll_number', 'cardno']:
            if key in col_map:
                emp_id_col = col_map[key]
                break

        name_col = None
        for key in ['name', 'employee_name', 'emp_name', 'user_name', 'username']:
            if key in col_map:
                name_col = col_map[key]
                break

        date_col = None
        for key in ['stime', 'time', 'date', 'punch_date', 'att_date', 'datetime', 'date_time', 'punchtime', 'log_time', 'att_time', 'check_time', 'time/date', 'date/time']:
            if key in col_map:
                date_col = col_map[key]
                break

        in_col = None
        for key in ['check_in', 'time_in', 'in_time', 'in', 'first_in']:
            if key in col_map:
                in_col = col_map[key]
                break

        out_col = None
        for key in ['check_out', 'time_out', 'out_time', 'out', 'last_out']:
            if key in col_map:
                out_col = col_map[key]
                break

        # 3. Content Auto-Detection Fallback if headers were missing or custom
        if not emp_id_col or not date_col:
            for col in df.columns:
                sample_vals = [str(val).strip() for val in df[col].dropna().head(10).values]
                
                # Check for DateTime patterns (e.g. "7/26/2026 8:29:10 PM", "2026-07-27 15:18:50")
                if not date_col and any((':' in v or '/' in v or '-' in v) and any(c.isdigit() for c in v) for v in sample_vals):
                    date_col = col

                # Check for Emp ID patterns (numeric values like 10, 14, 18, 101)
                elif not emp_id_col and any(v.isdigit() for v in sample_vals):
                    emp_id_col = col

        records = []
        
        # Parse dataset with row-by-row punches (Emp ID, DateTime)
        if emp_id_col and date_col and not (in_col and out_col):
            punches_by_emp_date = {}
            for _, row in df.iterrows():
                e_id = str(row[emp_id_col]).strip()
                if not e_id or e_id.lower() in ['nan', 'none', 'id', 'emp_id', 'ac-no']:
                    continue
                dt_val = str(row[date_col]).strip()
                if not dt_val or dt_val.lower() in ['nan', 'none', 'stime', 'time']:
                    continue

                name_val = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else f"Emp-{e_id}"
                
                # Parse date and time string formats
                dt_obj = None
                for fmt in ["%m/%d/%Y %I:%M:%S %p", "%d/%m/%Y %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
                    try:
                        dt_obj = datetime.datetime.strptime(dt_val, fmt)
                        break
                    except Exception:
                        pass
                
                emp = employees_map.get(e_id) if employees_map else None
                shift_id = emp.get('shift_id', 'S5') if emp else 'S5'
                shift = (shifts_map.get(shift_id) if shifts_map else None) or DEFAULT_SHIFTS.get(shift_id, DEFAULT_SHIFTS['S5'])

                if dt_obj:
                    work_d_str = get_work_date(dt_obj, shift)
                    t_str = dt_obj.strftime("%H:%M")
                    cal_d_str = dt_obj.strftime("%Y-%m-%d")
                else:
                    parts = dt_val.split()
                    work_d_str = parts[0]
                    t_str = parts[1] if len(parts) > 1 else "00:00"
                    cal_d_str = parts[0]
                    dt_obj = datetime.datetime.now()

                key = (e_id, work_d_str)
                if key not in punches_by_emp_date:
                    punches_by_emp_date[key] = {"name": name_val, "shift": shift, "punches": []}
                punches_by_emp_date[key]["punches"].append({"dt": dt_obj, "time_str": t_str, "cal_date": cal_d_str})

            for (e_id, work_d_str), info in punches_by_emp_date.items():
                shift = info["shift"]
                start_h = int(shift.get('start_time', '09:00').split(':')[0])
                end_h = int(shift.get('end_time', '17:00').split(':')[0])
                is_overnight = end_h < start_h

                sorted_items = sorted(info["punches"], key=lambda x: x["dt"])
                check_in = None
                check_out = None

                if is_overnight:
                    eve_punches = [p for p in sorted_items if p["cal_date"] == work_d_str or int(p["time_str"].split(':')[0]) >= 12]
                    morn_punches = [p for p in sorted_items if p["cal_date"] != work_d_str and int(p["time_str"].split(':')[0]) < 12]

                    if eve_punches:
                        check_in = eve_punches[0]["time_str"]
                    if morn_punches:
                        check_out = morn_punches[-1]["time_str"]
                    elif len(eve_punches) > 1:
                        t_last = eve_punches[-1]["time_str"]
                        in_h, in_m = map(int, check_in.split(':'))
                        t_h, t_m = map(int, t_last.split(':'))
                        if (t_h * 60 + t_m) - (in_h * 60 + in_m) >= 10:
                            check_out = t_last
                else:
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

                records.append({
                    "emp_id": e_id,
                    "name": info["name"],
                    "date": work_d_str,
                    "check_in": check_in,
                    "check_out": check_out
                })

        # Parse dataset with explicit Check In / Check Out columns
        elif emp_id_col:
            for _, row in df.iterrows():
                e_id = str(row[emp_id_col]).strip()
                if not e_id or e_id.lower() in ['nan', 'none', 'id']:
                    continue
                name_val = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else f"Emp-{e_id}"
                d_str = str(row[date_col]).strip() if date_col and pd.notna(row[date_col]) else datetime.date.today().strftime("%Y-%m-%d")
                in_str = str(row[in_col]).strip() if in_col and pd.notna(row[in_col]) else None
                out_str = str(row[out_col]).strip() if out_col and pd.notna(row[out_col]) else None

                records.append({
                    "emp_id": e_id,
                    "name": name_val,
                    "date": d_str,
                    "check_in": in_str,
                    "check_out": out_str
                })

        return {"success": True, "count": len(records), "records": records}

    except Exception as e:
        return {"success": False, "error": str(e), "records": []}

