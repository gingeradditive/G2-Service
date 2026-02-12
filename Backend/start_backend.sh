#!/bin/bash

# Install Backend dependencies
echo "Installing Backend dependencies..."
pip3 install -r requirements.txt

# Start the Backend server
echo "Starting Backend server..."
python3 server.py
