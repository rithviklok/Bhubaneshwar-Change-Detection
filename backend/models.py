"""
models.py  —  Pydantic request / response models.
"""

from pydantic import BaseModel, Field


class YearRequest(BaseModel):
    year: int = Field(..., ge=2015, le=2030, description="Sentinel-2 year")


class PeriodRequest(BaseModel):
    year1: int = Field(..., ge=2015, le=2030)
    year2: int = Field(..., ge=2015, le=2030)


class TileResponse(BaseModel):
    tile_url: str
    year1: int | None = None
    year2: int | None = None
    year:  int | None = None


class AreaStatsResponse(BaseModel):
    city:        str
    year1:       int
    year2:       int
    year1_stats: dict
    year2_stats: dict
    changes:     dict
