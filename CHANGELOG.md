# Changelog

## v1.4.2 — 2026-09-25

- Added eleven newly measured systems and completed swanOne's sealed run; all rows use the full 842-decision protocol.
- New #1: decider-4b v2 (64.13), after an independent verification of its cost basis, generalization gap, overlap and score. Jev 1.13.0 out-reasons it (Intelligence 53.1 vs 49.4); decider-4b v2 leads on speed and cost.
- Systems without a public, bookable price carry a labelled estimate from their base model's public price.
- Kept the v1.4 scoring formula and every v1.4.1 measurement unchanged.

## v1.4.1 — 2026-09-23

- Added six systems omitted from the frozen v1.4.0 board, each with a completed 308-item sealed measurement.
- Kept the v1.4 scoring formula and all 76 v1.4.0 scores unchanged; the approved top five remains unchanged.
- Published aggregate accuracy and calibration data only. The six new rows have no API exposure flag because their sealed items were evaluated offline.

## v1.4.0 — 2026-09-23

- Added 308 fresh sealed decisions. Only aggregate results are published; task text and answers remain sealed.
- Set sealed Intelligence weight to 20% and blended Calibration by `0.2 / 0.35` toward the sealed-inclusive candidate axis.
- Added a generalization penalty for a public-to-sealed accuracy gap above 25 percentage points.
- Replaced the geometric composite with an equal-weight harmonic mean; retained the low-Intelligence penalty and added separate Speed and Cost gates below 50.
- Kept v1.3.0 Speed and Cost axes and the frozen v1.2 item measurements.
- Added API exposure flags and preserved contributor development and measurement disclosures.
- Added round 4, round 5 and GPT-6 Luna measurements. swanOne has no rank pending its sealed measurement.
