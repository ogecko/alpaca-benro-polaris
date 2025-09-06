import { defineStore } from 'pinia'
import { useDeviceStore } from 'stores/device'

const dev = useDeviceStore()

export type StatusResponse = ReturnType<typeof useStatusStore>['$state']

export const useStatusStore = defineStore('status', {
    state: () => ({
        fetchedAt: 0,             // local timestamp of when config was last fetched
        polarismode: 0,
        battery_is_available: false,
        battery_is_charging: false,
        battery_level: 0,
        connected: false,
        tracking: false,
        trackingrate: 0,
        athome: false,
        atpark: false,
        slewing: false,
        gotoing: false,
        ispulseguiding: false,
        altitude: 0,
        azimuth: 0,
        roll: 0,
        rotation: 0,
        declination: 0,
        rightascension: 0,
        siderealtime: 0,
        pidmode: '',
        deltaref: [0,0,0],
        alpharef: [0,0,0],
        omegaref: [0,0,0],
        motorref: [0,0,0],
    }),

    actions: {
        async statusFetch() {
            try {
                const response = await dev.apiAction<StatusResponse>('Polaris:StatusFetch');
                this.$patch(response)
                this.fetchedAt = Date.now()
            } catch (err) {
                console.warn('Status fetch failed:', err);
            }
        },
    },
    getters: {
        deltarefRAhrs: (state): number => (state.deltaref[0]??0)/180*12,
        trackingratestr: (state): string => {
            const tr = state.trackingrate;
            return tr === 0 ? 'Sidereal' :
                tr === 1 ? 'Lunar' :
                tr === 2 ? 'Solar' : 'Custom';
        }
    }

})
