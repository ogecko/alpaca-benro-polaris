import { defineStore } from 'pinia'
import { useDeviceStore } from 'stores/device'

const dev = useDeviceStore()
export const polarisModeOptions = [
  { value: 8, label: 'Astro' },
  { value: 1, label: 'Photo' },
  { value: 2, label: 'Pano' },
  { value: 3, label: 'Focus' },
  { value: 4, label: 'Timelapse' },
  { value: 5, label: 'Pathlapse' },
  { value: 6, label: 'HDR' },
  { value: 7, label: 'Sun' },
  { value: 9, label: 'Program' },
  { value: 10, label: 'Video' },
  { value: 0, label: 'Unknown' },
] as const;

export type StatusResponse = ReturnType<typeof useStatusStore>['$state']

export const useStatusStore = defineStore('status', {
    state: () => ({
        fetchedAt: 0,             // local timestamp of when config was last fetched
        polarismode: 0,
        polarislbracket: false,
        battery_is_available: false,
        battery_is_charging: false,
        battery_level: 0,
        compassed: false,
        aligned: false,
        aligned_count: 0,
        tilt_adj_az: 0,
        tilt_adj_mag: 0,
        az_adj: 0,
        roll_adj: 0,
        aligning: false,
        connected: false,
        connecting: false,
        connectionmsg: '',
        age517: 0,
        age518: 0,
        tracking: false,
        trackingrate: 0,
        trackingname: '',
        orbitalstatus: [0, 0, 0],
        orbitalfetchmsg: '',
        athome: false,
        atpark: false,
        slewing: false,
        gotoing: false,
        rotating: false,
        iszetamoving: false,
        ispulseguiding: false,
        paltitude: 0,
        pazimuth: 0,
        proll: 0,
        altitude: 0,
        azimuth: 0,
        roll: 0,
        rotation: 0,
        declination: 0,
        rightascension: 0,
        siderealtime: 0,
        parallacticangle: 0,
        positionangle: 0,
        lifecycleevent: 'NONE',
        pidmode: '',
        pidglock: false,
        qraw: [0,0,0,0],
        qstate: [0,0,0,0],
        qalign: [0,0,0,0],
        qpv: [0,0,0,0],
        zetameas: [0,0,0],
        lotameas: [0,0,0,0,0],
        traw: [0,0,0],
        tstate: [0,0,0],
        astate: [0,0,0],
        tpv: [0,0,0],
        tref: [0,0,0],
        gdrate: [0,0,0],
        gdaccum: [0,0,0],
        dslew: [0,0,0],
        aslew: [0,0,0],
        dofst: [0,0,0],
        aofst: [0,0,0],
        dsp: [0,0,0],
        asp: [0,0,0],
        errsig: [0,0,0],
        deltaref: [0,0,0],
        alpharef: [0,0,0],
        omegaref: [0,0,0],
        motorref: [0,0,0],
        motorcmd: ['','',''],
        omegamin: [0,0,0],
        omegamax: [0,0,0],
        bledevices: [] as string[],
        bleselected: '',
        bleisenablingwifi: false,
        bleiswifienabled: false,
        polarisswver: '',
        polarishwver: '',
        polarisastrover: '',
        rbcerror: 0,
        sccerror: 0,
        mpaerror: 0,
        pec: [0,0,0,0],
        pidKc: 0.75,
    }),

    actions: {
        async statusFetch() {               // no longer used after WebSockets introduced
            try {
                const response = await dev.apiAction<StatusResponse>('Polaris:StatusFetch');
                this.$patch(response)
                this.fetchedAt = Date.now()
            } catch (err) {
                console.warn('Status fetch failed:', err);
            }
        },
        // called from socket.onmessage whenever a status subscription payload comes in
        statusUpdate(data: StatusResponse) {
            this.$patch(data)
            this.fetchedAt = Date.now()
        },
    },
    getters: {
        deltarefRAhrs: (state): number => (state.deltaref[0]??0)/180*12,
        trackingratestr: (state): string => {
            const tr = state.trackingrate;
            return tr === 0 ? 'Sidereal' :
                tr === 1 ? 'Lunar' :
                tr === 2 ? 'Solar' : 'Custom';
        },
        polarismodestr: (state): string => {
            const mode = polarisModeOptions.find(m => m.value === state.polarismode);
            return mode?.label ?? 'Unknown';
        }
    }

})
