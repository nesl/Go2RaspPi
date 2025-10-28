#!/usr/bin/env python3
import threading
import subprocess
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from std_msgs.msg import UInt8MultiArray
from std_msgs.msg import Bool

class TTSPlayerNode(Node):
    def __init__(self):
        super().__init__("tts_player")

        # Parameters (change if your device name/rate differ)
        self.declare_parameter("alsa_device", "default")   # e.g., "plughw:1,0" or "hw:0,0" or "default"
        self.declare_parameter("sample_rate", 16000)
        self.declare_parameter("channels", 1)
        self.declare_parameter("sample_format", "S16_LE")  # PCM 16-bit little-endian

        self._alsa_device = self.get_parameter("alsa_device").get_parameter_value().string_value
        self._rate = int(self.get_parameter("sample_rate").get_parameter_value().integer_value or 16000)
        self._ch = int(self.get_parameter("channels").get_parameter_value().integer_value or 1)
        self._fmt = self.get_parameter("sample_format").get_parameter_value().string_value or "S16_LE"

        # Reliable delivery since we send whole utterance in one message
        qos = QoSProfile(depth=5)
        qos.reliability = QoSReliabilityPolicy.RELIABLE
        qos.history = QoSHistoryPolicy.KEEP_LAST

        self.sub = self.create_subscription(UInt8MultiArray, "/tts_wav", self.cb, qos)
        self.get_logger().info(f"🎧 TTSPlayer ready on /tts_wav → aplay ({self._fmt}, {self._rate} Hz, ch={self._ch}) @ {self._alsa_device}")

        self.busy_pub = self.create_publisher(Bool, "/tts_busy", 1)
        self._busy = False


        self._lock = threading.Lock()
        self._proc = None  # aplay process


    def _set_busy(self, val: bool):
        if self._busy == val:
            return
        self._busy = val
        self.busy_pub.publish(Bool(data=val))
        self.get_logger().info("🟠 speaking=True" if val else "🟢 speaking=False")


    def _stop_current(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._proc = None

    def cb(self, msg: UInt8MultiArray):
        data = bytes(msg.data)
        if not data:
            self.get_logger().warn("Received empty WAV payload")
            return

        with self._lock:
            # Stop previous playback if still running
            self._stop_current()

            # Pipe bytes into aplay on stdin
            cmd = [
                "aplay",
                "-q",                         # quiet
                "-D", self._alsa_device,      # ALSA device
                "-f", self._fmt,              # sample format
                "-r", str(self._rate),        # sample rate
                "-c", str(self._ch),          # channels
            ]

            # If you send WAV containers (RIFF) not raw PCM, add "-t", "wav"
            # We *are* sending WAV bytes, so:
            cmd += ["-t", "wav"]
            try:
                self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                self._set_busy(True)
                self._proc.stdin.write(data)
                self._proc.stdin.close()
                self.get_logger().info(f"▶️  Playing {len(data)} bytes…")

                def _wait_and_clear():
                    try:
                        self._proc.wait()
                    finally:
                        self._set_busy(False)

                threading.Thread(target=_wait_and_clear, daemon=True).start()

            except FileNotFoundError:
                self.get_logger().error("aplay not found. Install with: sudo apt-get install alsa-utils")
            except Exception as e:
                self.get_logger().error(f"Playback error: {e}")


def main():
    rclpy.init()
    node = TTSPlayerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
