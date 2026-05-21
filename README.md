# Smart Attendance Monitoring System

A browser-based face recognition attendance system for schools and colleges.

## Features

- Auto face detection and recognition from webcam frames
- Student enrollment with multiple face samples
- Real-time attendance dashboard
- Excel and PDF attendance export
- Email and SMS absentee alerts
- SQLite database storage

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`.

## How to Use

1. Add a student with roll number, class, email, and phone.
2. Select the student and capture 5-10 clear face samples.
3. Click Start Recognition to mark attendance automatically.
4. Use Export Excel or Export PDF for reports.
5. Use Send Absentee Alerts after configuring `.env`.

## Notes

This project uses OpenCV Haar face detection and a lightweight grayscale face embedding matcher so it runs without GPU or heavy native face-recognition dependencies. For production, use consent-based enrollment, secure storage, access controls, and a stronger face embedding model.
