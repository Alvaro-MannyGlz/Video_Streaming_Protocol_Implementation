"""
Client that uses a GBN transport (socket-like) to request a video, receive chunked frames,
and hand them off to FrameHandler for reassembly/playback/QoE metrics.

Usage: Create a gbn_transport object compatible with the expected API:
  - gbn.send(bytes)
  - gbn.recv() -> bytes (blocking), or raises/returns b'' on closed connection
  - gbn.close()

Then call run_client(gbn, filename, ...)

If your transport is different, adapt the calls in receive_loop().
"""

import threading
import time
import logging
import sys
import os
from typing import Optional

# Setup path to find 'shared' folder 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the shared protocol
from shared.gbn_protocol import GBNReceiver, GBNUtilities

# Import the local frame handler (from ./frame_handler.py)
from frame_handler import FrameHandler

logger = logging.getLogger("VideoClient")
logging.basicConfig(level=logging.INFO)

PLAY_CMD_TEMPLATE = "PLAY {}\n".encode('utf-8')

class VideoClient:
    def __init__(self,
                 gbn_transport,
                 filename: str,
                 fps: float = 30.0,
                 buffer_capacity_frames: int = 120,
                 start_frame_id: int = 0,
                 display_callback: Optional[callable] = None):
        """
        gbn_transport: object with send(bytes), recv()->bytes, close()
        """
        self.gbn = gbn_transport
        self.filename = filename
        self.frame_handler = FrameHandler(fps=fps,
                                          buffer_capacity_frames=buffer_capacity_frames,
                                          display_callback=display_callback)
        self.start_frame_id = start_frame_id

        self._recv_thread = None
        self._recv_stop = threading.Event()

    def start(self):
        # Send initial PLAY command
        logger.info("Sending PLAY request for '%s'", self.filename)
        try:
            self.gbn.send(PLAY_CMD_TEMPLATE.replace(b'{}', self.filename.encode('utf-8')))
        except Exception:
            # fallback: format before encoding
            try:
                self.gbn.send(f"PLAY {self.filename}\n".encode('utf-8'))
            except Exception:
                logger.exception("Failed to send PLAY request")
                raise

        # start frame handler playback
        self.frame_handler.start_playback(self.start_frame_id)

        # start recv loop
        self._recv_stop.clear()
        self._recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
        self._recv_thread.start()

    def stop(self):
        self._recv_stop.set()
        if self._recv_thread:
            self._recv_thread.join(timeout=2.0)
        self.frame_handler.stop_playback()
        try:
            self.gbn.close()
        except Exception:
            pass

    def receive_loop(self):
        """
        Loop that receives from gbn and feeds frame_handler.parse_payload_and_add.
        This is the place to adapt to your transport's packet object.
        """
        while not self._recv_stop.is_set():
            try:
                payload = self.gbn.recv()  # blocking
            except Exception:
                logger.exception("Error receiving from GBN transport")
                break

            if not payload:
                logger.info("GBN transport closed/empty payload")
                break

            # feed to frame handler
            try:
                self.frame_handler.parse_payload_and_add(payload)
            except Exception:
                logger.exception("Failed to parse payload")

            # stop if EOS observed by frame_handler
            if self.frame_handler.eos_received:
                logger.info("EOS observed by client; stopping receive loop")
                break

        # Once receive loop finishes, allow playback to finish then stop
        logger.info("Receive loop exiting. Waiting for playback to finish.")
        # Wait a short time for playback to finish
        time.sleep(0.5)

    def get_metrics(self):
        return self.frame_handler.get_metrics()

# Optional helper: example display_callback showing how to save frames or open with cv2 if available
def example_display_callback(frame_id: int, frame_bytes: bytes):
    """
    Default display callback: attempts to show the frame with OpenCV if available,
    otherwise saves to disk as frame_<id>.jpg
    """
    try:
        import cv2
        import numpy as np
        # decode image bytes into numpy array
        nparr = np.frombuffer(frame_bytes, dtype='uint8')
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            # fallback: write to file
            with open(f"frame_{frame_id}.bin", "wb") as f:
                f.write(frame_bytes)
        else:
            cv2.imshow('video_client', img)
            cv2.waitKey(1)  # display briefly
    except Exception:
        # save bytes as file if cv2 not available
        with open(f"frame_{frame_id}.bin", "wb") as f:
            f.write(frame_bytes)

# Convenience run function
def run_client(gbn_transport, filename: str, fps: float = 30.0, duration_seconds: Optional[float] = None):
    """
    Starts the client and returns metrics after streaming finishes or duration_seconds passes.
    """
    client = VideoClient(gbn_transport, filename, fps=fps, display_callback=example_display_callback)
    client.start()
    start = time.time()
    try:
        # Optionally enforce a maximum runtime
        while True:
            if duration_seconds and (time.time() - start) > duration_seconds:
                logger.info("Max duration reached; stopping client.")
                break
            if client.frame_handler.eos_received:
                # allow playback to finish gracefully
                time.sleep(0.5)
                break
            time.sleep(0.1)
    finally:
        client.stop()
    return client.get_metrics()
