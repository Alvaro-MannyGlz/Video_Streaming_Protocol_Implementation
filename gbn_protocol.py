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

    def send_data(self,data):
        # if-else for the sending logic
        pass

    def receive_ack(self, ack_num):
        # if-else for receiving logic
        pass

    def handle_timeout(self):
        # Logic for when retransmission timer expires
        pass

# -- Receiver Structure (Francisco) --
class GBNReceiver:
#    ... (Logic for checking sequence numbers, generating ACKs, and delivering in-order data)
    pass # delete after adding
