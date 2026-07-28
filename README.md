# NEFLOGIX | ZKTeco Biometric Multi-Shift HR & Payroll System

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-green.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/Database-MS%20SQL%20Server-red.svg)](https://www.microsoft.com/sql-server)
[![Device](https://img.shields.io/badge/Biometric-ZKTeco%20MB360-orange.svg)](https://www.zkteco.com/)

**NEFLOGIX ZKTeco Biometric Multi-Shift HR & Payroll Management System** is a full-featured, enterprise-ready solution engineered for real-time employee attendance tracking, cross-midnight overnight shift engine processing, automated salary cut calculations, printable monthly payslips, and system audit logging.

---

## 🌟 Key Features

- **ZKTeco Biometric Hardware Live Sync**: Direct socket connection (`pyzk`) with ZKTeco devices (e.g., MB360 @ `192.168.18.25:4370`).
- **Biometric Log File Importer**: Supports drag-and-drop parsing for `.xlsx`, `.xls`, `.csv`, `.txt`, and `.dat` biometric log formats.
- **Cross-Midnight Overnight Shift Engine**:
  - Handles complex shifts spanning midnight (e.g., 7:00 PM – 4:00 AM, 8:00 PM – 5:00 AM, 10:00 PM – 6:00 AM).
  - Automatically maps morning check-outs (up to 12:00 PM / 6:30 AM) to the previous calendar day's shift.
- **Automated Attendance Penalty Tiers**:
  - **Grace Period**: 15 minutes.
  - **Quarter Cut (0.25)**: Late by 1st quarter of shift duration.
  - **Half Cut (0.50)**: Late by 2nd quarter of shift duration.
  - **3-Quarter Cut (0.75)**: Late by 3rd quarter of shift duration.
  - **Full Cut (1.0)**: Absence or severe tardiness.
- **Automated Monthly Payroll & Deductions**:
  - Daily rate wage calculation based on employee base salary.
  - Annual free leave quota (24.0 days/year) tracking.
  - Automatic deduction of excess days beyond quota.
  - Strictly considers **Approved** leaves only.
- **Printable Monthly Salary Slips**:
  - One-click payslip generation for single or all employees.
  - Printable PDF layout with company header, itemized breakdown, and signature lines.
- **System Audit Trail & History Logs**:
  - Stored in MS SQL Server `AuditLogs` table.
  - Tracks all machine syncs, employee edits, shift updates, manual punches, and leave approvals.

---

## 🏗️ System Architecture

```
                       +-----------------------------------+
                       |    ZKTeco MB360 Biometric Device  |
                       +-----------------+-----------------+
                                         | Socket Sync (pyzk)
                                         v
+-----------------------+      +-------------------+      +-------------------------+
| Biometric File Upload | ---> | Flask REST API    | <--> | MS SQL Server Database  |
| (Excel, CSV, DAT)     |      | (server.py)       |      | (HR_Management)         |
+-----------------------+      +---------+---------+      +-------------------------+
                                         |
                                         v
                       +-----------------------------------+
                       | Vanilla JS / Glassmorphism UI     |
                       | (index.html, app.js, styles.css)  |
                       +-----------------------------------+
```

---

## 🛠️ Technology Stack

- **Backend**: Python 3.9+, Flask REST API, PyZK (ZKTeco SDK), PyODBC
- **Database**: Microsoft SQL Server (`HR_Management` DB, `pyodbc`)
- **Frontend**: Vanilla HTML5, CSS3 (Glassmorphism & `@media print`), Vanilla JavaScript
- **Hardware Integration**: ZKTeco MB360 / K40 / iFace series over UDP/TCP port 4370

---

## 🚀 Installation & Setup Guide

### 1. Prerequisites
- Python 3.9 or higher
- Microsoft SQL Server (`.\SQLEXPRESS`)
- ZKTeco Biometric Attendance Device connected on local network

### 2. Database Configuration
Ensure MS SQL Server is running locally. The application automatically initializes tables (`Employees`, `Shifts`, `Attendance`, `Leaves`, `AuditLogs`) on first startup.

### 3. Install Dependencies
```bash
pip install flask pyzk pyodbc openpyxl pandas
```

### 4. Running the Application
Start the server:
```bash
python server.py
```
Open your browser and navigate to:
```
http://localhost:5000
```

---

## 📄 License & Attribution

Developed by **NEFLOGIX**. All rights reserved.
