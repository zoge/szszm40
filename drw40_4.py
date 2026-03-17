"""
drw40_4.py – A munka2.jpg-ből kinyert kézzel rajzolt sablon alapján
keres hasonló utcamintákat Szigetszentmiklós utcahálózatán.
"""
import osmnx as ox
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from shapely.geometry import MultiPoint, LineString
from shapely.ops import unary_union
import warnings
warnings.filterwarnings("ignore")

# ── 1. Pink útvonal kinyerése a munka2.jpg-ből ───────────────────────────────
print("Pink útvonal kinyerése munka2.jpg-ből...")
img = np.array(Image.open("munka2.jpg"))
r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
# Magenta/pink szín detektálás
mask = (r > 180) & (g < 100) & (b > 100) & (r > g + 80) & (b > g + 40)

ys, xs = np.where(mask)
print(f"  Pink pixelek: {len(xs)}")

# Normalizálás 0..1 tartományba (y tengelyt megfordítjuk: képkoord → geo irány)
img_h, img_w = img.shape[:2]
xs_n = xs / img_w          # 0..1
ys_n = 1.0 - ys / img_h   # y-tengely megfordítása (képen lefelé = geo-ban felfelé)

# Mintavételezés: ne legyen túl sok pont (max 500)
step = max(1, len(xs_n) // 500)
xs_s = xs_n[::step]
ys_s = ys_n[::step]

print(f"  Mintavételezett pontok: {len(xs_s)}")

# ── 2. Utcahálózat betöltése ──────────────────────────────────────────────────
print("Utcahálózat betöltése...")
G = ox.graph_from_place("Szigetszentmiklós, Hungary", network_type="drive")
G_proj = ox.project_graph(G)
nodes_proj, edges_proj = ox.graph_to_gdfs(G_proj)

bbox   = nodes_proj.total_bounds    # [minx, miny, maxx, maxy]
cx0    = (bbox[0] + bbox[2]) / 2
cy0    = (bbox[1] + bbox[3]) / 2
city_w = bbox[2] - bbox[0]
city_h = bbox[3] - bbox[1]

print("Utcahálózat unió...")
all_streets = unary_union(edges_proj.geometry.values)

# ── 3. Sablon alkalmazása: skálázás + forgatás + eltolás ─────────────────────
def build_template_zone(cx, cy, scale, angle_deg, buf_frac=0.030):
    """A normalizált pontokat transzformálja geo-koordinátákba."""
    angle = np.radians(angle_deg)
    ca, sa = np.cos(angle), np.sin(angle)

    # Normalizált koordináták középre igazítása (-0.5..0.5)
    lxs = (xs_s - 0.5) * scale
    lys = (ys_s - 0.5) * scale

    # Forgatás
    rxs = lxs * ca - lys * sa
    rys = lxs * sa + lys * ca

    # Pozicionálás
    gxs = cx + rxs
    gys = cy + rys

    pts = list(zip(gxs, gys))
    mp = MultiPoint(pts)
    buf = scale * buf_frac
    zone = mp.buffer(buf).simplify(buf * 0.5)
    return zone


def score_config(cx, cy, scale, angle_deg):
    zone = build_template_zone(cx, cy, scale, angle_deg)
    covered = all_streets.intersection(zone).length
    template_area = zone.area
    # Fedési arány: fedett utcahossz normalizálva a sablon területével
    city_street_density = all_streets.length / (city_w * city_h)
    expected = city_street_density * template_area
    return covered / (expected + 1e-9)


# ── 4. Rácsos keresés ────────────────────────────────────────────────────────
print("Rácsos keresés (durva)...")

scales  = np.linspace(city_w * 0.20, city_w * 0.55, 5)
angles  = np.linspace(-30, 30, 7)
xs_g    = np.linspace(bbox[0] + city_w * 0.15, bbox[2] - city_w * 0.15, 5)
ys_g    = np.linspace(bbox[1] + city_h * 0.15, bbox[3] - city_h * 0.15, 5)

best_score  = -1
best_params = None
total_iter  = len(scales) * len(angles) * len(xs_g) * len(ys_g)
i = 0

for scale in scales:
    for angle in angles:
        for xg in xs_g:
            for yg in ys_g:
                sc = score_config(xg, yg, scale, angle)
                if sc > best_score:
                    best_score = sc
                    best_params = (xg, yg, scale, angle)
                i += 1
                if i % 50 == 0:
                    print(f"  {i}/{total_iter} | legjobb: {best_score:.3f}", end="\r")

bx, by, bscale, bangle = best_params
print(f"\nDurva legjobb: score={best_score:.3f}, szög={bangle:.1f}°")

# ── 5. Finomítás ──────────────────────────────────────────────────────────────
print("Finomítás...")
fine = []
for da in np.linspace(-10, 10, 9):
    for ds in np.linspace(0.80, 1.20, 5):
        for dx in np.linspace(-city_w * 0.06, city_w * 0.06, 5):
            for dy in np.linspace(-city_h * 0.06, city_h * 0.06, 5):
                sc = score_config(bx + dx, by + dy, bscale * ds, bangle + da)
                fine.append((sc, bx + dx, by + dy, bscale * ds, bangle + da))

fine.sort(reverse=True)
best_score, bx, by, bscale, bangle = fine[0]
print(f"Finomított: score={best_score:.3f}, szög={bangle:.1f}°")
print(f"  pozíció: ({bx:.0f}, {by:.0f}), méret: {bscale:.0f} m")

# ── 6. Kiemelt utcák meghatározása ────────────────────────────────────────────
zone = build_template_zone(bx, by, bscale, bangle)
edges_proj = edges_proj.copy()
edges_proj["is_match"] = edges_proj.geometry.intersects(zone)
print(f"Kiemelt utcaszakasz: {edges_proj['is_match'].sum()} / {len(edges_proj)}")

# ── 7. Vizualizáció ───────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(20, 10), facecolor="#1a1a2e")

# Bal: eredeti kézzel rajzolt sablon
ax0 = axes[0]
ax0.set_facecolor("#1a1a2e")
ax0.imshow(img, extent=[0, img_w, 0, img_h], aspect="auto")
pink_ys_img = (1.0 - ys_s) * img_h
pink_xs_img = xs_s * img_w
ax0.scatter(pink_xs_img, pink_ys_img, c="cyan", s=1, alpha=0.5)
ax0.set_title("Eredeti rajz (munka2.jpg)", color="white", fontsize=13)
ax0.set_axis_off()

# Jobb: illesztett utcák
ax1 = axes[1]
ax1.set_facecolor("#1a1a2e")
edges_proj[~edges_proj["is_match"]].plot(
    ax=ax1, color="#3a3a5c", linewidth=0.6, alpha=0.6)
edges_proj[edges_proj["is_match"]].plot(
    ax=ax1, color="#e63946", linewidth=3.0, alpha=0.95)

# Sablon kontúr (szaggatott)
if hasattr(zone, "exterior"):
    zx, zy = zone.exterior.xy
    ax1.plot(zx, zy, "--", color="#ffaa00", linewidth=0.8, alpha=0.35)
elif hasattr(zone, "geoms"):
    for geom in zone.geoms:
        if hasattr(geom, "exterior"):
            zx, zy = geom.exterior.xy
            ax1.plot(zx, zy, "--", color="#ffaa00", linewidth=0.8, alpha=0.35)

ax1.set_title(
    f"Illesztett utcák (szög: {bangle:.1f}°, score: {best_score:.2f})",
    color="white", fontsize=13
)
ax1.set_axis_off()

plt.tight_layout()
plt.savefig("szigetszentmiklos_40_utcak4.png", dpi=180, bbox_inches="tight")
print("Kész: szigetszentmiklos_40_utcak4.png")
