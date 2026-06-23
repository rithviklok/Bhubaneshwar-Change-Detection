# 🛰 Bhubaneswar Change Detection

Satellite land-use change analysis for **Bhubaneswar, Odisha, India** across four two-year periods
(2018–2026), powered by Google Earth Engine and Sentinel-2 imagery.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/YOUR_GITHUB_USERNAME/bhubaneswar-change-detection/blob/main/notebooks/bhubaneswar_analysis.ipynb)

**Live App**: `https://your-vercel-app.vercel.app`  
**Analysis Page**: `https://your-vercel-app.vercel.app/analysis`

---

## Project Structure

```
├── backend/          FastAPI backend (deployed on Render.com)
│   ├── main.py
│   ├── ee_service.py
│   ├── models.py
│   ├── database.py
│   ├── requirements.txt
│   └── render.yaml
├── frontend/         Static frontend (deployed on Vercel)
│   ├── index.html    Swipe map application
│   ├── app.js
│   ├── style.css
│   └── analysis.html Read-only methodology + analysis page
├── notebooks/
│   └── bhubaneswar_analysis.ipynb
└── vercel.json
```

---

## Local Development

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
# For local dev, authenticate GEE:
earthengine authenticate
# Start server:
python -m uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
python -m http.server 5500
# Open: http://localhost:5500
```

The frontend auto-detects `localhost` and points to `http://localhost:8000`.

---

## Deployment

### Backend → Render.com

1. Push this repo to GitHub
2. Create a **New Web Service** on [render.com](https://render.com)
3. Connect the repo, set **Root Directory** to `backend/`
4. Render detects `render.yaml` automatically
5. Add environment secret: `GEE_CREDENTIALS_JSON` (base64-encoded service account JSON)
6. Note the Render URL (e.g. `https://bhubaneswar-cd-api.onrender.com`)

### Frontend → Vercel

1. Update `API_BASE` in `frontend/app.js` with your Render URL
2. Update the Colab badge URL in `frontend/analysis.html` with your GitHub username
3. Import the repo on [vercel.com](https://vercel.com)
4. Vercel detects `vercel.json` and deploys `frontend/` as a static site
5. No environment variables needed — the frontend contains no secrets

### Notebook → Google Colab

Update the badge URL in `notebooks/bhubaneswar_analysis.ipynb`:
```
https://colab.research.google.com/github/YOUR_GITHUB_USERNAME/bhubaneswar-change-detection/blob/main/notebooks/bhubaneswar_analysis.ipynb
```

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

- **Project**: `change-detection-494607` (shared with parent project)
- **Asset namespace**: `bhubaneswar_change_detection`
- **Imagery**: `COPERNICUS/S2_SR_HARMONIZED`
- **Composite window**: February–March (peak Rabi season)
- **Resolution**: 60 m for area stats, native for tile visualisation
- **Classification**: BUI (NDBI − NDVI) based, 3-class per year → 6-class change

---

*Airawat Research Foundation*
