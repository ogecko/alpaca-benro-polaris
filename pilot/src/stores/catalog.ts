import axios from 'axios'
import { defineStore, acceptHMRUpdate } from 'pinia'
// import { sleep } from 'src/utils/sleep'
import { AppVisibility } from 'quasar'


export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    dsos: [] as CatalogItem[],
    page: 1,
    pageSize: 8,
    selected: 0,
    filter: {
        Rt: undefined as DsoRating | undefined,
        Sz: undefined as DsoSize | undefined,
        Vz: undefined as DsoVisibility | undefined,
        Cn: undefined as DsoConstellation | undefined,
        C1: undefined as DsoType | undefined,
        C2: undefined as DsoSubtype | undefined,
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
        return this.dsos.filter(dso => {
            return Object.entries(this.filter).every(([key, value]) => {
            return value === undefined || dso[key as keyof CatalogItem] === value;
            });
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
    }



  },

  actions: {
    async catalogFetch() {
      try {
        const resp = await axios.get('/catalog_a_lg.json');
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
            Subtype: subtypeLookup[dso.C2]
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
  RA_deg: number;
  Dec_deg: number;
  // Enriched display fields
  Rating?: string;
  Size?: string;
  Visibility?: string;
  Constellation?: string;
  Type?: string;
  Subtype?: string;

}



// ---------- Helpers
type DsoType = 0 | 1 | 2 | 3;

const typeLookupIcon: Record<DsoType, string>  = {
  0: 'mdi-horse-variant', 
  1: 'mdi-cryengine', 
  2: 'mdi-blur', 
  3: 'mdi-flare'
}

type DsoRating = 0 | 1 | 2 | 3 | 4 | 5;
const ratingLookup: Record<DsoRating, string> = {
  5: 'Top 2%', 
  4: 'Top 10%', 
  3: 'Top 25%', 
  2: 'Typical', 
  1: 'Hard', 
  0: 'Avoid'
}

type DsoSize = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;
const sizeLookup: Record<DsoSize, string> = {
  0: 'Tiny (<0.5′)', 
  1: 'Small (0.5 – 1′)', 
  2: 'Compact (1 – 2′)', 
  3: 'Moderate (2 – 5′)', 
  4: 'Prominent (5 – 10′)', 
  5: 'Wide (10 – 30′)', 
  6: 'Extended (30 – 100′)', 
  7: 'Expansive (100′+)'
}

type DsoVisibility = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;
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




type DsoSubtype = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
                  10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 |
                  20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28;
const subtypeLookup: Record<DsoSubtype, string> = {
  0: 'Set of Chained Galaxies', 
  1: 'Set of Clustered Galaxies', 
  2: 'Set of Grouped Galaxies', 
  3: 'Set of Merging Galaxies',
  4: 'Pair of Galaxies', 
  5: 'Trio of Galaxies', 
  6: 'Blue Compact Dwarf Galaxy', 
  7: 'Collisional Ring Galaxy', 
  8: 'Dwarf Galaxy', 
  9: 'Elliptical Galaxy', 
  10: 'Flocculent Galaxy', 
  11: 'Lenticular Galaxy', 
  12: 'Magellanic Galaxy', 
  13: 'Polar Galaxy', 
  14: 'Spiral Galaxy', 
  15: 'Dark Nebula', 
  16: 'Emission Nebula', 
  17: 'Molecular Cloud Nebula', 
  18: 'Planetary Nebula', 
  19: 'Protoplanetary Nebula', 
  20: 'Reflection Nebula', 
  21: 'Supernova Remnant Nebula', 
  22: 'Globular Cluster', 
  23: 'Herbig-Haro Object', 
  24: 'Nova Object', 
  25: 'Open Cluster', 
  26: 'Star', 
  27: 'Star Cloud', 
  28: 'Young Stellar Object'
}

type DsoConstellation =
  | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9
  | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19
  | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29
  | 30 | 31 | 32 | 33 | 34 | 35 | 36 | 37 | 38 | 39
  | 40 | 41 | 42 | 43 | 44 | 45 | 46 | 47 | 48 | 49
  | 50 | 51 | 52 | 53 | 54 | 55 | 56 | 57 | 58 | 59
  | 60 | 61 | 62 | 63 | 64 | 65 | 66 | 67 | 68 | 69
  | 70 | 71 | 72 | 73 | 74 | 75 | 76 | 77 | 78 | 79
  | 80 | 81 | 82;
const constellationLookup: Record<DsoConstellation, string> = {
  0: 'Andromeda', 1: 'Antlia', 2: 'Apus', 3: 'Aquila', 4: 'Aquarius', 5: 'Ara',
  6: 'Aries', 7: 'Auriga', 8: 'Boötes', 9: 'Canis Major', 10: 'Canis Minor',
  11: 'Canes Venatici', 12: 'Camelopardalis', 13: 'Capricornus', 14: 'Carina',
  15: 'Cassiopeia', 16: 'Centaurus', 17: 'Cepheus', 18: 'Cetus', 19: 'Chamaeleon',
  20: 'Circinus', 21: 'Cancer', 22: 'Columba', 23: 'Coma Berenices', 24: 'Corona Australis',
  25: 'Corona Borealis', 26: 'Crater', 27: 'Crux', 28: 'Corvus', 29: 'Cygnus',
  30: 'Delphinus', 31: 'Dorado', 32: 'Draco', 33: 'Eridanus', 34: 'Fornax',
  35: 'Gemini', 36: 'Grus', 37: 'Hercules', 38: 'Horologium', 39: 'Hydra',
  40: 'Leo Minor', 41: 'Lacerta', 42: 'Leo', 43: 'Lepus', 44: 'Libra',
  45: 'Lupus', 46: 'Lynx', 47: 'Lyra', 48: 'Mensa', 49: 'Microscopium',
  50: 'Monoceros', 51: 'Musca', 52: 'Norma', 53: 'Octans', 54: 'Ophiuchus',
  55: 'Orion', 56: 'Pavo', 57: 'Pegasus', 58: 'Perseus', 59: 'Pictor',
  60: 'Piscis Austrinus', 61: 'Pisces', 62: 'Puppis', 63: 'Pyxis', 64: 'Reticulum',
  65: 'Sculptor', 66: 'Scorpius', 67: 'Scutum', 68: 'Serpens', 69: 'Sextans',
  70: 'Sagitta', 71: 'Sagittarius', 72: 'Taurus', 73: 'Telescopium',
  74: 'Triangulum Australe', 75: 'Triangulum', 76: 'Tucana', 77: 'Ursa Major',
  78: 'Ursa Minor', 79: 'Vela', 80: 'Virgo', 81: 'Volans', 82: 'Vulpecula'
};



if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useCatalogStore, import.meta.hot))
}
