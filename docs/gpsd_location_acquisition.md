# GPSD Location Acquisition

Research note, 2026-10-04.

## Findings

GPSD is an intermediary between a USB/serial receiver and clients. Its ordinary TPV interface exposes decoded position reports rather than raw satellite observations; GPSD also has raw-data modes for some receivers. A TPV report's fields depend on data sent by the receiver and values GPSD may calculate. GPSD says TPVs are usually sent at least once per measurement epoch, and multiple TPVs can be sent in one epoch when a receiver delivers its data incrementally. The protocol does not define a general moving-average policy for clients to rely on. See the [GPSD daemon documentation](https://gpsd.io/gpsd.html) and [TPV protocol documentation](https://gpsd.io/gpsd_json.html#_tpv).

The ordinary NMEA parser converts the latitude and longitude fields into a fix directly. GPSD also supports a specific averaged-position input: Ericsson's proprietary `$PERC,GPavp` sentence, documented in the parser as a surveyed, averaged position-hold reference. That is a receiver-provided special sentence, not GPSD averaging ordinary consecutive TPV fixes. See the [upstream NMEA parser](https://gitlab.com/gpsd/gpsd/-/blob/master/drivers/driver_nmea0183.c).

INDI's [`indi_gpsd` driver](https://github.com/indilib/indi-3rdparty/blob/master/indi-gpsd/gps_driver.cpp#L228-L315) waits up to one second, drains the gpsd queue while keeping only the last buffered report, rejects a report below 2D mode, and copies its latitude/longitude directly. It uses altitude for 3D fixes and sets altitude to zero for 2D fixes. INDI's [base GPS interface](https://github.com/indilib/indi/blob/master/libs/indibase/indigpsinterface.cpp#L88-L101) publishes the driver's result; it adds no smoothing. This is a latest-buffered-report policy, not a first-report policy, and the driver refreshes periodically.

In this project, [`driver/gps_location.py`](../driver/gps_location.py) owns the averaging policy: it ignores repeated TPV timestamps, gathers up to three distinct valid fixes, and averages the available samples (using a circular mean for longitude). If the read ends or times out earlier, it can return an average of fewer samples.

## Recommendation

For a stationary telescope site, keep the short application-level average and make its contract explicit in the Raspberry Pi guide: the first successful acquisition applies the mean of up to three distinct valid GPSD fixes from that attempt. This is a deliberate small reduction of sample noise; it is not something GPSD guarantees. Avoid claiming the average guarantees greater accuracy, since consecutive receiver errors can be correlated and receiver accuracy estimates are not uniformly defined.

If the originating requirement really means "apply the first valid TPV immediately," change the implementation and tests to return that fix and document the latency/behavior accordingly. INDI is useful precedent for consuming the latest current fix, but it is not a reason by itself to remove this application's bounded averaging. The available acceptance wording was added in the same change and is ambiguous about whether "first valid result" means a raw TPV or the first successful acquisition result.

## Sources

- [GPSD daemon manual](https://gpsd.io/gpsd.html): receiver device inputs, client interface, and protocol overview.
- [GPSD JSON protocol, TPV](https://gpsd.io/gpsd_json.html#_tpv): report fields and per-epoch/multiple-message semantics.
- [GPSD limitations](https://gpsd.io/gpsd.html#_limitations): a TPV can combine NMEA fields from different talkers; this is field assembly, not temporal averaging.
- [GPSD NMEA parser](https://gitlab.com/gpsd/gpsd/-/blob/master/drivers/driver_nmea0183.c): direct coordinate parsing and the special `$PERC,GPavp` averaged-position input.
- [INDI gpsd driver](https://github.com/indilib/indi-3rdparty/blob/master/indi-gpsd/gps_driver.cpp#L228-L315) and [INDI GPS interface](https://github.com/indilib/indi/blob/master/libs/indibase/indigpsinterface.cpp#L88-L101).