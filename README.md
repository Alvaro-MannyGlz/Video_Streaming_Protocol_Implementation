# Video_Streaming_Protocol_Implementation

---

Team Name's 
- Alvaro Gonzalez
- Jesus Lopez
- Gabriel Garcia
- ...
- ...

---

## Project Overview
This project implements a video streaming system consisting of a server and a client. The goal is to demonstrate a functional network protocol stack where the client can request a video from the server and stream it over a custom, reliable transport protocol. We will specifically implement the PLAY command to initiate streaming. The final product will be tested under various network conditions to measure performance and validate the protocol's reliability.

## Transport Protocol Design Plan
We plan to implement the Go-Back-N (GBN) Automatic Repeat Request (ARQ) protocol. GBN is chosen for its simplicity relative to Selective Repeat while still offering significant performance improvements over Stop-and-Wait, which is crucial for video streaming.

---

### Design Details:
fill-in later

### Reliability and Error Handling:
fill-in later

---

## Application Layer Design Plan
The application layer will use a simple, text-based request-response model over the reliable GBN transport layer.

## Client and Server Interaction:
- Client: Establishes a connection (socket) to the server.
- Client: Sends the PLAY request with the desired video file name.
- Server: Receives and parses the request.
- If the file exists, the Server replies with 200 OK and immediately begins sending video frames encapsulated in GBN packets.
- If the file is not found, the Server replies with 404 Not Found and closes the connection.
- Streaming Loop: The Server continues sending frames. The Client continuously sends ACK packets back to the server to acknowledge successful frame reception.

## Testing and Metrics Plan
Testing will focus on validating both the correctness (reliability) and the performance of the GBN implementation under adverse conditions.

- Testing Plan (Network Profiles):
Clean Network: Test the system with 0% packet loss and 0 reordering. This validates the baseline throughput and ensures the protocol correctly handles the normal flow (no retransmissions).

- Random Loss: Introduce a constant, small percentage of random packet loss (e.g., 5% loss). This tests the core GBN retransmission logic and the timeout mechanism.

- Burst Loss: Introduce periods of high loss (e.g., 50% loss over a 100ms window) to simulate heavy network congestion. This pushes the limits of the GBN window size and tests its ability to recover from multiple consecutive losses.
