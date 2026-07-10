"""Upload forecast artifacts to S3 under a tidy, Hive-partitioned layout."""
import json
import logging

import boto3

from . import config

log = logging.getLogger("wm3pipe.s3io")
_s3 = boto3.client("s3", region_name=config.REGION)


def prefix(init_iso, lead_hours):
    return f"forecasts/init={init_iso}/lead={lead_hours:03d}h"


def upload_cycle(local_files, init_iso, lead_hours, bucket=None):
    """local_files: dict s3-relative-name -> local path. Returns dict of s3 URIs."""
    bucket = bucket or config.OUTPUT_BUCKET
    base = prefix(init_iso, lead_hours)
    uris = {}
    for name, path in local_files.items():
        key = f"{base}/{name}"
        _s3.upload_file(str(path), bucket, key)
        uris[name] = f"s3://{bucket}/{key}"
        log.info("uploaded %s", uris[name])
    return uris


def write_pointer(init_iso, lead_hours, uris, meta, bucket=None):
    """Write forecasts/init=.../metadata.json and a top-level latest.json pointer."""
    bucket = bucket or config.OUTPUT_BUCKET
    doc = {"init": init_iso, "lead_hours": lead_hours, "artifacts": uris, "metadata": meta}
    body = json.dumps(doc, indent=2, default=str).encode()
    _s3.put_object(Bucket=bucket, Key=f"forecasts/init={init_iso}/metadata.json", Body=body)
    _s3.put_object(Bucket=bucket, Key="latest.json", Body=body)
    return f"s3://{bucket}/latest.json"


def write_manifest(bucket=None):
    bucket = bucket or config.OUTPUT_BUCKET
    text = (
        "WeatherMesh-3 forecast outputs\n\n"
        "Layout:\n"
        "  forecasts/init=<YYYY-MM-DDTHHZ>/lead=<NNNh>/weathermesh3.fNNN.nc   CF netCDF\n"
        "  forecasts/init=<...>/lead=<...>/overview.png                        proof plot\n"
        "  forecasts/init=<...>/metadata.json                                  run provenance\n"
        "  latest.json                                                         newest cycle pointer\n"
    )
    _s3.put_object(Bucket=bucket, Key="README.txt", Body=text.encode())
