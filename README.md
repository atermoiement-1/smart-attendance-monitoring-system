# Face Recognition Attendance System

<p align="center">
  <img src="https://img.shields.io/badge/Backend-Flask-0f172a?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Computer%20Vision-OpenCV-2563eb?style=for-the-badge&logo=opencv&logoColor=white" alt="OpenCV" />
  <img src="https://img.shields.io/badge/Database-SQLite-0369a1?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/Reports-Excel%20%7C%20PDF-16a34a?style=for-the-badge" alt="Reports" />
</p>

A browser-based attendance system that uses face detection and recognition to automate student attendance. It includes student enrollment, webcam-based recognition, attendance records, report exports, and absentee alerts.

## Highlights

- Student enrollment with multiple face samples
- Webcam-based face detection and recognition
- Real-time attendance dashboard
- Excel and PDF attendance export
- Email and SMS absentee alerts
- SQLite-backed local data storage
- Lightweight approach that runs without GPU-heavy dependencies

## Tech Stack

| Area | Tools |
| --- | --- |
| Backend | Python, Flask |
| Computer Vision | OpenCV, NumPy |
| Data and Reports | Pandas, openpyxl, ReportLab |
| Database | SQLite |
| Notifications | Email, Twilio SMS |
| Frontend | HTML, CSS, JavaScript |

## Project Structure

```text
smart-attendance-monitoring-system/
|-- app.py
|-- face_engine.py
|-- alerts.py
|-- requirements.txt
|-- templates/
|-- static/
|-- data/
|   |-- samples/
```

## Getting Started

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Usage Flow

1. Add a student with roll number, class, email, and phone number.
2. Capture 5-10 clear face samples for enrollment.
3. Start recognition to mark attendance automatically.
4. Export attendance reports in Excel or PDF.
5. Send absentee alerts after configuring environment variables.

## Interview Talking Points

- How OpenCV Haar detection is used for face localization
- Why multiple enrollment samples improve recognition reliability
- How attendance data is stored and exported
- How absentee alert workflows can support school/college administration
- Production considerations: consent, privacy, secure storage, access control, and stronger embeddings
