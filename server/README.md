# WeatherMesh-3 — real-time inference pipeline

Fetches the latest real-time **GFS** initial condition, runs **WeatherMesh-3**, and
publishes physically-validated forecasts to **S3**, on a 6-hourly schedule, with
**CloudWatch** observability. Built for the WindBorne ML-Ops take-home.

## Architecture

```
SageMaker notebook GPU — 6-hourly cron (00/06/12/18Z)
   run_cycle:  GFS fetch → preprocess → WM-3 → validate → netCDF/plots/metadata
      → S3 (forecasts/init=…/lead=…; invalid → quarantine/…, never latest.json)
      + CloudWatch (timings, output_valid, diagnostics)  + SNS (on failure/invalid)
```

> **Status:** the diagram is the *target* design and is **not implemented** — no
> Step Functions / Processing IaC is committed, because the g5 processing-job quota is in
> manual review (a Processing job can't launch or be tested). The **live** runner is a
> 6-hourly cron on a SageMaker notebook GPU that runs the source via `uv`
> (`infra/cron-onstart.sh`) — a continuously-on instance (~24 GPU-hr/day). The ephemeral
> ~1 GPU-hr/day figure would apply to the Processing design once the quota clears.

Why Processing over AWS Batch (in the target design): Batch runs on EC2 G instances,
blocked by the same on-demand-G quota. SageMaker's endpoint/notebook quotas auto-approved
instantly; the *processing-job* quota did not — hence the notebook-cron interim.

## Package (`server/wm3pipe`)
| module | responsibility |
|---|---|
| `gfs.py` | fetch GFS f000 from `noaa-gfs-bdp-pds` via `.idx` byte-ranges (only needed fields) |
| `preprocess.py` | GFS → both encoder inputs; GFS feeds the HRES encoder too, levels reconciled with `interp_levels` |
| `inference.py` | load WM-3, run forward, de-normalize to physical units |
| `validate.py` | physical-plausibility checks (temp/pressure/wind bounds, NaNs) |
| `outputs.py` | CF-metadata netCDF + overview plot + `metadata.json` |
| `s3io.py` | Hive-partitioned S3 upload + `latest.json` pointer |
| `metrics.py` | CloudWatch metrics + timers |
| `run_cycle.py` | orchestrates one cycle; emits metrics; SNS alert on failure |

## The GFS-for-both-encoders note
ECMWF open data lacks required pressure levels, so **GFS drives both encoders**.
The GFS encoder consumes 25 levels, the HRES encoder 20 — both sourced from GFS,
each lifted to the model's 28 internal levels. Missing high-altitude fields (e.g.
GFS specific humidity above ~100 hPa) fall back to the normalized mean.

## Run
Local smoke (CPU, no model — validates fetch + preprocess shapes/ranges):
```bash
uv run --with boto3 --with eccodes python server/tests/smoke_fetch.py
```
Container (GPU; fetches weights from S3, writes forecasts to S3):
```bash
# natten builds from a vendored wheel (shi-labs host is unreliable) — fetch it first
mkdir -p server/wheels && aws s3 cp \
  s3://wm3-gpu-194290773983/wheels/natten-0.17.3+torch240cu121-cp311-cp311-linux_x86_64.whl server/wheels/
docker build -f server/Dockerfile -t wm3-pipeline .
docker run --gpus all \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_REGION=us-east-1 \
  -e WM3_WEIGHTS_S3=s3://wm3-gpu-194290773983/model/WeatherMesh3.pt \
  -e WM3_OUTPUT_BUCKET=wm3-forecasts-194290773983 \
  wm3-pipeline --lead-hours 6
```
Container self-test (no GPU/weights — imports the stack + builds meshes, used in CI):
```bash
docker run --rm wm3-pipeline --selftest
```

## Output format
The netCDF matches the [WindBorne gridded-forecast API](https://api.windbornesystems.com/forecasts/version_1/gridded-forecast/gridded-forecast/)
schema (the Part 1 bonus): surface vars `temperature_2m`, `dewpoint_2m`,
`pressure_msl`, `wind_{u,v,speed}_{10m,100m}`, `total_cloud_cover`,
`total_precipitation_6h`; upper-level `geopotential`, `temperature`, `wind_u`,
`wind_v`, `specific_humidity` on `(time, level, lat, lon)` with the API's 25
pressure levels; CF-1.8 metadata.

## S3 output layout — `s3://wm3-forecasts-<account>/`
```
forecasts/init=2026-07-10T18Z/lead=006h/weathermesh3.f006.nc
forecasts/init=2026-07-10T18Z/lead=006h/overview.png
forecasts/init=2026-07-10T18Z/metadata.json
latest.json          # pointer to the newest cycle
```

## Monitoring (CloudWatch namespace `WeatherMesh3`)
`fetch_seconds`, `preprocess_seconds`, `inference_seconds`, `cycle_seconds`,
`cycle_success`, `output_valid`, `nonfinite_count`, field bounds (`t2m_*`, `mslp_*`,
`jet250_max_ms`), and physical-consistency diagnostics (`neg_humidity_frac`,
`dewpoint_gt_temp_frac`, `precip_capped_frac`, `precip_p99_mm`). Dashboard body in
`infra/dash.json`; a staleness/failure alarm pages SNS, and `run_cycle` also publishes
to SNS directly on failure.
