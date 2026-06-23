"""
ee_service.py  —  Google Earth Engine processing for Bhubaneswar Change Detection.

All computation is scoped to the Bhubaneswar Municipal Corporation area.
Asset / naming convention: bhubaneswar_change_detection/*
GEE Project              : change-detection-494607  (shared with parent project)
"""

from __future__ import annotations

import os
import json
import base64
import ee
from google.oauth2 import service_account


# ── Constants ──────────────────────────────────────────────────────────────────

# Bhubaneswar Municipal Corporation bounding box  [W, S, E, N]
BBSR_BOUNDS: list[float] = [85.7200, 20.1200, 85.9800, 20.4000]

# Four two-year analysis periods (up to 2026)
PERIODS: list[dict] = [
    {"id": "p1", "year1": 2018, "year2": 2020, "label": "2018 → 2020",
     "context": "Post-Cyclone Titli recovery & early Smart City phase"},
    {"id": "p2", "year1": 2020, "year2": 2022, "label": "2020 → 2022",
     "context": "COVID-19 lockdown greening & infrastructure resumption"},
    {"id": "p3", "year1": 2022, "year2": 2024, "label": "2022 → 2024",
     "context": "Smart City Phase-2 & metro corridor development"},
    {"id": "p4", "year1": 2024, "year2": 2026, "label": "2024 → 2026",
     "context": "Metro expansion & recent urban growth"},
]

# 6-class change detection colour palette
CHANGE_PALETTE: list[str] = [
    "#ef4444",  # 1  Built-up Gain
    "#f97316",  # 2  Built-up Loss
    "#facc15",  # 3  Vegetation Loss
    "#22c55e",  # 4  Vegetation Gain
    "#3b82f6",  # 5  Water Gain
    "#06b6d4",  # 6  Water Recession
]

CHANGE_LABELS: list[str] = [
    "Built-up Gain", "Built-up Loss",
    "Vegetation Loss", "Vegetation Gain",
    "Water Gain", "Water Recession",
]


# ── Initialization ─────────────────────────────────────────────────────────────

def initialize_ee() -> None:
    """
    Initialize Google Earth Engine.

    Local dev  : uses cached user credentials (earthengine authenticate).
    Cloud / CI : reads GEE_CREDENTIALS_JSON (base-64-encoded service-account
                 JSON) and GEE_PROJECT_ID from environment variables.
    """
    project   = os.environ.get("GEE_PROJECT_ID", "change-detection-494607")
    creds_b64 = os.environ.get("GEE_CREDENTIALS_JSON", "")

    try:
        if creds_b64:
            creds_dict  = json.loads(base64.b64decode(creds_b64))
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=["https://www.googleapis.com/auth/earthengine"],
            )
            ee.Initialize(credentials, project=project)
            print("[OK] EE initialized (service account) — project:", project)
        else:
            ee.Initialize(project=project)
            print("[OK] EE initialized (user auth) — project:", project)
    except Exception as exc:
        raise RuntimeError(f"EE Initialization failed: {exc}") from exc


# ── Internal helpers ───────────────────────────────────────────────────────────

def _get_roi() -> ee.Geometry:
    return ee.Geometry.Rectangle(BBSR_BOUNDS)


def _mask_s2_clouds(image: ee.Image) -> ee.Image:
    """Apply QA60 cloud and cirrus mask for Sentinel-2."""
    qa            = image.select("QA60")
    cloud_bit     = 1 << 10
    cirrus_bit    = 1 << 11
    mask = (
        qa.bitwiseAnd(cloud_bit).eq(0)
        .And(qa.bitwiseAnd(cirrus_bit).eq(0))
    )
    return image.updateMask(mask)


def _s2_composite(year: int) -> ee.Image:
    """
    February–March median composite (peak Rabi/wheat season).

    Rationale: crops reach maximum greenness in Feb–Mar across Odisha,
    so agricultural pixels are reliably classified as 'vegetation', while
    built-up areas maintain low NDVI year-round.  Using the same
    phenological window each year eliminates inter-year spectral drift.
    """
    roi = _get_roi()
    return (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(f"{year}-02-01", f"{year}-03-31")
        .filterBounds(roi)
        .map(_mask_s2_clouds)
        .median()
        .select(["B3", "B4", "B8", "B11"])   # Green, Red, NIR, SWIR1
        .divide(10000)
        .clip(roi)
    )


def _classify(img: ee.Image) -> ee.Image:
    """
    3-class land-cover classification.
      0 = other / unclassified
      1 = vegetation
      2 = water
      3 = built-up
    """
    ndvi = img.normalizedDifference(["B8", "B4"])
    ndwi = img.normalizedDifference(["B3", "B8"])
    ndbi = img.normalizedDifference(["B11", "B8"])
    bui  = ndbi.subtract(ndvi)   # Built-up Index: BUI = NDBI - NDVI

    water      = ndwi.gt(0.10)
    vegetation = ndvi.gt(0.30).And(ndwi.lte(0.10))
    builtup    = bui.gt(0.0).And(ndwi.lte(0.05))

    return (
        ee.Image(0)
        .where(vegetation, 1)
        .where(water,      2)
        .where(builtup,    3)
    )


# ── Public computation functions ───────────────────────────────────────────────

def compute_rgb_map(year: int) -> str:
    """Return GEE tile URL for a natural-colour (B4/B3/B2) composite."""
    roi = _get_roi()
    rgb = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(f"{year}-02-01", f"{year}-03-31")
        .filterBounds(roi)
        .map(_mask_s2_clouds)
        .median()
        .select(["B4", "B3", "B2"])
        .divide(10000)
        .clip(roi)
    )
    map_id = rgb.getMapId({"min": 0.02, "max": 0.28})
    return map_id["tile_fetcher"].url_format


def compute_change_map(year1: int, year2: int) -> str:
    """Return GEE tile URL for the 6-class change detection map."""
    cls1 = _classify(_s2_composite(year1))
    cls2 = _classify(_s2_composite(year2))

    builtup_gain = cls1.neq(3).And(cls2.eq(3))
    builtup_loss = cls1.eq(3).And(cls2.neq(3))
    veg_loss     = cls1.eq(1).And(cls2.neq(1))
    veg_gain     = cls1.neq(1).And(cls2.eq(1))
    water_gain   = cls1.neq(2).And(cls2.eq(2))
    water_loss   = cls1.eq(2).And(cls2.neq(2))

    change = (
        ee.Image(0)
        .where(builtup_gain, 1)
        .where(builtup_loss, 2)
        .where(veg_loss,     3)
        .where(veg_gain,     4)
        .where(water_gain,   5)
        .where(water_loss,   6)
    )
    change = change.updateMask(change.gt(0))

    map_id = change.getMapId({
        "min": 1, "max": 6,
        "palette": CHANGE_PALETTE,
    })
    return map_id["tile_fetcher"].url_format


def compute_classification_map(year1: int, year2: int) -> str:
    """
    Return GEE tile URL for a continuous NDVI-delta map
    (green = vegetation gain, red = vegetation / cover loss).
    """
    img1      = _s2_composite(year1)
    img2      = _s2_composite(year2)
    ndvi1     = img1.normalizedDifference(["B8", "B4"])
    ndvi2     = img2.normalizedDifference(["B8", "B4"])
    delta     = ndvi2.subtract(ndvi1).clip(_get_roi())

    map_id = delta.getMapId({
        "min": -0.4, "max": 0.4,
        "palette": ["#ef4444", "#f97316", "#facc15",
                    "#bbf7d0", "#22c55e", "#15803d"],
    })
    return map_id["tile_fetcher"].url_format


def compute_area_stats(year1: int, year2: int) -> dict:
    """
    Compute land-cover area (km²) for vegetation, water and built-up
    in both years, plus absolute and relative change between them.

    Uses ee.Image.pixelArea() so the result is correct regardless of
    the scale at which GEE evaluates the reduction.
    """
    roi = _get_roi()

    def get_areas(year: int) -> dict:
        img  = _s2_composite(year)
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("ndvi")
        ndwi = img.normalizedDifference(["B3", "B8"]).rename("ndwi")
        ndbi = img.normalizedDifference(["B11", "B8"]).rename("ndbi")
        bui  = ndbi.subtract(ndvi).rename("bui")

        water      = ndwi.gt(0.10).rename("water")
        vegetation = ndvi.gt(0.30).And(ndwi.lte(0.10)).rename("vegetation")
        builtup    = bui.gt(0.0).And(ndwi.lte(0.05)).rename("builtup")

        px_km2  = ee.Image.pixelArea().divide(1e6)
        stacked = (
            vegetation.multiply(px_km2).rename("vegetation")
            .addBands(water.multiply(px_km2).rename("water"))
            .addBands(builtup.multiply(px_km2).rename("builtup"))
        )
        result = stacked.reduceRegion(
            reducer    = ee.Reducer.sum(),
            geometry   = roi,
            scale      = 60,
            bestEffort = False,
            maxPixels  = 1e8,
            tileScale  = 4,
        ).getInfo()

        return {
            "vegetation_sqkm": round(result.get("vegetation") or 0, 2),
            "water_sqkm":      round(result.get("water")      or 0, 2),
            "builtup_sqkm":    round(result.get("builtup")    or 0, 2),
        }

    stats1 = get_areas(year1)
    stats2 = get_areas(year2)

    changes: dict = {}
    for key in ("vegetation", "water", "builtup"):
        v1    = stats1[f"{key}_sqkm"]
        v2    = stats2[f"{key}_sqkm"]
        delta = round(v2 - v1, 2)
        pct   = round((v2 - v1) / v1 * 100, 1) if v1 > 0 else None
        changes[f"{key}_delta_sqkm"] = delta
        changes[f"{key}_pct"]        = pct

    return {
        "city":        "Bhubaneswar",
        "year1":       year1,
        "year2":       year2,
        "year1_stats": stats1,
        "year2_stats": stats2,
        "changes":     changes,
    }
