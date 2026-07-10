# WeatherMesh-3 — real-time inference pipeline

Fetches the latest real-time **GFS** initial condition, runs **WeatherMesh-3**, and
publishes physically-validated forecasts to **S3**, on a 6-hourly schedule, with
**CloudWatch** observability. Built for the WindBorne ML-Ops take-home.

## Architecture

```
EventBridge (cron, 00/06/12/18Z)
      → Step Functions (retry + catch → SNS alert)
        → SageMaker Processing Job  (ml.g5.xlarge, ephemeral GPU, this container)
            run_cycle:  GFS fetch → preprocess → WM-3 → validate → netCDF/plots
              → S3 (forecasts/init=…/lead=…)   +   CloudWatch (timings, validation, min/max)
```

GPU compute is a **SageMaker Processing Job** rather than AWS Batch: Batch runs on
EC2 G instances (blocked by an unraised on-demand-G quota), whereas SageMaker's
quotas auto-approve. Jobs are ephemeral (~1 GPU-hr/day ≈ ~$1.4/day) instead of a
GPU idling 24/7.

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
Container (GPU; weights fetched from S3 at runtime):
```bash
docker build -f server/Dockerfile -t wm3-pipeline .
docker run --gpus all -e WM3_WEIGHTS=/weights/WeatherMesh3.pt wm3-pipeline --lead-hours 6
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
`cycle_success`, `output_valid`, `nan_count`, and field bounds
(`t2m_min_C`/`max`, `mslp_*`, `jet250_max_ms`, `precip_max_mm`, `latent_l2`).
A dashboard visualizes these; an alarm on `cycle_success`/staleness pages SNS.
