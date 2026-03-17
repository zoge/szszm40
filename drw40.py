import osmnx as ox
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
from shapely.geometry import LineString
from shapely.ops import unary_union
import numpy as np

# ── 1. Utcahálózat letöltése ──────────────────────────────────────────────────
print("Térkép letöltése...")
G = ox.graph_from_place("Szigetszentmiklós, Hungary", network_type="drive")
G_proj = ox.project_graph(G)                    # metrikus vetítés (EOV-szerű)
nodes_proj, edges_proj = ox.graph_to_gdfs(G_proj)

bbox   = nodes_proj.total_bounds               # [minx, miny, maxx, maxy]
cx     = (bbox[0] + bbox[2]) / 2
cy     = (bbox[1] + bbox[3]) / 2
city_w = bbox[2] - bbox[0]
city_h = bbox[3] - bbox[1]

# ── 2. "40" betűk vektoros körvonala ─────────────────────────────────────────
fp = FontProperties(family="DejaVu Sans", weight="bold")
tp = TextPath((0, 0), "40", size=1, prop=fp)

verts = tp.vertices.copy()
codes = tp.codes

# Normalizálás + skálázás (a felirat a város ~55%-a legyen)
v_min  = verts.min(axis=0)
v_max  = verts.max(axis=0)
v_span = v_max - v_min

scale = city_w * 0.55
verts_s = (verts - v_min) / v_span              # 0..1 közé
verts_s[:, 0] = verts_s[:, 0] * scale + cx - scale / 2
verts_s[:, 1] = verts_s[:, 1] * scale * (v_span[1] / v_span[0]) + cy - scale * 0.15

# ── 3. Betű-szárak kinyerése (MOVETO / LINETO szegmensek) ────────────────────
segments = []
prev = None

for v, c in zip(verts_s, codes):
    if c == 1:                                  # MOVETO
        prev = v
    elif c == 2 and prev is not None:           # LINETO
        seg_len = np.hypot(v[0] - prev[0], v[1] - prev[1])
        if seg_len > 1:                         # csak érdemi szegmens
            segments.append(LineString([prev, v]))
        prev = v
    elif c in (3, 4):                           # CURVE (végpontját követjük)
        prev = v

print(f"Betűszár-szegmensek: {len(segments)}")

# ── 4. Buffer-terület a betű-szárak körül ─────────────────────────────────────
buffer_m = city_w * 0.012                      # ~60-80 méteres tolerancia
text_zone = unary_union([s.buffer(buffer_m) for s in segments])

# ── 5. Utcaszakaszok szűrése ──────────────────────────────────────────────────
edges_proj = edges_proj.copy()
edges_proj["is_40"] = edges_proj.geometry.intersects(text_zone)

matched  = edges_proj["is_40"].sum()
total    = len(edges_proj)
print(f"Egyező utcaszakasz: {matched} / {total}")

# ── 6. Vizualizáció ───────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 14), facecolor="#1a1a2e")
ax.set_facecolor("#1a1a2e")

# Alap utcahálózat
edges_proj[~edges_proj["is_40"]].plot(
    ax=ax, color="#3a3a5c", linewidth=0.6, alpha=0.7
)

# Kiemelt (40-es) utcák
edges_proj[edges_proj["is_40"]].plot(
    ax=ax, color="#e63946", linewidth=2.2, alpha=0.95
)

# Betűszárak vázlata (átlátszó overlay)
import matplotlib.patches as mpatches
from matplotlib.path import Path as MplPath
mpl_path = MplPath(verts_s, codes)
patch = mpatches.PathPatch(
    mpl_path, facecolor="none",
    edgecolor="#ff6b6b", linewidth=0.8, linestyle="--", alpha=0.35
)
ax.add_patch(patch)

# Felirat
ax.set_title(
    "Szigetszentmiklós – 40-es felirat utcák vonalán",
    color="white", fontsize=16, pad=14
)
ax.set_axis_off()

legend = [
    mpatches.Patch(color="#e63946", label="Egyező utcák"),
    mpatches.Patch(color="#3a3a5c", label="Többi utca"),
]
ax.legend(handles=legend, loc="lower right",
          facecolor="#2a2a4a", labelcolor="white", fontsize=11)

plt.tight_layout()
plt.savefig("szigetszentmiklos_40_utcak.png", dpi=180, bbox_inches="tight")
plt.show()
print("Kész: szigetszentmiklos_40_utcak.png")
