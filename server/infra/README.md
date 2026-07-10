# Orchestration & automation

Two runners share the `run_cycle` entrypoint but **not** the same environment: the
production path runs the **container image**; the interim notebook cron runs the
**source via `uv`**.

## Production: EventBridge → Step Functions → SageMaker Processing
Serverless, ephemeral GPU per cycle. `statemachine.json` is the state machine
(one processing job, retries, catch → SNS).

```bash
# state machine (needs a role that can sagemaker:CreateProcessingJob + iam:PassRole + sns:Publish)
aws stepfunctions create-state-machine --name wm3-cycle \
  --definition file://statemachine.json --role-arn <SFN_ROLE_ARN> --region us-east-1

# 6-hourly trigger
aws scheduler create-schedule --name wm3-6h \
  --schedule-expression 'cron(0 0/6 * * ? *)' \
  --flexible-time-window '{"Mode":"OFF"}' \
  --target '{"Arn":"<STATE_MACHINE_ARN>","RoleArn":"<SCHEDULER_ROLE_ARN>"}' --region us-east-1
```

Blocked as of now only by the `ml.g5.xlarge for processing job usage` quota being
in manual review. Everything else (image, role, S3, SNS) is in place.

## Interim: 6-hourly cron on the SageMaker notebook GPU
`cron-onstart.sh` is a notebook lifecycle that installs a 6-hourly cron and runs one
cycle immediately. This gives a real 24h+ runner today, without waiting on the quota.
Attach it and (re)start the notebook:

```bash
aws sagemaker create-notebook-instance-lifecycle-config \
  --notebook-instance-lifecycle-config-name wm3-cron \
  --on-start Content=$(base64 -i cron-onstart.sh) --region us-east-1
```
