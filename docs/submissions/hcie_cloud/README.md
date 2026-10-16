# JevBench v1.4.2.2 Official Submission Package: Agent MIKI Cloud Edition

This directory contains the official PR submission package for **Agent MIKI Cloud Edition v1.3.7** evaluated in **europe-west4 (Eemshaven, Netherlands)** for the JevBench Official Leaderboard.

## Package Manifest
- [`official_cloud_receipt.json`](official_cloud_receipt.json): Cryptographic execution receipt sealed with Canonical SHA-256 signature (`57ecc8f80f7584c3202c42bfe31be877596c3db4990c4d4e9b3c74cc4db8fab6`).
- [`hcie-cloud-ROW-v1.4.2.2.json`](hcie-cloud-ROW-v1.4.2.2.json): JevBench v1.4.2.2 official submission row.
- [`ANTI_CONTAMINATION_CERTIFICATE_CLOUD.md`](ANTI_CONTAMINATION_CERTIFICATE_CLOUD.md): Formal affidavit of clean-room compliance with BAN-001 through BAN-007.
- [`PR_SPECIFICATION_CLOUD.md`](PR_SPECIFICATION_CLOUD.md): GitHub Pull Request specification for `fstandhartinger/jevbench`.
- [`reproduce_cloud_benchmark.py`](reproduce_cloud_benchmark.py): Single-command third-party verifier script.
- [`../results/cuda_cloud_jevbench_europe.jsonl`](../results/cuda_cloud_jevbench_europe.jsonl): Full 231-task raw E2E inference execution log with real-time `pynvml` hardware telemetry.

## Verification
Run from the repository root:
```bash
python docs/submissions/hcie_cloud/reproduce_cloud_benchmark.py
```
Or run from within this directory:
```bash
python reproduce_cloud_benchmark.py
```
