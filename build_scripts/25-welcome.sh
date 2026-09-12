#!/usr/bin/env bash

set -xeuo pipefail

WELCOME_PROFILE="/etc/profile.d/uwelcome.sh"

# The desktop session sources /etc/profile non-interactively. Do not export the
# deduplication marker there, otherwise Ptyxis inherits it and suppresses the
# banner when it starts the user's interactive shell.
grep -F 'if [ "$(id -u)" != "0" ] && [ -z "${UWELCOME_SHOWN-}" ]; then' "${WELCOME_PROFILE}"
sed -i 's/if \[ "$(id -u)" != "0" \] && \[ -z "${UWELCOME_SHOWN-}" \]; then/if [[ $- == *i* ]] \&\& [ "$(id -u)" != "0" ] \&\& [ -z "${UWELCOME_SHOWN-}" ]; then/' "${WELCOME_PROFILE}"
grep -F 'if [[ $- == *i* ]] && [ "$(id -u)" != "0" ] && [ -z "${UWELCOME_SHOWN-}" ]; then' "${WELCOME_PROFILE}"

# Keep the inherited hook and its configured MOTD command actionable.
test -x /usr/bin/uwelcome
test -x /usr/bin/umotd
