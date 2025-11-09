<template>
  <q-page class="q-pa-sm dark-page">

    <StatusBanners />

    <!-- Page Header -->
    <div class="row q-pb-sm q-col-gutter-md items-center">
      <div class="col text-h6 q-ml-md">
        System Advisory & Usage Notes
        <div class="text-caption text-grey-6">
          Important safety, security, and performance guidance for Alpaca Benro Polaris Driver users.
        </div>
      </div>
      <q-space />
    </div>

    <!-- Advisory Cards -->
    <div class="row q-col-gutter-md items-stretch">
      <div class="col-12 col-md-6 flex">
        <q-card flat bordered class="full-width">
          <q-card-section>
            <div class="text-h6 text-bold">⚠️ Warranty Disclaimer</div>
            <div class="text-body2 q-mt-sm">
              <p>
                This software is developed independently and is <strong>not officially affiliated with, endorsed by, or supported by Benro</strong> or its parent companies. It is provided by the community as a third-party enhancement to the Polaris mount, intended to unlock additional capabilities and improve user experience.
              </p>
              <p>By choosing to install and use this driver, you acknowledge that:</p>
              <ul>
                <li>You are doing so <strong>at your own discretion and risk</strong></li>
                <li>The developers make <strong>no guarantees</strong> regarding performance, reliability, or compatibility</li>
                <li>The software is provided <strong>"as-is"</strong>, without any express or implied warranties</li>
                <li>You assume full responsibility for any outcomes, including potential data loss, unintended motion, or equipment damage</li>
              </ul>
            </div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-md-6 flex">
        <q-card flat bordered class="full-width">
          <q-card-section>
            <div class="text-h6 text-bold">⚠️ Unattended Operation Warning</div>
            <div class="text-body2 q-mt-sm">
              Do <strong>not</strong> leave the system unattended while the ABP Driver is actively controlling the Polaris mount.  
              If the driver loses connection or is interrupted, the last movement command may continue indefinitely.  
              <br><br>
              To stop the mount:
              <ul>
                <li>Reconnect the ABP Driver (it will attempt to auto-reconnect if possible)</li>
                <li>Use the Benro Polaris mobile app to issue a stop command</li>
              </ul>
              Because this failure mode cannot be fully mitigated in ABP v2.0, <strong>unattended use is strongly discouraged</strong>.
            </div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-md-6 flex">
        <q-card flat bordered class="full-width">
          <q-card-section>
            <div class="text-h6 text-bold">⚠️ Network Security Advisory</div>
            <div class="text-body2 q-mt-sm">
              <p>
                The <strong>ASCOM Alpaca protocol</strong> is intentionally designed to be open and lightweight, enabling seamless communication between astronomy devices and software across platforms. However, this openness comes with a critical caveat: <strong>Alpaca does not include built-in security mechanisms</strong> such as authentication, encryption, or access control.
              </p>
              <p>
                <strong>Do not expose the ABP Driver to public networks, open Wi-Fi, or internet-facing environments.</strong> Doing so may allow unintended control of your mount or access to sensitive imaging information.
              </p>
              <p>
                For best practices:
              </p>
              <ul>
                <li>Use a dedicated VLAN or subnet for your observatory equipment</li>
                <li>Restrict access to trusted IP ranges or devices</li>
                <li>Avoid port forwarding or exposing Alpaca endpoints to the internet</li>
                <li>Consider using VPNs or firewalls to isolate traffic</li>
              </ul>
              <p>
                Remember: <strong>Alpaca and network security are separate concerns</strong>. It is your responsibility to ensure safe deployment in your environment.
              </p>
            </div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-md-6 flex">
        <q-card flat bordered class="full-width">
          <q-card-section>
            <div class="text-h6 text-bold">⚠️ Performance Limitations</div>
            <div class="text-body2 q-mt-sm">
              <p>
                The <strong>Alpaca Benro Polaris (ABP) Driver</strong> unlocks advanced control and precision features that enhance the capabilities of the Benro Polaris mount.
                However, it's important to understand that the ABP Driver operates within the physical limits of the Polaris hardware. 
                While software enhancements can improve performance, they cannot fully compensate for mechanical or firmware constraints.
              </p>
              <p>
                You may even find that some of the <strong>advanced control algorithms</strong> introduced by the ABP Driver do not yield noticeable improvements over the standard Benro firmware. This is not necessarily a flaw in the driver. In some cases, the simplicity and tuning of the original Benro firmware may outperform adaptive algorithms, particularly in well-balanced setups or when operating under ideal conditions. We encourage users to experiment with both configurations.
              </p>
              <p>
                In short, while the ABP Driver elevates what the Polaris can do, it does not transform it into a high-end equatorial mount. 
                <strong>Calibrate your expectations accordingly</strong> — especially when targeting deep-sky objects that demand sub-arcsecond precision, long focal lengths and extended exposures.
              </p>
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

  </q-page>
</template>




<script setup lang="ts">
import StatusBanners from 'src/components/StatusBanners.vue'

</script>

<style lang="scss">
  .q-markdown--link {
    color: $grey-6;

    &:hover {
      text-decoration: underline;
      color: $grey-4;
    }
  }
</style>
