#!/usr/bin/env bash
set -euo pipefail

# ======= Bluetooth Scanner + Audio Forwarder (robust shutdown) =======
# IMPORTANT: run this script directly (./run_bt_audio.sh), do NOT `source` it.


# remember script pid / process group id
SCRIPT_PID=$$
PGID="$SCRIPT_PID"   # child processes inherit this PGID by default

# Track background PIDs (optional, for nicer logging)
PIDS=()

# cleanup flag to avoid double-run
_CLEANED_UP=0

cleanup() {
  if [ "$_CLEANED_UP" -ne 0 ]; then
    return
  fi
  _CLEANED_UP=1

  echo ""
  echo "Stopping processes (graceful TERM -> wait -> KILL if needed)..."

  # First attempt: polite termination of entire process group
  # Negative PID means "process group"
  kill -TERM -- -"$PGID" 2>/dev/null || true

  # give children some time to exit gracefully
  SECONDS_TO_WAIT=5
  for i in $(seq 1 $SECONDS_TO_WAIT); do
    sleep 1
    # check if any child processes remain in group
    if ! ps -o pid= -g "$PGID" >/dev/null 2>&1; then
      break
    fi
  done

  # If something still alive, escalate
  if ps -o pid= -g "$PGID" >/dev/null 2>&1; then
    echo "Some processes did not exit, sending SIGKILL..."
    kill -KILL -- -"$PGID" 2>/dev/null || true
  fi

  echo "Cleanup done."
}

# ensure cleanup runs on Ctrl+C, TERM or on shell exit
trap 'cleanup' SIGINT SIGTERM EXIT

# Start bt_scan_publisher in background
ros2 run bt_scan_publisher bt_scan_publisher &
SCAN_PID=$!
PIDS+=("$SCAN_PID")

# Start audio pipeline in a single child process (so $! captures the pipeline group)
# We use bash -c so the pipeline runs under that child process; the whole pipeline still belongs to the same PGID
bash -c 'arecord -D hw:ArrayUAC10 -f S16_LE -c 6 -r 16000 -t raw -q | nc IP 9004' &
AUDIO_PID=$!
PIDS+=("$AUDIO_PID")

# Start TTS and RFID nodes
ros2 run tts_player tts_player_node --ros-args -p alsa_device:=plughw:2,0 &
TTS_PID=$!
PIDS+=("$TTS_PID")

ros2 run rfid_reader rfid_reader &
RFID_PID=$!
PIDS+=("$RFID_PID")

echo "Started bt_scan_publisher (PID $SCAN_PID)"
echo "Started audio pipeline (PID $AUDIO_PID)"
echo "Started tts_player (PID $TTS_PID)"
echo "Started rfid_reader (PID $RFID_PID)"
echo "Press Ctrl+C to stop everything."

# Wait for all background children. When SIGINT arrives, trap triggers cleanup.
# Using wait without args waits for all childs; return code of wait is last job's exit code.
wait
# When wait returns (because children exited or after cleanup killed them), clear trap and exit normally.
trap - SIGINT SIGTERM EXIT
exit 0
