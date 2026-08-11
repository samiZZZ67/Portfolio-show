#!/usr/bin/env bash
# Frontend build script for Render Static Site
if [ -n "$ELA_API_URL" ]; then
  echo "Injecting ELA_API_URL: $ELA_API_URL"
  sed -i "s|__ELA_API_URL_PLACEHOLDER__|${ELA_API_URL}|g" config.js
else
  echo "No ELA_API_URL provided, keeping default"
fi
echo "Frontend build completed successfully."
