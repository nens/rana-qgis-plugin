#!/bin/bash
# Set up virtual screen
Xvfb :99 -ac -screen 0 "$XVFB_RES" -nolisten tcp $XVFB_ARGS &
XVFB_PROC=$!
export DISPLAY=:99
sleep 1

# Start window manager
fluxbox &

# Start VNC server for visual inspection (optional)
x11vnc -display :99 -nopw -forever -shared &

ffmpeg -f x11grab -video_size 1920x1080 -framerate 15 -i :99 -c:v libx264 -preset veryfast -crf 28 -pix_fmt yuv420p -movflags +faststart output.mp4 &
FFMPEG_PROC=$!

sleep 1

"$@"
EXIT_CODE=$?   # Capture the exit code of pytest

# Stop ffmpeg and xvfb cleanly
kill -INT $FFMPEG_PROC
wait $FFMPEG_PROC
kill $XVFB_PROC

# Exit the container with pytest's exit code
exit $EXIT_CODE