import cv2 
import struct
import sys
import os
import time
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client.frame_handler import FrameHandler

END_OF_STREAM_FRAME_ID = 0xFFFFFFFF
END_OF_STREAM_TOTAL_CHUNKS = 0xFFFF

class RTPStreamer:
    """
    RTPStreamer responsibilites:
        - frame encoding
        - fragmenting frames into RTP chunks
        - pacing frames using FPS
    """
    def __init__(self, gbn_sender, max_packet_size=1400, fps: Optional[float] = None, server_socket):
        self.gbn = gbn_sender
        self.max_packet_size = max_packet_size
        self.max_chunk_bytes = max_packet_size - 8
        self.fps = fps
        self.frame_id = 0
        self._stop = False
        self.server_socket = server_socket

        # Ideal conditions
        self.loss = LossModel(
            random_loss_rate=0.0,
            burst_loss_rate=0.0,
            burst_duration_ms=0,
            burst_interval_ms=0
        )
        # Random 5% loss simulation
        """
        self.loss = LossModel(
            random_loss_rate=0.05,
            burst_loss_rate=0.0,
            burst_duration_ms=0,
            burst_interval_ms=0
        )
        """
        # Heavy traffic w/ heavy loss simulation
        """
        self.loss = LossModel(
            random_loss_rate=0.0,
            burst_loss_rate=0.1,
            burst_duration_ms=100,
            burst_interval_ms=1000
        )
        """
    
    def _encode_frame(self, frame):
        # Convert raw images into JPEG bytes
        ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        
        if not ok:
            raise RuntimeError("Failed to encode frame to JPEG")
        
        return buf.tobytes()
    
    
    def _chunk_bytes(self, data):
        # Splitting bytes into max_chunk_bytes sized chunks
        chunks = []
        length = len(data)    
        for i in range(0, length, self.max_chunk_bytes):
            chunks.append(data[i:i+self.max_chunk_bytes])

        return chunks
    
    def send_frame(self,frame):
        # Encode the frame, split it into RTP chunks, send frame using GBN
        jpeg_bytes = self._encode_frame(frame)
        chunks = self._chunk_bytes(jpeg_bytes)
        total_chunks = len(chunks)
        
        if total_chunks == 0:
            return
        
        if total_chunks > 0xFFFF:
            raise RuntimeError(f"Too many chunks: {total_chunks}")
        
        # Construct and send each chunk with header
        for chunk_idx in range(total_chunks):
            header = struct.pack(
                '!IHH',
                self.frame_id,
                chunk_idx,
                total_chunks
            )
            packet = header + chunks[chunk_idx]
            self.gbn.send_data(packet)
        
        self.frame_id += 1
    
    def send_eos(self):
        # Send end-of-stream marker so client stops playback
        header = struct.pack('!IHH', END_OF_STREAM_FRAME_ID, 0, END_OF_STREAM_TOTAL_CHUNKS)
        self.gbn.send_data(header)
    
    def stream_file(self, video_path, loop=False):
        # Read frames from video file and stream to client
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")
        
        try:
            while not self._stop:
                ret, frame = cap.read()
                # End of video
                if not ret:
                    if loop:
                        # Restarts from beginning if enabled
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    break
                
                self.send_frame(frame)
                
                if self.fps:
                    time.sleep(1.0/ self.fps)
        finally:
            cap.release()
            self.send_eos()
            
    def stop_stream(self):
        # Stops streaming loop
        self._stop = True
