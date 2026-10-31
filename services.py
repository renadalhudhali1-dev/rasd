"""Validation -> Feature extraction -> Fusion -> Rule-based anomaly detection -> Alerts.
Thresholds come from config/thresholds.json (PROTOTYPE values, not medical limits).
The system does NOT diagnose and does NOT predict fainting."""
import json
import os

from models import StudentHealthReading

CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "thresholds.json")


def load_config():
    with open(CFG_PATH, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ Validation
def validate(r: StudentHealthReading, c: dict):
    """Returns (is_valid, reason). Invalid readings never raise a health alert."""
    if r.skinTemperature is None or r.heartRate is None:
        return False, "بيانات ناقصة"
    if r.signalQuality < c["min_signal_quality"]:
        return False, "جودة الإشارة ضعيفة"
    lo, hi = c["temp_valid_range"]
    hlo, hhi = c["hr_valid_range"]
    if not (lo <= r.skinTemperature <= hi and hlo <= r.heartRate <= hhi):
        return False, "قراءة متعارضة / خارج النطاق الفيزيائي"
    return True, ""


# ------------------------------------------------------------------ Anomaly detection
class AnomalyDetectionService:
    """Rule-based. Replace `analyze` with an ML model later; keep the same
    input (reading + previous reading) and output (status, reasons, action)."""

    def __init__(self, cfg):
        self.c = cfg

    def extract_features(self, r, prev):
        c = self.c
        return {
            "temp_elevated": r.skinTemperature >= c["temp_elevated"],
            "hr_abnormal": not (c["hr_low"] <= r.heartRate <= c["hr_high"]),
            "hr_jump": bool(prev and prev.heartRate and abs(r.heartRate - prev.heartRate) >= c["hr_delta"]),
            "symptoms": bool(r.reportedSymptoms),
        }

    def analyze(self, r, prev=None):
        ok, why = validate(r, self.c)
        if not ok:
            r.validationStatus = "INVALID"
            r.status, r.confidence = "REMEASURE", 0.0
            r.reasons = ["القراءة غير واضحة — يُنصح بإعادة القياس", why]
            r.action = "إعادة القياس"
            return r
        r.validationStatus = "VALID"
        f = self.extract_features(r, prev)               # feature extraction
        names = {"temp_elevated": "حرارة سطح الجلد مرتفعة نسبيًا", "hr_abnormal": "معدل نبض غير معتاد",
                 "hr_jump": "تغيّر كبير في النبض عن القراءة السابقة", "symptoms": "أعراض مبلغ عنها"}
        flags = [k for k, v in f.items() if v]
        r.reasons = [names[k] for k in flags]
        r.confidence = r.signalQuality    # confidence = data quality (not a medical probability)
        # Fusion: several independent indicators + good data => nurse review
        if len(flags) >= 2:
            r.status, r.action = "NURSE_REVIEW", "مراجعة الممرضة"
        elif len(flags) == 1:
            if flags[0] in ("temp_elevated", "hr_jump"):   # single thermal/jump indicator: confirm first
                r.status, r.action = "REMEASURE", "إعادة القياس"
            else:
                r.status, r.action = "NURSE_REVIEW", "مراجعة الممرضة"
        else:
            r.status, r.action, r.reasons = "NORMAL", "لا إجراء", ["ضمن النطاق التجريبي"]
        return r


# ------------------------------------------------------------------ Notifications
class NotificationService:
    def __init__(self, cfg):
        self.c = cfg
        self.log = []

    def is_emergency(self, r):
        """Direct emergency path: does NOT wait for the anomaly model."""
        return any(s in self.c["emergency_symptoms"] for s in r.reportedSymptoms)

    def nurse_alert(self, r):
        if r.status == "NORMAL":
            return None
        a = {"studentId": r.studentId, "message": f"الحالة {r.studentId} تحتاج "
             + ("مراجعة الممرضة" if r.status == "NURSE_REVIEW" else "إعادة القياس"),
             "time": r.timestamp, "action": r.action, "emergency": r.emergency}
        self.log.append(a)
        return a

    def parent_notification(self, r):  # only after nurse decision; simulated (no real SMS)
        n = {"studentId": r.studentId, "message": "إشعار ولي الأمر (محاكاة) بعد تصعيد الممرضة", "time": r.timestamp}
        self.log.append(n)
        return n


# ------------------------------------------------------------------ Simulation scenarios
SCENARIOS = {
    "normal":   {"label": "حالة طبيعية", "temp": 34.6, "hr": 82, "noise": 0.08, "symptoms": []},
    "unclear":  {"label": "قراءة غير واضحة", "temp": 34.8, "hr": 85, "noise": 1.6, "symptoms": []},
    "temp":     {"label": "حرارة مرتفعة نسبيًا", "temp": 36.4, "hr": 84, "noise": 0.08, "symptoms": []},
    "hr":       {"label": "نبض غير معتاد", "temp": 34.7, "hr": 128, "noise": 0.08, "symptoms": []},
    "multi":    {"label": "عدة مؤشرات", "temp": 36.6, "hr": 122, "noise": 0.08, "symptoms": ["دوخة", "غثيان"]},
}
DEMO_SEQUENCE = ["normal", "unclear", "temp", "hr", "multi"]
