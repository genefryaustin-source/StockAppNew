#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${BASE_URL:-https://aiqintellus.com/legal}"

PAGES=(
    "privacy-policy.html"
    "terms-of-service.html"
    "cookie-policy.html"
    "financial-disclaimer.html"
    "risk-disclosure.html"
    "ai-disclosure.html"
    "market-data-disclaimer.html"
    "acceptable-use-policy.html"
    "api-license.html"
    "security.html"
    "accessibility.html"
    "contact.html"
)

for page in "${PAGES[@]}"; do
    printf 'Checking %s/%s ... ' "$BASE_URL" "$page"

    status="$(
        curl \
            --silent \
            --output /dev/null \
            --write-out '%{http_code}' \
            --max-time 20 \
            "$BASE_URL/$page"
    )"

    if [[ "$status" != "200" ]]; then
        printf 'FAILED (%s)\n' "$status"
        exit 1
    fi

    printf 'OK\n'
done
