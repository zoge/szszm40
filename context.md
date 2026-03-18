# Szigetszentmiklós – 40-es felirat utcákon: Projekt kontextus

## A feladat lényege

Szigetszentmiklós utcahálózatára a **„40"** számjegy alakját kell ráilleszteni úgy,
hogy a szám körvonalait/szárait valódi utcaszakaszok rajzolják ki.
A projekt az OSMnx könyvtárral tölti le az utcahálózatot, majd különböző módszerekkel
keres illeszkedést a „4" és „0" sablonhoz.

---

## Verzók fejlődése

### drw40.py – Fontból kinyert vektor sablon
- `matplotlib.textpath.TextPath`-szal generált „40" betűkörvonal (DejaVu Sans Bold)
- A betűszár-szegmensek körül buffer-zóna (`city_w * 0.012` ≈ 60–80 m)
- Statikus elhelyezés: a felirat a város szélességének ~55%-a, középre igazítva
- **Korlát:** nincs keresés/optimalizálás, a sablon rögzített pozícióban áll

### drw40_2.py – Kézzel rajzolt egyszáras sablon
- A „4"-et 2 vonal definiálja: bal L-szár + vízszintes + jobb függőleges
- A „0"-t 60 pontos ellipszis közelíti (`np.linspace(0, 2π, 60)`)
- Skálázás: egy szám szélessége = `city_w * 0.30`, közük = `city_w * 0.06`
- Buffer: `city_w * 0.010`
- **Elv:** minimális, stilizált vonalak → jobban illeszkedik az utcarácsra

### drw40_3.py – Rácsos kereső + forgatás
- Durva rács: 5 méret × 7 szög (−25°…+25°) × 5×5 pozíció = 875 iteráció
- Finomítás: a legjobb köré ±8° × ±15% méret × ±5% pozíció
- **Pontszám (score):** fedett utcahossz / sablon teljes hossza
- **Elv:** nem kell előre tudni, hova essen a felirat – a keresés megtalálja

### drw40_4.py – Kézzel rajzolt sablon képből (munka2.jpg)
- Pink pixelek kinyerése: `r>180, g<100, b>100, r>g+80, b>g+40`
- Egyszerűsített skeleton: ismételt erózió + eredeti mask fallback
- **KD-fa alapú illesztés** (`scipy.spatial.cKDTree`): a sablon pontjainak
  mekkora hányada esik utca közelében (threshold = `scale * 0.038`)
- Durva rács: 5 méret × 9 szög × 6×6 pozíció = 1620 iteráció
- Finomítás: ±12° × ±25% méret × ±7% pozíció (13×7×7×7 = 3969 lépés)
- **Korlát:** a skeleton-algoritmus egyszerű, komplex rajznál hiányos lehet

---

## Ismétlődő tervezési elvek

| Elv | Megjelenés |
|-----|-----------|
| Vetített koordináta-rendszer | Mindig `ox.project_graph` → méterben számolunk |
| Buffer-tolerancia | 1–3,8% a sablon méretéhez képest |
| Durva → finom keresés | drw40_3, drw40_4 |
| Sötét háttér vizualizáció | `#1a1a2e` alap, `#e63946` kiemelt utcák |
| Szaggatott sablon-overlay | Ellenőrzéshez minden verzióban |

---

## Nyitott kérdések / továbblépési irányok

1. **Score definíció:** a fedett utcahossz vs. sablon-pontok közelsége eltérő
   eredményt adhat; melyik megbízhatóbb?
2. **Skeleton minősége:** a `munka2.jpg` pink maszkjából nyert vonal töredékes
   lehet – érdemes lenne valódi skeletonizációs algoritmust (pl. `skimage.morphology.skeletonize`) alkalmazni.
3. **Illeszkedési küszöb:** a buffer/threshold értéke kritikus – túl nagy esetén
   minden utca „egyezik", túl kicsi esetén semmi sem.
4. **Szimmetria:** a „0" ellipszis illeszkedhet tükrözve is; a „4" forgatási
   szimmetriája korlátozott, de tükörképe tévesen jó pontszámot adhat.
5. **Több megoldás:** a rácsos keresés a globális maximumot nem garantálja – érdemes
   több legjobb jelöltet megőrizni és megjeleníteni.

---

## Jellemző pontok Szigetszentmiklóson

### Az egyszáras 4 körvonalát leíró pontok

Ezekre a valós csomópontokra illeszthető az egyszáras „4" sablon:

| Neve | Szélesség (lat) | Hosszúság (lon) |
|------|----------------|----------------|
| Katolikus templom körforgalom | 47.34575412670619 | 19.04091169468922 |
| Gyári úti körforgalom | 47.337975104395916 | 19.035786208780905 |
| Gyár 2 körforgalom | 47.33823188438878 | 19.041848857524084 |
| Kéktó-sarok | 47.33644977218012 | 19.04273364657472 |

### Az egyszáras 0 körvonalát leíró pontok

| Neve | Szélesség (lat) | Hosszúság (lon) |
|------|----------------|----------------|
| Sárgaház sarok | 47.34464826784159| 19.042064737476498 |
| Sétány büfé | 47.34005012463215 | 19.048464593299702 |
| Dunapart | 47.34325070552266 | 19.052555473911458 |
| Ádám Jenő emlékház | 47.34654382509927| 19.047297571138635 |

### Összefoglaló: koordináta-listák Python-formátumban

```python
# 40-es útvonalszám illesztési pontjai mely a 4 és a 0 vonalakból kellene állnia

# "4" alakzat sarokpontjai (lat, lon)
points_4 = {
    "katolikus_templom_korforgalom": (47.34575412670619, 19.04091169468922),
    "gyari_uti_korforgalom":         (47.337975104395916, 19.035786208780905),
    "gyar2_korforgalom":             (47.33823188438878, 19.041848857524084),
    "kekto_sarok":                   (47.33644977218012, 19.04273364657472),
}

# "0" alakzat referenciapont (lat, lon)
points_0 = {
    "noske": (47.341211, 19.044253),
    "setany_bufe":  (47.34005012463215, 19.048464593299702),
    "dunapart":     (47.34325070552266, 19.052555473911458),
    "hev_allomas":  (47.34437139832502, 19.04981420414185),
}
```

---

## Fájlstruktúra

| Fájl | Leírás |
|------|--------|
| `drw40.py` | Font-alapú sablon, statikus elhelyezés |
| `drw40_2.py` | Egyszáras kézzel rajzolt sablon, statikus |
| `drw40_3.py` | Egyszáras sablon + rácsos kereső + forgatás |
| `drw40_4.py` | Képből kinyert pink sablon + KD-fa illesztő |
| `munka2.jpg` | Kézzel rajzolt sablon forrásképe |
| `szigetszentmiklos_40_utcak.png` | drw40.py kimenete |
| `szigetszentmiklos_40_utcak2.png` | drw40_2.py kimenete |
| `szigetszentmiklos_40_utcak3.png` | drw40_3.py kimenete |
| `szigetszentmiklos_40_utcak4.png` | drw40_4.py kimenete |
| `context.md` | Ez a fájl – projekt összefoglaló |
