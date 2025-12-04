import sys
import os
import rtp_streamer
import socket 
import threading

# Add the parent directory to the path so we can see 'shared'
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)

from shared.gbn_protocol import GBNSender, GBNUtilities

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
            # Receive command from client
            data, client_addr = self.server_socket.recvfrom(2048)
            message = data.decode()
            print(f"[SERVER] Received from {client_addr}: {message}")
            
            # Client command handing
            threading.Thread(
                target=self.handle_client,
                args=(message, client_addr),
                daemon=True
            ).start()
    
    # Command Parser and Handler
    def handle_client(self, message, client_addr):
        parts = message.split(maxsplit=1)
        command = parts[0]
        
        # Extract filename 
        if len(parts) > 1:
            argument = parts[1].strip()
        else:
            argument = ""
        
        # Create session entry for new clients
        if client_addr not in client_sessions:
            client_sessions[client_addr] = {
                "streamer": None,
                "frames": None
            }
            
        session = client_sessions[client_addr]
        
        if command == "PLAY":
            filename = argument.strip()
            
            try:
                # Crete GBN sender for client
                sender = GBNSender(self.server_socket)
                               
                streamer = rtp_streamer.RTPStreamer(sender)
                
                session["streamer"] = streamer
                
                # Stream video in background thread
                threading.Thread(
                    target=streamer.stream_file,
                    args=(filename,),
                    daemon=True
                ).start()
                
                self.server_socket.sendto(b"200 OK PLAY", client_addr)
            
                
            except FileNotFoundError:
                self.server_socket.sendto(b"404 NOT_FOUND", client_addr)
        
        elif command == "STOP":
            if session["streamer"]:
                session["streamer"].stop_stream()
            self.server_socket.sendto(b"200 OK STOP", client_addr)
        else:
            self.server_socket.sendto(b"400 BAD_REQUEST", client_addr)
