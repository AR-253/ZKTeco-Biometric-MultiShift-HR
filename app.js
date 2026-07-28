const API_BASE = '/api';

let appState = {
  employees: [],
  shifts: {},
  attendance: [],
  leaves: [],
  payroll: []
};

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  startLiveClock();

  // Restore active tab across page refreshes
  const savedTab = localStorage.getItem('activeTab');
  if (savedTab && document.getElementById(`tab-${savedTab}`)) {
    switchTab(savedTab);
  }

  fetchInitialData();

  // Set default month pickers to current YYYY-MM
  const now = new Date();
  const ym = now.toISOString().slice(0, 7);
  document.getElementById('history-month-picker').value = ym;
  document.getElementById('payroll-month-picker').value = ym;
  document.getElementById('manual-date').value = now.toISOString().slice(0, 10);
  document.getElementById('leave-from').value = now.toISOString().slice(0, 10);
  document.getElementById('leave-to').value = now.toISOString().slice(0, 10);

  // Setup drag and drop
  setupDragAndDrop();

  // Close modals on overlay backdrop click or Escape key
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.classList.remove('active');
      }
    });
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.active').forEach(overlay => {
        overlay.classList.remove('active');
      });
    }
  });

  // Auto-sync ZKTeco machine (192.168.18.25) and refresh dashboard every 30 seconds
  let isAutoSyncing = false;
  setInterval(async () => {
    if (isAutoSyncing) return;
    isAutoSyncing = true;
    try {
      await fetch(`${API_BASE}/zkteco/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip: '192.168.18.25', port: 4370 })
      });
      await fetchInitialData();
    } catch (e) {
      // silent background sync catch
    } finally {
      isAutoSyncing = false;
    }
  }, 30000);
});


// Live ZKTeco Machine Sync
async function syncZKTecoMachine() {
  const btn = document.querySelector('button[onclick="syncZKTecoMachine()"]');
  const originalText = btn.innerHTML;
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Syncing ZKTeco...`;
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/zkteco/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip: '192.168.18.25', port: 4370 })
    });
    const result = await res.json();
    if (res.ok && result.success) {
      alert(`ZKTeco Sync Complete!\n${result.message}`);
      await fetchInitialData();
    } else {
      alert(`ZKTeco Sync Error: ${result.error || 'Failed to connect to machine.'}`);
    }
  } catch (err) {
    alert(`ZKTeco Sync Failed: ${err.message}`);
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}

async function syncZKTecoTime() {
  const btn = document.querySelector('button[onclick="syncZKTecoTime()"]');
  const originalText = btn.innerHTML;
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Fixing Machine Clock...`;
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/zkteco/sync-time`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip: '192.168.18.25', port: 4370 })
    });
    const result = await res.json();
    if (res.ok && result.success) {
      alert(`Machine Time Calibrated!\n${result.message}`);
    } else {
      alert(`Time Sync Error: ${result.error || 'Failed to calibrate machine clock.'}`);
    }
  } catch (err) {
    alert(`Time Sync Failed: ${err.message}`);
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}


function startLiveClock() {
  const clock = document.getElementById('live-clock');
  setInterval(() => {
    const d = new Date();
    clock.textContent = d.toLocaleTimeString();
  }, 1000);
}

// Fetch all system data from Flask REST API
async function fetchInitialData() {
  try {
    const res = await fetch(`${API_BASE}/data`);
    appState = await res.json();

    renderDashboard();
    renderEmployees();
    renderLeaves();
    renderHistory();
    fetchPayroll();
  } catch (err) {
    console.error('Error fetching data:', err);
  }
}

// Navigation Tabs
function switchTab(tabName) {
  document.querySelectorAll('.tab-page').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.nav-item button').forEach(el => el.classList.remove('active'));

  const tabEl = document.getElementById(`tab-${tabName}`);
  const navEl = document.getElementById(`nav-${tabName}`);
  if (tabEl) tabEl.style.display = 'block';
  if (navEl) navEl.classList.add('active');

  const titles = {
    dashboard: 'Real-Time Attendance Dashboard',
    biometric: 'Import Biometric Machine Excel Log',
    employees: 'Employee Directory & Shift Management',
    leaves: 'Leave Management (Quarter, Half & Full)',
    history: 'Monthly Biometric Attendance History',
    payroll: 'Payroll & Automated Salary Cut Deductions',
    audit: 'System Audit Trail & History Logs'
  };
  document.getElementById('page-title').textContent = titles[tabName] || 'HR System';
  localStorage.setItem('activeTab', tabName);

  if (tabName === 'history') renderHistory();
  if (tabName === 'payroll') fetchPayroll();
  if (tabName === 'audit') fetchAuditLogs();
}

// Render Dashboard
function renderDashboard() {
  document.getElementById('stat-total-emp').textContent = appState.employees.length;

  const todayStr = new Date().toISOString().slice(0, 10);
  const todayAtt = appState.attendance.filter(a => a.date === todayStr);

  const onTime = todayAtt.filter(a => a.status === 'On Time').length;
  const cuts = todayAtt.filter(a => ['Quarter Cut', 'Half Cut', 'Full Cut'].includes(a.status)).length;
  const totalIn = todayAtt.length;
  const absent = Math.max(0, appState.employees.length - totalIn);

  document.getElementById('stat-ontime').textContent = onTime;
  document.getElementById('stat-late-cuts').textContent = cuts;
  document.getElementById('stat-absent').textContent = absent;

  const tbody = document.getElementById('live-attendance-tbody');
  tbody.innerHTML = '';

  if (todayAtt.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:24px;">No biometric attendance recorded for today yet. Upload an Excel log file or add a manual punch!</td></tr>`;
    return;
  }

  todayAtt.forEach(a => {
    const emp = appState.employees.find(e => String(e.id) === String(a.emp_id));
    const currentShift = (emp && appState.shifts[emp.shift_id]) ? appState.shifts[emp.shift_id] : (appState.shifts[a.shift_id] || { name: a.shift_name || 'Standard' });

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${a.emp_id}</strong></td>
      <td>${emp ? emp.name : a.emp_name}</td>
      <td><span class="badge badge-shift">${currentShift.name}</span></td>
      <td>${a.check_in || '--:--'}</td>
      <td>${a.check_out || '--:--'}</td>
      <td>${a.hours_worked || '0.0'} hrs</td>
      <td>${getStatusBadge(a.status)}</td>
      <td style="font-size:12px; color:var(--text-muted);">${a.remarks}</td>
      <td>
        <button class="btn btn-secondary" style="padding:4px 10px; font-size:12px;" onclick="editAttendancePunch('${a.emp_id}', '${a.date}', '${a.check_in || ''}', '${a.check_out || ''}')" title="Fix / Manual Check-In">
          <i class="fa-solid fa-pen-to-square"></i> Edit
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });


}

function getStatusBadge(status) {
  switch (status) {
    case 'On Time': return `<span class="badge badge-ontime"><i class="fa-solid fa-check"></i> On Time</span>`;
    case 'Quarter Cut': return `<span class="badge badge-quarter"><i class="fa-solid fa-triangle-exclamation"></i> Quarter Cut (0.25)</span>`;
    case 'Half Cut': return `<span class="badge badge-half"><i class="fa-solid fa-circle-exclamation"></i> Half Cut (0.50)</span>`;
    case 'Full Cut': case 'Absent': return `<span class="badge badge-full"><i class="fa-solid fa-xmark"></i> Full Cut (1.0)</span>`;
    default: return `<span class="badge badge-shift">${status}</span>`;
  }
}

// Drag and Drop Upload for Biometric Excel Logs
function setupDragAndDrop() {
  const dropzone = document.getElementById('dropzone');

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  });
}

function handleFileSelect(e) {
  const files = e.target.files;
  if (files.length > 0) {
    uploadFile(files[0]);
  }
}

async function uploadFile(file) {
  const statusDiv = document.getElementById('upload-status');
  statusDiv.innerHTML = `<div style="color:var(--primary); font-weight:600;"><i class="fa-solid fa-spinner fa-spin"></i> Parsing biometric Excel log file...</div>`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`${API_BASE}/biometric/upload`, {
      method: 'POST',
      body: formData
    });
    const result = await res.json();

    if (res.ok) {
      statusDiv.innerHTML = `<div style="color:var(--success); font-weight:700;"><i class="fa-solid fa-circle-check"></i> ${result.message}</div>`;
      await fetchInitialData();
      setTimeout(() => switchTab('dashboard'), 1500);
    } else {
      statusDiv.innerHTML = `<div style="color:var(--danger); font-weight:700;"><i class="fa-solid fa-circle-xmark"></i> ${result.error}</div>`;
    }
  } catch (err) {
    statusDiv.innerHTML = `<div style="color:var(--danger); font-weight:700;"><i class="fa-solid fa-circle-xmark"></i> Failed to upload log file.</div>`;
  }
}

// Employees & Shifts
function renderEmployees() {
  renderShifts();
  updateShiftDropdowns();

  const tbody = document.getElementById('employees-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const filterSelect = document.getElementById('employee-status-filter');
  const filterVal = filterSelect ? filterSelect.value : 'Active';

  const filteredEmployees = appState.employees.filter(emp => {
    const empStatus = emp.status || 'Active';
    if (filterVal === 'Active') return empStatus === 'Active';
    if (filterVal === 'Inactive') return empStatus === 'Inactive';
    return true; // 'All'
  });

  filteredEmployees.forEach(emp => {
    const shift = appState.shifts[emp.shift_id] || { name: 'Standard (09:00 - 17:00)' };
    const empStatus = emp.status || 'Active';
    const statusBadge = empStatus === 'Active'
      ? `<span class="badge badge-ontime"><i class="fa-solid fa-circle-check"></i> Active</span>`
      : `<span class="badge badge-full"><i class="fa-solid fa-circle-xmark"></i> Inactive</span>`;

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${emp.id}</strong></td>
      <td>${emp.name}</td>
      <td>${emp.department || 'General'}</td>
      <td>${emp.role || 'Staff'}</td>
      <td>PKR ${Number(emp.base_salary).toLocaleString()}</td>
      <td><span class="badge badge-shift"><i class="fa-solid fa-clock"></i> ${shift.name}</span></td>
      <td>${statusBadge}</td>
      <td style="display:flex; gap:8px;">
        <button class="btn btn-primary" style="padding:4px 10px; font-size:12px;" onclick="editEmployee('${emp.id}')">
          <i class="fa-solid fa-pen-to-square"></i> Edit
        </button>
        <button class="btn btn-secondary" style="padding:4px 10px; font-size:12px;" onclick="deleteEmployee('${emp.id}')">
          <i class="fa-solid fa-trash" style="color:var(--danger);"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function renderShifts() {
  const tbody = document.getElementById('shifts-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  Object.values(appState.shifts).forEach(shift => {
    const isOvernight = shift.end_time < shift.start_time;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${shift.id}</strong></td>
      <td>${shift.name}</td>
      <td>${shift.start_time}</td>
      <td>${shift.end_time}</td>
      <td>${shift.grace_minutes} mins</td>
      <td><span class="badge ${isOvernight ? 'badge-half' : 'badge-shift'}">${isOvernight ? 'Overnight Shift' : 'Standard Shift'}</span></td>
      <td style="display:flex; gap:8px;">
        <button class="btn btn-primary" style="padding:4px 10px; font-size:12px;" onclick="editShift('${shift.id}')">
          <i class="fa-solid fa-pen-to-square"></i> Edit
        </button>
        <button class="btn btn-secondary" style="padding:4px 10px; font-size:12px;" onclick="deleteShift('${shift.id}')">
          <i class="fa-solid fa-trash" style="color:var(--danger);"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function updateShiftDropdowns() {
  const empShiftSelect = document.getElementById('emp-shift');
  if (empShiftSelect) {
    empShiftSelect.innerHTML = '';
    Object.values(appState.shifts).forEach(shift => {
      empShiftSelect.innerHTML += `<option value="${shift.id}">${shift.name} (${shift.start_time} - ${shift.end_time})</option>`;
    });
  }
}

function openShiftModal() {
  document.getElementById('shift-form').reset();
  document.getElementById('shift-id').readOnly = false;
  if (document.getElementById('shift-modal-title')) {
    document.getElementById('shift-modal-title').textContent = 'Add Custom Shift';
  }
  document.getElementById('shift-modal').classList.add('active');
}

function editShift(shiftId) {
  const shift = appState.shifts[shiftId];
  if (!shift) return;

  document.getElementById('shift-id').value = shift.id;
  document.getElementById('shift-id').readOnly = true;
  document.getElementById('shift-name').value = shift.name;
  document.getElementById('shift-start').value = shift.start_time;
  document.getElementById('shift-end').value = shift.end_time;
  document.getElementById('shift-grace').value = shift.grace_minutes || 15;

  if (document.getElementById('shift-modal-title')) {
    document.getElementById('shift-modal-title').textContent = `Edit Shift (${shift.id})`;
  }
  document.getElementById('shift-modal').classList.add('active');
}

function closeShiftModal() {
  document.getElementById('shift-modal').classList.remove('active');
}


async function saveShift(e) {
  e.preventDefault();
  const shiftData = {
    id: document.getElementById('shift-id').value.trim(),
    name: document.getElementById('shift-name').value.trim(),
    start_time: document.getElementById('shift-start').value,
    end_time: document.getElementById('shift-end').value,
    grace_minutes: parseInt(document.getElementById('shift-grace').value) || 15
  };

  // Instant UI Update
  appState.shifts[shiftData.id] = shiftData;
  closeShiftModal();
  renderEmployees();

  try {
    await fetch(`${API_BASE}/shifts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(shiftData)
    });
  } catch (err) {
    console.error('Error saving custom shift:', err);
  }
}

async function deleteShift(shiftId) {
  if (!confirm(`Are you sure you want to delete shift ${shiftId}?`)) return;
  
  // Instant UI Update
  delete appState.shifts[shiftId];
  renderEmployees();

  try {
    const res = await fetch(`${API_BASE}/shifts/${shiftId}`, { method: 'DELETE' });
    const result = await res.json();
    if (!res.ok || !result.success) {
      fetchInitialData();
    }
  } catch (err) {
    fetchInitialData();
  }
}


function openEmployeeModal() {
  document.getElementById('emp-form').reset();
  document.getElementById('emp-id').readOnly = false;
  if (document.getElementById('emp-status')) {
    document.getElementById('emp-status').value = 'Active';
  }
  if (document.getElementById('emp-initial-leaves')) {
    document.getElementById('emp-initial-leaves').value = '0.0';
  }
  document.getElementById('emp-modal-title').textContent = 'Add Employee';
  document.getElementById('employee-modal').classList.add('active');
}

function editEmployee(empId) {
  const emp = appState.employees.find(e => String(e.id) === String(empId));
  if (!emp) return;

  document.getElementById('emp-id').value = emp.id;
  document.getElementById('emp-id').readOnly = true;
  document.getElementById('emp-name').value = emp.name;
  document.getElementById('emp-dept').value = emp.department || '';
  document.getElementById('emp-role').value = emp.role || '';
  document.getElementById('emp-salary').value = emp.base_salary;
  document.getElementById('emp-quota').value = emp.annual_leave_quota || 24.0;
  if (document.getElementById('emp-initial-leaves')) {
    document.getElementById('emp-initial-leaves').value = emp.initial_leaves_taken !== undefined ? emp.initial_leaves_taken : 0.0;
  }
  if (document.getElementById('emp-shift')) {
    document.getElementById('emp-shift').value = emp.shift_id;
  }
  if (document.getElementById('emp-status')) {
    document.getElementById('emp-status').value = emp.status || 'Active';
  }

  document.getElementById('emp-modal-title').textContent = `Edit Employee (ID: ${emp.id})`;
  document.getElementById('employee-modal').classList.add('active');
}

function closeEmployeeModal() {
  document.getElementById('employee-modal').classList.remove('active');
}

async function saveEmployee(e) {
  e.preventDefault();
  const empData = {
    id: document.getElementById('emp-id').value.trim(),
    name: document.getElementById('emp-name').value.trim(),
    department: document.getElementById('emp-dept').value.trim(),
    role: document.getElementById('emp-role').value.trim(),
    base_salary: parseFloat(document.getElementById('emp-salary').value),
    annual_leave_quota: parseFloat(document.getElementById('emp-quota').value) || 24.0,
    initial_leaves_taken: parseFloat(document.getElementById('emp-initial-leaves').value) || 0.0,
    shift_id: document.getElementById('emp-shift').value,
    status: document.getElementById('emp-status') ? document.getElementById('emp-status').value : 'Active'
  };

  // Instant UI Update
  const idx = appState.employees.findIndex(emp => String(emp.id) === String(empData.id));
  if (idx >= 0) {
    appState.employees[idx] = { ...appState.employees[idx], ...empData };
  } else {
    appState.employees.push(empData);
  }
  closeEmployeeModal();
  renderEmployees();
  renderDashboard();

  try {
    await fetch(`${API_BASE}/employees`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(empData)
    });
  } catch (err) {
    console.error('Error saving employee:', err);
  }
}


async function deleteEmployee(empId) {
  if (!confirm(`Are you sure you want to delete employee ID ${empId}?`)) return;

  // Instant UI Update
  appState.employees = appState.employees.filter(e => String(e.id) !== String(empId));
  renderEmployees();
  renderDashboard();

  try {
    await fetch(`${API_BASE}/employees/${empId}`, { method: 'DELETE' });
  } catch (err) {
    console.error('Error deleting employee:', err);
  }
}


// Leaves
function renderLeaves() {
  const tbody = document.getElementById('leaves-tbody');
  tbody.innerHTML = '';

  const leaves = appState.leaves || [];
  if (leaves.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:var(--text-muted); padding:24px;">No leave applications found.</td></tr>`;
    return;
  }

  leaves.forEach(l => {
    const shift = appState.shifts[l.shift_id] || { name: 'Standard' };
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${l.id}</strong></td>
      <td>${l.emp_name} (ID: ${l.emp_id})</td>
      <td><span class="badge badge-shift">${shift.name}</span></td>
      <td>${l.from_date}</td>
      <td>${l.to_date}</td>
      <td><strong>${l.leave_type} Day</strong></td>
      <td><span class="badge badge-quarter">${l.deduction_value} Day Salary Cut</span></td>
      <td>${l.reason || 'N/A'}</td>
      <td><span class="badge badge-ontime">Approved</span></td>
      <td style="display:flex; gap:8px;">
        <button class="btn btn-primary" style="padding:4px 10px; font-size:12px;" onclick="editLeave('${l.id}')">
          <i class="fa-solid fa-pen-to-square"></i> Edit
        </button>
        <button class="btn btn-secondary" style="padding:4px 10px; font-size:12px;" onclick="deleteLeave('${l.id}')">
          <i class="fa-solid fa-trash" style="color:var(--danger);"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function openLeaveModal() {
  const select = document.getElementById('leave-emp-select');
  select.innerHTML = '<option value="">-- Select Employee --</option>';
  appState.employees.forEach(emp => {
    select.innerHTML += `<option value="${emp.id}">${emp.name} (ID: ${emp.id})</option>`;
  });
  if (document.getElementById('leave-id')) document.getElementById('leave-id').value = '';
  if (document.getElementById('leave-form')) document.getElementById('leave-form').reset();
  if (document.getElementById('leave-modal-title')) document.getElementById('leave-modal-title').textContent = 'Apply Leave Request';
  document.getElementById('leave-shift-info').textContent = '';
  document.getElementById('leave-modal').classList.add('active');
}

function editLeave(leaveId) {
  const leave = (appState.leaves || []).find(l => String(l.id) === String(leaveId));
  if (!leave) return;

  openLeaveModal();

  if (document.getElementById('leave-id')) document.getElementById('leave-id').value = leave.id;
  if (document.getElementById('leave-modal-title')) document.getElementById('leave-modal-title').textContent = `Edit Leave Request (${leave.id})`;

  document.getElementById('leave-emp-select').value = String(leave.emp_id);
  document.getElementById('leave-type-select').value = leave.leave_type || 'Full';
  document.getElementById('leave-from').value = leave.from_date || '';
  document.getElementById('leave-to').value = leave.to_date || '';
  document.getElementById('leave-reason').value = leave.reason || '';

  updateLeaveShiftInfo();
}

function closeLeaveModal() {
  document.getElementById('leave-modal').classList.remove('active');
}

function updateLeaveShiftInfo() {
  const empId = document.getElementById('leave-emp-select').value;
  const emp = appState.employees.find(e => String(e.id) === String(empId));
  const infoDiv = document.getElementById('leave-shift-info');
  if (emp) {
    const shift = appState.shifts[emp.shift_id] || { name: 'Standard (09:00 - 17:00)' };
    infoDiv.textContent = `Assigned Shift: ${shift.name} (${shift.start_time} - ${shift.end_time})`;
  } else {
    infoDiv.textContent = '';
  }
}

async function saveLeave(e) {
  e.preventDefault();
  const leaveId = document.getElementById('leave-id') ? document.getElementById('leave-id').value : '';
  const empId = document.getElementById('leave-emp-select').value;
  const emp = appState.employees.find(el => String(el.id) === String(empId));
  const leaveData = {
    id: leaveId || `L-${Date.now()}`,
    emp_id: empId,
    emp_name: emp ? emp.name : `Emp ${empId}`,
    leave_type: document.getElementById('leave-type-select').value,
    from_date: document.getElementById('leave-from').value,
    to_date: document.getElementById('leave-to').value,
    reason: document.getElementById('leave-reason').value.trim(),
    status: 'Approved',
    deduction_value: document.getElementById('leave-type-select').value === 'Full' ? 1.0 : (document.getElementById('leave-type-select').value === 'Half' ? 0.5 : 0.25)
  };

  // Instant UI Update
  if (!appState.leaves) appState.leaves = [];
  const idx = appState.leaves.findIndex(l => String(l.id) === String(leaveData.id));
  if (idx >= 0) {
    appState.leaves[idx] = { ...appState.leaves[idx], ...leaveData };
  } else {
    appState.leaves.unshift(leaveData);
  }
  closeLeaveModal();
  renderLeaves();

  try {
    const res = await fetch(`${API_BASE}/leaves`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(leaveData)
    });
    if (res.ok) {
      await fetchInitialData();
    }
  } catch (err) {
    console.error('Error saving leave application:', err);
  }
}

async function deleteLeave(leaveId) {
  if (!confirm(`Are you sure you want to delete leave record ${leaveId}?`)) return;

  // Instant UI Update
  if (appState.leaves) {
    appState.leaves = appState.leaves.filter(l => String(l.id) !== String(leaveId));
    renderLeaves();
  }

  try {
    const res = await fetch(`${API_BASE}/leaves/${leaveId}`, { method: 'DELETE' });
    if (res.ok) {
      await fetchInitialData();
    }
  } catch (err) {
    console.error('Error deleting leave:', err);
  }
}


// Monthly History (Calendar & Day View)
let selectedHistoryDateStr = new Date().toISOString().slice(0, 10);

function renderHistory() {
  const datePicker = document.getElementById('history-date-picker');
  const monthPicker = document.getElementById('history-month-picker');

  if (datePicker && !datePicker.value) {
    datePicker.value = selectedHistoryDateStr;
  }
  if (datePicker && datePicker.value) {
    selectedHistoryDateStr = datePicker.value;
  }
  if (monthPicker) {
    monthPicker.value = selectedHistoryDateStr.slice(0, 7);
  }

  renderHistoryCalendar();
  renderHistoryTableForDate(selectedHistoryDateStr);
}

function renderHistoryCalendar() {
  const monthPicker = document.getElementById('history-month-picker');
  const container = document.getElementById('calendar-days-container');
  if (!container || !monthPicker) return;

  container.innerHTML = '';
  const ym = monthPicker.value || selectedHistoryDateStr.slice(0, 7);
  const [yearStr, monthStr] = ym.split('-');
  const year = parseInt(yearStr);
  const month = parseInt(monthStr) - 1; // 0-indexed

  // First day of month and total days in month
  const firstDayObj = new Date(year, month, 1);
  const lastDayObj = new Date(year, month + 1, 0);
  const totalDays = lastDayObj.getDate();

  // Day of week for 1st day (0 = Sun, 1 = Mon, ..., 6 = Sat)
  // We want Monday-based grid (0 = Mon, ..., 6 = Sun)
  let startDayOfWeek = firstDayObj.getDay() - 1;
  if (startDayOfWeek === -1) startDayOfWeek = 6; // Sunday becomes 6

  // Render empty leading cells for days before the 1st
  for (let i = 0; i < startDayOfWeek; i++) {
    const emptyCard = document.createElement('div');
    emptyCard.className = 'calendar-day-card other-month';
    container.appendChild(emptyCard);
  }

  // Render days of the month
  for (let day = 1; day <= totalDays; day++) {
    const dayStr = String(day).padStart(2, '0');
    const dateStr = `${yearStr}-${monthStr}-${dayStr}`;

    const dayPunches = appState.attendance.filter(a => a.date === dateStr);
    const count = dayPunches.length;

    const isSelected = dateStr === selectedHistoryDateStr;
    const card = document.createElement('div');
    card.className = `calendar-day-card ${isSelected ? 'active-day' : ''}`;
    card.onclick = () => selectHistoryDate(dateStr);

    const badgeHtml = count > 0
      ? `<span class="calendar-day-badge badge-has-data"><i class="fa-solid fa-check"></i> ${count} Logs</span>`
      : `<span class="calendar-day-badge badge-no-data">No logs</span>`;

    card.innerHTML = `
      <div class="calendar-day-num">${day}</div>
      ${badgeHtml}
    `;

    container.appendChild(card);
  }
}

function selectHistoryDate(dateStr) {
  selectedHistoryDateStr = dateStr;

  const datePicker = document.getElementById('history-date-picker');
  const monthPicker = document.getElementById('history-month-picker');
  if (datePicker) datePicker.value = dateStr;
  if (monthPicker) monthPicker.value = dateStr.slice(0, 7);

  renderHistoryCalendar();
  renderHistoryTableForDate(dateStr);
}

function jumpToTodayHistory() {
  const todayStr = new Date().toISOString().slice(0, 10);
  selectHistoryDate(todayStr);
}

function renderHistoryTableForDate(dateStr) {
  const tbody = document.getElementById('history-tbody');
  const headerEl = document.getElementById('history-selected-date-header');
  const summaryBadgeEl = document.getElementById('history-day-summary-badge');
  if (!tbody) return;

  tbody.innerHTML = '';

  const dateObj = new Date(dateStr + 'T00:00:00');
  const formattedDate = dateObj.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  if (headerEl) {
    headerEl.innerHTML = `<i class="fa-solid fa-calendar-check" style="color:var(--primary);"></i> Attendance Logs for ${formattedDate}`;
  }

  const dayAtt = appState.attendance.filter(a => a.date === dateStr);

  if (summaryBadgeEl) {
    if (dayAtt.length === 0) {
      summaryBadgeEl.innerHTML = `<span style="color:var(--text-muted);">0 Records Logged</span>`;
    } else {
      const onTime = dayAtt.filter(a => a.status === 'On Time').length;
      const cuts = dayAtt.filter(a => ['Quarter Cut', 'Half Cut', 'Full Cut'].includes(a.status)).length;
      summaryBadgeEl.innerHTML = `<span class="badge badge-ontime"><i class="fa-solid fa-users"></i> ${dayAtt.length} Employees Logged</span> <span class="badge badge-shift">On-Time: ${onTime}</span> <span class="badge badge-half">Penalties: ${cuts}</span>`;
    }
  }

  if (dayAtt.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:32px;">No biometric attendance recorded for <strong>${dateStr}</strong>. Select another date from the calendar above!</td></tr>`;
    return;
  }

  dayAtt.sort((a, b) => (a.check_in || '').localeCompare(b.check_in || '')).forEach(a => {
    const emp = appState.employees.find(e => String(e.id) === String(a.emp_id));
    const currentShift = (emp && appState.shifts[emp.shift_id]) ? appState.shifts[emp.shift_id] : (appState.shifts[a.shift_id] || { name: a.shift_name || 'Standard' });

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${a.date}</strong></td>
      <td><strong>${a.emp_id}</strong></td>
      <td>${emp ? emp.name : a.emp_name}</td>
      <td><span class="badge badge-shift">${currentShift.name}</span></td>
      <td>${a.check_in || '--:--'}</td>
      <td>${a.check_out || '--:--'}</td>
      <td>${a.hours_worked || '0.0'} hrs</td>
      <td>${getStatusBadge(a.status)}</td>
      <td style="font-size:12px; color:var(--text-muted);">${a.remarks}</td>
    `;
    tbody.appendChild(tr);
  });
}

// Payroll
async function fetchPayroll() {
  const ym = document.getElementById('payroll-month-picker').value || new Date().toISOString().slice(0, 7);
  const statusFilter = document.getElementById('payroll-status-filter') ? document.getElementById('payroll-status-filter').value : 'Active';
  try {
    const res = await fetch(`${API_BASE}/payroll/calculate?month=${ym}&status=${statusFilter}`);
    const data = await res.json();
    appState.currentPayroll = data.payroll || [];
    renderPayrollTable(data.payroll);
  } catch (err) {
    console.error('Error fetching payroll:', err);
  }
}

function renderPayrollTable(payrollList) {
  const tbody = document.getElementById('payroll-tbody');
  tbody.innerHTML = '';

  if (!payrollList || payrollList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:var(--text-muted); padding:24px;">No employees to generate payroll.</td></tr>`;
    return;
  }

  payrollList.forEach(p => {
    const tr = document.createElement('tr');
    const hasDeduction = p.chargeable_days > 0;
    tr.innerHTML = `
      <td><strong>${p.emp_id}</strong></td>
      <td>${p.emp_name}</td>
      <td>PKR ${Number(p.base_salary).toLocaleString()}</td>
      <td><span class="badge badge-shift">${p.annual_quota} Days / Year</span></td>
      <td><strong>${p.total_ytd_used} Days</strong></td>
      <td><span class="badge ${p.quota_remaining > 0 ? 'badge-ontime' : 'badge-full'}">${p.quota_remaining} Days Left</span></td>
      <td><span class="badge ${hasDeduction ? 'badge-full' : 'badge-ontime'}">${p.chargeable_days} Cut Days</span></td>
      <td style="color:${hasDeduction ? 'var(--danger)' : 'var(--success)'}; font-weight:700;">${hasDeduction ? '- PKR ' + Number(p.deduction_amount).toLocaleString() : 'PKR 0 (Within ' + p.annual_quota + ' Quota)'}</td>
      <td><strong style="color:var(--success); font-size:16px;">PKR ${Number(p.net_salary).toLocaleString()}</strong></td>
      <td style="display:flex; gap:8px;">
        <button class="btn btn-primary" style="padding:4px 10px; font-size:12px;" onclick="openPayslipModalSingle('${p.emp_id}')" title="Generate & Print Monthly Payslip">
          <i class="fa-solid fa-file-invoice-dollar"></i> Payslip
        </button>
        <button class="btn btn-secondary" style="padding:4px 10px; font-size:12px;" onclick="openPayrollEditModal('${p.emp_id}')" title="Edit Annual Quota / Total Leaves Settings">
          <i class="fa-solid fa-pen-to-square"></i> Edit
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function openPayrollEditModal(empId) {
  const emp = appState.employees.find(e => String(e.id) === String(empId));
  if (!emp) return;

  const currentP = appState.currentPayroll ? appState.currentPayroll.find(p => String(p.emp_id) === String(empId)) : null;
  const currentTotalUsed = currentP ? currentP.total_ytd_used : 0.0;
  const bioPenalty = currentP ? (currentP.biometric_penalty || 0.0) : 0.0;

  document.getElementById('payroll-edit-emp-id').dataset.bioPenalty = bioPenalty;
  document.getElementById('payroll-edit-emp-id').value = emp.id;
  document.getElementById('payroll-edit-emp-name').value = `${emp.name} (ID: ${emp.id})`;
  document.getElementById('payroll-edit-quota').value = emp.annual_leave_quota !== undefined ? emp.annual_leave_quota : 24.0;
  document.getElementById('payroll-edit-total-used').value = currentTotalUsed;
  document.getElementById('payroll-edit-salary').value = emp.base_salary || 60000;

  updatePayrollEditPreview();
  document.getElementById('payroll-edit-modal').classList.add('active');
}

function updatePayrollEditPreview() {
  const quota = parseFloat(document.getElementById('payroll-edit-quota').value) || 0;
  const totalUsed = parseFloat(document.getElementById('payroll-edit-total-used').value) || 0;
  const remaining = Math.max(0, Math.round((quota - totalUsed) * 100) / 100);

  const previewEl = document.getElementById('payroll-edit-preview');
  if (previewEl) {
    previewEl.innerHTML = `<i class="fa-solid fa-calculator" style="color:var(--primary);"></i> Annual Quota: <strong>${quota} Days</strong> | Total Leaves Used: <strong>${totalUsed} Days</strong> | Free Quota Left: <strong style="color:${remaining > 0 ? 'var(--success)' : 'var(--danger)'}">${remaining} Days Left</strong>`;
  }
}

function closePayrollEditModal() {
  document.getElementById('payroll-edit-modal').classList.remove('active');
}

async function savePayrollQuota(e) {
  e.preventDefault();
  const empId = document.getElementById('payroll-edit-emp-id').value;
  const emp = appState.employees.find(e => String(e.id) === String(empId));
  if (!emp) return;

  const desiredTotalUsed = parseFloat(document.getElementById('payroll-edit-total-used').value) || 0.0;
  const bioPenalty = parseFloat(document.getElementById('payroll-edit-emp-id').dataset.bioPenalty) || 0.0;
  const initialLeavesNeeded = Math.round((desiredTotalUsed - bioPenalty) * 100) / 100;

  const updatedEmp = {
    ...emp,
    shift_id: emp.shift_id,
    annual_leave_quota: parseFloat(document.getElementById('payroll-edit-quota').value),
    initial_leaves_taken: initialLeavesNeeded,
    base_salary: parseFloat(document.getElementById('payroll-edit-salary').value)
  };

  try {
    const res = await fetch(`${API_BASE}/employees`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedEmp)
    });
    if (res.ok) {
      closePayrollEditModal();
      await fetchInitialData();
      await fetchPayroll();
    }
  } catch (err) {
    alert('Error updating employee quota');
  }
}


// Manual Punch Modal
function openManualPunchModal() {
  const select = document.getElementById('manual-emp-select');
  select.innerHTML = '<option value="">-- Select Employee --</option>';
  appState.employees.forEach(emp => {
    select.innerHTML += `<option value="${emp.id}">${emp.name} (ID: ${emp.id})</option>`;
  });
  document.getElementById('manual-date').value = new Date().toISOString().slice(0, 10);
  document.getElementById('manual-modal').classList.add('active');
}

function editAttendancePunch(empId, dateStr, checkIn, checkOut) {
  openManualPunchModal();
  document.getElementById('manual-emp-select').value = String(empId);
  document.getElementById('manual-date').value = dateStr;
  document.getElementById('manual-in').value = checkIn !== 'null' && checkIn !== '--:--' ? checkIn : '';
  document.getElementById('manual-out').value = checkOut !== 'null' && checkOut !== '--:--' ? checkOut : '';
}

function closeManualModal() {
  document.getElementById('manual-modal').classList.remove('active');
}


async function saveManualPunch(e) {
  e.preventDefault();
  const punchData = {
    emp_id: document.getElementById('manual-emp-select').value,
    date: document.getElementById('manual-date').value,
    check_in: document.getElementById('manual-in').value,
    check_out: document.getElementById('manual-out').value
  };

  closeManualModal();

  try {
    const res = await fetch(`${API_BASE}/attendance/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(punchData)
    });
    if (res.ok) {
      await fetchInitialData();
    }
  } catch (err) {
    console.error('Error saving manual punch:', err);
  }
}


function str(val) {
  return String(val || '').trim();
}


// AUDIT TRAIL & SYSTEM LOGS
let appAuditLogs = [];

async function fetchAuditLogs() {
  const tbody = document.getElementById('audit-tbody');
  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:24px; color:var(--primary);"><i class="fa-solid fa-spinner fa-spin"></i> Loading system audit logs...</td></tr>`;
  }
  try {
    const res = await fetch(`${API_BASE}/audit-logs?limit=200`);
    const data = await res.json();
    appAuditLogs = data.logs || [];
    renderAuditLogs(appAuditLogs);
  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:24px; color:var(--danger);">Failed to load audit logs.</td></tr>`;
    }
  }
}

function renderAuditLogs(logs) {
  const tbody = document.getElementById('audit-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!logs || logs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:32px;">No system audit activity recorded yet.</td></tr>`;
    return;
  }

  logs.forEach(l => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>#${l.id}</strong></td>
      <td><span style="font-size:12px; color:var(--text-muted);"><i class="fa-regular fa-clock"></i> ${l.timestamp}</span></td>
      <td><span class="badge badge-shift"><i class="fa-solid fa-shield-halved"></i> ${l.action}</span></td>
      <td>${l.details}</td>
      <td><span class="badge badge-ontime">${l.performed_by}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function filterAuditLogs() {
  const query = (document.getElementById('audit-search-input').value || '').toLowerCase().trim();
  if (!query) {
    renderAuditLogs(appAuditLogs);
    return;
  }
  const filtered = appAuditLogs.filter(l => 
    String(l.id).includes(query) ||
    (l.action || '').toLowerCase().includes(query) ||
    (l.details || '').toLowerCase().includes(query) ||
    (l.performed_by || '').toLowerCase().includes(query) ||
    (l.timestamp || '').toLowerCase().includes(query)
  );
  renderAuditLogs(filtered);
}

async function logAuditEvent(action, details, performed_by = 'System Admin') {
  try {
    await fetch(`${API_BASE}/audit-logs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, details, performed_by })
    });
  } catch (e) {
    // silent catch for audit log ping
  }
}


// PAYSLIP GENERATOR & EXPORTER
function openPayslipModalAll() {
  if (!appState.currentPayroll || appState.currentPayroll.length === 0) {
    alert('No payroll summary generated for selected month. Please select a valid month first.');
    return;
  }
  renderPayslips(appState.currentPayroll);
  document.getElementById('payslip-modal').classList.add('active');
}

function openPayslipModalSingle(empId) {
  if (!appState.currentPayroll || appState.currentPayroll.length === 0) {
    alert('No payroll calculated.');
    return;
  }
  const singleP = appState.currentPayroll.filter(p => String(p.emp_id) === String(empId));
  if (singleP.length === 0) {
    alert('Employee payroll record not found.');
    return;
  }
  renderPayslips(singleP);
  document.getElementById('payslip-modal').classList.add('active');
}

function closePayslipModal() {
  document.getElementById('payslip-modal').classList.remove('active');
}

function renderPayslips(payrollList) {
  const container = document.getElementById('payslips-printable-area');
  if (!container) return;

  container.innerHTML = '';
  const monthStr = document.getElementById('payroll-month-picker').value || new Date().toISOString().slice(0, 7);

  payrollList.forEach(p => {
    const card = document.createElement('div');
    card.className = 'payslip-card';
    card.innerHTML = `
      <div class="payslip-header">
        <div>
          <div class="payslip-company" style="display:flex; align-items:center; gap:10px;">
            <img src="logo.svg" alt="NEFLOGIX Logo" style="height:34px; width:auto;">
            <span style="font-weight:900; letter-spacing:1.5px; color:#0f172a;">NEFLOGIX</span>
          </div>
          <div style="font-size:12px; color:#64748b; margin-top:2px;">Smart Biometric & Multi-Shift Payroll Management</div>
        </div>
        <div style="text-align:right;">
          <div class="payslip-title">Official Salary Slip</div>
          <div style="font-size:13px; font-weight:700; color:#0f172a;">Month: ${p.month || monthStr}</div>
        </div>
      </div>

      <div class="payslip-info-grid">
        <div class="payslip-info-item"><span class="payslip-info-label">Employee ID:</span><span class="payslip-info-val">${p.emp_id}</span></div>
        <div class="payslip-info-item"><span class="payslip-info-label">Employee Name:</span><span class="payslip-info-val">${p.emp_name}</span></div>
        <div class="payslip-info-item"><span class="payslip-info-label">Department:</span><span class="payslip-info-val">${p.department || 'General'}</span></div>
        <div class="payslip-info-item"><span class="payslip-info-label">Base Salary:</span><span class="payslip-info-val">PKR ${Number(p.base_salary).toLocaleString()}</span></div>
        <div class="payslip-info-item"><span class="payslip-info-label">Daily Wage Rate:</span><span class="payslip-info-val">PKR ${Number(p.daily_rate).toLocaleString()} / day</span></div>
        <div class="payslip-info-item"><span class="payslip-info-label">Annual Free Quota:</span><span class="payslip-info-val">${p.annual_quota} Days / Year</span></div>
      </div>

      <table class="payslip-table">
        <thead>
          <tr>
            <th>Description / Leave Breakdown</th>
            <th style="text-align:right;">Days / Factor</th>
            <th style="text-align:right;">Amount (PKR)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Basic Monthly Base Salary</strong></td>
            <td style="text-align:right;">30 Days</td>
            <td style="text-align:right;">PKR ${Number(p.base_salary).toLocaleString()}</td>
          </tr>
          <tr>
            <td>Total YTD Leaves & Biometric Shift Cuts Used</td>
            <td style="text-align:right;">${p.total_ytd_used} Days</td>
            <td style="text-align:right;">--</td>
          </tr>
          <tr>
            <td>Remaining Free Quota Available</td>
            <td style="text-align:right;">${p.quota_remaining} Days</td>
            <td style="text-align:right;">--</td>
          </tr>
          <tr>
            <td><strong>Chargeable Excess Deductions (This Month)</strong></td>
            <td style="text-align:right; font-weight:700; color:${p.chargeable_days > 0 ? '#ef4444' : '#10b981'};">${p.chargeable_days} Cut Days</td>
            <td style="text-align:right; font-weight:700; color:${p.chargeable_days > 0 ? '#ef4444' : '#10b981'};">${p.chargeable_days > 0 ? '- PKR ' + Number(p.deduction_amount).toLocaleString() : 'PKR 0'}</td>
          </tr>
        </tbody>
      </table>

      <div class="payslip-summary-box">
        <div class="payslip-total-label">NET PAYABLE SALARY:</div>
        <div class="payslip-total-val">PKR ${Number(p.net_salary).toLocaleString()}</div>
      </div>

      <div class="payslip-signatures">
        <div class="payslip-sig-line">Prepared By (HR Dept)</div>
        <div class="payslip-sig-line">Approved By (Finance)</div>
        <div class="payslip-sig-line">Employee Signature</div>
      </div>
    `;
    container.appendChild(card);
  });
}

function printPayslips() {
  window.print();
}
