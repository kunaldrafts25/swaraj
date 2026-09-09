#!/bin/bash
# SWARAJ Health Check Script
# Used by Docker and manual verification

set -euo pipefail

API_URL="${SWARAJ_API_URL:-http://127.0.0.1:8000}"

# Check API health
response=$(curl -s -w "\n%{http_code}" "$API_URL/health" 2>/dev/null || echo -e "\n000")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "200" ]; then
    # Parse response to check registry_ready
    registry_ready=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('registry_ready', False))" 2>/dev/null || echo "false")
    
    if [ "$registry_ready" = "True" ]; then
        echo "HEALTHY: API responding, registry ready"
        exit 0
    else
        echo "DEGRADED: API responding but registry not ready (model may be missing)"
        exit 0  # Still healthy, just degraded
    fi
else
    echo "UNHEALTHY: API not responding (HTTP $http_code)"
    exit 1
fi
