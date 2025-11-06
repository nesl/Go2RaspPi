#!/usr/bin/env python3
import threading
import subprocess
import sys
import time
import queue

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from std_msgs.msg import UInt8MultiArray, Bool


class TTSPlayerNode(Node):
    def __init__(self):
        super().__init__("tts_player")

        # Parameters
        self.declare_parameter("alsa_device", "default")   # e.g., "plughw:1,0" or "hw:0,0" or "default"
        self.declare_parameter("sample_rate", 16000)
        self.declare_parameter("channels", 1)
        self.declare_parameter("sample_format", "S16_LE")  # PCM 16-bit little-endian
        self.declare_parameter("queue_size", 16)           # max pending clips
        self.declare_parameter("enqueue_block_ms", 150)    # how long to block if queue is full before dropping

        self._alsa_device = self.get_parameter("alsa_device").get_parameter_value().string_value
        self._rate = int(self.get_parameter("sample_rate").get_parameter_value().integer_value or 16000)
        self._ch = int(self.get_parameter("channels").get_parameter_value().integer_value or 1)
        self._fmt = self.get_parameter("sample_format").get_parameter_value().string_value or "S16_LE"
        self._qmax = int(self.get_parameter("queue_size").get_parameter_value().integer_value or 16)
        self._enqueue_block_ms = int(self.get_parameter("enqueue_block_ms").get_parameter_value().integer_value or 150)

        # QoS
        qos = QoSProfile(depth=5)
        qos.reliability = QoSReliabilityPolicy.RELIABLE
        qos.history = QoSHistoryPolicy.KEEP_LAST

        # ROS I/O
        self.sub = self.create_subscription(UInt8MultiArray, "/tts_wav", self.cb, qos)
        self.busy_pub = self.create_publisher(Bool, "/tts_busy", 1)

        # State
        self._busy = False
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=self._qmax)
        self._stop_evt = threading.Event()

        # Worker
        self._worker = threading.Thread(target=self._run_player, daemon=True)
        self._worker.start()

        self.get_logger().info(
            f"🎧 TTSPlayer (queued) on /tts_wav → aplay ({self._fmt}, {self._rate} Hz, ch={self._ch}) @ {self._alsa_device}"
        )

    # -------- Helpers --------
    def _set_busy(self, val: bool):
        if self._busy == val:
            return
        self._busy = val
        try:
            self.busy_pub.publish(Bool(data=val))
        except Exception:
            pass
        self.get_logger().info("🟠 speaking=True" if val else "🟢 speaking=False")

    @staticmethod
    def _guess_container(data: bytes) -> str:
        # Detect a RIFF/WAVE header; otherwise treat as raw PCM
        return "wav" if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE" else "raw"

    # -------- Subscriber: enqueue only --------
    def cb(self, msg: UInt8MultiArray):
        data = bytes(msg.data)
        if not data:
            self.get_logger().warn("Received empty WAV payload")
            return

        # Try to enqueue; wait a little if full; then drop newest if still full
        try:
            self._queue.put(data, timeout=self._enqueue_block_ms / 1000.0)
            self.get_logger().info(f"📥 queued clip ({len(data)} bytes). depth={self._queue.qsize()}/{self._qmax}")
        except queue.Full:
            self.get_logger().warn("Queue full — dropping newest clip to preserve latency.")
            # Drop-policy alternative: drop oldest instead of newest
            # try:
            #     _ = self._queue.get_nowait()
            #     self._queue.put_nowait(data)
            #     self.get_logger().warn("Queue full — dropped oldest, enqueued newest.")
            # except queue.Empty:
            #     pass

    # -------- Worker: play FIFO, no interruption --------
    def _run_player(self):
        while not self._stop_evt.is_set():
            try:
                data = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if data is None:  # sentinel for shutdown
                break

            # Build aplay command per payload type
            ctype = self._guess_container(data)
            cmd = [
                "aplay",
                "-q",
                "-D", self._alsa_device,
                "-f", self._fmt,
                "-r", str(self._rate),
                "-c", str(self._ch),
                "-t", ctype,
            ]

            proc = None
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                self._set_busy(True)
                assert proc.stdin is not None
                proc.stdin.write(data)
                proc.stdin.flush()
                proc.stdin.close()
                self.get_logger().info(f"▶️  Playing {len(data)} bytes…")
                proc.wait()
            except FileNotFoundError:
                self.get_logger().error("aplay not found. Install with: sudo apt-get install alsa-utils")
            except Exception as e:
                self.get_logger().error(f"Playback error: {e}")
            finally:
                self._set_busy(False)
                try:
                    if proc and proc.poll() is None:
                        proc.terminate()
                except Exception:
                    pass
                # let next item play
                self._queue.task_done()

    # -------- Shutdown --------
    def destroy_node(self):
        # Stop worker cleanly
        self._stop_evt.set()
        try:
            self._queue.put_nowait(None)  # sentinel
        except Exception:
            pass
        try:
            if self._worker.is_alive():
                self._worker.join(timeout=1.0)
        except Exception:
            pass
        super().destroy_node()


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
