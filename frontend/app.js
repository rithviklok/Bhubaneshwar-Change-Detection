/* ============================================================
   app.js  —  Bhubaneswar Change Detection
   Leaflet swipe map, API calls, stats rendering, save analysis
   ============================================================ */

'use strict';

// ── Configuration ─────────────────────────────────────────────────────────────

const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://bhubaneswar-cd-api-360781948089.asia-south1.run.app';   // ← update after Cloud Run deploy

const CITY_CENTER = [20.2961, 85.8245];
const CITY_ZOOM   = 12;

const PERIODS = [
  { id: 'p1', year1: 2018, year2: 2020, label: '2018 → 2020', ctx: 'Post-Cyclone Titli recovery & early Smart City phase' },
  { id: 'p2', year1: 2020, year2: 2022, label: '2020 → 2022', ctx: 'COVID-19 lockdown greening & infrastructure resumption' },
  { id: 'p3', year1: 2022, year2: 2024, label: '2022 → 2024', ctx: 'Smart City Phase-2 & metro corridor development' },
  { id: 'p4', year1: 2024, year2: 2026, label: '2024 → 2026', ctx: 'Metro expansion & recent urban growth' },
];

const LEGEND_CHANGE = [
  { color: '#ef4444', label: 'Built-up Gain'    },
  { color: '#f97316', label: 'Built-up Loss'    },
  { color: '#facc15', label: 'Vegetation Loss'  },
  { color: '#22c55e', label: 'Vegetation Gain'  },
  { color: '#3b82f6', label: 'Water Gain'       },
  { color: '#06b6d4', label: 'Water Recession'  },
];

const LEGEND_CLASSIFY = [
  { color: '#ef4444', label: 'Strong cover loss'    },
  { color: '#f97316', label: 'Moderate cover loss'  },
  { color: '#facc15', label: 'Slight change'        },
  { color: '#bbf7d0', label: 'Slight gain'          },
  { color: '#22c55e', label: 'Moderate cover gain'  },
  { color: '#15803d', label: 'Strong cover gain'    },
];

const LEGEND_RGB = [
  { color: '#27ae60', label: 'Vegetation'  },
  { color: '#95a5a6', label: 'Built-up'   },
  { color: '#2980b9', label: 'Water body' },
  { color: '#f1c40f', label: 'Bare soil'  },
];

// ── State ──────────────────────────────────────────────────────────────────────

let currentPeriodIdx = 0;
let currentLayer     = 'rgb';
let leftTileLayer    = null;
let rightTileLayer   = null;
let sbsControl       = null;
let tileCache        = {};          // key → URL
let statsCache       = {};          // key → stats object
let lastStats        = null;        // for Save Analysis

// ── Map initialisation ─────────────────────────────────────────────────────────

const map = L.map('map', { zoomControl: true }).setView(CITY_CENTER, CITY_ZOOM);

const baseTile = L.tileLayer(
  'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  { attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom: 19 }
).addTo(map);

// Invalidate on load (Leaflet size fix)
window.addEventListener('load', () => setTimeout(() => map.invalidateSize(), 100));

// ── Helpers ────────────────────────────────────────────────────────────────────

function setStatus(msg) {
  document.getElementById('status-msg').textContent = msg;
}

function showLoading(visible, msg = 'Loading satellite imagery…') {
  const el = document.getElementById('loading-overlay');
  document.getElementById('loading-text').textContent = msg;
  el.classList.toggle('visible', visible);
}

function showError(msg) {
  const toast = document.getElementById('error-toast');
  toast.textContent = '⚠ ' + msg;
  toast.classList.add('visible');
  setTimeout(() => toast.classList.remove('visible'), 4000);
}

function togglePanel(id) {
  document.getElementById(id).classList.toggle('collapsed');
}

function updateYearLabels(leftYear, rightYear, leftSuffix = '', rightSuffix = '') {
  document.getElementById('label-left').textContent  = leftYear  + (leftSuffix  ? ' · ' + leftSuffix  : '');
  document.getElementById('label-right').textContent = rightYear + (rightSuffix ? ' · ' + rightSuffix : '');
}

function updateLegend(type) {
  const items = type === 'change'   ? LEGEND_CHANGE
              : type === 'classify' ? LEGEND_CLASSIFY
              : LEGEND_RGB;
  document.getElementById('legend-body').innerHTML = items.map(it =>
    `<div class="legend-item">
       <span class="legend-dot" style="background:${it.color}"></span>${it.label}
     </div>`
  ).join('');
}

// ── API calls ──────────────────────────────────────────────────────────────────

async function fetchTileUrl(endpoint, body) {
  const key = endpoint + JSON.stringify(body);
  if (tileCache[key]) return tileCache[key];

  const res = await fetch(API_BASE + endpoint, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  const data = await res.json();
  tileCache[key] = data.tile_url;
  return data.tile_url;
}

async function fetchStats(year1, year2) {
  const key = `stats_${year1}_${year2}`;
  if (statsCache[key]) return statsCache[key];

  const res = await fetch(API_BASE + '/area-stats', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ year1, year2 }),
  });
  if (!res.ok) throw new Error('Stats API error');
  const data = await res.json();
  statsCache[key] = data;
  return data;
}

// ── Map layer management ───────────────────────────────────────────────────────

function clearLayers() {
  if (sbsControl)     { sbsControl.remove();         sbsControl    = null; }
  if (leftTileLayer)  { map.removeLayer(leftTileLayer);  leftTileLayer  = null; }
  if (rightTileLayer) { map.removeLayer(rightTileLayer); rightTileLayer = null; }
}

function applySwipe(leftUrl, rightUrl) {
  clearLayers();

  leftTileLayer = L.tileLayer(leftUrl, {
    attribution: 'Google Earth Engine / Sentinel-2',
    opacity:     1,
  });
  rightTileLayer = L.tileLayer(rightUrl, {
    attribution: 'Google Earth Engine / Sentinel-2',
    opacity:     1,
  });

  leftTileLayer.addTo(map);
  rightTileLayer.addTo(map);

  sbsControl = L.control.sideBySide(leftTileLayer, rightTileLayer);
  sbsControl.addTo(map);
}

// ── Main load function ─────────────────────────────────────────────────────────

async function loadLayers() {
  const period = PERIODS[currentPeriodIdx];
  const { year1, year2 } = period;

  showLoading(true, `Fetching ${currentLayer} imagery for ${period.label}…`);
  setStatus(`Loading ${period.label} · ${currentLayer}…`);

  try {
    let leftUrl, rightUrl;

    if (currentLayer === 'rgb') {
      [leftUrl, rightUrl] = await Promise.all([
        fetchTileUrl('/rgb-map',    { year: year1 }),
        fetchTileUrl('/rgb-map',    { year: year2 }),
      ]);
      updateYearLabels(year1, year2, 'RGB', 'RGB');
    } else if (currentLayer === 'change') {
      [leftUrl, rightUrl] = await Promise.all([
        fetchTileUrl('/rgb-map',    { year: year1 }),
        fetchTileUrl('/change-map', { year1, year2 }),
      ]);
      updateYearLabels(year1, year2, 'RGB', 'Change Map');
    } else {
      [leftUrl, rightUrl] = await Promise.all([
        fetchTileUrl('/rgb-map',  { year: year1 }),
        fetchTileUrl('/classify', { year1, year2 }),
      ]);
      updateYearLabels(year1, year2, 'RGB', 'NDVI Delta');
    }

    applySwipe(leftUrl, rightUrl);
    updateLegend(currentLayer);
    setStatus(`${period.label} · ${currentLayer.toUpperCase()} · ${period.ctx}`);

    // Load stats in background
    loadStats(year1, year2);

  } catch (err) {
    showError(err.message);
    setStatus('Error — check console');
    console.error(err);
  } finally {
    showLoading(false);
  }
}

// ── Stats rendering ────────────────────────────────────────────────────────────

async function loadStats(year1, year2) {
  try {
    const stats = await fetchStats(year1, year2);
    lastStats = stats;
    renderStats(stats);
  } catch (err) {
    console.warn('Stats load failed:', err.message);
  }
}

function renderStats(s) {
  const { year1_stats: s1, year2_stats: s2, changes, year1, year2 } = s;

  const maxVal = Math.max(
    s1.vegetation_sqkm, s2.vegetation_sqkm,
    s1.builtup_sqkm,    s2.builtup_sqkm,
    s1.water_sqkm,      s2.water_sqkm,
    1
  );

  function pct(v) { return Math.round((v / maxVal) * 100); }

  function deltaTag(pctVal) {
    if (pctVal === null || pctVal === undefined) return '';
    const cls = pctVal > 0 ? 'pos' : pctVal < 0 ? 'neg' : 'neu';
    const sign = pctVal > 0 ? '+' : '';
    return `<span class="stat-delta ${cls}">${sign}${pctVal}%</span>`;
  }

  function row(label, color, y1, y2, delta) {
    return `
      <div class="stat-row">
        <div class="stat-label">
          <span>${label}</span>
          ${deltaTag(delta)}
        </div>
        <div class="bar-wrap"><div class="bar-fill bar-y1" style="width:${pct(y1)}%;background:${color}55"></div></div>
        <div class="bar-wrap"><div class="bar-fill bar-y2" style="width:${pct(y2)}%;background:${color}"></div></div>
        <div class="stat-vals">
          <span>${year1}: ${y1.toFixed(1)} km²</span>
          <span>${year2}: ${y2.toFixed(1)} km²</span>
        </div>
      </div>`;
  }

  document.getElementById('stats-body').innerHTML =
    `<div style="font-size:0.65rem;color:var(--text-muted);margin-bottom:8px">
       Bhubaneswar · ${year1} → ${year2}
     </div>` +
    row('Vegetation', '#22c55e', s1.vegetation_sqkm, s2.vegetation_sqkm, changes.vegetation_pct) +
    row('Built-up',  '#ef4444', s1.builtup_sqkm,    s2.builtup_sqkm,    changes.builtup_pct)    +
    row('Water',     '#3b82f6', s1.water_sqkm,       s2.water_sqkm,      changes.water_pct);
}

// ── Save analysis ──────────────────────────────────────────────────────────────

document.getElementById('btn-save').addEventListener('click', () => {
  if (!lastStats) {
    showError('Load a layer first to generate stats');
    return;
  }
  const period = PERIODS[currentPeriodIdx];
  const payload = {
    project:     'bhubaneswar_change_detection',
    city:        'Bhubaneswar, Odisha, India',
    period:      period.label,
    context:     period.ctx,
    layer:       currentLayer,
    exported_at: new Date().toISOString(),
    stats:       lastStats,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `bbsr_analysis_${period.year1}_${period.year2}.json`;
  a.click();
  URL.revokeObjectURL(url);
});

// ── Recording mode ─────────────────────────────────────────────────────────────

document.getElementById('btn-record').addEventListener('click', () => {
  document.body.classList.toggle('recording-mode');
  map.invalidateSize();
});

// ── Period & layer button wiring ───────────────────────────────────────────────

document.querySelectorAll('.btn-period').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.btn-period').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentPeriodIdx = parseInt(btn.dataset.period);
    loadLayers();
  });
});

['rgb', 'change', 'classify'].forEach(layer => {
  document.getElementById('lbtn-' + layer).addEventListener('click', () => {
    document.querySelectorAll('#controls-bar .ctrl-group .btn:not(.btn-period)').forEach(b => b.classList.remove('active'));
    document.getElementById('lbtn-' + layer).classList.add('active');
    currentLayer = layer;
    loadLayers();
  });
});

// ── Auto-load on startup ───────────────────────────────────────────────────────

loadLayers();
