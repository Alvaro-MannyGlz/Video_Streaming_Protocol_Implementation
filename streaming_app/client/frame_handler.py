"""
FrameHandler:
- Reassembles frames from chunked payloads.
- Maintains a playback buffer (a mapping frame_id -> frame_bytes).
- Provides a playback loop that consumes frames at target FPS.
- Computes QoE metrics: dropped_frames, stall_time.

Assumptions:
- Payload format: 4 bytes frame_id (uint32), 2 bytes chunk_idx (uint16),
  2 bytes total_chunks (uint16), then chunk bytes.
- End-of-stream: frame_id == 0xFFFFFFFF and total_chunks == 0xFFFF

If your payload format differs, update parse_payload().
"""

import struct
import time
import threading
import collections
import logging
from typing import Optional, Callable

logger = logging.getLogger("FrameHandler")
logging.basicConfig(level=logging.INFO)

END_OF_STREAM_FRAME_ID = 0xFFFFFFFF
END_OF_STREAM_TOTAL_CHUNKS = 0xFFFF

class FrameReassemblyBuffer:
    def __init__(self):
        # for each frame_id -> dict(chunk_idx -> bytes), expected total_chunks
        self._frames = {}  # frame_id -> {'chunks': dict, 'total': int, 'received': int, 'first_arrival': float}
        self._lock = threading.Lock()

    def add_chunk(self, frame_id: int, chunk_idx: int, total_chunks: int, data: bytes):
        with self._lock:
            if frame_id not in self._frames:
                self._frames[frame_id] = {
                    'chunks': {},
                    'total': total_chunks,
                    'received': 0,
                    'first_arrival': time.time(),
                }
            entry = self._frames[frame_id]
            # in case total_chunks was previously unknown or mismatched, prefer the new value if greater.
            entry['total'] = max(entry['total'], total_chunks)
            if chunk_idx not in entry['chunks']:
                entry['chunks'][chunk_idx] = data
                entry['received'] += 1

    def is_complete(self, frame_id: int) -> bool:
        with self._lock:
            e = self._frames.get(frame_id)
            if not e:
                return False
            return e['received'] >= e['total'] and e['total'] > 0

    def assemble_frame(self, frame_id: int) -> Optional[bytes]:
        with self._lock:
            e = self._frames.get(frame_id)
            if not e:
                return None
            if e['received'] < e['total'] or e['total'] <= 0:
                return None
            # assemble in chunk order 0..total-1
            chunks = [e['chunks'].get(i, b'') for i in range(e['total'])]
            frame_bytes = b''.join(chunks)
            # optional: delete reassembly buffer for this frame to free memory
            del self._frames[frame_id]
            return frame_bytes

    def cleanup_older_than(self, min_frame_id: int):
        """Remove frames with frame_id < min_frame_id"""
        with self._lock:
            to_delete = [fid for fid in self._frames if fid < min_frame_id]
            for fid in to_delete:
                del self._frames[fid]

class FrameHandler:
    def __init__(self,
                 fps: float = 30.0,
                 buffer_capacity_frames: int = 120,
                 display_callback: Optional[Callable[[int, bytes], None]] = None):
        """
        display_callback(frame_id:int, frame_bytes:bytes) -> None
          - optional callback to render or save a frame when it's displayed.
        """
        self.fps = fps
        self.frame_interval = 1.0 / fps
        self.buffer_capacity_frames = buffer_capacity_frames
        self.reassembly = FrameReassemblyBuffer()
        # playback buffer: maps frame_id -> frame_bytes
        self.playback_buffer = {}
        self.playback_lock = threading.Lock()
        self.display_callback = display_callback

        self.expected_frame_id = 0
        self._playback_thread = None
        self._playback_stop = threading.Event()

        # QoE metrics
        self.dropped_frames = 0
        self.stall_time = 0.0
        self._stalling = False
        self._stall_start = None

        # stats
        self.received_frames_total = 0
        self.frames_reassembled_total = 0
        self.eos_received = False

    def parse_payload_and_add(self, payload: bytes):
        """
        Parse the bytes payload into (frame_id, chunk_idx, total_chunks, data) and add chunk.
        Header format: !IHH  (uint32, uint16, uint16)
        """
        if len(payload) < 8:
            logger.warning("Received payload too short; ignoring")
            return
        frame_id, chunk_idx, total_chunks = struct.unpack('!IHH', payload[:8])
        chunk_data = payload[8:]
        self.received_frames_total += 1

        # End of stream sentinel
        if frame_id == END_OF_STREAM_FRAME_ID and total_chunks == END_OF_STREAM_TOTAL_CHUNKS:
            logger.info("End of stream received.")
            self.eos_received = True
            return

        self.reassembly.add_chunk(frame_id, chunk_idx, total_chunks, chunk_data)

        # If frame complete, move to playback buffer
        if self.reassembly.is_complete(frame_id):
            frame_bytes = self.reassembly.assemble_frame(frame_id)
            if frame_bytes is not None:
                with self.playback_lock:
                    if len(self.playback_buffer) < self.buffer_capacity_frames:
                        self.playback_buffer[frame_id] = frame_bytes
                        self.frames_reassembled_total += 1
                    else:
                        # buffer full: drop oldest in buffer to make space (or drop new frame)
                        # We'll drop the new frame (conservative) and count as dropped (playback will miss it).
                        logger.info("Playback buffer full; dropping reassembled frame %d", frame_id)
                        self.dropped_frames += 1

    def start_playback(self, start_frame_id: int = 0):
        """Start playback loop in separate thread."""
        self.expected_frame_id = start_frame_id
        self._playback_stop.clear()
        self._playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._playback_thread.start()

    def stop_playback(self):
        self._playback_stop.set()
        if self._playback_thread:
            self._playback_thread.join(timeout=2.0)

    def _playback_loop(self):
        next_display_time = time.time()
        while not self._playback_stop.is_set():
            now = time.time()
            if now < next_display_time:
                time.sleep(min(0.01, next_display_time - now))
                continue

            # Attempt to fetch expected frame
            with self.playback_lock:
                frame = self.playback_buffer.pop(self.expected_frame_id, None)

            if frame is None:
                # frame missing at scheduled display time -> dropped or stall
                # Wait briefly for small network jitter: we allow a tiny grace window (e.g., 50ms)
                grace = min(0.05, self.frame_interval * 0.5)
                t_wait_start = time.time()
                waited = 0.0
                found = False
                while waited < grace and not self._playback_stop.is_set():
                    with self.playback_lock:
                        frame = self.playback_buffer.pop(self.expected_frame_id, None)
                    if frame is not None:
                        found = True
                        break
                    time.sleep(0.005)
                    waited = time.time() - t_wait_start

                if found:
                    # display found frame
                    if self._stalling:
                        # we were stalling; accumulate stall time and clear.
                        self._stalling = False
                        self._stall_start = None
                else:
                    # Cannot find frame within grace window -> treat as stall
                    # Start stall if not already
                    if not self._stalling:
                        self._stalling = True
                        self._stall_start = time.time()
                    # Wait until frame becomes available or EOS
                    while not self._playback_stop.is_set():
                        with self.playback_lock:
                            frame = self.playback_buffer.pop(self.expected_frame_id, None)
                        if frame is not None:
                            # stop stall
                            if self._stalling and self._stall_start is not None:
                                additional = time.time() - self._stall_start
                                self.stall_time += additional
                                self._stalling = False
                                self._stall_start = None
                            break
                        # If EOS and no frame will come, count as dropped and move on
                        if self.eos_received:
                            # Consider frame dropped, increment metrics, move to next frame
                            logger.debug("EOS reached and frame %d not available: counting as dropped", self.expected_frame_id)
                            self.dropped_frames += 1
                            break
                        time.sleep(0.01)  # wait a bit for arrivals
                    # after stall resolved or dropped, continue loop: if frame still None and eos -> continue
            # If we have frame now, display it
            if frame is not None:
                try:
                    if self.display_callback:
                        self.display_callback(self.expected_frame_id, frame)
                except Exception:
                    logger.exception("display_callback failed")
            else:
                # frame is None here: either dropped because EOS or buffer never got it
                self.dropped_frames += 1

            # advance to next expected frame
            self.expected_frame_id += 1
            # housekeeping: cleanup very old frames
            self.reassembly.cleanup_older_than(self.expected_frame_id - 10)
            # schedule next display time
            next_display_time += self.frame_interval

            # if we reach EOS and playback buffer empty and expected >= last delivered, exit loop
            if self.eos_received:
                with self.playback_lock:
                    if len(self.playback_buffer) == 0:
                        break

    def get_metrics(self):
        return {
            'received_chunks_total': self.received_frames_total,
            'frames_reassembled_total': self.frames_reassembled_total,
            'dropped_frames': self.dropped_frames,
            'stall_time_seconds': round(self.stall_time, 4),
            'eos_received': self.eos_received
        }