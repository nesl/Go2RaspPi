#!/usr/bin/env python3
import threading
import time
import json
from typing import Optional, Tuple

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSHistoryPolicy, QoSReliabilityPolicy
from std_msgs.msg import String, UInt64

# Hardware libs (must be installed on the Pi)
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522


class RFIDReaderNode(Node):
    """
    ROS2 node that reads MFRC522 tags and publishes:
      - /rfid/tag_id           (UInt64)   → numeric UID
      - /rfid/text             (String)   → text stored on the tag (if any)
      - /rfid/read             (String)   → JSON: {"id": <int>, "text": "<str>", "ts": <float>}
    Parameters:
      poll_sleep_sec (double): sleep between polls after a read (default 0.25)
      min_repeat_sec (double): suppress re-publishing the same tag within this window (default 1.0)
      frame_id       (string): optional tag frame id in JSON (default "rfid_link")
      log_reads      (bool)  : log every published read (default True)
    """

    def __init__(self):
        super().__init__('rfid_reader')
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )

        self.pub_id = self.create_publisher(UInt64, 'rfid/tag_id', qos)
        self.pub_text = self.create_publisher(String, 'rfid/text', qos)
        self.pub_json = self.create_publisher(String, 'rfid/read', qos)

        # Parameters
        self.declare_parameter('poll_sleep_sec', 0.25)
        self.declare_parameter('min_repeat_sec', 1.0)
        self.declare_parameter('frame_id', 'base_link')
        self.declare_parameter('log_reads', True)

        self.poll_sleep_sec = float(self.get_parameter('poll_sleep_sec').value)
        self.min_repeat_sec = float(self.get_parameter('min_repeat_sec').value)
        self.frame_id = str(self.get_parameter('frame_id').value)
        self.log_reads = bool(self.get_parameter('log_reads').value)

        # Reader setup
        self.reader = SimpleMFRC522()

        # Dedup state
        self._last_id: Optional[int] = None
        self._last_pub_at: float = 0.0

        # Thread to avoid blocking rclpy executor
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

        self.get_logger().info('RFIDReaderNode started. Waiting for tags...')

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                # This call blocks until a tag is present.
                tag_id, text = self.reader.read()
                now = time.time()

                # Debounce identical consecutive reads
                if self._should_publish(tag_id, now):
                    self._publish(tag_id, text or '', now)
                    self._last_id = tag_id
                    self._last_pub_at = now

                # Short sleep to avoid frantic loops if the tag stays on the reader
                time.sleep(self.poll_sleep_sec)

            except Exception as e:
                # Log and keep trying (GPIO glitches, transient errors)
                self.get_logger().warn(f'RFID read error: {e!r}')
                time.sleep(0.5)

    def _should_publish(self, tag_id: int, now: float) -> bool:
        if self._last_id is None:
            return True
        if tag_id != self._last_id:
            return True
        return (now - self._last_pub_at) >= self.min_repeat_sec

    def _publish(self, tag_id: int, text: str, ts: float):
        # /rfid/tag_id
        id_msg = UInt64()
        id_msg.data = int(tag_id) & 0xFFFFFFFFFFFFFFFF
        self.pub_id.publish(id_msg)

        # /rfid/text
        txt_msg = String()
        txt_msg.data = text
        self.pub_text.publish(txt_msg)

        # /rfid/read (JSON bundle)
        bundle = {
            "id": int(tag_id),
            "text": text,
            "ts": ts,
            "frame_id": self.frame_id,
        }
        json_msg = String()
        json_msg.data = json.dumps(bundle, ensure_ascii=False)
        self.pub_json.publish(json_msg)

        if self.log_reads:
            self.get_logger().info(f'RFID tag read → id={tag_id}, text="{text.strip()}"')

    def destroy_node(self):
        # Stop thread and cleanup GPIO safely
        self._stop_event.set()
        try:
            if self._thread.is_alive():
                self._thread.join(timeout=2.0)
        finally:
            try:
                GPIO.cleanup()
            except Exception:
                pass
        super().destroy_node()


def main():
    rclpy.init()
    node = RFIDReaderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
