import { defineStore } from 'pinia'
import { useDeviceStore } from 'stores/device'

const dev = useDeviceStore()

export type StatusResponse = ReturnType<typeof useStatusStore>['$state']

export const useStatusStore = defineStore('status', {
    state: () => ({
        fetchedAt: 0,             // local timestamp of when config was last fetched
        battery_is_available: false,
        battery_is_charging: false,
        battery_level: 0,
        connected: false,
        tracking: false,
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
    }
})
