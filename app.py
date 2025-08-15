from flask import Flask, render_template, request, redirect, url_for, session, send_file, after_this_request
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "secret_key_123"  # Change this in production

DB_NAME = "database.db"

# -------------- DB UTIL --------------
def get_conn():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# ---------------- DATABASE INIT ----------------
def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password_hash TEXT
                )''')

    # Participants table
    c.execute('''CREATE TABLE IF NOT EXISTS participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    district TEXT,
                    contact TEXT
                )''')

    # Events table
    c.execute('''CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    frequency_per_month INTEGER DEFAULT 1
                )''')

    # Attendance table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    participant_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    FOREIGN KEY(participant_id) REFERENCES participants(id) ON DELETE CASCADE,
                    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
                )''')

    conn.commit()

    # Default admin
    c.execute("SELECT 1 FROM users WHERE username=?", ("admin",))
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                  ("admin", generate_password_hash("admin123")))

    # Default events
    events_list = [
        ("Event A", 1),
        ("Event B", 3),
        ("Event C", 2),
        ("Event D", 1),
        ("Event E", 4),
        ("Event F", 1)
    ]
    for e in events_list:
        c.execute("SELECT 1 FROM events WHERE name=?", (e[0],))
        if not c.fetchone():
            c.execute("INSERT INTO events (name, frequency_per_month) VALUES (?, ?)", e)

    conn.commit()
    conn.close()

# Always init tables (safe with IF NOT EXISTS)
init_db()

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id, username, password_hash FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM participants")
    participants_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM events")
    events_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM attendance")
    attendance_count = c.fetchone()[0]
    conn.close()

    return render_template("dashboard.html",
                           participants_count=participants_count,
                           events_count=events_count,
                           attendance_count=attendance_count)

# ---------------- PARTICIPANTS ----------------
@app.route("/add_participant", methods=["GET", "POST"])
def add_participant():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        district = request.form.get("district", "").strip()
        contact = request.form.get("contact", "").strip()

        if not name:
            return render_template("add_participant.html", error="Name is required")

        try:
            conn = get_conn()
            c = conn.cursor()
            c.execute("INSERT INTO participants (name, district, contact) VALUES (?, ?, ?)",
                      (name, district, contact))
            conn.commit()
        except Exception as e:
            return render_template("add_participant.html", error=f"Error: {e}")
        finally:
            conn.close()
        return redirect(url_for("view_participants"))

    return render_template("add_participant.html")

@app.route("/view_participants")
def view_participants():
    if "user" not in session:
        return redirect(url_for("login"))

    district_filter = request.args.get("district", "").strip()

    conn = get_conn()
    c = conn.cursor()
    if district_filter:
        c.execute("SELECT id, name, district, contact FROM participants WHERE district=?", (district_filter,))
    else:
        c.execute("SELECT id, name, district, contact FROM participants")
    participants = c.fetchall()
    conn.close()

    return render_template("view_participants.html", participants=participants, district_filter=district_filter)

# ---------------- ATTENDANCE ----------------
@app.route("/mark_attendance", methods=["GET", "POST"])
def mark_attendance():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name FROM participants ORDER BY name")
    participants = c.fetchall()
    c.execute("SELECT id, name FROM events ORDER BY name")
    events = c.fetchall()

    if request.method == "POST":
        participant_id = request.form.get("participant_id")
        event_id = request.form.get("event_id")
        date = request.form.get("date") or datetime.today().strftime("%Y-%m-%d")

        try:
            c.execute("INSERT INTO attendance (participant_id, event_id, date) VALUES (?, ?, ?)",
                      (participant_id, event_id, date))
            conn.commit()
        except Exception as e:
            conn.close()
            return render_template("mark_attendance.html", participants=participants, events=events, error=f"Error: {e}")
        conn.close()
        return redirect(url_for("view_attendance"))

    conn.close()
    return render_template("mark_attendance.html", participants=participants, events=events)

@app.route("/view_attendance")
def view_attendance():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT attendance.id, participants.name, participants.district, events.name as event_name, attendance.date
        FROM attendance
        JOIN participants ON attendance.participant_id = participants.id
        JOIN events ON attendance.event_id = events.id
        ORDER BY date DESC
    """, conn)
    conn.close()

    return render_template("view_attendance.html", rows=df.to_dict(orient="records"))

@app.route("/export_attendance")
def export_attendance():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT participants.name, participants.district, events.name as event_name, attendance.date
        FROM attendance
        JOIN participants ON attendance.participant_id = participants.id
        JOIN events ON attendance.event_id = events.id
        ORDER BY date DESC
    """, conn)
    conn.close()

    filename = "attendance_report.xlsx"
    df.to_excel(filename, index=False)

    @after_this_request
    def remove_file(response):
        try:
            os.remove(filename)
        except Exception as e:
            print(f"Error deleting file: {e}")
        return response

    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
