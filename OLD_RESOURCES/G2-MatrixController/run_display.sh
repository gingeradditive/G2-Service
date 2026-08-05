#!/bin/bash

MSG="$1"

/home/pi/G2-MatrixController/venv/bin/python \
/home/pi/G2-MatrixController/led_matrix_display.py "$MSG" &
