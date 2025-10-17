# implement the Go-Back-N(GBN) server and receiver logic
# Sequence Numbers
# Window Management
# Cumulative ACKs
# Checksums
# Retransmission Timer

#basic structure for code
class GBN:
    def __init__(self, window_size, timeout):
        self.window_size = window_size
        self.base = 0
        self.next_seq_num = 0
        self.buffer = ()
        self.timer = None

    def compute_checksun(data: bytes) -> init:
        checksun = 0
        for i in range(0, len(data), 2):
            section = data[i] << 8
            if i + 1 < len(data):
                i += 1
                section += data[i]
            checksum += section
            checksum = (checksum & 0xFFFF) + (checksum >> 16)  
        return ~checksum & 0xFFFF

    def create_packet(self, seq_num, data):
        pass

    def send_paclet(self, packet):
        pass

    def receive_ack(self, ack_num):
        pass

    def timeout(self):
        pass