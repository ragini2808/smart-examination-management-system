import { useCallback, useEffect, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

const MENU = [
  { id: "overview", icon: "▦", label: "Dashboard" },
  { id: "exams", icon: "▤", label: "Examinations" },
  { id: "students", icon: "♙", label: "Students" },
  { id: "rooms", icon: "▥", label: "Examination Rooms" },
  { id: "slots", icon: "◷", label: "Time Slots" },
  { id: "timetable", icon: "▦", label: "Timetable" },
];

function getArray(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.exams)) return data.exams;
  if (Array.isArray(data?.students)) return data.students;
  if (Array.isArray(data?.rooms)) return data.rooms;
  if (Array.isArray(data?.time_slots)) return data.time_slots;
  if (Array.isArray(data?.assignments)) return data.assignments;
  return [];
}

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(`${value}`.slice(0, 10) + "T00:00:00");

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
}

function getErrorMessage(data, fallback) {
  if (typeof data?.detail === "string") return data.detail;
  if (data?.detail?.message) return data.detail.message;
  if (data?.message) return data.message;
  return fallback;
}

function App() {
  const [token, setToken] = useState(
    () => localStorage.getItem("smart_exam_token") || ""
  );

  const [loginForm, setLoginForm] = useState({
    email: "",
    password: "",
  });

  const [activePage, setActivePage] = useState("overview");
  const [exams, setExams] = useState([]);
  const [students, setStudents] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [slots, setSlots] = useState([]);
  const [schedule, setSchedule] = useState([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");

  const [scheduleRules, setScheduleRules] = useState({
    max_regular_exams_per_day: 2,
    max_ese_exams_per_day: 1,
    ese_gap_days: 1,
  });

  const [showExamForm, setShowExamForm] = useState(false);
  const [examForm, setExamForm] = useState({
    exam_id: "",
    subject: "",
    duration_minutes: 180,
    enrolled_student_ids: "",
  });

  const request = useCallback(
    async (path, options = {}) => {
      const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      };

      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      const response = await fetch(`${API_URL}${path}`, {
        ...options,
        headers,
      });

      const text = await response.text();
      let data = {};

      try {
        data = text ? JSON.parse(text) : {};
      } catch {
        data = { message: text };
      }

      if (response.status === 401) {
        localStorage.removeItem("smart_exam_token");
        setToken("");
        throw new Error("Session expired. Please log in again.");
      }

      if (!response.ok) {
        throw new Error(
          getErrorMessage(
            data,
            `Request failed with status ${response.status}`
          )
        );
      }

      return data;
    },
    [token]
  );

  const loadData = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError("");

    const endpoints = [
      ["/admin/exams", setExams],
      ["/admin/students", setStudents],
      ["/admin/rooms", setRooms],
      ["/admin/time-slots", setSlots],
      ["/admin/schedule", setSchedule],
    ];

    const results = await Promise.allSettled(
      endpoints.map(([path]) => request(path))
    );

    const failed = [];

    results.forEach((result, index) => {
      const [path, setter] = endpoints[index];

      if (result.status === "fulfilled") {
        const data = result.value;

        if (path === "/admin/schedule") {
          setter(getArray(data));
        } else {
          setter(getArray(data));
        }
      } else {
        failed.push(`${path}: ${result.reason.message}`);
      }
    });

    if (failed.length) {
      setError(
        `Some information could not be loaded. Check the API routes and permissions. ${failed.join(" | ")}`
      );
    }

    setLoading(false);
  }, [request, token]);

  useEffect(() => {
    if (token) loadData();
  }, [token, loadData]);

  async function handleLogin(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);

    try {
      const data = await request("/login", {
        method: "POST",
        body: JSON.stringify(loginForm),
      });

      const accessToken = data.access_token || data.token;

      if (!accessToken) {
        throw new Error("Login succeeded but no access token was returned.");
      }

      localStorage.setItem("smart_exam_token", accessToken);
      setToken(accessToken);
      setNotice("Login successful!");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("smart_exam_token");
    setToken("");
    setExams([]);
    setStudents([]);
    setRooms([]);
    setSlots([]);
    setSchedule([]);
    setActivePage("overview");
    setError("");
    setNotice("You have been logged out.");
  }

  async function generateTimetable() {
    setGenerating(true);
    setError("");
    setNotice("");

    try {
      const data = await request("/admin/schedule/generate", {
        method: "POST",
        body: JSON.stringify(scheduleRules),
      });

      setNotice(
        data.message || "Timetable generated and validated successfully."
      );

      await loadData();
      setActivePage("timetable");
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  async function createExam(event) {
    event.preventDefault();
    setError("");
    setNotice("");

    const studentIds = examForm.enrolled_student_ids
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);

    try {
      const payload = {
        exam_id: examForm.exam_id.trim(),
        subject: examForm.subject.trim(),
        duration_minutes: Number(examForm.duration_minutes),
        enrolled_student_ids: studentIds,
      };

      const data = await request("/admin/exams", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setNotice(data.message || "Examination created successfully.");
      setShowExamForm(false);
      setExamForm({
        exam_id: "",
        subject: "",
        duration_minutes: 180,
        enrolled_student_ids: "",
      });

      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  if (!token) {
    return (
      <div className="login-screen">
        <div className="login-decoration decoration-one" />
        <div className="login-decoration decoration-two" />

        <form className="login-card" onSubmit={handleLogin}>
          <div className="brand-icon login-brand">SE</div>

          <p className="eyebrow">SMART EXAMINATION SYSTEM</p>
          <h1>Welcome back</h1>
          <p className="login-subtitle">
            Sign in to manage examinations and generate timetables.
          </p>

          {error && <div className="alert error-alert">{error}</div>}
          {notice && <div className="alert success-alert">{notice}</div>}

          <label htmlFor="email">Email address</label>
          <input
            id="email"
            type="email"
            placeholder="admin@example.com"
            autoComplete="username"
            value={loginForm.email}
            onChange={(event) =>
              setLoginForm({ ...loginForm, email: event.target.value })
            }
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            placeholder="Enter your password"
            autoComplete="current-password"
            value={loginForm.password}
            onChange={(event) =>
              setLoginForm({ ...loginForm, password: event.target.value })
            }
            required
          />

          <button className="primary-button login-button" disabled={loading}>
            {loading ? "Signing in..." : "Sign in →"}
          </button>

          <p className="login-footer">
            Authorized personnel only · Smart Examination System
          </p>
        </form>
      </div>
    );
  }

  const currentPage = MENU.find((item) => item.id === activePage);

  const filteredExams = exams.filter((exam) =>
    `${exam.subject || ""} ${exam.exam_id || ""}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const filteredStudents = students.filter((student) =>
    `${student.student_id || ""} ${student.department || ""}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">SE</div>
          <div>
            <h2>ExamFlow</h2>
            <span>Management Portal</span>
          </div>
        </div>

        <div className="nav-caption">WORKSPACE</div>

        <nav className="navigation">
          {MENU.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${
                activePage === item.id ? "active" : ""
              }`}
              onClick={() => {
                setActivePage(item.id);
                setSearch("");
                setError("");
                setNotice("");
              }}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
              {activePage === item.id && <span className="active-dot" />}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="system-status">
            <span className="status-dot" />
            <div>
              <strong>Examination System</strong>
              <small>Backend connection status</small>
            </div>
          </div>

          <button className="logout-button" onClick={logout}>
            ↪ &nbsp; Sign out
          </button>

          <div className="sidebar-version">SMART EXAM SYSTEM · v1.0</div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <div className="breadcrumb">Workspace / {currentPage?.label}</div>
            <h1>{currentPage?.label || "Dashboard"}</h1>
          </div>

          <div className="topbar-right">
            <button
              className="icon-button"
              title="Refresh data"
              onClick={loadData}
              disabled={loading}
            >
              ↻
            </button>

            <div className="user-profile">
              <div className="avatar">A</div>
              <div className="user-details">
                <strong>Administrator</strong>
                <span>System Admin</span>
              </div>
            </div>
          </div>
        </header>

        <section className="content">
          {error && (
            <div className="alert error-alert">
              <span>{error}</span>
              <button onClick={() => setError("")}>×</button>
            </div>
          )}

          {notice && (
            <div className="alert success-alert">
              <span>{notice}</span>
              <button onClick={() => setNotice("")}>×</button>
            </div>
          )}

          {loading && (
            <div className="loading-banner">Refreshing examination data...</div>
          )}

          {activePage === "overview" && (
            <>
              <section className="welcome-banner">
                <div>
                  <p className="welcome-label">ADMINISTRATOR OVERVIEW</p>
                  <h2>Welcome to ExamFlow 👋</h2>
                  <p>
                    Manage examinations, coordinate resources, and generate
                    conflict-free timetables from one place.
                  </p>
                  <button
                    className="banner-button"
                    onClick={() => setActivePage("timetable")}
                  >
                    View timetable <span>→</span>
                  </button>
                </div>

                <div className="banner-illustration" aria-hidden="true">
                  <div className="illustration-card card-back">✓</div>
                  <div className="illustration-card card-front">
                    <div className="illustration-check">✓</div>
                    <div className="illustration-line long-line" />
                    <div className="illustration-line" />
                    <div className="illustration-line short-line" />
                  </div>
                  <div className="floating-badge">✦ AI Powered</div>
                </div>
              </section>

              <div className="section-heading">
                <div>
                  <h2>System overview</h2>
                  <p>A quick summary of your examination resources.</p>
                </div>
                <span className="live-badge">
                  <span className="status-dot" /> Live data
                </span>
              </div>

              <section className="stats-grid">
                <StatCard
                  icon="▤"
                  color="purple"
                  label="Total examinations"
                  value={exams.length}
                  description="Registered exams"
                  onClick={() => setActivePage("exams")}
                />

                <StatCard
                  icon="♙"
                  color="blue"
                  label="Total students"
                  value={students.length}
                  description="Registered students"
                  onClick={() => setActivePage("students")}
                />

                <StatCard
                  icon="▥"
                  color="orange"
                  label="Available rooms"
                  value={rooms.length}
                  description="Registered rooms"
                  onClick={() => setActivePage("rooms")}
                />

                <StatCard
                  icon="✓"
                  color="green"
                  label="Scheduled exams"
                  value={schedule.length}
                  description="Saved assignments"
                  onClick={() => setActivePage("timetable")}
                />
              </section>

              <section className="dashboard-grid">
                <div className="panel recent-panel">
                  <div className="panel-header">
                    <div>
                      <h3>Recent examinations</h3>
                      <p>Latest registered examinations</p>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => setActivePage("exams")}
                    >
                      View all →
                    </button>
                  </div>

                  {exams.length === 0 ? (
                    <EmptyState message="No examinations loaded yet." />
                  ) : (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>EXAMINATION</th>
                            <th>DURATION</th>
                            <th>STATUS</th>
                          </tr>
                        </thead>
                        <tbody>
                          {exams.slice(0, 5).map((exam) => (
                            <tr key={exam.exam_id}>
                              <td>
                                <div className="table-primary">
                                  {exam.subject || "Untitled exam"}
                                </div>
                                <div className="table-secondary">
                                  {exam.exam_id}
                                </div>
                              </td>
                              <td>{exam.duration_minutes || "—"} min</td>
                              <td>
                                <span className="badge badge-green">
                                  Registered
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                <div className="panel quick-panel">
                  <div className="panel-header">
                    <div>
                      <h3>Quick actions</h3>
                      <p>Common administrative tasks</p>
                    </div>
                  </div>

                  <QuickAction
                    icon="▤"
                    color="purple"
                    title="Manage examinations"
                    description="Review registered examinations"
                    onClick={() => setActivePage("exams")}
                  />

                  <QuickAction
                    icon="◷"
                    color="blue"
                    title="View timetable"
                    description="Check scheduled exam slots"
                    onClick={() => setActivePage("timetable")}
                  />

                  <QuickAction
                    icon="✦"
                    color="green"
                    title="Generate timetable"
                    description="Run the scheduling engine"
                    onClick={() => setActivePage("timetable")}
                  />
                </div>
              </section>
            </>
          )}

          {activePage === "exams" && (
            <section className="panel page-panel">
              <div className="panel-header">
                <div>
                  <h2>Examinations</h2>
                  <p>Review and register examinations.</p>
                </div>

                <button
                  className="primary-button"
                  onClick={() => setShowExamForm(!showExamForm)}
                >
                  {showExamForm ? "Cancel" : "+ Add examination"}
                </button>
              </div>

              {showExamForm && (
                <form className="exam-form" onSubmit={createExam}>
                  <div className="form-grid">
                    <label>
                      Examination ID
                      <input
                        value={examForm.exam_id}
                        onChange={(e) =>
                          setExamForm({
                            ...examForm,
                            exam_id: e.target.value,
                          })
                        }
                        placeholder="EXAM005"
                        required
                      />
                    </label>

                    <label>
                      Subject
                      <input
                        value={examForm.subject}
                        onChange={(e) =>
                          setExamForm({
                            ...examForm,
                            subject: e.target.value,
                          })
                        }
                        placeholder="Operating Systems"
                        required
                      />
                    </label>

                    <label>
                      Duration (minutes)
                      <input
                        type="number"
                        min="1"
                        value={examForm.duration_minutes}
                        onChange={(e) =>
                          setExamForm({
                            ...examForm,
                            duration_minutes: e.target.value,
                          })
                        }
                        required
                      />
                    </label>

                    <label>
                      Enrolled student IDs
                      <input
                        value={examForm.enrolled_student_ids}
                        onChange={(e) =>
                          setExamForm({
                            ...examForm,
                            enrolled_student_ids: e.target.value,
                          })
                        }
                        placeholder="STU001, STU002"
                      />
                    </label>
                  </div>

                  <p className="form-hint">
                    Enter existing student IDs separated by commas.
                  </p>

                  <button className="primary-button" type="submit">
                    Save examination
                  </button>
                </form>
              )}

              <SearchBox value={search} onChange={setSearch} />

              <DataTable
                headers={["EXAM ID", "SUBJECT", "DURATION", "STUDENTS"]}
                rows={filteredExams.map((exam) => [
                  exam.exam_id,
                  exam.subject,
                  `${exam.duration_minutes || "—"} min`,
                  Array.isArray(exam.enrolled_student_ids)
                    ? exam.enrolled_student_ids.length
                    : "—",
                ])}
                empty="No examinations found."
              />
            </section>
          )}

          {activePage === "students" && (
            <section className="panel page-panel">
              <div className="panel-header">
                <div>
                  <h2>Students</h2>
                  <p>Registered students and their academic details.</p>
                </div>
                <span className="count-pill">{students.length} students</span>
              </div>

              <SearchBox value={search} onChange={setSearch} />

              <DataTable
                headers={["STUDENT ID", "DEPARTMENT", "SEMESTER", "USER ID"]}
                rows={filteredStudents.map((student) => [
                  student.student_id,
                  student.department || "—",
                  student.semester ?? "—",
                  student.user_id ?? "—",
                ])}
                empty="No students found."
              />
            </section>
          )}

          {activePage === "rooms" && (
            <section className="panel page-panel">
              <div className="panel-header">
                <div>
                  <h2>Examination rooms</h2>
                  <p>Room capacity and registered examination venues.</p>
                </div>
                <span className="count-pill">{rooms.length} rooms</span>
              </div>

              <div className="room-grid">
                {rooms.map((room) => (
                  <div className="room-card" key={room.room_id}>
                    <div className="room-icon">▥</div>
                    <div className="room-capacity">
                      {room.capacity} seats
                    </div>
                    <h3>{room.room_name}</h3>
                    <p>Room ID: {room.room_id}</p>
                    <span className="badge badge-green">Registered</span>
                  </div>
                ))}
              </div>

              {rooms.length === 0 && (
                <EmptyState message="No examination rooms loaded." />
              )}
            </section>
          )}

          {activePage === "slots" && (
            <section className="panel page-panel">
              <div className="panel-header">
                <div>
                  <h2>Time slots</h2>
                  <p>Available examination dates and timings.</p>
                </div>
                <span className="count-pill">{slots.length} slots</span>
              </div>

              <DataTable
                headers={["SLOT ID", "DATE", "START TIME", "END TIME"]}
                rows={slots.map((slot) => [
                  slot.slot_id,
                  formatDate(slot.date),
                  slot.start_time,
                  slot.end_time,
                ])}
                empty="No time slots found."
              />
            </section>
          )}

          {activePage === "timetable" && (
            <>
              <section className="welcome-banner timetable-banner">
                <div>
                  <p className="welcome-label">AUTOMATED SCHEDULING</p>
                  <h2>Examination timetable</h2>
                  <p>
                    Generate a timetable using the scheduling engine and
                    review the saved assignments.
                  </p>
                </div>
                <div className="banner-symbol">◷</div>
              </section>

              <section className="panel rules-panel">
                <div className="panel-header">
                  <div>
                    <h2>Scheduling configuration</h2>
                    <p>Choose the scheduling limits for this run.</p>
                  </div>
                  <span className="ai-badge">✦ OR-Tools Solver</span>
                </div>

                <div className="form-grid rules-grid">
                  <label>
                    Maximum regular exams per day
                    <input
                      type="number"
                      min="0"
                      value={scheduleRules.max_regular_exams_per_day}
                      onChange={(e) =>
                        setScheduleRules({
                          ...scheduleRules,
                          max_regular_exams_per_day: Number(e.target.value),
                        })
                      }
                    />
                  </label>

                  <label>
                    Maximum ESE exams per day
                    <input
                      type="number"
                      min="0"
                      value={scheduleRules.max_ese_exams_per_day}
                      onChange={(e) =>
                        setScheduleRules({
                          ...scheduleRules,
                          max_ese_exams_per_day: Number(e.target.value),
                        })
                      }
                    />
                  </label>

                  <label>
                    ESE gap (days)
                    <input
                      type="number"
                      min="0"
                      value={scheduleRules.ese_gap_days}
                      onChange={(e) =>
                        setScheduleRules({
                          ...scheduleRules,
                          ese_gap_days: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                </div>

                <button
                  className="primary-button generate-button"
                  onClick={generateTimetable}
                  disabled={generating || loading}
                >
                  {generating ? "Generating timetable..." : "✦ Generate timetable"}
                </button>
              </section>

              <section className="panel page-panel timetable-results">
                <div className="panel-header">
                  <div>
                    <h2>Generated assignments</h2>
                    <p>
                      {schedule.length} saved examination assignments
                    </p>
                  </div>
                  <button
                    className="secondary-button"
                    onClick={loadData}
                    disabled={loading}
                  >
                    ↻ Refresh
                  </button>
                </div>

                <DataTable
                  headers={[
                    "EXAM ID",
                    "SUBJECT",
                    "DATE",
                    "TIME SLOT",
                    "ROOMS",
                  ]}
                  rows={schedule.map((assignment) => {
                    const exam = exams.find(
                      (item) => item.exam_id === assignment.exam_id
                    );

                    const slot = slots.find(
                      (item) => item.slot_id === assignment.slot_id
                    );

                    const roomNames = (assignment.room_ids || [])
                      .map((roomId) => {
                        const room = rooms.find(
                          (item) => item.room_id === roomId
                        );
                        return room?.room_name || roomId;
                      })
                      .join(", ");

                    return [
                      assignment.exam_id,
                      exam?.subject || "—",
                      formatDate(slot?.date || assignment.date),
                      slot
                        ? `${slot.start_time} – ${slot.end_time}`
                        : assignment.slot_id,
                      roomNames || "—",
                    ];
                  })}
                  empty="No saved timetable assignments. Generate a timetable to get started."
                />
              </section>
            </>
          )}

          <footer className="page-footer">
            <span>© 2026 ExamFlow · Smart Examination Management System</span>
            <span>Built with React + FastAPI</span>
          </footer>
        </section>
      </main>
    </div>
  );
}

function StatCard({ icon, color, label, value, description, onClick }) {
  return (
    <button className="stat-card" onClick={onClick}>
      <div className={`stat-icon ${color}`}>{icon}</div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-description">{description}</div>
      <span className="stat-arrow">↗</span>
    </button>
  );
}

function QuickAction({ icon, color, title, description, onClick }) {
  return (
    <button className="quick-action" onClick={onClick}>
      <span className={`quick-icon ${color}`}>{icon}</span>
      <span className="quick-copy">
        <strong>{title}</strong>
        <small>{description}</small>
      </span>
      <span className="quick-arrow">→</span>
    </button>
  );
}

function SearchBox({ value, onChange }) {
  return (
    <div className="search-box">
      <span>⌕</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Search records..."
      />
    </div>
  );
}

function EmptyState({ message }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">▤</div>
      <p>{message}</p>
    </div>
  );
}

function DataTable({ headers, rows, empty }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((row, index) => (
              <tr key={`${row[0]}-${index}`}>
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex}>
                    {cellIndex === 0 ? (
                      <span className="table-primary">{cell ?? "—"}</span>
                    ) : (
                      cell ?? "—"
                    )}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={headers.length}>
                <EmptyState message={empty} />
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default App;