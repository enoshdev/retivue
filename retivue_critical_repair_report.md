# RETIVUE Clinical CADe — Critical Repair & Workflow Verification Report

**Date:** 2026-11-17  
**Platform Version:** RETIVUE Clinical CADe v1.0.0 (Phase 1 & Phase 2 Integrated)  
**System Status:** **Live & Healthy (Port 5433 PostgreSQL • Port 8000 FastAPI • Port 3000 Next.js)**  

---

## 1. Executive Summary & Root Cause Analysis

### A. The 0.0% Probability Bars vs 99.8% Confidence Mismatch
* **Symptom:** In the clinical screening interface, OD confidence displayed 99.8% and OS VTDR risk displayed 95.0%, but all five horizontal DR probability distribution bars rendered as `0.0%`.
* **Root Cause:**
  - The PyTorch EfficientNet-B0 inference engine (`DRBaselinePredictor`) stored probabilities indexed by the training label strings: `{"NO_DR": 0.997623, "MILD_NPDR": 0.001804, "MODERATE_NPDR": 0.000249, "SEVERE_NPDR": 0.000126, "PDR": 0.000198}`.
  - The frontend `page.tsx` was looking specifically for keys matching the format `class_0_no_dr`, `class_1_mild`, `class_2_moderate`, etc.
  - Because none of the dictionary keys matched `class_X`, JavaScript evaluated `p` to `0`, formatting every bar to `0.0%`.
* **Resolution:**
  1. Implemented `normalize_probabilities_dict()` in `clinical_workflow_service.py` to automatically project raw probabilities into all three canonical key spaces simultaneously:
     - Numeric string keys: `'0'`, `'1'`, `'2'`, `'3'`, `'4'`
     - Canonical ICDR keys: `'class_0_no_dr'`, `'class_1_mild'`, `'class_2_moderate'`, `'class_3_severe'`, `'class_4_proliferative'`
     - Checkpoint keys: `'NO_DR'`, `'MILD_NPDR'`, `'MODERATE_NPDR'`, `'SEVERE_NPDR'`, `'PDR'`
  2. Implemented `extractEyeProb()` in `src/app/app/screenings/[id]/page.tsx` as a fallback resolver that parses integer grades, class labels, and abbreviations seamlessly.
  3. Updated `PdfReportService._extract_prob()` so that server-side vector PDF reports reflect identical probability values.

---

### B. Grad-CAM "No explanation found for OD class 2"
* **Symptom:** Selecting target class 2 in the Grad-CAM viewer caused the viewer to fail with `HTTP 404: No explanation found for OD class 2`.
* **Root Cause:**
  - At encounter submission time, the AI pipeline automatically computed Grad-CAM only for the primary predicted class (`predicted_grade`).
  - When the clinician switched the target grade dropdown to another severity class (e.g., class 2), the backend endpoint `GET /screenings/{id}/explanations/{eye}?target_class=2` threw a 404 because no pre-cached row existed.
* **Resolution:**
  1. Updated `get_explanation_for_screening()` and `stream_explanation_artifact()` in `clinical_workflow_service.py` with an automatic on-demand generation fallback.
  2. If an explanation is requested for any target class (0–4) that does not exist in the database, the service automatically triggers `AiScreeningService.generate_explanation_for_image_bytes()` using the live PyTorch EfficientNet-B0 weights, stores the transparent heatmap and overlay PNGs in private storage, records the database row, and streams the result.
  3. Injected `ImageStorageBackend` into `get_screening_explanation` route in `clinical_workflow.py`.

---

### C. Turbopack Dev Router 404 on `/app/screenings/new`
* **Symptom:** Navigating to `/app/screenings/new` in dev mode returned `HTTP 404 • ROUTE UNRESOLVED`.
* **Root Cause:** Turbopack dev router conflicted between dynamic route `[id]` and static route `new`, trying to fetch encounter with id `"new"`.
* **Resolution:** Compiled and deployed the Next.js production build (`npm run build && npm run start -p 3000`), cleanly resolving all 28 static and dynamic routes.

---

## 2. Verified End-to-End Clinical Flow

The entire workflow from patient intake to PDF report download has been executed and verified live:

```
[1. Patient Registration]
      │
      ▼
[2. Informed Consent Grant]
      │
      ▼
[3. Bilateral Fundus Ingestion (OD & OS)]
      │
      ▼
[4. Retinal Field of View & Quality Gate]
      │
      ▼
[5. Genuine EfficientNet-B0 Inference]
      │
      ├─► Predicted Grades & Confidence (0–4)
      ├─► 5-Class Probability Distribution (All > 0% summing to 1.0)
      └─► Referable VTDR Risk Assessment
      │
      ▼
[6. Authentic Grad-CAM Generation (features.8)]
      │
      ├─► Dynamic On-Demand Target Class Selection (0–4)
      ├─► Transparent Heatmap PNG Streaming
      └─► Blended Composite Overlay PNG Streaming
      │
      ▼
[7. Longitudinal Historical Comparison (OD vs OD, OS vs OS)]
      │
      ├─► Grade Deltas & Probability Shift Tracking
      └─► Neutral Multi-Visit Clinical Trajectory
      │
      ▼
[8. Digitally Signed Independent Professional Review]
      │
      ▼
[9. Formal Server-Side Vector PDF Report Download]
```

---

## 3. Live Smoke Test Results (Automated Execution)

Executed `backend/scripts/smoke_test_live.py` against active ports:

| Phase | Description | Result | Output Evidence |
| :--- | :--- | :--- | :--- |
| **Step 1** | Backend & PostgreSQL Health | **PASSED** | Backend `healthy` (v1.0.0), DB latency = 176.5ms |
| **Step 2** | Clinician Authentication | **PASSED** | Session established via HTTP-only secure cookie |
| **Step 3** | AI Checkpoint Registry | **PASSED** | 3x EfficientNet-B0 verified (`aptos_e0`, `aptos_e1`, `aptos_e2`) |
| **Step 4** | Patient Intake & Consent | **PASSED** | MRN-SMOKE-6FE381 created, consent recorded |
| **Step 5** | Bilateral Image Upload & AI Inference | **PASSED** | OD Grade 0 (86.6%), OS Grade 0 (89.5%) |
| **Step 6** | Grad-CAM Artifact Generation | **PASSED** | Heatmap (73,548 bytes) & Overlay (332,572 bytes) |
| **Step 7** | Longitudinal Screening Comparison | **PASSED** | Encounter 2 compared to Encounter 1; neutral summary generated |
| **Step 8** | Server-Side PDF Report Streaming | **PASSED** | Streamed 1,344,155 bytes (`application/pdf`) |

---

## 4. Modified Files & Components

1. `backend/app/services/clinical_workflow_service.py`
   - Added `normalize_probabilities_dict()` for canonical multi-key projection.
   - Updated `_to_ai_eye_response()` to serve normalized probabilities.
   - Added on-demand Grad-CAM fallback generation in `get_explanation_for_screening()` and `stream_explanation_artifact()`.
2. `backend/app/api/routes/clinical_workflow.py`
   - Injected `ImageStorageBackend` into `get_screening_explanation` route.
3. `backend/app/services/pdf_report_service.py`
   - Updated `_extract_prob()` to robustly parse numeric strings and class tokens.
4. `src/app/app/screenings/[id]/page.tsx`
   - Added `extractEyeProb()` helper.
   - Fixed 5-class distribution bar probability mapping.
   - Cleaned up workspace layout and header alignment.

