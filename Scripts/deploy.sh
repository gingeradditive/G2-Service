#!/bin/bash
set -e

export DISCOVERY_HOST="discovery.local"
export DISCOVERY_HOST="192.168.1.194"

rsync -avz --delete \
  --exclude '__pycache__' \
  --exclude '.venv' \
  ./ pi@${DISCOVERY_HOST}:/home/pi/G2-Service

ssh pi@${DISCOVERY_HOST} "sudo systemctl restart fastapi-app"
