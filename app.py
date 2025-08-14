from flask import Flask, render_template, request, redirect, url_for, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "secret_key_123"  # Change this in production

DB_NAME = "database.db"

# ---------------- DATABASE INIT ----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password_hash TEXT)''')

    # Participants table
    c.execute('''CREATE TABLE IF NOT EXISTS participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    district TEXT,
                    contact TEXT)''')

    # Events table
    c.execute('''CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    frequency_per_month INTEGER)''')

    # Attendance table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    participant_id INTEGER,
                    event_id INTEGER,
                    date TEXT,
                    FOREIGN KEY(participant_id) REFERENCES participants(id),
                    FOREIGN KEY(event_id) REFERENCES events(id))''')

    conn.commit()

    # Default admin
    c.execute("SELECT * FROM users WHERE username=?", ("admin",))
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
        c.execute("SELECT * FROM events WHERE name=?", (e[0],))
        if not c.fetchone():
            c.execute("INSERT INTO events (name, frequency_per_month) VALUES (?, ?)", e)

    conn.commit()
    conn.close()

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
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
    return render_template("dashboard.html")

# ---------------- PARTICIPANTS ----------------
@app.route("/add_participant", methods=["GET", "POST"])
def add_participant():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        district = request.form["district"]
        contact = request.form["contact"]

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO participants (name, district, contact) VALUES (?, ?, ?)",
                  (name, district, contact))
        conn.commit()
        conn.close()
        return redirect(url_for("view_participants"))

    return render_template("add_participant.html")

@app.route("/view_participants")
def view_participants():
    if "user" not in session:
        return redirect(url_for("login"))

    district_filter = request.args.get("district", "")

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if district_filter:
        c.execute("SELECT * FROM participants WHERE district=?", (district_filter,))
    else:
        c.execute("SELECT * FROM participants")
    participants = c.fetchall()
    conn.close()

    return render_template("view_participants.html", participants=participants)

# ---------------- ATTENDANCE ----------------
@app.route("/mark_attendance", methods=["GET", "POST"])
def mark_attendance():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM participants")
    participants = c.fetchall()
    c.execute("SELECT * FROM events")
    events = c.fetchall()

    if request.method == "POST":
        participant_id = request.form["participant_id"]
        event_id = request.form["event_id"]
        date = request.form["date"]

        c.execute("INSERT INTO attendance (participant_id, event_id, date) VALUES (?, ?, ?)",
                  (participant_id, event_id, date))
        conn.commit()
        conn.close()
        return redirect(url_for("view_attendance"))

    conn.close()
    return render_template("mark_attendance.html", participants=participants, events=events)

@app.route("/view_attendance")
def view_attendance():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("""
        SELECT attendance.id, participants.name, participants.district, events.name as event_name, attendance.date
        FROM attendance
        JOIN participants ON attendance.participant_id = participants.id
        JOIN events ON attendance.event_id = events.id
    """, conn)
    conn.close()

    return render_template("view_attendance.html", tables=df.to_dict(orient="records"))

@app.route("/export_attendance")
def export_attendance():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("""
        SELECT participants.name, participants.district, events.name as event_name, attendance.date
        FROM attendance
        JOIN participants ON attendance.participant_id = participants.id
        JOIN events ON attendance.event_id = events.id
    """, conn)
    conn.close()

    filename = "attendance_report.xlsx"
    df.to_excel(filename, index=False)
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    if not os.path.exists(DB_NAME):
        init_db()
    app.run(debug=True)
