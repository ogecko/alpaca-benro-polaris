import axios from 'axios'
import { defineStore, acceptHMRUpdate } from 'pinia'
// import { sleep } from 'src/utils/sleep'
import { AppVisibility } from 'quasar'
import { useStatusStore } from './status'
import { useConfigStore } from './config'
import { getAzAlt, hrToDeg, toDeg, toRad } from 'src/utils/angles'
import { toRaw } from 'vue'
import { useDeviceStore } from './device'
// # Total Number of Objects:  3289
// #  ../pilot/public/catalog_top25_lg.json 556
// #  ../pilot/public/catalog_top25_sm.json 413
// #  ../pilot/public/catalog_typical_md.json 1714
// # Rt:  {5: 'Showcase (Top 2%)', 4: 'Excellent (Top 10%)', 3: 'Good (Top 25%)', 2: 'Typical', 1: 'Challenging', 0: 'Not recommended'}
// # Vz:  {0: 'Ultra Faint (Mag 12+)', 1: 'Ghostly (Mag 10-12)', 2: 'Faint (Mag 8-10)', 3: 'Dim (Mag 6-8)', 4: 'Visible (Mag 4-6)', 5: 'Bright (Mag 2-4)', 6: 'Brilliant (Mag <2)', 7: 'Unknown'}
// # Sz:  {0: 'Very-Tiny (<0.5′)', 1: 'Tiny (0.5–1′)', 2: 'Small (1–2′)', 3: 'Compact (2–5′)', 4: 'Moderate (5–10′)', 5: 'Prominent (10–30′)', 6: 'Extended (30–100′)', 7: 'Expansive (100′+)', 8: 'Unknown'}
// # C1:  {0: 'Nebula', 1: 'Galaxy', 2: 'Cluster', 3: 'Star', 4: 'Planet', 5: 'Moon'}
// # C2:  {0: 'Set of Chained Galaxies', 1: 'Set of Clustered Galaxies', 2: 'Set of Grouped Galaxies', 3: 'Set of Merging Galaxies', 4: 'Pair of Galaxies', 5: 'Trio of Galaxies', 6: 'Blue Compact Dwarf Galaxy', 7: 'Collisional Ring Galaxy', 8: 'Dwarf Galaxy', 9: 'Elliptical Galaxy', 10: 'Flocculent Galaxy', 11: 'Lenticular Galaxy', 12: 'Magellanic Galaxy', 13: 'Polar Galaxy', 14: 'Spiral Galaxy', 15: 'Dark Nebula', 16: 'Emission Nebula', 17: 'Molecular Cloud Nebula', 18: 'Planetary Nebula', 19: 'Protoplanetary Nebula', 20: 'Reflection Nebula', 21: 'Supernova Remnant Nebula', 22: 'Globular Cluster', 23: 'Herbig-Haro Object', 24: 'Nova Object', 25: 'Open Cluster', 26: 'Star', 27: 'Star Cloud', 28: 'Young Stellar Object', 29: 'Planet', 30: 'Dwarf Planet', 31: 'Martian Moon', 32: 'Galilean Moon', 33: 'Saturnian Moon', 34: 'Natural Satellite', 35: 'Space Station', 36: 'Satellite', 37: 'Rocket Body', 38: 'Space Debris', 39: 'Comet', 40: 'Asteroid'}
// # Cn:  {0: 'Andromeda', 1: 'Antlia', 2: 'Apus', 3: 'Aquila', 4: 'Aquarius', 5: 'Ara', 6: 'Aries', 7: 'Auriga', 8: 'Boötes', 9: 'Canis Major', 10: 'Canis Minor', 11: 'Canes Venatici', 12: 'Camelopardalis', 13: 'Capricornus', 14: 'Carina', 15: 'Cassiopeia', 16: 'Centaurus', 17: 'Cepheus', 18: 'Cetus', 19: 'Chamaeleon', 20: 'Circinus', 21: 'Cancer', 22: 'Columba', 23: 'Coma Berenices', 24: 'Corona Australis', 25: 'Corona Borealis', 26: 'Crater', 27: 'Crux', 28: 'Corvus', 29: 'Cygnus', 30: 'Delphinus', 31: 'Dorado', 32: 'Draco', 33: 'Eridanus', 34: 'Fornax', 35: 'Gemini', 36: 'Grus', 37: 'Hercules', 38: 'Horologium', 39: 'Hydra', 40: 'Leo Minor', 41: 'Lacerta', 42: 'Leo', 43: 'Lepus', 44: 'Libra', 45: 'Lupus', 46: 'Lynx', 47: 'Lyra', 48: 'Mensa', 49: 'Microscopium', 50: 'Monoceros', 51: 'Musca', 52: 'Norma', 53: 'Octans', 54: 'Ophiuchus', 55: 'Orion', 56: 'Pavo', 57: 'Pegasus', 58: 'Perseus', 59: 'Phoenix', 60: 'Pictor', 61: 'Piscis Austrinus', 62: 'Pisces', 63: 'Puppis', 64: 'Pyxis', 65: 'Reticulum', 66: 'Sculptor', 67: 'Scorpius', 68: 'Scutum', 69: 'Serpens', 70: 'Sextans', 71: 'Sagitta', 72: 'Sagittarius', 73: 'Taurus', 74: 'Telescopium', 75: 'Triangulum Australe', 76: 'Triangulum', 77: 'Tucana', 78: 'Ursa Major', 79: 'Ursa Minor', 80: 'Vela', 81: 'Virgo', 82: 'Volans', 83: 'Vulpecula', 84: 'Orbit'}
const p = useStatusStore()
const cfg = useConfigStore()
const dev = useDeviceStore()

let positionUpdateTimer: ReturnType<typeof setInterval> | null = null;
const defaultSorting = [
        { field: 'Rt', direction: 'desc' },
        { field: 'Sz', direction: 'desc' },
        { field: 'Name', direction: 'asc' }
    ] as { field: keyof CatalogItem; direction: 'asc' | 'desc' }[]

export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    orbs: {} as OrbitalExport,
    dsos: [] as CatalogItem[],
    dsoGotoed: undefined as CatalogItem | undefined,
    page: 1,
    pageSize: 10,
    selected: 0,
    searchFor: '',
    filter: {
        Rt: undefined as DsoRating[] | undefined,
        Sz: undefined as DsoSize[] | undefined,
        Vz: undefined as DsoBrightness[] | undefined,
        Cn: undefined as DsoConstellation[] | undefined,
        C1: undefined as DsoType[] | undefined,
        C2: undefined as DsoSubtype[] | undefined,
        Az: undefined as DsoAltitude[] | undefined,
        Alt: undefined as DsoAltitude[] | undefined,
    },
    sorting: [] as { field: keyof CatalogItem; direction: 'asc' | 'desc' }[],
  }),

  getters: {
    site_sidereal: () => p.siderealtime,  // current sidereal time
    site_lat: () => cfg.site_latitude,    // observing site latitude in dec deg
    site_lon: () => cfg.site_longitude,   // observing site longitude in dec deg
    cur_azimuth: () => p.azimuth,         // current azimuth of the telescope
    cur_altitude: () => p.altitude,       // current altitude of the telescope
    isVisible() {
        return AppVisibility.appVisible
    }, 
    filtered(): CatalogItem[] {
      const search = normalize(this.searchFor);

      return this.dsos.filter(dso => {
        const matchesFilter = Object.entries(this.filter).every(([key, value]) => {
          const fieldValue = dso[key as keyof CatalogItem];

          // Special case: Altitude filter default
          if (key === 'Alt') {
            const altFilter = ((value == null)  || (Array.isArray(value) && value.length === 0))
              ? ((search=='')? [1,2,3,4,5] : [0,1,2,3,4,5,6])   // default: exclude 0 and 6, unless search term then include all
              : value;                                          // use provided filter for altitude

            return altFilter.includes(fieldValue as DsoAltitude);
          }

          // General filter logic
          if (value == null || (Array.isArray(value) && value.length === 0)) return true;

          return Array.isArray(value)
            ? fieldValue != null && (value as (string | number)[]).includes(fieldValue)
            : fieldValue === value;
        });

        const matchesSearch = (search === '' || (dso.SearchText?.includes(search) ?? false));
        return matchesFilter && matchesSearch;
      });
    },
    isFiltered(): boolean {
        return Object.values(this.filter).some(value => {
            if (value == null) return false;
            if (Array.isArray(value)) return value.length > 0;
            return true;
        });
    },
    sorted(): CatalogItem[] {
        return [...this.filtered].sort((a, b) => {
            const effectiveSorting = this.sorting.length > 0 ? this.sorting : defaultSorting;
            for (const { field, direction } of effectiveSorting) {
            const valA = a[field];
            const valB = b[field];

            if (valA == null && valB == null) continue;
            if (valA == null) return 1;
            if (valB == null) return -1;

            if (valA > valB) return direction === 'asc' ? 1 : -1;
            if (valA < valB) return direction === 'asc' ? -1 : 1;
            // if equal, continue to next field
            }
            return 0;
        });
    },
    paginated(): CatalogItem[] {
        const start = (this.page - 1) * this.pageSize;
        return this.sorted.slice(start, start + this.pageSize);
    },
    numPages(): number {
        const pageSize = this.pageSize;
        return Math.ceil(this.filtered.length / pageSize);
    },
    C1Options() {
        const opt = Object.entries(typeLookup).map(([key, label]) => ({  label,  value: Number(key) as DsoType }))
        return opt
    },
    RtOptions() {
        const opt = Object.entries(ratingLookup).map(([key, label]) => ({  label,  value: Number(key) as DsoType })).reverse()
        return opt
    },
    VzOptions() {
        const opt = Object.entries(brightnessLookup).map(([key, label]) => ({  label,  value: Number(key) as DsoType })).reverse()
        if (opt.length>0 && opt[0]) opt[0].label = "Unknown"
        return opt
    },
    SzOptions() {
        const opt = Object.entries(sizeLookup).map(([key, label]) => ({  label,  value: Number(key) as DsoType })).reverse()
        return opt
    },
    C2Options(): { label: string; value: DsoSubtype }[] {
        const selectedTypes = this.filter.C1 ?? [];
        // If no C1 filter is applied, return all subtypes
        if (selectedTypes.length === 0) {
            return Object.entries(subtypeLookup).map(([key, label]) => ({ label, value: Number(key) as DsoSubtype }));
        }
        // Define subtype ranges for each DsoType
        const subtypeRanges: Record<DsoType, [number, number]> = {
            0: [15, 21], // Nebula
            1: [0, 14],  // Galaxy
            2: [22, 28], // Stellar (Cluster + Star)
            3: [22, 28],  // Star (merged with Stellar range)
            4: [29, 29], // Planet
            5: [30, 30], // Moon
        };
        // Collect all valid subtype keys based on selected C1 types
        const allowedSubtypes = new Set<number>();
        for (const type of selectedTypes) {
            const [start, end] = subtypeRanges[type] ?? [];
            for (let i = start; i <= end; i++) {
            allowedSubtypes.add(i);
            }
        }
        // Filter and map subtypeLookup
        return Object.entries(subtypeLookup)
            .filter(([key]) => allowedSubtypes.has(Number(key)))
            .map(([key, label]) => ({ label, value: Number(key) as DsoSubtype }));
    },
    AltOptions() {
        const opt = Object.entries(altitudeLookup).map(([key, label]) => ({  label,  value: Number(key) as DsoType })).reverse()
        return opt
    },

  },

  actions: {
    clearFilter() {
        this.filter.Rt = undefined;
        this.filter.Sz = undefined;
        this.filter.Vz = undefined;
        this.filter.Cn = undefined;
        this.filter.C1 = undefined;
        this.filter.C2 = undefined;
        this.filter.Az = undefined;
        this.filter.Alt = undefined;
        this.searchFor = '';
    },
    async catalogFetch() {
      this.orbs = await dev.getOrbitals()
      try {
        const resp = await axios.get('/catalog_top25_lg.json');
        if (resp.status !== 200) {
          throw new Error(`Unexpected status code: ${resp.status}`);
        }
        const raw = resp.data;
        // Optional: validate structure
        if (!Array.isArray(raw))  throw new Error('Catalog data is not an array');

        const enriched = raw.map((dso: CatalogItem) => ({
            ...dso,
            Rating: ratingLookup[dso.Rt],
            Visibility: visibilityLookup(dso.Vz, dso.Sz),
            Constellation: constellationLookup[dso.Cn],
            Type: typeLookupIcon[dso.C1],
            Subtype: subtypeLookup[dso.C2],
            SearchText: normalize(`${dso.MainID} ${dso.OtherIDs} ${dso.Name}`)
            }));

        this.dsos = enriched;
    } catch  {
        return []; // fallback to empty array
      }
    },
    updateDsoPositions() {
      const latDeg = this.site_lat;
      const lonDeg = this.site_lon;
      this.dsos = this.dsos.map(dso => {
        const { ra, dec } = getRaDec(dso, this.orbs)
        const { az, alt } = getAzAlt(ra, dec, latDeg, lonDeg); //Now
        const Az = enumAz(az)
        const Alt = enumAlt(alt)
        return {
          ...dso,
          Position: positionLookup(Az, Alt),
          RA_hr: ra,
          Dec_deg: dec,
          Az_deg: az,
          Alt_deg: alt,
          Az,
          Alt
        };
      });
    },
    startPositionUpdater() {
      if (positionUpdateTimer) return; // already running

      const tryStart = () => {
        const lat = this.site_lat;
        const lon = this.site_lon;

        if (typeof lon === 'number' && typeof lat === 'number') {
          this.updateDsoPositions(); // initial run

          positionUpdateTimer = setInterval(() => {
            this.updateDsoPositions();
          }, 15 * 60 * 1000); // every 15 minutes
        } else {
          setTimeout(tryStart, 10000); // retry in 10s
        }
      };
      tryStart();
    },
    stopPositionUpdater() {
      if (positionUpdateTimer) {
        clearInterval(positionUpdateTimer);
        positionUpdateTimer = null;
      }
    },
    updateDsoProximity(currentRA_hr: number, currentDec_deg: number) {
      const ra1 = toRad(hrToDeg(currentRA_hr));
      const dec1 = toRad(currentDec_deg);

      const updated = this.dsos.map(item => {
        const ra2 = toRad(hrToDeg(item.RA_hr));
        const dec2 = toRad(item.Dec_deg);
        // Angular separation using spherical law of cosines
        const cosAngle = Math.sin(dec1) * Math.sin(dec2) + Math.cos(dec1) * Math.cos(dec2) * Math.cos(ra1 - ra2);
        const angleRad = Math.acos(Math.min(Math.max(cosAngle, -1), 1));
        const angleDeg = toDeg(angleRad);
        return {
          ...toRaw(item), // strip reactivity from original item
          Proximity: angleDeg,
        };
      });

      // Replace the reactive array with a new one
      this.dsos = updated;
    }
  }
})

export type OrbitalExport = {
  [id: string]: {
    MainID: string;
    RA_hr?: number;
    DEC_deg?: number;
    Az_deg?: number;
    Alt_deg?: number;
    Proximity?: number;
  };
};


export interface CatalogItem {
  MainID: string;
  Name: string;
  Notes: string;
  Class: string | null;
  OtherIDs: string;
  Rt: DsoRating;
  Sz: DsoSize;
  Vz: DsoBrightness;
  Cn: DsoConstellation;
  C1: DsoType;
  C2: DsoSubtype;
  RA_hr: number;
  Dec_deg: number;
  // Enriched display fields
  Rating?: string;
  Visibility?: string;
  Constellation?: string;
  Type?: string;
  Subtype?: string;
  SearchText?: string;
  Alt_deg?: number;
  Az_deg?: number;
  Az?: DsoAzimuth; 
  Alt?: DsoAltitude; 
  Position?: string;
  Proximity?: number;
}

// ---------- Helpers




// Bin azimuth (8 compass directions, 45° each)
function enumAz(azDeg: number) {
  const azEnum: DsoAzimuth = Math.floor(((azDeg + 22.5) % 360) / 45) as DsoAzimuth;
  return azEnum
}

// Bin altitude
function enumAlt(altDeg: number) {
  let altEnum: DsoAltitude = 0;
  if (altDeg < 0) altEnum = 0;
  else if (altDeg < 15) altEnum = 1;
  else if (altDeg < 30) altEnum = 2;
  else if (altDeg < 45) altEnum = 3;
  else if (altDeg < 60) altEnum = 4;
  else if (altDeg < 82) altEnum = 5;
  else altEnum = 6;

  return altEnum
}

function getRaDec(dso: CatalogItem, orbs: OrbitalExport) {
  let ra = dso.RA_hr
  let dec = dso.Dec_deg
  if (dso.Cn==84) {
    const orb = orbs?.[dso.MainID];
    if (orb) {
      ra = orb.RA_hr ?? ra;
      dec = orb.DEC_deg ?? dec;
    }
  }
  return { ra, dec }
}

function positionLookup(azEnum: DsoAzimuth, altEnum: DsoAltitude) {
  const azStr = azimuthLookup[azEnum].split(' ')[0] ?? ''
  const altStr = altitudeLookup[altEnum].split(' ')[0] ?? ''
  return (altEnum==0 || altEnum==6) ? altStr :
         (altEnum==1) ? 'At ' + azStr + ' ' + altStr 
                      : altStr + ' ' + azStr
}

function visibilityLookup(brtEnum: DsoBrightness, sizeEnum: DsoSize):string {
  const brtStr =  brightnessLookup[brtEnum].split(' ')[0] ?? ''
  const sizeStr = sizeLookup[sizeEnum].split(' ')[0] ?? ''
  const str = (brtEnum==7 && sizeEnum==8) ? '' :
              (brtEnum==7) ? sizeStr :
              (sizeEnum==8) ? brtStr : brtStr + ', ' + sizeStr
  return str
}

export type DsoAltitude = 0 | 1 | 2 | 3 | 4 | 5 | 6;
export const altitudeLookup: Record<DsoAltitude, string> = {
  0: 'Below-Horizon < 0°',       // < 0°
  1: 'Horizon (0–15°)',             // 0–15°
  2: 'Low (15–30°)',                 // 15–30°
  3: 'Mid-Low (30–45°)',             // 30–45°
  4: 'Mid-High (45–60°)',            // 45–60°
  5: 'High (60–82°)',                // 60–82°
  6: 'Near-Zenith > 82°'          // > 82°
};

export type DsoAzimuth = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;
export const azimuthLookup: Record<DsoAzimuth, string> = {
  0: 'North',
  1: 'NE',
  2: 'East',
  3: 'SE',
  4: 'South',
  5: 'SW',
  6: 'West',
  7: 'NW'
};


export type DsoType = 0 | 1 | 2 | 3 | 4 | 5;
export const typeLookupIcon: Record<DsoType, string>  = {
  0: 'mdi-horse-variant', 
  1: 'mdi-cryengine', 
  2: 'mdi-blur', 
  3: 'mdi-flare',
  4: 'mdi-moon-full',
  5: 'mdi-moon-waning-crescent'
}

const typeLookup: Record<DsoType, string>  = {
  0: 'Nebula', 
  1: 'Galaxy', 
  2: 'Cluster', 
  3: 'Star',
  4: 'Planet',
  5: 'Moon'
}



export type DsoRating = 0 | 1 | 2 | 3 | 4 | 5;
const ratingLookup: Record<DsoRating, string> = {
  5: 'Top 2%', 
  4: 'Top 10%', 
  3: 'Top 25%', 
  2: 'Typical', 
  1: 'Hard', 
  0: 'Avoid'
}

export type DsoSize = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;
const sizeLookup: Record<DsoSize, string> = {
  0: 'Very-Tiny < 0.5′', 
  1: 'Tiny (0.5-1′)', 
  2: 'Small (1-2′)', 
  3: 'Compact (2-5′)', 
  4: 'Moderate (5-10′)', 
  5: 'Prominent (10-30′)', 
  6: 'Extended (30-100′)', 
  7: 'Expansive > 100′',
  8: 'Unknown'
}

export type DsoBrightness = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;
const brightnessLookup: Record<DsoBrightness, string> = {
  0: 'Ultra-Faint (Mag 12+)', 
  1: 'Ghostly (Mag 10 = 12)', 
  2: 'Faint (Mag 8 - 10)', 
  3: 'Dim (Mag 6 - 8)', 
  4: 'Visible (Mag 4 - 6)', 
  5: 'Bright (Mag 2 - 4)', 
  6: 'Brilliant (Mag <2)',
  7: 'Unknown'
}




export type DsoSubtype = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
                  10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 |
                  20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 |
                  31 | 32 | 33 | 34 | 35 | 36 | 37 | 38 | 39 | 40;
const subtypeLookup: Record<DsoSubtype, string> = {
  0: 'Chained Galaxies', 
  1: 'Clustered Galaxies', 
  2: 'Grouped Galaxies', 
  3: 'Merging Galaxies',
  4: 'Pair of Galaxies', 
  5: 'Trio of Galaxies', 
  6: 'Blue Dwarf', 
  7: 'Collisional Ring', 
  8: 'Dwarf Galaxy', 
  9: 'Elliptical Galaxy', 
  10: 'Flocculent Galaxy', 
  11: 'Lenticular Galaxy', 
  12: 'Magellanic Galaxy', 
  13: 'Polar Galaxy', 
  14: 'Spiral Galaxy', 
  15: 'Dark Nebula', 
  16: 'Emission Nebula', 
  17: 'Molecular Cloud', 
  18: 'Planetary Nebula', 
  19: 'Protoplanetary', 
  20: 'Reflection Nebula', 
  21: 'Supernova Remnant', 
  22: 'Globular Cluster', 
  23: 'Herbig-Haro Object', 
  24: 'Nova Object', 
  25: 'Open Cluster', 
  26: 'Star', 
  27: 'Star Cloud', 
  28: 'Young Stellar Object',
  29: 'Planet', 30: 'Dwarf Planet', 31: 'Martian Moon', 32: 'Galilean Moon', 33: 'Saturnian Moon', 
  34: 'Natural Satellite', 35: 'Space Station', 36: 'Satellite', 37: 'Rocket Body', 38: 'Space Debris', 39: 'Comet', 40: 'Asteroid'
}

export type DsoConstellation =
  | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9
  | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19
  | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29
  | 30 | 31 | 32 | 33 | 34 | 35 | 36 | 37 | 38 | 39
  | 40 | 41 | 42 | 43 | 44 | 45 | 46 | 47 | 48 | 49
  | 50 | 51 | 52 | 53 | 54 | 55 | 56 | 57 | 58 | 59
  | 60 | 61 | 62 | 63 | 64 | 65 | 66 | 67 | 68 | 69
  | 70 | 71 | 72 | 73 | 74 | 75 | 76 | 77 | 78 | 79
  | 80 | 81 | 82 | 83 | 84;
const constellationLookup: Record<DsoConstellation, string> = {
  0: 'Andromeda', 1: 'Antlia', 2: 'Apus', 3: 'Aquila',
  4: 'Aquarius', 5: 'Ara', 6: 'Aries', 7: 'Auriga',
  8: 'Boötes', 9: 'Canis Major', 10: 'Canis Minor', 11: 'Canes Venatici',
  12: 'Camelopardalis', 13: 'Capricornus', 14: 'Carina', 15: 'Cassiopeia',
  16: 'Centaurus', 17: 'Cepheus', 18: 'Cetus', 19: 'Chamaeleon',
  20: 'Circinus', 21: 'Cancer', 22: 'Columba', 23: 'Coma Berenices',
  24: 'Corona Australis', 25: 'Corona Borealis', 26: 'Crater', 27: 'Crux',
  28: 'Corvus', 29: 'Cygnus', 30: 'Delphinus', 31: 'Dorado',
  32: 'Draco', 33: 'Eridanus', 34: 'Fornax', 35: 'Gemini',
  36: 'Grus', 37: 'Hercules', 38: 'Horologium', 39: 'Hydra',
  40: 'Leo Minor', 41: 'Lacerta', 42: 'Leo', 43: 'Lepus',
  44: 'Libra', 45: 'Lupus', 46: 'Lynx', 47: 'Lyra',
  48: 'Mensa', 49: 'Microscopium', 50: 'Monoceros', 51: 'Musca',
  52: 'Norma', 53: 'Octans', 54: 'Ophiuchus', 55: 'Orion',
  56: 'Pavo', 57: 'Pegasus', 58: 'Perseus', 59: 'Phoenix',
  60: 'Pictor', 61: 'Piscis Austrinus', 62: 'Pisces', 63: 'Puppis',
  64: 'Pyxis', 65: 'Reticulum', 66: 'Sculptor', 67: 'Scorpius',
  68: 'Scutum', 69: 'Serpens', 70: 'Sextans', 71: 'Sagitta',
  72: 'Sagittarius', 73: 'Taurus', 74: 'Telescopium', 75: 'Triangulum Australe',
  76: 'Triangulum', 77: 'Tucana', 78: 'Ursa Major', 79: 'Ursa Minor',
  80: 'Vela', 81: 'Virgo', 82: 'Volans', 83: 'Vulpecula', 84: 'Orbit'
}


function normalize(str: string): string {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/gi, ' ') // collapse punctuation
    .trim();
}


if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useCatalogStore, import.meta.hot))
}
