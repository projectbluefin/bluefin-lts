#!/usr/bin/env bash
# Refresh stale mirror metadata once; dependency and signature failures stay fatal.
dnf_retry() {
    local log status attempt
    log=$(mktemp)
    for attempt in 1 2; do
        status=0
        dnf "$@" 2>&1 | tee "$log" || status=$?
        if [ "$status" -eq 0 ]; then rm -f "$log"; return 0; fi
        if [ "$attempt" -eq 2 ] || ! grep -Eq \
            'Failed to download metadata|Cannot download.*all mirrors|all mirrors were already tried|Curl error' "$log"; then
            rm -f "$log"
            return "$status"
        fi
        echo 'Refreshing stale repository metadata before one retry' >&2
        dnf clean metadata || { rm -f "$log"; return 1; }
    done
}
