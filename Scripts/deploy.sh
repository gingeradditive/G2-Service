#!/bin/bash
set -e

rsync -avz --delete \
  --exclude '__pycache__' \
  --exclude '.venv' \
  ./ pi@discovery.local:/home/pi/G2-Service

ssh pi@discovery.local "sudo systemctl restart fastapi-app"
