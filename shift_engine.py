import datetime

DEFAULT_SHIFTS = {
    "S1": {
        "id": "S1",
        "name": "Shift 1 (Morning)",
        "start_time": "08:00",
        "end_time": "16:00",
        "grace_minutes": 15
    },
    "S2": {
        "id": "S2",
        "name": "Shift 2 (Mid Day)",
        "start_time": "12:00",
        "end_time": "20:00",
        "grace_minutes": 15
    },
    "S3": {
        "id": "S3",
        "name": "Shift 3 (Evening)",
        "start_time": "16:00",
        "end_time": "00:00",
        "grace_minutes": 15
    },
    "S4": {
        "id": "S4",
        "name": "Shift 4 (Night)",
        "start_time": "22:00",
        "end_time": "06:00",
        "grace_minutes": 15
    },
    "S5": {
        "id": "S5",
        "name": "Shift 5 (Standard)",
        "start_time": "09:00",
        "end_time": "17:00",
        "grace_minutes": 15
    }
}


def parse_time(time_str):
    if not time_str:
        return None
    try:
        parts = str(time_str).strip().split(":")
        return datetime.time(int(parts[0]), int(parts[1]))
    except Exception:
        return None


def get_work_date(dt_obj, shift=None):
    """
    Given a datetime object and an assigned shift, returns the Work Date string (YYYY-MM-DD).
    For overnight shifts (e.g. 19:00 to 04:00, where end_time < start_time):
    Punches between 00:00:00 and 12:00:00 (noon) belong to the shift 
    that started on the PREVIOUS calendar day (dt_obj.date() - 1 day).
    """
    if isinstance(dt_obj, str):
        try:
            dt_obj = datetime.datetime.strptime(dt_obj, "%Y-%m-%d %H:%M:%S")
        except Exception:
            try:
                dt_obj = datetime.datetime.strptime(dt_obj, "%Y-%m-%d %H:%M")
            except Exception:
                return dt_obj.split(" ")[0] if " " in dt_obj else dt_obj

    cal_date = dt_obj.date()
    if not shift:
        return cal_date.strftime("%Y-%m-%d")

    start_str = shift.get("start_time", "09:00")
    end_str = shift.get("end_time", "17:00")

    try:
        start_h = int(start_str.split(":")[0])
        end_h = int(end_str.split(":")[0])
    except Exception:
        start_h, end_h = 9, 17

    is_overnight = end_h < start_h
    if is_overnight:
        # Cutoff: punches from 00:00 up to 12:00 PM belong to previous day's shift
        if dt_obj.time() < datetime.time(12, 0):
            work_date = cal_date - datetime.timedelta(days=1)
            return work_date.strftime("%Y-%m-%d")

    return cal_date.strftime("%Y-%m-%d")


def calculate_punch_status(shift, check_in_str, check_out_str):
    """
    Evaluates check-in and check-out against assigned shift (including overnight shifts like 19:00 to 04:00).
    Returns status, late minutes, hours worked, and penalty multiplier (0, 0.25, 0.5, 1.0).
    """
    if not shift:
        shift = DEFAULT_SHIFTS["S5"]
    
    start_t = parse_time(shift.get("start_time", "09:00"))
    end_t = parse_time(shift.get("end_time", "17:00"))
    grace = int(shift.get("grace_minutes", 15))

    in_t = parse_time(check_in_str)
    out_t = parse_time(check_out_str)

    if not in_t:
        return {
            "status": "Absent",
            "late_minutes": 0,
            "early_minutes": 0,
            "hours_worked": 0.0,
            "penalty_days": 1.0,
            "remarks": "No check-in recorded (Full Cut)"
        }

    # Total minutes from midnight (00:00)
    start_mins = start_t.hour * 60 + start_t.minute
    end_mins = end_t.hour * 60 + end_t.minute
    
    # Detect if shift spans overnight (e.g. 19:00 PM to 04:00 AM)
    is_overnight = end_mins < start_mins
    if is_overnight:
        end_mins += 24 * 60  # e.g., 04:00 AM becomes 28 hours (1680 mins)

    in_mins = in_t.hour * 60 + in_t.minute
    # For overnight shift, if employee checks in early hours (e.g. 01:00 AM after midnight), adjust in_mins
    if is_overnight and in_mins < (start_mins - 180): # checked in after midnight
        in_mins += 24 * 60

    late_minutes = max(0, in_mins - start_mins)

    # Hours worked & Early exit calculation
    hours_worked = 0.0
    early_minutes = 0
    if out_t:
        out_mins = out_t.hour * 60 + out_t.minute
        if is_overnight and out_mins < start_mins:
            out_mins += 24 * 60
        elif out_mins < in_mins:
            out_mins += 24 * 60

        hours_worked = round(max(0, out_mins - in_mins) / 60.0, 2)
        early_minutes = max(0, end_mins - out_mins)

    shift_duration_mins = max(60, end_mins - start_mins)
    half_shift_mins = shift_duration_mins / 2.0
    three_quarter_mins = (3 * shift_duration_mins) / 4.0
    quarter_mins = shift_duration_mins / 4.0

    # Late arrival penalty tier (User Rule: Late up to Half Shift = Quarter Cut 0.25)
    if late_minutes <= grace:
        late_penalty = 0.0
    elif late_minutes <= half_shift_mins:
        late_penalty = 0.25
    elif late_minutes <= three_quarter_mins:
        late_penalty = 0.50
    else:
        late_penalty = 1.0

    # Early exit / total hours worked penalty tier (only if check_out recorded)
    early_penalty = 0.0
    if out_t:
        if hours_worked >= (shift_duration_mins / 60.0 - 0.25):
            early_penalty = 0.0
        elif hours_worked >= (half_shift_mins / 60.0):
            early_penalty = 0.25
        elif hours_worked >= (quarter_mins / 60.0):
            early_penalty = 0.50
        else:
            early_penalty = 1.0

    # Final penalty is the max penalty of late arrival vs early exit
    penalty = max(late_penalty, early_penalty)

    if penalty == 0.0:
        status = "On Time"
        remarks = "On time" if out_t else "On time (Pending Check-out)"
    elif penalty == 0.25:
        status = "Quarter Cut"
        remarks = f"Late by {late_minutes}m (Quarter Day Cut)"
    elif penalty == 0.50:
        status = "Half Cut"
        remarks = f"Late by {late_minutes}m (Half Day Cut)"
    elif penalty == 0.75:
        status = "Quarter Cut" # Or 3-Quarter
        remarks = f"Late by {late_minutes}m (3-Quarter Day Cut)"
    else:
        status = "Full Cut"
        remarks = f"Severely late by {late_minutes}m or short shift (Full Day Cut)"

    return {
        "status": status,
        "late_minutes": late_minutes,
        "early_minutes": early_minutes,
        "hours_worked": hours_worked,
        "penalty_days": penalty,
        "remarks": remarks
    }
