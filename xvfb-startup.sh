#!/bin/bash
Xvfb :99 -ac -screen 0 "$XVFB_RES" -nolisten tcp $XVFB_ARGS &
XVFB_PROC=$!
sleep 1
export DISPLAY=:99
"$@"

EXIT_CODE=$?   # Capture the exit code of pytest

kill $XVFB_PROC

# Exit the container with pytest's exit code
exit $EXIT_CODE