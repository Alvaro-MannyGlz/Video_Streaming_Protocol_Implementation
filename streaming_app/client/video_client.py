"""
Client that uses a GBN transport (socket-like) to request a video, receive chunked frames,
and hand them off to FrameHandler for reassembly/playback/QoE metrics.
"""

import threading
import time
import logging
import sys
import os
import socket
from typing import Optional
from queue import Queue
import cv2
import numpy as np

frame_queue = Queue()

# Setup path to find 'shared' folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared.gbn_protocol import GBNReceiver
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
            cmd = PLAY_CMD_TEMPLATE.replace(b'{}', self.filename.encode('utf-8'))
            self.gbn.send(cmd)
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
        while not self._recv_stop.is_set():
            try:
                # GBNReceiver.recv() should block until a valid, in-order packet arrives
                payload = self.gbn.recv()
            except Exception:
                logger.exception("Error receiving from GBN transport")
                break

            if not payload:
                # This usually happens if connection closes
                break

            # feed to frame handler
            try:
                self.frame_handler.parse_payload_and_add(payload)
            except Exception:
                logger.exception("Failed to parse payload")

            if self.frame_handler.eos_received:
                logger.info("EOS observed by client; stopping receive loop")
                break

        logger.info("Receive loop exiting. Waiting for playback to finish.")
        time.sleep(0.5)

    def get_metrics(self):
        return self.frame_handler.get_metrics()

def example_display_callback(frame_id: int, frame_bytes: bytes):
    frame_queue.put(frame_bytes)

def run_client(gbn_transport, filename: str, fps: float = 30.0):
    client = VideoClient(gbn_transport, filename, fps=fps, display_callback=example_display_callback)
    client.start()
    
    # Capture Start Time for Duration/Completion calculation
    start_time = time.time()

    try:
        while not client.frame_handler.eos_received:
            # pull frame from queue
            if not frame_queue.empty():
                frame_bytes = frame_queue.get()
                nparr = np.frombuffer(frame_bytes, dtype='uint8')
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    cv2.imshow("CinePy Client", img)
                    cv2.waitKey(1)
            time.sleep(0.01)

    except KeyboardInterrupt:
        pass

    finally:
        client.stop()
        cv2.destroyAllWindows()
        
        # --- METRICS REPORT ---
        end_time = time.time()
        completion_time = end_time - start_time
        metrics = client.get_metrics()
        
        print("\n" + "="*30)
        print("CLIENT REPORT")
        print("="*30)
        print(f"Completion Time : {completion_time:.2f} seconds")
        print(f"Stall Time (Lag): {metrics['stall_time_seconds']} seconds")
        print(f"Dropped Frames  : {metrics['dropped_frames']}")
        print("="*30 + "\n")


# --- MAIN BLOCK ---
if __name__ == "__main__":
    # Usage: python video_client.py <server_ip> <server_port> <filename>
    server_ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    server_port = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
    filename = sys.argv[3] if len(sys.argv) > 3 else "test_video.mp4"

    print(f"Connecting to {server_ip}:{server_port} requesting {filename}")

    # 1. Create UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # 2. Wrap it in GBNReceiver (which we define in shared/gbn_protocol.py)
    transport = GBNReceiver(sock, (server_ip, server_port))
    # 3. Run
    run_client(transport, filename)