import sys
import os
import socket
import threading

# Add the parent directory to the path so we can see 'shared'
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)

from shared.gbn_protocol import GBNSender, GBNUtilities
# Ensure this file exists and imports cv2 successfully now
import rtp_streamer 

client_sessions = {}

class VideoServer:
    def __init__(self, host='0.0.0.0', port=9000):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((self.host, self.port))
        
        print(f"[SERVER] Server running on {self.host}:{self.port}")
    
    def start(self):
        print("[SERVER] Waiting for client command...")
        
        while True:
            try:
                # Receive data from client (could be Command OR ACK)
                data, client_addr = self.server_socket.recvfrom(2048)
                
                # 1. Check if it is a Text Command (PLAY/STOP)
                if data.startswith(b"PLAY") or data.startswith(b"STOP"):
                    message = data.decode('utf-8')
                    print(f"[SERVER] Command from {client_addr}: {message}")
                    
                    threading.Thread(
                        target=self.handle_client,
                        args=(message, client_addr),
                        daemon=True
                    ).start()

                # 2. Check if it is a Binary ACK (GBN Protocol)
                else:
                    # It's likely an ACK. 
                    # If we have an active session, pass the ACK to the sender.
                    if client_addr in client_sessions:
                        session = client_sessions[client_addr]
                        if session["sender"]:
                            # We need to extract the seq_num from the packet
                            # Assuming your GBNUtilities has a parse method:
                            seq_num, checksum, _ = GBNUtilities.parse_header(data)
                            if seq_num is not None:
                                session["sender"].process_ack(seq_num)

            except Exception as e:
                print(f"[SERVER] Error in main loop: {e}")
    
    def handle_client(self, message, client_addr):
        parts = message.split(maxsplit=1)
        command = parts[0]
        
        # Extract filename 
        if len(parts) > 1:
            argument = parts[1].strip()
        else:
            argument = ""
        
        # Create session entry for new clients if needed
        if client_addr not in client_sessions:
            client_sessions[client_addr] = {
                "streamer": None,
                "sender": None # Store sender here to access it for ACKs
            }
            
        session = client_sessions[client_addr]
        
        if command == "PLAY":
            filename = argument.strip()
            
            try:
                # --- FIX: Pass client_addr to GBNSender ---
                sender = GBNSender(self.server_socket, client_addr)
                session["sender"] = sender
                
                # We pass the sender to the streamer so it can "push" packets
                streamer = rtp_streamer.RTPStreamer(sender)
                session["streamer"] = streamer
                
                # Stream video in background thread
                threading.Thread(
                    target=streamer.stream_file,
                    args=(filename,),
                    daemon=True
                ).start()
                
                # Acknowledge the command
                self.server_socket.sendto(b"200 OK PLAY", client_addr)
            
            except Exception as e:
                print(f"[SERVER] Play Error: {e}")
                self.server_socket.sendto(b"500 INTERNAL_ERROR", client_addr)
        
        elif command == "STOP":
            if session["streamer"]:
                # Ensure your RTPStreamer has a stop method
                # session["streamer"].stop_stream() 
                pass
            self.server_socket.sendto(b"200 OK STOP", client_addr)
        else:
            self.server_socket.sendto(b"400 BAD_REQUEST", client_addr)

if __name__ == "__main__":
    # Allow running this file directly
    server = VideoServer()
    server.start()