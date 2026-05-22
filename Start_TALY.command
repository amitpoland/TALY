#!/bin/bash
cd "$(dirname "$0")" || exit 1
./scripts/start-local.sh
echo
echo "TALY launcher finished. Keep the server windows/processes running while using the app."
echo "Press Enter to close this window."
read -r
