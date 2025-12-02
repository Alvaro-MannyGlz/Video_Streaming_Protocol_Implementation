# THINGS NEEDED
# Cumulative ACKs
# Checksums?
# Retransmission Timer
# Receiver Structure (Francisco)

import socket
import struct
import time
from threading import Timer

# implement the Go-Back-N(GBN) server and receiver logic
# -- Protocol Constants --
seq_num = 65536 # 2^16
header_format = '!H H' # Seq Num, 16-bit checksum
header_size = struct.calcsize(header_format)
timeout_int = 0.5 # seconds till a retransmission is sent

# 
class GBNPacket:
    def __init__(self, seq_num, checksum, payload):
        self.seq_num = seq_num
        self.checksum = checksum
        self.payload = payload

# -- Packet Structure --
class GBNUtilities:
    def compute_checksum(data: bytes) -> int:
        checksum = 0
        for i in range(0, len(data), 2):
            section = data [i] << 8
            if i+ 1 < len(data):
                i += 1
                section += data[i]
            checksum += section
            checksum = (checksum & 0xFFFF) + (checksum >> 16)
        return ~checksum & 0xFFFF

    def serialize_packet(self, seq_num: int, checksum: int, payload: bytes) -> bytes:
        # Header (byte string)
        header = struct.pack(header_format, seq_num, checksum)
        # Combines header + payload
        full_packet = header + payload

        return full_packet

    def deserialize_packet(self, data: bytes) -> tuple:
        # If too short
        if len(data) < header_size:
            # No header
            return None
        # Seperate Header and Payload
        header = data[:header_size]
        payload = data[header_size:]

        try:
            seq_num, checksum = struct.unpack(header_format, header)
        
        except struct.error:
            return None
        
        return (seq_num, checksum, payload)

# -- Sending Structure --
class GBNSender:
    def __init__(self, socket):
        self.socket = socket
        self.send_base = 0
        self.next_seq_num = 0
        self.window_size = 5
        self.unacked_buffer = {}
        self.timer = None

    def send_data(self,data):
        seq_num, checksum, payload = parsed_ack
        if GBNUtilities.compute_checksum(payload) != checksum:
            return

    def receive_ack(self, ack_num):
        # if-else for receiving logic
        pass

    def handle_timeout(self):
        # Logic for when retransmission timer expires
        pass

    # Call when send_base == next_seq_num, which when window was empty and first packet just sent
    def start_timer(self):
        if self.timer is None:
            self.timer = Timer(timeout_int, self.handle_timeout)
            self.timer.start()

    # Call when all unacked packets r acknowledges (send_base = next_seq_num)
    def stop_timer(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    # Call after receiving valid ACK that shifts send_base
    def restart_timer(self):
        self.stop_timer()
        self.start_timer()

    def handle_timeout(self):
        # Resend all packets in window starting at send_base
        for seq in sorted(self.unacked_buffer.keys()):
            packet = self.unacked_buffer[seq]
            self.socket.sendto(packet, self.receiver_addr)

        self.restart_timer()
    


# -- Receiver Structure (Francisco) --
class GBNReceiver:
    seq_num, checksum, payload = parsed

    computed = GBNUtilities.compute_checksum(payload)

    #If checksum fails
    if computed != checksum:
        return None
