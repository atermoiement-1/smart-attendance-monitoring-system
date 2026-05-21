from __future__ import annotations

from collections import defaultdict

import cv2
import numpy as np


class FaceEngine:
    def __init__(self, threshold: float = 0.22) -> None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.detector = cv2.CascadeClassifier(cascade_path)
        self.threshold = threshold

    def detect_faces(self, image: np.ndarray) -> list[tuple[int, int, int, int]]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80),
        )
        return sorted([tuple(map(int, face)) for face in faces], key=lambda f: f[2] * f[3], reverse=True)

    def embedding(self, image: np.ndarray, face: tuple[int, int, int, int]) -> np.ndarray:
        x, y, w, h = face
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        crop = gray[y : y + h, x : x + w]
        crop = cv2.resize(crop, (80, 80), interpolation=cv2.INTER_AREA)
        crop = cv2.equalizeHist(crop)
        vector = crop.astype(np.float32).flatten() / 255.0
        vector = vector - np.mean(vector)
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def match(self, vector: np.ndarray, known: list[dict]) -> dict | None:
        if not known:
            return None

        grouped: dict[int, list[tuple[float, dict]]] = defaultdict(list)
        for item in known:
            score = float(1 - np.dot(vector, item["vector"]))
            grouped[int(item["student_id"])].append((score, item))

        best_match = None
        best_score = float("inf")
        for samples in grouped.values():
            scores = sorted(score for score, _ in samples)
            score = float(np.mean(scores[: min(3, len(scores))]))
            if score < best_score:
                best_score = score
                best_match = samples[0][1]

        if best_match and best_score <= self.threshold:
            return {
                "student_id": best_match["student_id"],
                "name": best_match["name"],
                "roll_no": best_match["roll_no"],
                "class_name": best_match["class_name"],
                "confidence": round(max(0.0, 1 - best_score), 3),
            }
        return None
