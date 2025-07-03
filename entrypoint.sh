#!/bin/bash

# Exit on any error
set -e

# Check the MODE environment variable to decide which script to run
case "$MODE" in
  "SELLER")
    echo "Running SELLER..."
    python /app/spl_seller/main_seller.py
    ;;
  *)
    echo "Error: MODE environment variable must be 'BUYER' or 'SELLER', got '$MODE'"
    exit 1
    ;;
esac