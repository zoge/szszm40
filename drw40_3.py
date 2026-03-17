import osmnx as ox
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import LineString
from shapely.ops import unary_union

# ── 1. Utcahálózat ────────────────────────────────────────────────────────────
print("Térkép letöltése...")
G = ox.graph_from_place("Szigetszentmiklós, Hungary", network_type="drive")
G_proj = ox.project_graph(G)
nodes_proj, edges_proj = ox.graph_to_gdfs(G_proj)

bbox   = nodes_proj.total_bounds
cx0    = (bbox[0] + bbox[2]) / 2
cy0    = (bbox[1] + bbox[3]) / 2
city_w = bbox[2] - bbox[0]
city_h = bbox[3] - bbox[1]

# Összes utca egyetlen geometria → gyors intersection
print("Utcahálózat előkészítése...")
all_streets = unary_union(edges_proj.geometry.values)

# ── 2. Egyszáras "4" és "0" sablon (normalizált -0.5..0.5) ───────────────────
def get_template_strokes():
    """
    '4': bal oldali L + jobb függőleges
    '0': ellipszis
    Mindkettő 0..1 egységnégyzeten belül, majd x-eltolással egymás mellé kerül.
    """
    # "4" – bal szám: x ∈ 0.0..0.7
    s4 = [
        [(0.00, 0.95), (0.00, 0.45), (0.70, 0.45)],  # bal szár + vízszintes
        [(0.55, 1.00), (0.55, 0.00)],                  # jobb szár
    ]
    # "0" – jobb szám: x ∈ 0.0..1.0 → majd eltolva
    t = np.linspace(0, 2 * np.pi, 64)
    oval = list(zip(0.50 + 0.46 * np.cos(t),
                    0.50 + 0.50 * np.sin(t)))
    s0 = [oval]
    return s4, s0


def build_strokes(cx, cy, scale, angle_deg):
    """Sablon strokes transzformálása: skálázás + forgatás + pozicionálás."""
    s4_raw, s0_raw = get_template_strokes()
    angle = np.radians(angle_deg)
    ca, sa = np.cos(angle), np.sin(angle)

    # A "4" és "0" egymás mellé kerül; köztük kis rés
    num_w = 1.0          # egy szám normalizált szélessége
    gap   = 0.18         # rés a két szám között (normalizált)
    total = 2 * num_w + gap
    x4_off = -total / 2          # "4" bal széle
    x0_off = -total / 2 + num_w + gap   # "0" bal széle

    lines = []
    for raw_strokes, x_base in [(s4_raw, x4_off), (s0_raw, x0_off)]:
        for stroke in raw_strokes:
            pts = []
            for nx, ny in stroke:
                lx = (nx + x_base - total / 2 + total / 2) * scale  # újracentrálva
                # Egyszerűbb: eltolt x koordináta
                lx = ((nx + x_base) - (x4_off + x0_off + num_w) / 2) * scale
                ly = (ny - 0.5) * scale
                rx = lx * ca - ly * sa
                ry = lx * sa + ly * ca
                pts.append((cx + rx, cy + ry))
            if len(pts) >= 2:
                lines.append(LineString(pts))
    return lines


def score_config(cx, cy, scale, angle_deg, buf_frac=0.035):
    """Pontozás: hány méternyi utca esik a sablon buffer-zónájába."""
    strokes = build_strokes(cx, cy, scale, angle_deg)
    buf = scale * buf_frac
    zone = unary_union([s.buffer(buf) for s in strokes])
    # Fedett utcahossz / sablon teljes hossza → arányos illeszkedés
    covered = all_streets.intersection(zone).length
    template_len = sum(s.length for s in strokes)
    return covered / (template_len + 1e-9), strokes


# ── 3. Rácsos keresés (durva → finom) ────────────────────────────────────────
print("Legjobb illeszkedés keresése...")

scales  = np.linspace(city_w * 0.22, city_w * 0.55, 5)
angles  = np.linspace(-25, 25, 7)
xs      = np.linspace(bbox[0] + city_w * 0.18, bbox[2] - city_w * 0.18, 5)
ys      = np.linspace(bbox[1] + city_h * 0.18, bbox[3] - city_h * 0.18, 5)

best_score  = -1
best_params = None
total_iter  = len(scales) * len(angles) * len(xs) * len(ys)
i = 0

for scale in scales:
    for angle in angles:
        for x in xs:
            for y in ys:
                sc, _ = score_config(x, y, scale, angle)
                if sc > best_score:
                    best_score = sc
                    best_params = (x, y, scale, angle)
                i += 1
                if i % 100 == 0:
                    print(f"  {i}/{total_iter} | legjobb: {best_score:.3f}", end="\r")

print(f"\n\nLegjobb konfiguráció:")
bx, by, bscale, bangle = best_params
print(f"  pozíció: ({bx:.0f}, {by:.0f})")
print(f"  méret:   {bscale:.0f} m")
print(f"  szög:    {bangle:.1f}°")
print(f"  score:   {best_score:.3f}")

# ── 4. Finomítás a legjobb pont körül ────────────────────────────────────────
print("Finomítás...")
fine_scores = []
for da in np.linspace(-8, 8, 9):
    for ds in np.linspace(0.85, 1.15, 5):
        for dx in np.linspace(-city_w*0.05, city_w*0.05, 5):
            for dy in np.linspace(-city_h*0.05, city_h*0.05, 5):
                sc, _ = score_config(bx+dx, by+dy, bscale*ds, bangle+da)
                fine_scores.append((sc, bx+dx, by+dy, bscale*ds, bangle+da))

fine_scores.sort(reverse=True)
best_score, bx, by, bscale, bangle = fine_scores[0]
print(f"  finomított score: {best_score:.3f}, szög: {bangle:.1f}°")

# ── 5. Végső kiemelés ─────────────────────────────────────────────────────────
_, best_strokes = score_config(bx, by, bscale, bangle)
buf = bscale * 0.035
zone = unary_union([s.buffer(buf) for s in best_strokes])

edges_proj = edges_proj.copy()
edges_proj["is_40"] = edges_proj.geometry.intersects(zone)
print(f"Kiemelt utcaszakasz: {edges_proj['is_40'].sum()} / {len(edges_proj)}")

# ── 6. Rajzolás ───────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 14), facecolor="#1a1a2e")
ax.set_facecolor("#1a1a2e")

edges_proj[~edges_proj["is_40"]].plot(ax=ax, color="#3a3a5c", linewidth=0.6, alpha=0.6)
edges_proj[ edges_proj["is_40"]].plot(ax=ax, color="#e63946", linewidth=3.5, alpha=0.95)

# sablon referenciavonal (szaggatott)
for s in best_strokes:
    xs2, ys2 = s.xy
    ax.plot(xs2, ys2, "--", color="#ffaa00", linewidth=1.0, alpha=0.35)

ax.set_title(
    f"Szigetszentmiklós – 40 minta (szög: {bangle:.1f}°, score: {best_score:.2f})",
    color="white", fontsize=14, pad=12
)
ax.set_axis_off()
plt.tight_layout()
plt.savefig("szigetszentmiklos_40_utcak3.png", dpi=180, bbox_inches="tight")
print("Kész: szigetszentmiklos_40_utcak3.png")
