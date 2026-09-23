# Changelog

## v1.4.0 — 2026-09-23

- Added 308 fresh sealed decisions. Only aggregate results are published; task text and answers remain sealed.
- Set sealed Intelligence weight to 20% and blended Calibration by `0.2 / 0.35` toward the sealed-inclusive candidate axis.
- Added a generalization penalty for a public-to-sealed accuracy gap above 25 percentage points.
- Replaced the geometric composite with an equal-weight harmonic mean; retained the low-Intelligence penalty and added separate Speed and Cost gates below 50.
- Kept v1.3.0 Speed and Cost axes and the frozen v1.2 item measurements.
- Added API exposure flags and preserved contributor development and measurement disclosures.
- Added round 4, round 5 and GPT-6 Luna measurements. swanOne has no rank pending its sealed measurement.
