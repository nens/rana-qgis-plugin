# #!/bin/bash
# Xvfb :99 -ac -screen 0 "$XVFB_RES" -nolisten tcp $XVFB_ARGS &
# XVFB_PROC=$!
# export DISPLAY=:99
# sleep 1

# # Start window manager
# fluxbox &

# # Start VNC server
# x11vnc -display :99 -nopw -forever -shared &

# sleep 1

"$@"

# EXIT_CODE=$?   # Capture the exit code of pytest

# kill $XVFB_PROC

# # Exit the container with pytest's exit code
# exit $EXIT_CODE