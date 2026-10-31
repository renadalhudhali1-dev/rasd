# رَصد | RASD — Prototype

نظام مساند للممرضة المدرسية لرصد القراءات الصحية غير الطبيعية. **لا يشخّص، ولا يتنبأ بالإغماء، ولا يستبدل الممرضة أو الطبيب.**

## التشغيل
المتطلبات: Python 3.9+ فقط (بدون مكتبات خارجية).
```
python backend/server.py
```


## البنية
- `backend/models.py` — StudentHealthReading (رقم الطالب فقط، بلا أسماء)
- `backend/sensors.py` — ThermalCameraService + OpticalSensorService (Adapters) ومعالجة إشارة PPG
- `backend/services.py` — Validation, AnomalyDetectionService (Rule-based), NotificationService, سيناريوهات المحاكاة
- `backend/server.py` — API + تحديث لحظي عبر SSE
- `frontend/index.html` — لوحة الممرضة (RTL)
- `config/thresholds.json` — العتبات (قيم تجريبية وليست حدودًا طبية)

## ربط الكاميرا الحرارية
نفّذ `ThermalCameraAdapter.read_skin_temperature()` في `RealThermalAdapter` (USB / RTSP / HTTP / SDK) ثم بدّل `SimulatedThermalAdapter` في `run_pipeline` (server.py). الكاميرا العادية لا تقيس الحرارة.

## ربط حساس PPG
نفّذ `PPGSensorAdapter.read_samples()` في `SerialPPGAdapter` (Serial / BLE / USB) وأعد قائمة عينات خام؛ معالجة الإشارة (كشف القمم → النبض + جودة الإشارة) جاهزة في `process_ppg`.

## API
`GET /api/state` · `GET /api/config` · `GET /api/stream` (SSE) · `POST /api/simulate` `{scenario | demo:true}` · `POST /api/emergency` · `POST /api/cases/<id>/` `{action: confirm|remeasure|note|escalate}`

## المنطق
Sensor → Validation (اكتمال/جودة/تعارض) → Feature Extraction → Fusion → Rule-based Detection → Nurse Alert → تقييم الممرضة → إشعار ولي الأمر (بعد التصعيد فقط). مسار الطوارئ يتجاوز التحليل. يمكن استبدال `AnomalyDetectionService.analyze` بنموذج ML بنفس المدخلات/المخرجات.

## حقيقي مقابل محاكاة
- حقيقي: خط المعالجة، معالجة إشارة PPG (على موجة مولَّدة)، التحقق، الدمج، التنبيهات، الإجراءات، التحديث اللحظي.
- محاكاة: قراءات الكاميرا الحرارية، موجة PPG، الأعراض، إشعار ولي الأمر، ونتيجة «إعادة القياس». لا توجد قياسات طبية حقيقية.
- الخصوصية: Student ID فقط، لا صور، بيانات تجريبية. الاستخدام الفعلي يحتاج موافقات وضوابط حماية بيانات.
