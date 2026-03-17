import osmnx as ox
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union

matplotlib.use("Agg")

# ── 1. Utcahálózat ────────────────────────────────────────────────────────────
print("Térkép letöltése...")
G = ox.graph_from_place("Szigetszentmiklós, Hungary", network_type="drive")
G_proj = ox.project_graph(G)
nodes_proj, edges_proj = ox.graph_to_gdfs(G_proj)

bbox   = nodes_proj.total_bounds
cx     = (bbox[0] + bbox[2]) / 2
cy     = (bbox[1] + bbox[3]) / 2
city_w = bbox[2] - bbox[0]

# ── 2. Egyszáras "4" és "0" normalizált koordinátákban (0..1) ─────────────────
# Minden szám 0..1 x 0..1 négyzetbe van belőve

def make_4():
    """'4' – 3 vonal"""
    return [
        [(0.0, 1.0), (0.0, 0.45), (0.75, 0.45)],   # bal függőleges + vízszintes
        [(0.75, 1.0), (0.75, 0.0)],                  # jobb függőleges
    ]

def make_0():
    """'0' – ellipszis közelítés pontokkal"""
    t = np.linspace(0, 2 * np.pi, 60)
    xs = 0.5 + 0.45 * np.cos(t)
    ys = 0.5 + 0.50 * np.sin(t)
    return [list(zip(xs, ys))]

# ── 3. Skálázás és pozicionálás ───────────────────────────────────────────────
scale     = city_w * 0.30    # egy szám szélessége
gap       = city_w * 0.06    # köz a két szám között
y_offset  = cy - scale * 0.50

def transform(strokes, x_offset):
    lines = []
    for stroke in strokes:
        pts = [(x * scale + x_offset,
                y * scale + y_offset) for x, y in stroke]
        if len(pts) >= 2:
            lines.append(LineString(pts))
    return lines

total_w = 2 * scale + gap
x0 = cx - total_w / 2

strokes_4 = transform(make_4(), x0)
strokes_0 = transform(make_0(), x0 + scale + gap)

all_strokes = strokes_4 + strokes_0

# ── 4. Buffer + utcaszűrés ────────────────────────────────────────────────────
buffer_m  = city_w * 0.010
text_zone = unary_union([s.buffer(buffer_m) for s in all_strokes])

edges_proj = edges_proj.copy()
edges_proj["is_40"] = edges_proj.geometry.intersects(text_zone)

print(f"Egyező utcaszakasz: {edges_proj['is_40'].sum()} / {len(edges_proj)}")

# ── 5. Rajzolás ───────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 14), facecolor="#1a1a2e")
ax.set_facecolor("#1a1a2e")

edges_proj[~edges_proj["is_40"]].plot(ax=ax, color="#3a3a5c", linewidth=0.6, alpha=0.7)
edges_proj[edges_proj["is_40"]].plot(ax=ax, color="#e63946", linewidth=2.5)

# Referencia-vonalak (szaggatott)
for s in all_strokes:
    xs, ys = s.xy
    ax.plot(xs, ys, "--", color="#ff6b6b", linewidth=0.8, alpha=0.4)

ax.set_title("Szigetszentmiklós – 40 (egyszáras)", color="white", fontsize=15)
ax.set_axis_off()
plt.tight_layout()
plt.savefig("szigetszentmiklos_40_utcak2.png", dpi=180, bbox_inches="tight")
print("Kész: szigetszentmiklos_40_utcak2.png")