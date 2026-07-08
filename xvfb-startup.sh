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
X11VNC_PROC=$!

ffmpeg -loglevel error -y -f x11grab -video_size 1920x1080 -framerate 15 -i :99 -c:v libx264 -preset veryfast -crf 28 -pix_fmt yuv420p -movflags +faststart output.mp4 &
FFMPEG_PROC=$!

sleep 1

"$@"
EXIT_CODE=$?   # Capture the exit code of pytest

# Stop ffmpeg, x11vnc and xvfb cleanly
kill -INT $FFMPEG_PROC
# Wait up to 10 seconds for ffmpeg to finalize, then force kill
for i in $(seq 1 10); do
    kill -0 $FFMPEG_PROC 2>/dev/null || break
    sleep 1
done
kill -9 $FFMPEG_PROC 2>/dev/null
wait $FFMPEG_PROC 2>/dev/null
kill $X11VNC_PROC 2>/dev/null
kill $XVFB_PROC 2>/dev/null

# Exit the container with pytest's exit code
exit $EXIT_CODE