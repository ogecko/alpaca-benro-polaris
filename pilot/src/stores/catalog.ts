import axios from 'axios'
import { defineStore, acceptHMRUpdate } from 'pinia'
// import { sleep } from 'src/utils/sleep'
import { AppVisibility } from 'quasar'

// # C1 {0: 'Nebula', 1: 'Galaxy', 2: 'Cluster', 3: 'Star'}
// # C2 {0: 'Set of Chained Galaxies', 1: 'Set of Clustered Galaxies', 2: 'Set of Grouped Galaxies', 3: 'Set of Merging Galaxies', 4: 'Pair of Galaxies', 5: 'Trio of Galaxies', 6: 'Blue Compact Dwarf Galaxy', 7: 'Collisional Ring Galaxy', 8: 'Dwarf Galaxy', 9: 'Elliptical Galaxy', 10: 'Flocculent Galaxy', 11: 'Lenticular Galaxy', 12: 'Magellanic Galaxy', 13: 'Polar Galaxy', 14: 'Spiral Galaxy', 15: 'Dark Nebula', 16: 'Emission Nebula', 17: 'Molecular Cloud Nebula', 18: 'Planetary Nebula', 19: 'Protoplanetary Nebula', 20: 'Reflection Nebula', 21: 'Supernova Remnant Nebula', 22: 'Globular Cluster', 23: 'Herbig-Haro Object', 24: 'Nova Object', 25: 'Open Cluster', 26: 'Star', 27: 'Star Cloud', 28: 'Young Stellar Object'}
// # Cn {0: 'Andromeda', 1: 'Antlia', 2: 'Apus', 3: 'Aquila', 4: 'Aquarius', 5: 'Ara', 6: 'Aries', 7: 'Auriga', 8: 'Boötes', 9: 'Canis Major', 10: 'Canis Minor', 11: 'Canes Venatici', 12: 'Camelopardalis', 13: 'Capricornus', 14: 'Carina', 15: 'Cassiopeia', 16: 'Centaurus', 17: 'Cepheus', 18: 'Cetus', 19: 'Chamaeleon', 20: 'Circinus', 21: 'Cancer', 22: 'Columba', 23: 'Coma Berenices', 24: 'Corona Australis', 25: 'Corona Borealis', 26: 'Crater', 27: 'Crux', 28: 'Corvus', 29: 'Cygnus', 30: 'Delphinus', 31: 'Dorado', 32: 'Draco', 33: 'Eridanus', 34: 'Fornax', 35: 'Gemini', 36: 'Grus', 37: 'Hercules', 38: 'Horologium', 39: 'Hydra', 40: 'Leo Minor', 41: 'Lacerta', 42: 'Leo', 43: 'Lepus', 44: 'Libra', 45: 'Lupus', 46: 'Lynx', 47: 'Lyra', 48: 'Mensa', 49: 'Microscopium', 50: 'Monoceros', 51: 'Musca', 52: 'Norma', 53: 'Octans', 54: 'Ophiuchus', 55: 'Orion', 56: 'Pavo', 57: 'Pegasus', 58: 'Perseus', 59: 'Pictor', 60: 'Piscis Austrinus', 61: 'Pisces', 62: 'Puppis', 63: 'Pyxis', 64: 'Reticulum', 65: 'Sculptor', 66: 'Scorpius', 67: 'Scutum', 68: 'Serpens', 69: 'Sextans', 70: 'Sagitta', 71: 'Sagittarius', 72: 'Taurus', 73: 'Telescopium', 74: 'Triangulum Australe', 75: 'Triangulum', 76: 'Tucana', 77: 'Ursa Major', 78: 'Ursa Minor', 79: 'Vela', 80: 'Virgo', 81: 'Volans', 82: 'Vulpecula'}
// # Sz {0: 'Tiny (<0.5′)', 1: 'Small (0.5–1′)', 2: 'Compact (1–2′)', 3: 'Moderate (2–5′)', 4: 'Prominent (5–10′)', 5: 'Wide (10–30′)', 6: 'Extended (30–100′)', 7: 'Expansive (100′+)'}
// # Rt {5: 'Showcase (Top 2%)', 4: 'Excellent (Top 10%)', 3: 'Good (Top 25%)', 2: 'Typical', 1: 'Challenging', 0: 'Not recommended'}
// # Vz {0: 'Ultra Faint (Mag 12+)', 1: 'Ghostly (Mag 10-12)', 2: 'Faint (Mag 8-10)', 3: 'Dim (Mag 6-8)', 4: 'Visible (Mag 4-6)', 5: 'Bright (Mag 2-4)', 6: 'Brilliant (Mag <2)', 7: 'Unknown'}


export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    dsos: [] as CatalogItem[],
    dsoGotoed: undefined as CatalogItem | undefined,
    page: 1,
    pageSize: 10,
    selected: 0,
    searchFor: '',
    filter: {
        Rt: undefined as DsoRating[] | undefined,
        Sz: undefined as DsoSize[] | undefined,
        Vz: undefined as DsoVisibility[] | undefined,
        Cn: undefined as DsoConstellation[] | undefined,
        C1: undefined as DsoType[] | undefined,
        C2: undefined as DsoSubtype[] | undefined,
    },
    sorting: [
        { field: 'Rt', direction: 'desc' },
        { field: 'Sz', direction: 'desc' },
        { field: 'Name', direction: 'asc' }
    ] as { field: keyof CatalogItem; direction: 'asc' | 'desc' }[],
  }),

  getters: {
    isVisible() {
        return AppVisibility.appVisible
    }, 
    filtered(): CatalogItem[] {
      const search = normalize(this.searchFor);

      return this.dsos.filter(dso => {
        // Filter match
        const matchesFilter = Object.entries(this.filter).every(([key, value]) => {
          if (value == null || (Array.isArray(value) && value.length === 0)) return true;
          const fieldValue = dso[key as keyof CatalogItem];
          return Array.isArray(value)
            ? fieldValue != null && (value as (string | number)[]).includes(fieldValue)
            : fieldValue === value;
        });
        // Search match
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
            for (const { field, direction } of this.sorting) {
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
        const opt = Object.entries(visibilityLookup).map(([key, label]) => ({  label,  value: Number(key) as DsoType })).reverse()
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
            3: [22, 28]  // Star (merged with Stellar range)
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

  },

  actions: {
    clearFilter() {
        this.filter.Rt = undefined;
        this.filter.Sz = undefined;
        this.filter.Vz = undefined;
        this.filter.Cn = undefined;
        this.filter.C1 = undefined;
        this.filter.C2 = undefined;
        this.searchFor = '';
    },
    async catalogFetch() {
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
            Size: sizeLookup[dso.Sz],
            Visibility: visibilityLookup[dso.Vz],
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

  }
})


export interface CatalogItem {
  MainID: string;
  Name: string;
  Notes: string;
  Class: string | null;
  OtherIDs: string;
  Rt: DsoRating;
  Sz: DsoSize;
  Vz: DsoVisibility;
  Cn: DsoConstellation;
  C1: DsoType;
  C2: DsoSubtype;
  RA_hr: number;
  Dec_deg: number;
  // Enriched display fields
  Rating?: string;
  Size?: string;
  Visibility?: string;
  Constellation?: string;
  Type?: string;
  Subtype?: string;
  SearchText?: string;
}



// ---------- Helpers
export type DsoType = 0 | 1 | 2 | 3;

const typeLookupIcon: Record<DsoType, string>  = {
  0: 'mdi-horse-variant', 
  1: 'mdi-cryengine', 
  2: 'mdi-blur', 
  3: 'mdi-flare'
}

const typeLookup: Record<DsoType, string>  = {
  0: 'Nebula', 
  1: 'Galaxy', 
  2: 'Cluster', 
  3: 'Star'
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
  0: 'Tiny (<0.5′)', 
  1: 'Small (0.5 – 1′)', 
  2: 'Compact (1 – 2′)', 
  3: 'Moderate (2 – 5′)', 
  4: 'Prominent (5 – 10′)', 
  5: 'Wide (10 – 30′)', 
  6: 'Extended (30 – 100′)', 
  7: 'Expansive (100′+)',
  8: ''
}

export type DsoVisibility = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;
const visibilityLookup: Record<DsoVisibility, string> = {
  0: 'Ultra Faint (Mag 12+)', 
  1: 'Ghostly (Mag 10 = 12)', 
  2: 'Faint (Mag 8 - 10)', 
  3: 'Dim (Mag 6 - 8)', 
  4: 'Visible (Mag 4 - 6)', 
  5: 'Bright (Mag 2 - 4)', 
  6: 'Brilliant (Mag <2)',
  7: ''
}




export type DsoSubtype = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
                  10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 |
                  20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28;
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
  28: 'Young Stellar Object'
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
  | 80 | 81 | 82 | 83;
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
  80: 'Vela', 81: 'Virgo', 82: 'Volans', 83: 'Vulpecula'
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
