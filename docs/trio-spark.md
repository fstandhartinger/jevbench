# Trio-Spark v1.0 production API submission

This adapter submits MachineFi's hosted [Trio-Spark v1.0](https://github.com/machinefi/trio-spark)
for independent evaluation. It does not add or alter a leaderboard result.

## Transport and mapping

Each JevBench item becomes one request to the production endpoint. Trio-Spark
accepts one bounded Choice with 2–8 options and returns the selected option plus
native probabilities for the complete option set.

- `choice`: preserves each canonical label and description.
- `noul`: maps `no` and `yes` to the benchmark's false and true criteria.
- `score`: maps ordered levels to their canonical string indices.

The adapter preserves option order, sends no expected answer, and neither repairs
nor truncates distributions. Every current public item has at most six options.
Malformed or incomplete responses fail the item. The benchmark's serial,
no-retry policy remains unchanged.

## Access and identity

- Product release: Trio-Spark v1.0
- API model identifier: `trio-spark-preview`
- Default endpoint: `https://platform.machinefi.com/api/spark/v1/decisions`
- Authentication: bearer token from `TRIO_SPARK_API_KEY`
- Published tariff: $0.042 per million billed input tokens; zero output tokens
- Weights and training artifacts: closed; hosted API only

An evaluator can create an account and key at
[platform.machinefi.com/spark](https://platform.machinefi.com/spark), or ask
MachineFi for a temporary evaluation key. A sealed run necessarily exposes the
sealed item text to the production API and should therefore carry the benchmark's
API flag.

## Run

```sh
python -m jevbench.cli run \
  --tasks datasets/public/easy.jsonl,datasets/public/original.jsonl,datasets/public/hard.jsonl \
  --adapter trio_spark --key-env TRIO_SPARK_API_KEY \
  --price-in-per-m 0.042 --price-out-per-m 0 --delay-s 1.2 \
  --results ../private/trio-spark/results.jsonl \
  --raw-dir ../private/trio-spark/raw \
  --ledger ../private/trio-spark/ledger.jsonl \
  --manifest ../private/trio-spark/manifest.json --cap-usd 15
```

The delay keeps a public evaluation below the production account rate limit. Raw
requests and responses stay outside the repository under the harness's standard
evidence rules. API credentials are read from the environment and never logged.
