[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Catalog Reference
[Reference Catalogs](#reference-catalogs) | [Extending the Catalog](#extending-the-alpaca-pilot-catalog) | [Field Enumerations](#catalog-field-enumerations)

This page lists the reference catalogues behind Alpaca Pilot's catalog, and explains how to extend the catalog with your own entries. For how to search, filter and slew to catalog targets, see [Using the Catalog](./pilot.md#iv-using-the-catalog) in the Alpaca Pilot Guide.

## Reference Catalogs

Alpaca Pilot’s select list of objects are cross-referenced with more than 25 master catalogues, encompassing the most popular and scientifically significant deep-sky objects observed by both amateur and professional astronomers.



| Catalogue                       | Description                                                                       | Objects |
| ------------------------------- | --------------------------------------------------------------------------------- | ------- |
|| **General Catalogues** |
||
| **Messier (M)**                 | Classic list of 110 bright deep-sky objects compiled by Charles Messier (~1774).  | 110     |
| **Caldwell (Caldwell)**                | Patrick Moore’s 1995 complement to Messier, covering both hemispheres.            | 109     |
| **Herschel 400 (H)**        | 400 of William Herschel’s best nebulae and clusters from his 18th-century survey. | 400     |
| **New General Catalogue (NGC)** | The main reference catalogue for deep-sky objects (~1888).                        | 7,840   |
| **Index Catalogue (IC)**        | Supplement to the NGC with later discoveries (~1912).                             | 5,386   |
| **Henry Draper (HD)** | Comprehensive stellar catalogue listing over 225,000 stars, compiled at Harvard College Observatory (1918–1924). Each star is identified by spectral type and magnitude.| 225,300+ |
||
|| **Galaxy Catalogues** |
||
| **Abell**         | Clusters of galaxies—the largest bound structures in the universe (~1958). | 4,073   |
| **Arp**           | Atlas of 338 “peculiar” or interacting galaxies (~1966).                   | 338     |
| **Hickson** | Compact groups of small, closely packed galaxies (~1982).                  | 100     |
| **PGC**           | Principal Galaxies Catalogue—comprehensive all-sky galaxy list (~1995).    | 73,197  |
| **UGC**           | Uppsala General Catalogue—northern hemisphere galaxies (~1973).            | 12,921  |
||
|| **Planetary Nebulae Catalogues** |
||
| **Abell**         | Old planetary nebulae from Palomar Sky Survey (~1966).     | 86      |
| **Minkowski** | PNe discovered in the 1940s; includes the M 1–4 series.    | 207     |
| **Kohoutek**  | Extensive PN survey by Luboš Kohoutek (~1967).             | 1,500   |
| **Griffiths**     | Modern visual selection of bright, interesting PN (~2012). | 45      |
||
|| **Nebulae Catalogues** |
||
| **Barnard**     | Classic dark nebulae photographed by E.E. Barnard (~1927). | 349     |
| **LDN**             | Lynds Dark Nebulae from Palomar survey (~1962).            | 1,802   |
| **LBN**             | Lynds Bright Nebulae—bright diffuse nebulosity (~1965).    | 1,025   |
| **Sharpless (Sh 2-)** | Emission nebulae and H II regions (~1959).                 | 313     |
| **RCW**             | Southern emission nebulae (~1960).                         | 182     |
| **Gum**         | Southern H II regions catalogue (~1955).                   | 85      |
| **vdB**             | Reflection nebulae (~1966).                                | 159     |
| **SNR**             | Galactic Supernova Remnants (~1984).                       | 294     |
||
|| **Other Special Catalogues** |
||
| **Hidden Treasures (HT)**  | Stephen O’Meara’s list of 109 overlooked but beautiful objects (~2007).        | 109     |
| **Secret Deep (SD)**       | Further 109 deep-sky highlights not in Messier or Caldwell (~2011).            | 109     |
| **Orphaned Beauties (OB)** | Astrophotography-focused list of 109 large, under-appreciated objects (~2020). | 109     |
| **Small Packages (SP)**    | 109 compact but fascinating small targets (~2020).                             | 109     |
| **Satellites (ID)**    | NORAD-tracked artificial objects with known brightness and motion (~ongoing).  | 32k+    |
| **Solar System Bodies (IAU)**  | IAU-designated planetary and lunar objects including Sun, Moon, Planets, Moons | 30+     |

<br>
<br>

## Extending the Alpaca Pilot Catalog

Alpaca Pilot includes a built-in deep-sky catalog, planetary data, and live orbital objects.
However, you may also **extend the catalog with your own custom entries**, including local landmarks, favourite observing targets, or additional DSOs not included in the standard database.

Custom items are defined in a file named **`catalog.json`** placed in the Alpaca Driver’s *data directory*.

Whenever Alpaca Pilot loads or you refresh a catalog page (via **F5**), the Pilot application requests this file from the Driver. If it exists and contains valid entries, those entries are **merged directly into the main catalog** and displayed alongside all standard objects. 

Once loaded, your user-defined entries are fully integrated into Alpaca Pilot. They appear alongside the standard catalog and support all normal features, including search, filtering, sorting, and object interaction.

### File Format Overview

A sample file named **`catalog.sample.json`** is included in the *data directory* to help you get started.

To create your own custom catalog entries, simply copy this file to **`catalog.json`** and edit/add the values as needed. The sample outlines the required structure and field names, making it easy to add, remove, or modify entities with confidence.

Your custom **`catalog.json`** file must follow standard JSON rules:

* The **top-level structure must be an array** (`[...]`)
* Each catalog entry must be an **object** with quoted field names (`"Name": "Example`")
* **Field Names and Strings** must be quoted
* **Commas** are required between fields and entries
* **full-line comments** beginning with `//` are allowed
* **trailing commas** on the last field or entry are allowed


### Required Structure of an Entry

Each entry in `catalog.json` must follow the structure below.
All fields are optional except `MainID`, `Name`, and at least one co-ordinate pair 
* `RA_hr`, `Dec_deg` - Equatorial Co-ordinates of the entity 
* `Az_deg`, `Alt_deg` - Topocentric Co-ordinates, only relevant for Landmarks ie C1=9

Adding the other fields provides richer detail and better UI integration.

```jsonc
{
  "MainID": string,     // A unique identifier for the object (e.g. "U001")
  "Name": string,       // Short human-readable name
  "Notes": string,      // Longer description shown in the UI
  "Class": string,      // Optional Class Object Classification Codes see below (e.g. "SHO")
  "OtherIDs": string,   // Comma-separated alternate identifiers

  "Rt": integer,        // Rating 0–5 (Showcase → Not recommended)
  "Vz": integer,        // Visibility class 0–7
  "Sz": integer,        // Apparent size class 0–8

  "C1": integer,        // Object Type (Galaxy, Nebula, Planet, Landmark, etc.)
  "C2": integer,        // Subtype (Spiral Galaxy, Emission Nebula, etc.)
  "Cn": integer,        // Constellation index (0–84)

  "RA_hr": float,       // Right Ascension (hours)
  "Dec_deg": float,     // Declination (degrees)

  // OR, for Landmarks where C1=9, fixed non-celestial objects:
  "Az_deg": float,      // Azimuth position (degrees)
  "Alt_deg": float      // Altitude position (degrees)
}
```



## Catalog Field Enumerations

Several fields in the custom catalog use numeric codes rather than text labels. Alpaca Pilot converts these codes into readable descriptions for display. The tables below define every possible value for each enumeration.


### **Rating (Rt)**

Represents an overall “quality” or showcase value of the object.

| Value | Meaning             |
| ----- | ------------------- |
| **5** | Showcase (Top 2%) (Default)  |
| **4** | Excellent (Top 10%) |
| **3** | Good (Top 25%)      |
| **2** | Typical             |
| **1** | Challenging         |
| **0** | Not recommended     |


### **Visibility (Vz)**

Approximate naked-eye or binocular visibility based on magnitude.

| Value | Meaning               |
| ----- | --------------------- |
| **0** | Ultra Faint (Mag 12+) |
| **1** | Ghostly (Mag 10–12)   |
| **2** | Faint (Mag 8–10)      |
| **3** | Dim (Mag 6–8)         |
| **4** | Visible (Mag 4–6)     |
| **5** | Bright (Mag 2–4)      |
| **6** | Brilliant (Mag <2)    |
| **7** | Unknown  (Default)    |


### **Size (Sz)**

Apparent angular size of the object.

| Value | Meaning            |
| ----- | ------------------ |
| **0** | Very Tiny (<0.5′)  |
| **1** | Tiny (0.5–1′)      |
| **2** | Small (1–2′)       |
| **3** | Compact (2–5′)     |
| **4** | Moderate (5–10′)   |
| **5** | Prominent (10–30′) |
| **6** | Extended (30–100′) |
| **7** | Expansive (100′+)  |
| **8** | Unknown  (Default) |


### **Primary Type (C1)**

The high-level category of object.

| Value | Meaning                       |
| ----- | ----------------------------- |
| **0** | Nebula                        |
| **1** | Galaxy                        |
| **2** | Cluster                       |
| **3** | Star                          |
| **4** | Planet                        |
| **5** | Moon                          |
| **6** | Satellite                     |
| **7** | Comet                         |
| **8** | Asteroid                      |
| **9** | Landmark (for Az/Alt)         |
| **10** | Custom (Default)             |

### **Subtype (C2)**

A more specific classification depending on the primary type.
All values are listed for completeness.

| Value | Meaning                   |
| ----- | ------------------------- |
| 0     | Set of Chained Galaxies   |
| 1     | Set of Clustered Galaxies |
| 2     | Set of Grouped Galaxies   |
| 3     | Set of Merging Galaxies   |
| 4     | Pair of Galaxies          |
| 5     | Trio of Galaxies          |
| 6     | Blue Compact Dwarf Galaxy |
| 7     | Collisional Ring Galaxy   |
| 8     | Dwarf Galaxy              |
| 9     | Elliptical Galaxy         |
| 10    | Flocculent Galaxy         |
| 11    | Lenticular Galaxy         |
| 12    | Magellanic Galaxy         |
| 13    | Polar Galaxy              |
| 14    | Spiral Galaxy             |
| 15    | Dark Nebula               |
| 16    | Emission Nebula           |
| 17    | Molecular Cloud Nebula    |
| 18    | Planetary Nebula          |
| 19    | Protoplanetary Nebula     |
| 20    | Reflection Nebula         |
| 21    | Supernova Remnant Nebula  |
| 22    | Globular Cluster          |
| 23    | Herbig–Haro Object        |
| 24    | Nova Object               |
| 25    | Open Cluster              |
| 26    | Star                      |
| 27    | Star Cloud                |
| 28    | Young Stellar Object      |
| 29    | Planet                    |
| 30    | Dwarf Planet              |
| 31    | Martian Moon              |
| 32    | Galilean Moon             |
| 33    | Saturnian Moon            |
| 34    | Natural Satellite         |
| 35    | Space Station             |
| 36    | Satellite                 |
| 37    | Rocket Body               |
| 38    | Space Debris              |
| 39    | Comet                     |
| 40    | Asteroid                  |
| 41    | User-Defined (Default)    |



### **Constellation (Cn)**

Each number corresponds to a constellation by index.

| Value | Constellation                   |
| ----- | ------------------------------- |
| 0     | Andromeda                       |
| 1     | Antlia                          |
| 2     | Apus                            |
| 3     | Aquila                          |
| 4     | Aquarius                        |
| 5     | Ara                             |
| 6     | Aries                           |
| 7     | Auriga                          |
| 8     | Boötes                          |
| 9     | Canis Major                     |
| 10    | Canis Minor                     |
| 11    | Canes Venatici                  |
| 12    | Camelopardalis                  |
| 13    | Capricornus                     |
| 14    | Carina                          |
| 15    | Cassiopeia                      |
| 16    | Centaurus                       |
| 17    | Cepheus                         |
| 18    | Cetus                           |
| 19    | Chamaeleon                      |
| 20    | Circinus                        |
| 21    | Cancer                          |
| 22    | Columba                         |
| 23    | Coma Berenices                  |
| 24    | Corona Australis                |
| 25    | Corona Borealis                 |
| 26    | Crater                          |
| 27    | Crux                            |
| 28    | Corvus                          |
| 29    | Cygnus                          |
| 30    | Delphinus                       |
| 31    | Dorado                          |
| 32    | Draco                           |
| 33    | Eridanus                        |
| 34    | Fornax                          |
| 35    | Gemini                          |
| 36    | Grus                            |
| 37    | Hercules                        |
| 38    | Horologium                      |
| 39    | Hydra                           |
| 40    | Leo Minor                       |
| 41    | Lacerta                         |
| 42    | Leo                             |
| 43    | Lepus                           |
| 44    | Libra                           |
| 45    | Lupus                           |
| 46    | Lynx                            |
| 47    | Lyra                            |
| 48    | Mensa                           |
| 49    | Microscopium                    |
| 50    | Monoceros                       |
| 51    | Musca                           |
| 52    | Norma                           |
| 53    | Octans                          |
| 54    | Ophiuchus                       |
| 55    | Orion                           |
| 56    | Pavo                            |
| 57    | Pegasus                         |
| 58    | Perseus                         |
| 59    | Phoenix                         |
| 60    | Pictor                          |
| 61    | Piscis Austrinus                |
| 62    | Pisces                          |
| 63    | Puppis                          |
| 64    | Pyxis                           |
| 65    | Reticulum                       |
| 66    | Sculptor                        |
| 67    | Scorpius                        |
| 68    | Scutum                          |
| 69    | Serpens                         |
| 70    | Sextans                         |
| 71    | Sagitta                         |
| 72    | Sagittarius                     |
| 73    | Taurus                          |
| 74    | Telescopium                     |
| 75    | Triangulum Australe             |
| 76    | Triangulum                      |
| 77    | Tucana                          |
| 78    | Ursa Major                      |
| 79    | Ursa Minor                      |
| 80    | Vela                            |
| 81    | Virgo                           |
| 82    | Volans                          |
| 83    | Vulpecula                       |
| 84    | Orbit (Ephemeris-based objects) |
| 85    | Space (Default)                 |


### **Class - Object Classification Codes**
Objects in the standard catalog may include a **Class** field that helps guide your imaging strategy. This classification provides insight into the physical characteristics of the target and can inform choices such as filter selection and exposure balance.

For emission nebulae, the **Class** field indicates the narrowband emission types present and their relative signal strengths. For example, the Eagle Nebula (M16) has a Class of `SHO-.2/1/.3`

This means the nebula emits **Sulphur II (SII)**, **Hydrogen-alpha (Hα)**, and **Oxygen III (OIII)** in an approximate **20% / 100% / 30%** ratio. In practical terms, to balance the channels, weaker signals require **more integration time**:
* If you collect **10 minutes of Hα**
* You would need approximately:
  * **50 minutes of SII** (1 / 0.2 × 10)
  * **33 minutes of OIII** (1 / 0.3 × 10)

These ratios are **guidelines**, not strict rules. Actual exposure balance will depend on:
* Optical speed (f-ratio)
* Sensor quantum efficiency per wavelength
* Sky conditions and light pollution
* Target altitude and extinction

The full definition of the Class field depends on the C2 SubType of the target as follows:

#### Individual Galaxies - **Format:** `a/b` where

##### Galaxy Type (`a`)
* **S** — Spiral
* **SB** — Barred Spiral
* **S0** — Lenticular
* **SB0** — Barred Lenticular
* **E** — Elliptical
  * *E0* (nearly spherical) to *E7* (highly elongated)
* Spiral Subtypes
   * **a** — Large bulge, tightly wrapped smooth arms
   * **b** — Medium bulge, moderately open arms
   * **c** — Small bulge, open or patchy arms

##### Galaxy Features (`b`)

**Core**
* **l** — Barlens
* **p** — Peanut-shaped (X-shaped)
* **z** — Barred

**Disk**
* **d** — Edge-on
* **f** — Face-on
* **g** — Grand design (two strong symmetric arms)
* **k** — VV rows
* **t** — Superthin
* **w** — Warped

**Rings**
* **m** — Ring (concentric)
* **n** — Nuclear ring
* **o** — Outer ring
* **r** — Inner ring (mid-region)

**Star Streams**
* **h** — Shells
* **j** — Loops
* **u** — Single tail
* **x** — Dual tails
* **y** — Superlong

---

#### Multiple Galaxies - **Format:** `a` where

##### Number / Arrangement (`a`)
* **Cluster** — More than 12 galaxies
* **Group** — 12 or fewer galaxies
* **Chain** — More than 3 galaxies aligned along the line of sight

---

#### Galaxy Mergers - **Format:** `a/b` where

##### Merger Type (`a`)
* **I** — Long bridge (> 1 galaxy diameter)
* **II** — Short bridge (< 1 galaxy diameter, disks not touching)
* **III** — Two close cores, disks touching
* **IV** — Single core with tails
* **V** — Single core, no visible tails

##### Galaxy Features (`b`)
* Uses the same feature codes listed under *Individual Galaxies*.

---

#### Planetary Nebulae (PN) - **Format:** `abc/d` where

##### Shape (`a`)
* **A** — Ancient
* **B** — Bipolar
* **E** — Elliptical
* **M** — Multipolar
* **P** — Peculiar
* **S** — Spherical
* **X** — Stellar (≤ 0.2 arcmin diameter)

##### Signal (`b`)
* **O** — OIII dominant (cyan)
* **H** — Hα dominant (red)
* **C** — OIII and Hα comparable (gray)
* **R** — Hα rim with OIII interior

##### Progenitor Visibility (`c`)
* **Y** — Visible
* **N** — Not visible

##### PN Features (`d`)
* **c** — Bipolar lobes broken through
* **f** — Bright filaments
* **h** — Hexagonal shape
* **i** — ISM interaction
* **j** — Polar jets
* **o** — Owl (M97-type) / inner voids
* **q** — Opposing brightened rim segments
* **r** — Bright toroidal ring
* **t** — Thin rim
* **y** — Ansae

---

#### Emission Nebulae - **Format:** `a/b` where

##### Emission Type (`a`)
* **SHO** — All narrowband channels present
* **HII** — Hα dominant
* **SS** — Strömgren sphere
* **WR** — Wolf–Rayet nebula

##### Signal Strengths (`b`)
* Comparative strengths of SHO channels, normalized to the strongest signal

---

#### Dark Nebulae - **Format:** `a` where

##### Opacity Rating (`a`)
* **1** — Lightest
* **6** — Darkest
* **0** — Extremely faint

---

#### Globular Clusters - **Format:** `a` where

##### Shapley–Sawyer Concentration (`a`)
* **I** — Highly concentrated core
* **XII** — Very loose concentration

---

#### Open Clusters - **Format:** `a-b-c-d`

##### Trumpler Classification
* **a** — Concentration
  * **I** (strong) to **IV** (none)
* **b** — Brightness Range
  * **1** (uniform brightness) to **3** (wide brightness range)
* **c** — Number of stars
* **d** — Additional designations
  * **a** — Asterism
