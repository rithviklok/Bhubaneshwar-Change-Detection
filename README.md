# 🛰 Bhubaneswar Change Detection

Satellite land-use change analysis for **Bhubaneswar, Odisha, India** across four two-year periods
(2018–2026), powered by Google Earth Engine and Sentinel-2 imagery.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/YOUR_GITHUB_USERNAME/bhubaneswar-change-detection/blob/main/notebooks/bhubaneswar_analysis.ipynb)

**Live App**: `https://your-vercel-app.vercel.app`  
**Analysis Page**: `https://your-vercel-app.vercel.app/analysis`

---

## Architecture

```
┌───────────────────────┐        ┌──────────────────────────────┐
│   Vercel (frontend)   │  API   │   Google Cloud Run (backend) │
│   index.html          │───────▶│   FastAPI                    │
│   app.js / style.css  │        │   ADC → service account      │
│   analysis.html       │        │   No private keys            │
└───────────────────────┘        └──────────┬───────────────────┘
                                            │ GEE API
                                 ┌──────────▼───────────────────┐
                                 │   Google Earth Engine        │
                                 │   change-detection-494607    │
                                 └──────────────────────────────┘
```

**Key principle**: No service-account key files anywhere.  
Cloud Run uses Application Default Credentials (ADC) with an attached service account.

---

## Project Structure

```
├── backend/          FastAPI backend (deployed on Cloud Run)
│   ├── main.py
│   ├── ee_service.py
│   ├── models.py
│   ├── database.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/         Static frontend (deployed on Vercel)
│   ├── index.html    Swipe map application
│   ├── app.js
│   ├── style.css
│   └── analysis.html Methodology + analysis page
├── notebooks/
│   └── bhubaneswar_analysis.ipynb
├── deploy.sh         Cloud Run deployment script
└── vercel.json
```

---

## Local Development

### 1. Backend

```bash
cd backend
pip install -r requirements.txt

# Authenticate for local dev (one-time):
earthengine authenticate

# Start server:
python -m uvicorn main:app --reload --port 8000
```

EE initialises using your local user credentials — no key file needed.

### 2. Frontend

```bash
cd frontend
python -m http.server 5500
# Open: http://localhost:5500
```

The frontend auto-detects `localhost` and points to `http://localhost:8000`.

---

## Deployment

### Prerequisites

1. `gcloud` CLI installed and authenticated (`gcloud auth login`)
2. A GCP service account with:
   - `roles/earthengine.writer` (or `roles/earthengine.admin`) on the GEE project
   - The EE API enabled on the project
3. **No key file** — the service account is *attached* to Cloud Run, not exported

### Backend → Google Cloud Run

Edit `deploy.sh` and set:
- `SERVICE_ACCOUNT` to your dedicated EE service account email
- `VERCEL_ORIGIN` to your Vercel production URL

Then run:
```bash
bash deploy.sh
```

This will:
1. Build the container via Cloud Build
2. Deploy to Cloud Run (asia-south1 / Mumbai)
3. Attach the service account for keyless ADC auth
4. Allow unauthenticated HTTP access
5. Set `CORS_ORIGIN` for the Vercel frontend
6. Print the Cloud Run service URL

### Frontend → Vercel

1. Copy the Cloud Run URL from the deploy script output
2. Update `API_BASE` in `frontend/app.js` and `frontend/analysis.html`
3. Update the Colab badge URL with your GitHub username
4. Deploy:
   ```bash
   vercel --prod
   ```

### No Secrets in the Frontend

The Vercel deployment contains **zero secrets**:
- No GEE credentials
- No service-account keys or tokens
- No Cloud Run authentication tokens
- The Cloud Run URL is not a secret — all endpoints are read-only

---

## Analysis Periods

| Period | Context |
|---|---|
| 2018 → 2020 | Post-Cyclone Titli recovery & early Smart City phase |
| 2020 → 2022 | COVID-19 lockdown greening & infrastructure resumption |
| 2022 → 2024 | Smart City Phase-2 & metro corridor development |
| 2024 → 2026 | Metro expansion & recent urban growth |

---

## GEE Configuration

- **Project**: `change-detection-494607`
- **Auth**: Application Default Credentials (ADC) — no key file
- **Asset namespace**: `bhubaneswar_change_detection`
- **Imagery**: `COPERNICUS/S2_SR_HARMONIZED`
- **Composite window**: February–March (peak Rabi season)
- **Resolution**: 60 m for area stats, native for tile visualisation
- **Classification**: BUI (NDBI − NDVI) based, 3-class per year → 6-class change

---

*Airawat Research Foundation*
