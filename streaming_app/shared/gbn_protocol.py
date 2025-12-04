import socket
import struct
import time
import logging
from threading import Timer
from typing import Optional

# -- Protocol Constants --
SEQ_NUM_MODULO = 65536  # 2^16
HEADER_FORMAT = '!H H'  # Seq Num (16-bit), Checksum (16-bit)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
TIMEOUT_INTERVAL = 0.5  # Seconds

# -- Helper Classes --

class LossModel:
    """Simulates packet loss (for testing). Default behavior: No loss."""
    def allow_packet(self):
        return True

class GBNUtilities:
    @staticmethod
    def compute_checksum(data: bytes) -> int:
        checksum = 0
        for i in range(0, len(data), 2):
            section = data[i] << 8
            if i + 1 < len(data):
                section += data[i+1]
            checksum += section
            checksum = (checksum & 0xFFFF) + (checksum >> 16)
        return ~checksum & 0xFFFF

    @staticmethod
    def serialize_packet(seq_num: int, checksum: int, payload: bytes) -> bytes:
        header = struct.pack(HEADER_FORMAT, seq_num, checksum)
        return header + payload

    @staticmethod
    def deserialize_packet(data: bytes):
        if len(data) < HEADER_SIZE:
            return None
        header = data[:HEADER_SIZE]
        payload = data[HEADER_SIZE:]
        try:
            seq_num, checksum = struct.unpack(HEADER_FORMAT, header)
            return seq_num, checksum, payload
        except struct.error:
            return None
            
    @staticmethod
    def parse_header(data: bytes):
        """Alias for deserialize to match server calls"""
        return GBNUtilities.deserialize_packet(data)

# -- Sender Class --

class GBNSender:
    def __init__(self, sock, receiver_addr=None, loss_model=None):
        self.sock = sock
        self.receiver_addr = receiver_addr
        self.send_base = 0
        self.next_seq_num = 0
        self.window_size = 5
        self.unacked_buffer = {}
        self.timer = None
        self.loss_model = loss_model or LossModel()

        self.metrics = {
            "packets_sent": 0,
            "packets_delivered": 0,
            "packets_lost": 0,
            "retransmissions": 0,
            "timeouts": 0,
            "bytes_sent": 0,
            "start_time": time.time()
        }
        
    def send_data(self, data):
        # 1. Checksum includes SeqNum + Payload to match Receiver logic
        seq_bytes = struct.pack('!H', self.next_seq_num)
        checksum = GBNUtilities.compute_checksum(seq_bytes + data)
        
        packet = GBNUtilities.serialize_packet(self.next_seq_num, checksum, data)
        
        self.unacked_buffer[self.next_seq_num] = packet
        self.metrics["packets_sent"] += 1
        
        if self.loss_model.allow_packet():
            self.sock.sendto(packet, self.receiver_addr)
        else:
            print(f'[GBN] Loss simulated. Dropped seq={self.next_seq_num}')

        if self.send_base == self.next_seq_num:
            self.start_timer()

        self.next_seq_num = (self.next_seq_num + 1) % SEQ_NUM_MODULO
        return True

    def receive_ack(self, ack_num):
        self.stop_timer()
        
        if ack_num in self.unacked_buffer:
            # Remove all packets up to and including ack_num
            to_remove = []
            for seq in sorted(self.unacked_buffer.keys()):
                to_remove.append(seq)
                if seq == ack_num:
                    break
            
            for seq in to_remove:
                del self.unacked_buffer[seq]
                self.metrics["packets_delivered"] += 1
                
            # Update send_base (simplification: base follows the cleared buffer)
            if not self.unacked_buffer:
                self.send_base = self.next_seq_num
            
        if self.unacked_buffer:
            self.start_timer()

    def start_timer(self):
        if self.timer is None:
            self.timer = Timer(TIMEOUT_INTERVAL, self.handle_timeout)
            self.timer.start()

    def stop_timer(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    def restart_timer(self):
        self.stop_timer()
        self.start_timer()

    def handle_timeout(self):
        print("Timeout triggered!")
        self.metrics["timeouts"] += 1
        self.metrics["retransmissions"] += 1
        
        for seq in sorted(self.unacked_buffer.keys()):
            packet = self.unacked_buffer[seq]
            self.metrics["packets_sent"] += 1
            if self.loss_model.allow_packet():
                self.sock.sendto(packet, self.receiver_addr)
            else:
                self.metrics["packets_lost"] += 1

        self.restart_timer()

    def get_metrics(self):
        now = time.time()
        elapsed = now - self.metrics["start_time"]
        return {
            "packets_sent": self.metrics["packets_sent"],
            "packets_delivered": self.metrics["packets_delivered"],
            "packets_lost": self.metrics["packets_lost"],
            "retransmissions": self.metrics["retransmissions"],
            "timeouts": self.metrics["timeouts"],
            "elapsed_time_sec": elapsed
        }

# -- Receiver Class --

logger = logging.getLogger("GBNReceiver")
logging.basicConfig(level=logging.INFO)

class GBNReceiver:
    def __init__(self, sock: socket.socket, peer: tuple = None, recv_buf_size: int = 65536, timeout: float = None):
        self.sock = sock
        self.peer = peer
        self.recv_buf_size = recv_buf_size
        self._closed = False
        self.expected = 0 
        if timeout is not None:
            self.sock.settimeout(timeout)

    def _compute_check(self, seq_num: int, payload: bytes) -> int:
        seq_bytes = struct.pack('!H', seq_num)
        return GBNUtilities.compute_checksum(seq_bytes + payload)

    def _pack_ack(self, ack_num: int) -> bytes:
        chk = GBNUtilities.compute_checksum(struct.pack('!H', ack_num))
        return struct.pack(HEADER_FORMAT, ack_num, chk)

    def send(self, data: bytes):
        if self.peer:
            self.sock.sendto(data, self.peer)
        else:
            self.sock.send(data)

    def recv(self) -> Optional[bytes]:
        while not self._closed:
            try:
                raw, addr = self.sock.recvfrom(self.recv_buf_size)
            except socket.timeout:
                continue
            except Exception:
                return None

            if not self.peer:
                self.peer = addr

            parsed = GBNUtilities.deserialize_packet(raw)
            if not parsed:
                continue

            pkt_seq, pkt_checksum, payload = parsed

            # Verify checksum (Seq + Payload)
            calc = self._compute_check(pkt_seq, payload)
            if calc != pkt_checksum:
                # Corrupt
                continue

            # GBN In-Order Check
            if pkt_seq == self.expected:
                # Good packet
                ack_pkt = self._pack_ack(pkt_seq)
                self.sock.sendto(ack_pkt, self.peer)
                self.expected = (self.expected + 1) % SEQ_NUM_MODULO
                return payload
            else:
                # Out of order - Re-ACK last good packet
                ack_num = (self.expected - 1) % SEQ_NUM_MODULO
                ack_pkt = self._pack_ack(ack_num)
                self.sock.sendto(ack_pkt, self.peer)

        return None

    def close(self):
        self._closed = True
        try:
            self.sock.close()
        except:
            pass