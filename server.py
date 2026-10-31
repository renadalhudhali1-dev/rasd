"""RASD backend (Python stdlib only). Real-time push via Server-Sent Events (SSE).
Run:  python backend/server.py   ->  http://localhost:8000"""
import json, os, queue, random, threading, time
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from models import StudentHealthReading
from sensors import (ThermalCameraService, SimulatedThermalAdapter,
                     OpticalSensorService, SimulatedPPGAdapter)
from services import (load_config, AnomalyDetectionService, NotificationService,
                      SCENARIOS, DEMO_SEQUENCE)

CFG = load_config()
DETECTOR, NOTIFY = AnomalyDetectionService(CFG), NotificationService(CFG)
RECORDS, SUBS, LOCK = [], [], threading.Lock()
TOTAL_STUDENTS = 60
FRONT = os.path.join(os.path.dirname(__file__), "..", "frontend")


def broadcast(evt):
    for q in list(SUBS):
        q.put(evt)


def run_pipeline(scn_key, student=None, symptoms_extra=None):
    """Sensors -> Validation -> Anomaly detection -> Nurse alert."""
    scn = SCENARIOS[scn_key]
    # Swap these adapters for real ones (RealThermalAdapter / SerialPPGAdapter) when hardware exists.
    temp, cam = ThermalCameraService(SimulatedThermalAdapter(scn)).capture()
    hr, quality, ppg = OpticalSensorService(SimulatedPPGAdapter(scn)).measure()
    sid = student or f"{random.randint(1, TOTAL_STUDENTS):03d}"
    r = StudentHealthReading(sid, datetime.now().isoformat(timespec="seconds"), temp, hr, quality,
                             list(scn["symptoms"]) + (symptoms_extra or []), cam, ppg)
    r.id = f"R{len(RECORDS) + 1:04d}"
    with LOCK:
        prev = next((x for x in reversed(RECORDS) if x.studentId == sid), None)
        DETECTOR.analyze(r, prev)
        if NOTIFY.is_emergency(r):  # emergency path independent of the detector
            r.emergency, r.status, r.action = True, "NURSE_REVIEW", "طوارئ — تدخل مباشر"
            r.reasons.insert(0, "مسار الطوارئ المباشر")
        NOTIFY.nurse_alert(r)
        RECORDS.append(r)
    broadcast({"type": "reading", "id": r.id})
    return r


def state():
    with LOCK:
        recs = [r.to_dict() for r in RECORDS]
    openc = [r for r in recs if r["status"] != "NORMAL" and r["followUp"] == "مفتوحة"]
    review = [r for r in openc if r["status"] == "NURSE_REVIEW"]
    return {"records": recs, "alerts": NOTIFY.log[-20:],
            "stats": {"total": TOTAL_STUDENTS, "review": len(review),
                      "remeasure": len(openc) - len(review),
                      "urgent": len([r for r in review if r["emergency"] or len(r["reasons"]) >= 2]),
                      "normal": TOTAL_STUDENTS - len(openc)},
            "system": {"thermal": "وضع المحاكاة", "ppg": "وضع المحاكاة", "server": "متصل"},
            "scenarios": {k: v["label"] for k, v in SCENARIOS.items()}}


def demo_sequence():
    for k in DEMO_SEQUENCE:
        run_pipeline(k, student="024")
        time.sleep(2.5)


def case_action(rid, body):
    with LOCK:
        r = next((x for x in RECORDS if x.id == rid), None)
    if not r:
        return {"error": "not found"}
    a = body.get("action")
    if a == "confirm":
        r.followUp = "تم تأكيد التقييم"
    elif a == "note":
        r.notes.append(body.get("note", ""))
    elif a == "escalate":
        r.followUp = "تم التصعيد"
        NOTIFY.parent_notification(r)
    elif a == "remeasure":
        r.followUp = "أُعيد القياس"
        run_pipeline("normal", student=r.studentId)  # simulated outcome of the new measurement
    broadcast({"type": "update"})
    return {"ok": True}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path == "/api/state": return self._json(state())
        if self.path == "/api/config": return self._json(CFG)
        if self.path == "/api/stream":
            q = queue.Queue(); SUBS.append(q)
            self.send_response(200); self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache"); self.end_headers()
            try:
                while True:
                    try: evt = q.get(timeout=15); self.wfile.write(f"data: {json.dumps(evt)}\n\n".encode())
                    except queue.Empty: self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except Exception: pass
            finally: SUBS.remove(q)
            return
        p = os.path.join(FRONT, "index.html")
        b = open(p, "rb").read()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/simulate":
            if body.get("demo"):
                threading.Thread(target=demo_sequence, daemon=True).start(); return self._json({"ok": True})
            return self._json(run_pipeline(body.get("scenario", "normal")).to_dict())
        if self.path == "/api/emergency":  # direct emergency path (no AI wait)
            return self._json(run_pipeline("normal", body.get("studentId"), ["فقدان وعي"]).to_dict())
        if self.path.startswith("/api/cases/"):
            return self._json(case_action(self.path.split("/")[3], body))
        self._json({"error": "unknown"}, 404)


if __name__ == "__main__":
    print("RASD running on http://localhost:8000  (SIMULATION MODE)")
    ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
