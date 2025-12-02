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
import logging

logger = logging.getLogger("GBNReceiver")
logging.basicConfig(level=logging.INFO)
from typing import Optional


class GBNReceiver:
    """
    Go-Back-N receiver implementation that:
      - receives UDP datagrams containing (seq_num, checksum, payload)
      - verifies checksum
      - implements GBN receiver rules:
         * deliver only in-order packets (seq == expected)
         * send cumulative ACKs
         * discard out-of-order packets but re-ACK last in-order
      - exposes send(data), recv() -> payload bytes, close()
    """

    def __init__(self, sock: socket.socket, peer: tuple = None, recv_buf_size: int = 65536, timeout: float = None):
        """
        sock: UDP socket (bound). If peer is provided, send ACKs to peer via sendto(peer).
        peer: (host, port) tuple for sending ACKs (optional).
        recv_buf_size: maximum bytes for recvfrom
        timeout: optional socket timeout (seconds)
        """
        self.sock = sock
        self.peer = peer
        self.recv_buf_size = recv_buf_size
        self._closed = False
        self.expected = 0  # next expected sequence number
        if timeout is not None:
            self.sock.settimeout(timeout)

    def _compute_check(self, seq_num: int, payload: bytes) -> int:
        """
        Compute checksum consistent with GBNUtilities.compute_checksum.
        We compute over seq_num (2 bytes) + payload bytes.
        """
        seq_bytes = struct.pack('!H', seq_num)
        return GBNUtilities.compute_checksum(seq_bytes + payload)

    def _pack_ack(self, ack_num: int) -> bytes:
        """
        Pack an ACK header using the same header_format: (seq_num, checksum).
        ACK uses seq_num field to carry the ack number. No payload.
        """
        # compute checksum over seq_num only (no payload)
        chk = GBNUtilities.compute_checksum(struct.pack('!H', ack_num))
        return struct.pack(header_format, ack_num, chk)

    def _sendto(self, data: bytes, addr):
        try:
            self.sock.sendto(data, addr)
        except Exception:
            logger.exception("Failed to sendto %s", addr)

    def send(self, data: bytes):
        """
        Send raw application bytes to the peer. Used to send ASCII control like "PLAY ...".
        If the protocol required these to be wrapped in GBN packets, this method must be changed.
        """
        if self.peer:
            try:
                self.sock.sendto(data, self.peer)
            except Exception:
                logger.exception("Failed to send application data to peer")
        else:
            # try using connected socket send
            try:
                self.sock.send(data)
            except Exception:
                logger.exception("Failed to send application data (no peer known)")

    def recv(self) -> Optional[bytes]:
        """
        Blocking call that returns the application payload for the next in-order seq.
        Implements GBN receiver semantics.
        Returns:
            payload bytes for expected seq, or None on socket error/close.
        """
        MOD = globals().get('seq_num', 65536)

        while not self._closed:
            try:
                raw, addr = self.sock.recvfrom(self.recv_buf_size)
            except socket.timeout:
                # continue waiting; caller may close
                continue
            except Exception:
                logger.exception("Socket receive error")
                return None

            # learn peer if unknown
            if not self.peer:
                self.peer = addr

            # deserialize
            parsed = GBNUtilities.deserialize_packet(raw)
            if not parsed:
                logger.debug("Malformed or too-short packet received; ignoring")
                continue

            pkt_seq, pkt_checksum, payload = parsed

            # verify checksum by recomputing (seq + payload)
            calc = self._compute_check(pkt_seq, payload)
            if calc != pkt_checksum:
                logger.debug("Checksum mismatch (seq=%d). Dropping packet.", pkt_seq)
                continue

            # GBN behavior:
            if pkt_seq == self.expected:
                # in-order: ACK and deliver
                logger.debug("Received expected seq=%d; ACKing and delivering", pkt_seq)
                ack_pkt = self._pack_ack(pkt_seq)
                # send ACK back to sender
                try:
                    if self.peer:
                        self._sendto(ack_pkt, self.peer)
                    else:
                        self.sock.send(ack_pkt)
                except Exception:
                    logger.exception("Failed to send ACK for seq %d", pkt_seq)
                # increment expected (mod MOD)
                self.expected = (self.expected + 1) % MOD
                return payload
            elif (0 <= pkt_seq < self.expected) or ((self.expected == 0) and (pkt_seq == MOD - 1)):
                # duplicate (packet already received): resend ACK for last in-order (expected-1)
                ack_num = (self.expected - 1) % MOD
                logger.debug("Received duplicate seq=%d; re-ACKing %d", pkt_seq, ack_num)
                ack_pkt = self._pack_ack(ack_num)
                if self.peer:
                    self._sendto(ack_pkt, self.peer)
                else:
                    try:
                        self.sock.send(ack_pkt)
                    except Exception:
                        logger.exception("Failed to re-ACK duplicate")
                continue
            else:
                # out-of-order packet (pkt_seq > expected): drop packet, re-ACK last in-order
                ack_num = (self.expected - 1) % MOD
                logger.debug("Out-of-order seq=%d (expected %d); re-ACKing %d and dropping", pkt_seq, self.expected, ack_num)
                ack_pkt = self._pack_ack(ack_num)
                if self.peer:
                    self._sendto(ack_pkt, self.peer)
                else:
                    try:
                        self.sock.send(ack_pkt)
                    except Exception:
                        logger.exception("Failed to re-ACK for out-of-order")
                continue

        return None

    def close(self):
        self._closed = True
        try:
            self.sock.close()
        except Exception:
            pass

