#!/usr/bin/env bash

set -xeuo pipefail

WELCOME_PROFILE="/etc/profile.d/uwelcome.sh"

# The desktop session sources /etc/profile non-interactively. Do not export the
# deduplication marker there, otherwise Ptyxis inherits it and suppresses the
# banner when it starts the user's interactive shell.
# shellcheck disable=SC2016 # single quotes are deliberate: literal match/sed text
grep -F 'if [ "$(id -u)" != "0" ] && [ -z "${UWELCOME_SHOWN-}" ]; then' "${WELCOME_PROFILE}"
sed -i 's/if \[ "$(id -u)" != "0" \] && \[ -z "${UWELCOME_SHOWN-}" \]; then/if [[ $- == *i* ]] \&\& [ "$(id -u)" != "0" ] \&\& [ -z "${UWELCOME_SHOWN-}" ]; then/' "${WELCOME_PROFILE}"
grep -F 'if [[ $- == *i* ]] && [ "$(id -u)" != "0" ] && [ -z "${UWELCOME_SHOWN-}" ]; then' "${WELCOME_PROFILE}"
# shellcheck enable=SC2016

# Keep the inherited hook and its configured MOTD command actionable.
test -x /usr/bin/uwelcome
test -x /usr/bin/umotd
