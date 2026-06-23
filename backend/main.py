"""
main.py  —  FastAPI application for Bhubaneswar Change Detection.

Deployment : Render.com  (see render.yaml)
CORS       : allows all origins so the Vercel frontend can call this API.
Credentials: never returned to the browser; all GEE calls happen server-side.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import ee_service
import database
from models import YearRequest, PeriodRequest, TileResponse, AreaStatsResponse

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "Bhubaneswar Change Detection API",
    description = "Satellite land-use change analysis for Bhubaneswar, Odisha (2018–2026)",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],   # Vercel frontend URL (all origins for simplicity)
    allow_methods  = ["GET", "POST", "OPTIONS"],
    allow_headers  = ["*"],
)

# Initialise GEE once at startup
ee_service.initialize_ee()


# ── Utility ────────────────────────────────────────────────────────────────────

def _cached_tile(cache_key: str, compute_fn, *args) -> str:
    """Return a cached tile URL or compute + cache a new one."""
    cached = database.get_cached(cache_key)
    if cached:
        return cached
    tile_url = compute_fn(*args)
    database.save_cached(cache_key, tile_url)
    return tile_url


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status":  "ok",
        "city":    "Bhubaneswar",
        "project": "bhubaneswar_change_detection",
        "periods": ee_service.PERIODS,
    }


@app.get("/periods")
def periods():
    """Return the four fixed analysis periods."""
    return {"periods": ee_service.PERIODS}


# ── RGB natural-colour tiles ───────────────────────────────────────────────────

@app.post("/rgb-map", response_model=TileResponse)
async def rgb_map(req: YearRequest):
    """Get a natural-colour (B4/B3/B2) tile URL for a given year."""
    cache_key = f"bbsr_rgb_{req.year}"
    try:
        tile_url = _cached_tile(
            cache_key,
            ee_service.compute_rgb_map,
            req.year,
        )
        return TileResponse(tile_url=tile_url, year=req.year)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Change detection tiles ─────────────────────────────────────────────────────

@app.post("/change-map", response_model=TileResponse)
async def change_map(req: PeriodRequest):
    """Get a 6-class change detection tile URL for a period."""
    cache_key = f"bbsr_change_{req.year1}_{req.year2}"
    try:
        tile_url = _cached_tile(
            cache_key,
            ee_service.compute_change_map,
            req.year1, req.year2,
        )
        return TileResponse(tile_url=tile_url, year1=req.year1, year2=req.year2)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Classification / NDVI-delta tiles ─────────────────────────────────────────

@app.post("/classify", response_model=TileResponse)
async def classify(req: PeriodRequest):
    """Get a continuous NDVI-delta classification tile URL for a period."""
    cache_key = f"bbsr_classify_{req.year1}_{req.year2}"
    try:
        tile_url = _cached_tile(
            cache_key,
            ee_service.compute_classification_map,
            req.year1, req.year2,
        )
        return TileResponse(tile_url=tile_url, year1=req.year1, year2=req.year2)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Area statistics ────────────────────────────────────────────────────────────

@app.post("/area-stats", response_model=AreaStatsResponse)
async def area_stats(req: PeriodRequest):
    """Compute vegetation / water / built-up area (km²) and change statistics."""
    try:
        result = ee_service.compute_area_stats(req.year1, req.year2)
        return AreaStatsResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Admin ──────────────────────────────────────────────────────────────────────

@app.delete("/cache")
def clear_cache():
    """Clear the tile-URL cache (admin use only)."""
    deleted = database.clear_cache()
    return {"deleted": deleted}
