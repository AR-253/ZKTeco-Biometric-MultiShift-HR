import json
import os
from datetime import datetime

DATA_FILE = "hr_data.json"

# Load and save data
data = {
    "employees": [],
    "payrolls": [],
    "attendance": [],
    "leaves": [],
    "performance": [],
    "recruitments": [],
    "shifts": [],
    "expenses": [],
    "trainings": [],
    "feedbacks": []
}


def load_data():
    global data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            print("Failed to load data. Starting fresh.\n")


def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        print("Failed to save data.\n")


# Helper functions
def next_id(list_name, prefix=""):
    lst = data.get(list_name, [])
    if not lst:
        return f"{prefix}1" if prefix else 1
    last = lst[-1].get("id", lst[-1].get("emp_id", None))
    if isinstance(last, int):
        return last + 1
    # try to extract trailing number if possible
    try:
        num = int(''.join(ch for ch in str(last) if ch.isdigit()))
        return f"{prefix}{num + 1}" if prefix else num + 1
    except Exception:
        return f"{prefix}{len(lst) + 1}"


def find_employee_by_id(emp_id):
    for emp in data["employees"]:
        if str(emp.get("id")) == str(emp_id):
            return emp
    return None


def input_date(prompt, allow_blank=False):
    s = input(prompt).strip()
    if allow_blank and s == "":
        return ""
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        raise ValueError("Date must be YYYY-MM-DD.")
    return s


# Employee Management
def add_employee():
    try:
        emp_id = next_id("employees")
        name = input("Name: ").strip()
        age = int(input("Age: ").strip())
        position = input("Position: ").strip()
        email = input("Email: ").strip()
        data["employees"].append({
            "id": emp_id,
            "name": name,
            "age": age,
            "position": position,
            "email": email
        })
        save_data()
        print(f"Employee added with ID {emp_id}.\n")
    except Exception:
        print("Invalid input. Employee not added.\n")


def view_employees(employees=None):
    lst = employees if employees is not None else data["employees"]
    if not lst:
        print("No employees found.\n")
        return
    for emp in lst:
        print(f"ID: {emp['id']}, Name: {emp['name']}, Age: {emp['age']}, "
              f"Position: {emp['position']}, Email: {emp['email']}")
    print()


def edit_employee():
    try:
        view_employees()
        if not data["employees"]:
            return
        emp_id = input("Enter Employee ID to edit:").strip()
        emp = find_employee_by_id(emp_id)
        if not emp:
            print("Employee not found.\n")
            return
        name = input(f"Name ({emp['name']}): ").strip() or emp['name']
        age_input = input(f"Age ({emp['age']}): ").strip()
        age = int(age_input) if age_input else emp['age']
        position = input(f"Position ({emp['position']}): ").strip() or emp['position']
        email = input(f"Email ({emp['email']}): ").strip() or emp['email']
        emp.update({"name": name, "age": age, "position": position, "email": email})
        save_data()
        print("Employee updated.\n")
    except Exception:
        print("Invalid input.\n")


def delete_employee():
    try:
        view_employees()
        if not data["employees"]:
            return
        emp_id = input("Enter Employee ID to delete:").strip()
        emp = find_employee_by_id(emp_id)
        if not emp:
            print("Employee not found.\n")
            return
        confirm = input(f"Confirm delete {emp['name']}? (y/n): ").strip().lower()
        if confirm == "y":
            data["employees"].remove(emp)
            for key in ["payrolls", "attendance", "leaves", "performance",
                        "recruitments", "shifts", "expenses", "trainings", "feedbacks"]:
                data[key] = [item for item in data.get(key, []) if str(item.get("emp_id")) != str(emp_id)]
            save_data()
            print("Employee deleted.\n")
        else:
            print("Delete cancelled.\n")
    except Exception:
        print("Invalid input.\n")


def search_employees():
    try:
        query = input("Search by name or position: ").strip().lower()
        results = [e for e in data["employees"] if query in e["name"].lower() or query in e["position"].lower()]
        print(f"Found {len(results)} matching employee(s):")
        view_employees(results)
    except Exception:
        print("Invalid input.\n")


def filter_employees():
    try:
        print("Filter by:\n1. Age\n2. Position")
        min_age = input("Min Age (leave blank to skip):").strip()
        max_age = input("Max Age (leave blank to skip):").strip()
        position = input("Position (leave blank to skip):").strip().lower()
        lst = data["employees"]
        if min_age:
            lst = [e for e in lst if e["age"] >= int(min_age)]
        if max_age:
            lst = [e for e in lst if e["age"] <= int(max_age)]
        if position:
            lst = [e for e in lst if position in e["position"].lower()]
        view_employees(lst)
    except Exception:
        print("Invalid input for filter.\n")


# Payroll Module
def payroll_menu():
    try:
        view_employees()
        if not data["employees"]:
            return
        emp_id = input("Enter Employee ID for payroll:").strip()
        emp = find_employee_by_id(emp_id)
        if not emp:
            print("Employee not found.\n")
            return
        base = float(input("Base Salary:").strip())
        bonus_input = input("Bonus (leave blank for 0):").strip()
        bonus = float(bonus_input) if bonus_input else 0.0
        deduction_input = input("Deductions (leave blank for 0):").strip()
        deduction = float(deduction_input) if deduction_input else 0.0
        net = base + bonus - deduction
        data["payrolls"].append({
            "emp_id": emp_id,
            "base": base,
            "bonus": bonus,
            "deduction": deduction,
            "net": net,
            "date": datetime.now().strftime("%Y-%m-%d")
        })
        save_data()
        print(f"Payroll saved. Net: {net}\n")
    except Exception:
        print("Invalid input for Payroll.\n")


# Attendance Module
def attendance_menu():
    try:
        view_employees()
        if not data["employees"]:
            return
        emp_id = input("Enter Employee ID for attendance:").strip()
        emp = find_employee_by_id(emp_id)
        if not emp:
            print("Employee not found.\n")
            return
        date = input_date("Date (YYYY-MM-DD):")
        status = input("Status (Present/Absent/Leave):").strip().capitalize()
        if status not in ["Present", "Absent", "Leave"]:
            print("Invalid status.\n")
            return
        data["attendance"].append({"emp_id": emp_id, "date": date, "status": status})
        save_data()
        print("Attendance recorded.\n")
    except Exception:
        print("Invalid input for Attendance.\n")


# Leave Module
def leave_menu():
    try:
        view_employees()
        if not data["employees"]:
            return
        emp_id = input("Enter Employee ID for leave:").strip()
        emp = find_employee_by_id(emp_id)
        if not emp:
            print("Employee not found.\n")
            return
        from_date = input_date("Start Date (YYYY-MM-DD):")
        to_date = input_date("End Date (YYYY-MM-DD):")
        fd = datetime.strptime(from_date, "%Y-%m-%d")
        td = datetime.strptime(to_date, "%Y-%m-%d")
        if td < fd:
            print("End date cannot be before start date.\n")
            return
        days = (td - fd).days + 1
        reason = input("Reason for leave:").strip()
        data["leaves"].append({
            "emp_id": emp_id,
            "from_date": from_date,
            "to_date": to_date,
            "days": days,
            "reason": reason
        })
        save_data()
        print(f"Leave recorded for {days} day(s).\n")
    except Exception:
        print("Invalid input for Leave.\n")


# Performance Module
def performance_menu():
    try:
        view_employees()
        if not data["employees"]:
            return
        emp_id = input("Enter Employee ID for performance review:").strip()
        emp = find_employee_by_id(emp_id)
        if not emp:
            print("Employee not found.\n")
            return
        date = input_date("Review Date (YYYY-MM-DD):")
        rating = int(input("Rating (1-5):").strip())
        if rating < 1 or rating > 5:
            print("Rating must be between 1 and 5.\n")
            return
        comments = input("Comments:").strip()
        data["performance"].append({
            "emp_id": emp_id,
            "date": date,
            "rating": rating,
            "comments": comments
        })
        save_data()
        print("Performance review recorded.\n")
    except Exception:
        print("Invalid input for Performance Review.\n")


# Recruitment Module
def recruitment_menu():
    try:
        rec_id = next_id("recruitments", "C")
        name = input("Candidate Name: ").strip()
        position = input("Position Applied For: ").strip()
        exp_input = input("Years of Experience (leave blank for 0):").strip()
        experience = float(exp_input) if exp_input else 0.0
        status_input = input("Application Status (Applied/Interviewed/Hired/Rejected) [default Pending]:").strip()
        status = status_input.capitalize() if status_input else "Pending"
        data["recruitments"].append({
            "id": rec_id,
            "name": name,
            "position": position,
            "experience": experience,
            "status": status
        })
        save_data()
        print(f"Candidate added with ID {rec_id}.\n")
    except Exception:
        print("Invalid input for candidate.\n")


# Shift Scheduler
def shift_menu():
    try:
        view_employees()
        if not data["employees"]:
            return
        emp_id = input("Enter Employee ID for shift scheduling:").strip()
        emp = find_employee_by_id(emp_id)
        if not emp:
            print("Employee not found.\n")
            return
        date = input_date("Shift Date (YYYY-MM-DD):")
        shift_type = input("Shift Type (Morning/Evening/Night):").strip().capitalize()
        if shift_type not in ["Morning", "Evening", "Night"]:
            print("Invalid shift type.\n")
            return
        data["shifts"].append({"emp_id": emp_id, "date": date, "shift_type": shift_type})
        save_data()
        print("Shift scheduled.\n")
    except Exception:
        print("Invalid input for Shift Scheduling.\n")


# Expense Module
def expense_menu():
    try:
        view_employees()
        if not data["employees"]:
            return
        emp_id = input("Enter Employee ID for expense report:").strip()
        emp = find_employee_by_id(emp_id)
        if not emp:
            print("Employee not found.\n")
            return
        amount = float(input("Expense Amount:").strip())
        date = input_date("Expense Date (YYYY-MM-DD):")
        description = input("Expense Description:").strip()
        data["expenses"].append({
            "emp_id": emp_id,
            "amount": amount,
            "date": date,
            "description": description
        })
        save_data()
        print("Expense recorded.\n")
    except Exception:
        print("Invalid input for Expense Report.\n")


# Training Module
def training_menu():
    try:
        view_employees()
        if not data["employees"]:
            return
        emp_id = input("Enter Employee ID for training enrollment:").strip()
        emp = find_employee_by_id(emp_id)
        if not emp:
            print("Employee not found.\n")
            return
        title = input("Training/Certification title:").strip()
        # allow optional date
        date = input("Training Date (YYYY-MM-DD) [optional]:").strip()
        if date:
            # validate
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                print("Invalid date format.\n")
                return
        status_input = input("Status (Scheduled/Completed) [default Planned]:").strip()
        status = status_input.capitalize() if status_input else "Planned"
        data["trainings"].append({
            "emp_id": emp_id,
            "title": title,
            "date": date,
            "status": status
        })
        save_data()
        print("Training enrollment recorded.\n")
    except Exception:
        print("Invalid input for Training Enrollment.\n")


# Feedback Module
def feedback_menu():
    try:
        view_employees()
        if not data["employees"]:
            return
        emp_id = input("Enter Employee ID for feedback:").strip()
        emp = find_employee_by_id(emp_id)
        if not emp:
            print("Employee not found.\n")
            return
        date = input_date("Feedback Date (YYYY-MM-DD):")
        comments = input("Feedback Comments:").strip()
        rating = int(input("Rating (1-5):").strip())
        if rating < 1 or rating > 5:
            print("Rating must be between 1 and 5.\n")
            return
        data["feedbacks"].append({
            "emp_id": emp_id,
            "date": date,
            "comments": comments,
            "rating": rating
        })
        save_data()
        print("Feedback recorded.\n")
    except Exception:
        print("Invalid input for Feedback.\n")


# Main Menu
def main_menu():
    load_data()
    while True:
        print("Employee Management System")
        print("1. Employee Management")
        print("2. Search Employees")
        print("3. Filter Employee")
        print("4. Payroll Management")
        print("5. Attendance Tracking")
        print("6. Leave Management")
        print("7. Performance Tracker")
        print("8. Recruitment / Hiring")
        print("9. Shift Scheduling")
        print("10. Expense Management")
        print("11. Training / Certification")
        print("12. Feedback and Appraisals")
        print("13. Exit\n")

        choice = input("Select an option (1-13):").strip()
        print()

        try:
            if choice == "1":
                print("Employee Management")
                print("a. Add Employee")
                print("b. View Employees")
                print("c. Edit Employee")
                print("d. Delete Employee")
                print("e. Back to Main Menu\n")

                sub_choice = input("Select an option (a-e):").strip().lower()

                if sub_choice == "a":
                    add_employee()
                elif sub_choice == "b":
                    view_employees()
                elif sub_choice == "c":
                    edit_employee()
                elif sub_choice == "d":
                    delete_employee()
                elif sub_choice == "e":
                    pass
                else:
                    print("Invalid choice.\n")
                input("Press Enter to continue...\n")

            elif choice == "2":
                search_employees()
                input("Press Enter to continue...\n")

            elif choice == "3":
                filter_employees()
                input("Press Enter to continue...\n")

            elif choice == "4":
                payroll_menu()
                input("Press Enter to continue...\n")

            elif choice == "5":
                attendance_menu()
                input("Press Enter to continue...\n")

            elif choice == "6":
                leave_menu()
                input("Press Enter to continue...\n")

            elif choice == "7":
                performance_menu()
                input("Press Enter to continue...\n")

            elif choice == "8":
                recruitment_menu()
                input("Press Enter to continue...\n")

            elif choice == "9":
                shift_menu()
                input("Press Enter to continue...\n")

            elif choice == "10":
                expense_menu()
                input("Press Enter to continue...\n")

            elif choice == "11":
                training_menu()
                input("Press Enter to continue...\n")

            elif choice == "12":
                feedback_menu()
                input("Press Enter to continue...\n")

            elif choice == "13":
                save_data()
                print("Data saved. Goodbye!")
                break
            else:
                print("Invalid choice.\n")
        except Exception as e:
            print(f"An error occurred: {e}\n")


if __name__ == "__main__":
    main_menu()