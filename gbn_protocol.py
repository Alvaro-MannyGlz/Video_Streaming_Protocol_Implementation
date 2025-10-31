# implement the Go-Back-N(GBN) server and receiver logic
# -- Protocol Constants --
seq_num = 65536 # 2^16
window_size = 10 # Max num of unACKed packets
timeout_int = 0.5 # seconds till a retransmission is sent

# THINGS NEEDED
# Window Management
# Cumulative ACKs
# Checksums
# Retransmission Timer

# -- Packet Structure --
class GBNPacket:
    def __init__(self, seq_num, checksum, payload):
        self.seq_num = seq_num
        self.checksum = checksum
        self.payload = payload

    def make_checksum(data):


    def serialize_packet(packet):


    def deserialize_packet(data):


# -- Sending Structure --
class GBNSender:
    def __init__(self, socket):
        self.socket = socket


    def send_data(self,data):
        # if-else for the sending logic

    def receive_ack(self, ack_num):
        # if-else for receiving logic

    def handle_timeout(self):
        # Logic for when retransmission timer expires