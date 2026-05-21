from __future__ import annotations

import base64
import io
import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph

from alerts import send_absent_alert
from face_engine import FaceEngine


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"
DB_PATH = DATA_DIR / "attendance.db"

load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("APP_SECRET_KEY", "dev-smart-attendance")

engine = FaceEngine(threshold=float(os.getenv("FACE_MATCH_THRESHOLD", "0.22")))


def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                roll_no TEXT NOT NULL UNIQUE,
                class_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS face_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                vector TEXT NOT NULL,
                image_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                attendance_date TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Present',
                UNIQUE(student_id, attendance_date),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );
            """
        )


def row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def decode_image(data_url: str) -> np.ndarray:
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    raw = base64.b64decode(data_url)
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image")
    return image


def load_known_faces(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        """
        SELECT fs.student_id, fs.vector, s.name, s.roll_no, s.class_name
        FROM face_samples fs
        JOIN students s ON s.id = fs.student_id
        """
    ).fetchall()
    known = []
    for row in rows:
        known.append(
            {
                "student_id": row["student_id"],
                "vector": np.array(json.loads(row["vector"]), dtype=np.float32),
                "name": row["name"],
                "roll_no": row["roll_no"],
                "class_name": row["class_name"],
            }
        )
    return known


def mark_attendance(db: sqlite3.Connection, student_id: int) -> None:
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")
    db.execute(
        """
        INSERT INTO attendance (student_id, attendance_date, first_seen, last_seen, status)
        VALUES (?, ?, ?, ?, 'Present')
        ON CONFLICT(student_id, attendance_date)
        DO UPDATE SET last_seen = excluded.last_seen
        """,
        (student_id, today, now, now),
    )
    db.commit()


def attendance_rows(db: sqlite3.Connection, target_date: str) -> list[dict]:
    rows = db.execute(
        """
        SELECT
            s.id,
            s.name,
            s.roll_no,
            s.class_name,
            s.email,
            s.phone,
            COALESCE(a.status, 'Absent') AS status,
            a.first_seen,
            a.last_seen
        FROM students s
        LEFT JOIN attendance a
            ON a.student_id = s.id AND a.attendance_date = ?
        ORDER BY s.class_name, s.roll_no
        """,
        (target_date,),
    ).fetchall()
    return [row_to_dict(row) for row in rows]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/students", methods=["GET", "POST"])
def students():
    with get_db() as db:
        if request.method == "POST":
            payload = request.get_json(force=True)
            required = ["name", "roll_no", "class_name"]
            if any(not payload.get(field) for field in required):
                return jsonify({"error": "Name, roll number, and class are required."}), 400
            try:
                cursor = db.execute(
                    """
                    INSERT INTO students (name, roll_no, class_name, email, phone, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["name"].strip(),
                        payload["roll_no"].strip(),
                        payload["class_name"].strip(),
                        payload.get("email", "").strip(),
                        payload.get("phone", "").strip(),
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                db.commit()
            except sqlite3.IntegrityError:
                return jsonify({"error": "A student with this roll number already exists."}), 409
            return jsonify({"id": cursor.lastrowid}), 201

        rows = db.execute(
            """
            SELECT s.*, COUNT(fs.id) AS sample_count
            FROM students s
            LEFT JOIN face_samples fs ON fs.student_id = s.id
            GROUP BY s.id
            ORDER BY s.created_at DESC
            """
        ).fetchall()
        return jsonify([row_to_dict(row) for row in rows])


@app.route("/api/enroll-frame", methods=["POST"])
def enroll_frame():
    payload = request.get_json(force=True)
    student_id = int(payload.get("student_id", 0))
    if not student_id:
        return jsonify({"error": "Select a student before enrolling face samples."}), 400

    try:
        image = decode_image(payload["image"])
        faces = engine.detect_faces(image)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    if len(faces) != 1:
        return jsonify({"error": "Keep exactly one face in the camera frame while enrolling."}), 422

    face = faces[0]
    vector = engine.embedding(image, face)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    student_dir = SAMPLES_DIR / str(student_id)
    student_dir.mkdir(parents=True, exist_ok=True)
    image_path = student_dir / f"{timestamp}.jpg"
    x, y, w, h = face
    cv2.imwrite(str(image_path), image[y : y + h, x : x + w])

    with get_db() as db:
        if not db.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone():
            return jsonify({"error": "Student not found."}), 404
        db.execute(
            """
            INSERT INTO face_samples (student_id, vector, image_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                student_id,
                json.dumps(vector.tolist()),
                str(image_path.relative_to(BASE_DIR)),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        db.commit()
        count = db.execute(
            "SELECT COUNT(*) AS total FROM face_samples WHERE student_id = ?", (student_id,)
        ).fetchone()["total"]

    return jsonify({"message": "Face sample saved.", "sample_count": count})


@app.route("/api/recognize", methods=["POST"])
def recognize():
    payload = request.get_json(force=True)
    try:
        image = decode_image(payload["image"])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    with get_db() as db:
        known = load_known_faces(db)
        faces = engine.detect_faces(image)
        detections = []
        for face in faces:
            vector = engine.embedding(image, face)
            match = engine.match(vector, known)
            box = {"x": int(face[0]), "y": int(face[1]), "w": int(face[2]), "h": int(face[3])}
            if match:
                mark_attendance(db, int(match["student_id"]))
                detections.append({**match, "box": box, "status": "Present"})
            else:
                detections.append({"name": "Unknown", "box": box, "status": "Unknown"})

    return jsonify({"detections": detections})


@app.route("/api/dashboard")
def dashboard():
    target_date = request.args.get("date", date.today().isoformat())
    with get_db() as db:
        students_total = db.execute("SELECT COUNT(*) AS total FROM students").fetchone()["total"]
        present_total = db.execute(
            "SELECT COUNT(*) AS total FROM attendance WHERE attendance_date = ?",
            (target_date,),
        ).fetchone()["total"]
        recent = db.execute(
            """
            SELECT s.name, s.roll_no, s.class_name, a.last_seen
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            WHERE a.attendance_date = ?
            ORDER BY a.last_seen DESC
            LIMIT 8
            """,
            (target_date,),
        ).fetchall()
    return jsonify(
        {
            "date": target_date,
            "students": students_total,
            "present": present_total,
            "absent": max(students_total - present_total, 0),
            "recent": [row_to_dict(row) for row in recent],
        }
    )


@app.route("/api/attendance")
def attendance():
    target_date = request.args.get("date", date.today().isoformat())
    with get_db() as db:
        rows = attendance_rows(db, target_date)
    return jsonify(rows)


@app.route("/api/alerts/absent", methods=["POST"])
def absent_alerts():
    target_date = request.get_json(silent=True) or {}
    target_date = target_date.get("date", date.today().isoformat())
    sent = []
    skipped = []
    with get_db() as db:
        for row in attendance_rows(db, target_date):
            if row["status"] != "Absent":
                continue
            result = send_absent_alert(row, target_date)
            (sent if result["sent"] else skipped).append({**row, "reason": result["reason"]})
    return jsonify({"sent": sent, "skipped": skipped})


@app.route("/export/excel")
def export_excel():
    target_date = request.args.get("date", date.today().isoformat())
    with get_db() as db:
        rows = attendance_rows(db, target_date)
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"attendance_{target_date}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/export/pdf")
def export_pdf():
    target_date = request.args.get("date", date.today().isoformat())
    with get_db() as db:
        rows = attendance_rows(db, target_date)

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"Attendance Report - {target_date}", styles["Title"]), Spacer(1, 14)]
    data = [["Roll No", "Name", "Class", "Status", "First Seen", "Last Seen"]]
    for row in rows:
        data.append(
            [
                row["roll_no"],
                row["name"],
                row["class_name"],
                row["status"],
                row["first_seen"] or "-",
                row["last_seen"] or "-",
            ]
        )
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4d5a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef6f3")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"attendance_{target_date}.pdf")


@app.errorhandler(404)
def not_found(_):
    return redirect(url_for("index"))


init_db()


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
