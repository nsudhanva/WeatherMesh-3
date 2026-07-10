# Automation

**The live runner is a 6-hourly cron on the SageMaker notebook GPU** — `cron-onstart.sh`
is the notebook lifecycle that (on boot) ensures `crond` is running, installs the
crontab (`0 */6 * * *`), and kicks off one cycle immediately. Each run self-installs
`uv`, pulls the latest `server/` code, runs `run_cycle`, writes to S3, emits CloudWatch
metrics, and publishes to SNS on failure.

Deploy / update it:

```bash
aws sagemaker create-notebook-instance-lifecycle-config \
  --notebook-instance-lifecycle-config-name wm3-cron \
  --on-start Content=$(base64 -i cron-onstart.sh) --region us-east-1
# attach to the notebook (while stopped) and start it
aws sagemaker update-notebook-instance --notebook-instance-name weathermesh3-gpu-nb \
  --lifecycle-config-name wm3-cron --region us-east-1
```

`dash.json` is the CloudWatch dashboard body (`aws cloudwatch put-dashboard
--dashboard-name WeatherMesh3 --dashboard-body file://dash.json`).

## Not implemented: serverless orchestration

A production system would replace the always-on notebook with **EventBridge →
Step Functions → SageMaker Processing** (ephemeral GPU per cycle). It is **not built
here**: the `ml.g5.xlarge` processing-job quota is in manual review, so a Processing
job cannot launch, and there was no way to finish *and test* that path. The notebook
cron already satisfies the requirement (automated, real-time, 24h+), so this is left as
a described future step (see the docs' "99.9% uptime" answer), not as dead IaC.
