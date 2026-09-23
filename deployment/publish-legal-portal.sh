#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/stockapp/current}"
SOURCE_DIR="$APP_DIR/modules/legal_portal/pages"
STATIC_ROOT="${STATIC_ROOT:-/var/www/html/legal}"
NGINX_SERVICE="${NGINX_SERVICE:-nginx}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-https://aiqintellus.com/legal}"

log() {
    printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*"
}

fail() {
    log "FAILED: $*"
    exit 1
}

[[ -d "$SOURCE_DIR" ]] || fail "Legal source directory missing: $SOURCE_DIR"

log "Publishing legal portal documents"
install -d -o root -g root -m 0755 "$STATIC_ROOT"

mapfile -t HTML_FILES < <(find "$SOURCE_DIR" -maxdepth 1 -type f -name '*.html' -printf '%f\n' | sort)

(( ${#HTML_FILES[@]} > 0 )) || fail "No legal HTML files found"

for filename in "${HTML_FILES[@]}"; do
    install \
        -o root \
        -g root \
        -m 0644 \
        "$SOURCE_DIR/$filename" \
        "$STATIC_ROOT/$filename"

    log "Published $filename"
done

if [[ -f "$APP_DIR/manifest/documents.json" ]]; then
    install \
        -o root \
        -g root \
        -m 0644 \
        "$APP_DIR/manifest/documents.json" \
        "$STATIC_ROOT/documents.json"
fi

log "Testing Nginx configuration"
nginx -t

log "Reloading Nginx"
systemctl reload "$NGINX_SERVICE"

log "Verifying public legal pages"

for filename in "${HTML_FILES[@]}"; do
    curl \
        --fail \
        --silent \
        --show-error \
        --retry 3 \
        --retry-delay 2 \
        --max-time 20 \
        "$PUBLIC_BASE_URL/$filename" \
        >/dev/null

    log "Verified $PUBLIC_BASE_URL/$filename"
done

log "Legal portal publication completed successfully"
