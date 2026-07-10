#!/bin/bash
# SageMaker notebook lifecycle (on-start): interim 24h+ runner.
# Installs a 6-hourly cron that runs one WM-3 cycle, and kicks one off now.
# Used while the SageMaker processing-job GPU quota is in manual review; the
# production runner is EventBridge -> Step Functions -> Processing (statemachine.json).
set -ex

cat > /home/ec2-user/SageMaker/wm3_cron.sh <<'C'
#!/bin/bash
export HOME=/home/ec2-user
export PATH=$HOME/.local/bin:$PATH
cd /home/ec2-user/SageMaker/WeatherMesh-3 || exit 0
TS=$(date -u +%Y%m%dT%H%M%SZ)
LOG=/home/ec2-user/SageMaker/wm3_cron_$TS.log
WM3_OUTPUT_BUCKET=wm3-forecasts-194290773983 AWS_REGION=us-east-1 \
  uv run python -m server.wm3pipe.run_cycle --lead-hours 6 \
    --weights model/WeatherMesh3.pt --device cuda > "$LOG" 2>&1
aws s3 cp "$LOG" "s3://wm3-forecasts-194290773983/_runlogs/cron_$TS.log" || true
C
chmod +x /home/ec2-user/SageMaker/wm3_cron.sh
chown ec2-user:ec2-user /home/ec2-user/SageMaker/wm3_cron.sh

echo "0 */6 * * * /home/ec2-user/SageMaker/wm3_cron.sh" | crontab -u ec2-user -
sudo -u ec2-user -H nohup /home/ec2-user/SageMaker/wm3_cron.sh >/dev/null 2>&1 &
exit 0
