"""
drw40_4.py – A munka2.jpg-ből kinyert kézzel rajzolt sablon alapján
keres hasonló utcamintákat Szigetszentmiklós utcahálózatán.

Javított változat: KD-fa alapú pontosságos sablon-illesztés.
"""
import osmnx as ox
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from shapely.geometry import MultiPoint
from shapely.ops import unary_union
from scipy.ndimage import binary_erosion, binary_dilation, label
from scipy.spatial import cKDTree
import warnings
warnings.filterwarnings("ignore")

# ── 1. Pink útvonal kinyerése és skeletonizálása ─────────────────────────────
print("Pink útvonal kinyerése munka2.jpg-ből...")
img_pil = Image.open("munka2.jpg")
img = np.array(img_pil)
img_h, img_w = img.shape[:2]

r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
mask = (r > 180) & (g < 100) & (b > 100) & (r > g + 80) & (b > g + 40)
print(f"  Pink pixelek: {mask.sum()}")

# Lyukak bezárása + vékonyítás ismételt erózióval (egyszerű skeleton)
closed = binary_dilation(mask, iterations=4)
# Skeleton: iteráltan erodáljuk, de megtartjuk a "gerincet"
skel = closed.copy()
for _ in range(6):
    eroded = binary_erosion(skel)
    skel = skel & ~(binary_dilation(eroded) & ~eroded)
# Ha a skeleton üres, visszaesünk az eredeti maszkra
if skel.sum() < 20:
    skel = mask

ys_img, xs_img = np.where(skel)
print(f"  Skeleton pixelek: {len(xs_img)}")

# Normalizálás 0..1 tartományba; y-t megfordítjuk (képkoord→geo irány)
xs_n = xs_img / img_w
ys_n = 1.0 - ys_img / img_h

# Mintavételezés (max 600 pont)
step = max(1, len(xs_n) // 600)
xs_t = xs_n[::step]
ys_t = ys_n[::step]

# Sablon középre igazítása (-0.5..0.5)
xs_t = xs_t - xs_t.mean()
ys_t = ys_t - ys_t.mean()

print(f"  Sablon pontok: {len(xs_t)}")
print(f"  Sablon kiterjedés: x [{xs_t.min():.3f}..{xs_t.max():.3f}], "
      f"y [{ys_t.min():.3f}..{ys_t.max():.3f}]")

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

# Utcapontok KD-fa (gyors nearest-neighbor)
print("KD-fa építése...")
street_pts = []
for geom in edges_proj.geometry:
    coords = list(geom.coords) if hasattr(geom, "coords") else []
    if not coords and hasattr(geom, "geoms"):
        for g in geom.geoms:
            coords.extend(list(g.coords))
    # Midsamplong: ne legyen túl sűrű
    for i, pt in enumerate(coords):
        if i % 2 == 0:
            street_pts.append(pt)

street_pts = np.array(street_pts)
tree = cKDTree(street_pts)
print(f"  Utcapontok száma: {len(street_pts)}")

# ── 3. Pontozó függvény: milyen arányban esnek a sablon pontjai utca közelébe ─
def score_config(cx, cy, scale, angle_deg, threshold_frac=0.038):
    angle = np.radians(angle_deg)
    ca, sa = np.cos(angle), np.sin(angle)

    lxs = xs_t * scale
    lys = ys_t * scale

    rxs = lxs * ca - lys * sa
    rys = lxs * sa + lys * ca

    gxs = cx + rxs
    gys = cy + rys

    pts = np.column_stack([gxs, gys])
    threshold = scale * threshold_frac
    dists, _ = tree.query(pts)
    return float((dists < threshold).mean())


# ── 4. Rácsos keresés (durva) ─────────────────────────────────────────────────
print("Rácsos keresés (durva)...")

scales  = np.linspace(city_w * 0.20, city_w * 0.60, 5)
angles  = np.linspace(-35, 35, 9)
xs_g    = np.linspace(bbox[0] + city_w * 0.12, bbox[2] - city_w * 0.12, 6)
ys_g    = np.linspace(bbox[1] + city_h * 0.12, bbox[3] - city_h * 0.12, 6)

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
                if i % 100 == 0:
                    print(f"  {i}/{total_iter} | legjobb: {best_score:.3f}", end="\r")

bx, by, bscale, bangle = best_params
print(f"\nDurva legjobb: score={best_score:.3f}, szög={bangle:.1f}°")

# ── 5. Finomítás ──────────────────────────────────────────────────────────────
print("Finomítás...")
fine = []
for da in np.linspace(-12, 12, 13):
    for ds in np.linspace(0.75, 1.25, 7):
        for dx in np.linspace(-city_w * 0.07, city_w * 0.07, 7):
            for dy in np.linspace(-city_h * 0.07, city_h * 0.07, 7):
                sc = score_config(bx + dx, by + dy, bscale * ds, bangle + da)
                fine.append((sc, bx + dx, by + dy, bscale * ds, bangle + da))

fine.sort(reverse=True)
best_score, bx, by, bscale, bangle = fine[0]
print(f"Finomított: score={best_score:.3f}, szög={bangle:.1f}°")
print(f"  pozíció: ({bx:.0f}, {by:.0f}), méret: {bscale:.0f} m")

# ── 6. Kiemelt utcák ──────────────────────────────────────────────────────────
angle  = np.radians(bangle)
ca, sa = np.cos(angle), np.sin(angle)
lxs = xs_t * bscale;  lys = ys_t * bscale
rxs = lxs * ca - lys * sa;  rys = lxs * sa + lys * ca
gxs = bx + rxs;  gys = by + rys

zone = MultiPoint(list(zip(gxs, gys))).buffer(bscale * 0.038)
edges_proj = edges_proj.copy()
edges_proj["is_match"] = edges_proj.geometry.intersects(zone)
print(f"Kiemelt utcaszakasz: {edges_proj['is_match'].sum()} / {len(edges_proj)}")

# ── 7. Vizualizáció ───────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(22, 10), facecolor="#1a1a2e")

# Bal: eredeti kézzel rajzolt sablon (kiemelve a skeleton)
ax0 = axes[0]
ax0.set_facecolor("#1a1a2e")
ax0.imshow(img, extent=[0, img_w, 0, img_h], aspect="auto")
# Skeleton pontok megjelenítése
sk_xs_img = xs_t / (img_w / img_w) * img_w + img_w / 2 + img_w / 2
# Egyszerűbb: visszaalakítjuk képkoordinátává
orig_xs = (xs_t / 1.0 + xs_t.mean() + 0.5) * img_w  # nem pontos, marad az eredeti mask
ys_img2, xs_img2 = np.where(mask)
ax0.scatter(xs_img2, img_h - ys_img2, c="cyan", s=0.5, alpha=0.7)
ax0.set_title("Eredeti rajz (munka2.jpg) + detektált pink útvonal", color="white", fontsize=12)
ax0.set_axis_off()

# Jobb: illesztett utcák
ax1 = axes[1]
ax1.set_facecolor("#1a1a2e")
edges_proj[~edges_proj["is_match"]].plot(
    ax=ax1, color="#3a3a5c", linewidth=0.6, alpha=0.6)
edges_proj[edges_proj["is_match"]].plot(
    ax=ax1, color="#e63946", linewidth=3.0, alpha=0.95)

# Sablon pontok megjelenítése a térképen
ax1.scatter(gxs, gys, c="yellow", s=0.8, alpha=0.3, label="sablon")

ax1.set_title(
    f"Illesztett utcák  (szög: {bangle:.1f}°, egyezés: {best_score*100:.0f}%)",
    color="white", fontsize=13
)
ax1.set_axis_off()

plt.tight_layout()
plt.savefig("szigetszentmiklos_40_utcak4.png", dpi=180, bbox_inches="tight")
print("Kész: szigetszentmiklos_40_utcak4.png")
