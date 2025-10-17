# Video_Streaming_Protocol_Implementation

---

## Team Names
- Alvaro Gonzalez
- Jesus Lopez
- Gabriel Garcia
- Francisco Morales
- Daniel Villafranco

---

## Project Overview
This project implements a video streaming system consisting of a server and a client. The goal is to demonstrate a functional network protocol stack where the client can request a video from the server and stream it over a custom, reliable transport protocol. We will specifically implement the PLAY command to initiate streaming. The final product will be tested under various network conditions to measure performance and validate the protocol's reliability.

## Transport Protocol Design Plan
### Reliability Protocol
Go-Back-N (GBN) Automatic Repeat Request (ARQ) protocol.

### Design Details:
| Component | Implementation Detail |
| :--- | :--- |
| **Header Fields** | Sender: Sequence Number; Sender: Checksum; Receiver: ACK Number |
| **Timers** | Single Retransmission Timer |
| **Flow Control** | Sliding Window |
| **Retransmission Logic** | Timeout: If the timer expires, the sender retransmits the timed-out packet and all subsequent unacknowledged packets in the window (Go-Back-N). |

### Reliability and Error Handling:
| Error Type | GBN Handling Mechanism |
| :--- | :--- |
| **Packet Loss** | Timer expires, forcing Go-Back-N retransmission of the lost packet and all packets following it. |
| **Packet Duplication** | Receiver checks the Sequence Number; if duplicate, it is discarded and the ACK for the expected packet is resent. |
| **Packet Reordering** | Receiver checks for in-order Sequence Number; if out-of-order, the packet is discarded and the cumulative ACK for the previous correct sequence number is resent. |
  
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
Testing will focus on validating both the reliability and the performance of the GBN implementation under adverse conditions.

###Testing Plan:
- Clean Network: Test the system with 0% packet loss and 0 reordering. This validates the baseline throughput and ensures the protocol correctly handles the normal flow (no retransmissions).

- Random Loss: Introduce a constant, small percentage of random packet loss (e.g., 5% loss). This tests the core GBN retransmission logic and the timeout mechanism.

- Burst Loss: Introduce periods of high loss (e.g., 50% loss over a 100ms window) to simulate heavy network congestion. This pushes the limits of the GBN window size and tests its ability to recover from multiple consecutive losses.

## Team Responsibilities

I know y'all will see this Friday morning try and see if you can research a bit of what is being said as your responsibility we don't need a fully functional prototype, but something good enough to submit looking to submit something by **7 PM**
| Name | Primary Area of Responsibility | Key Components |
| :--- | :--- | :--- |
| **Alvaro Gonzalez** | **Project Lead / Transport Core** | GBN Sender Logic (Sequence Numbers, Window Management). |
| **Jesus Lopez** | **Transport Reliability / Timers** | GBN Retransmission Logic (Timeout implementation) and Checksum validation. |
| **Gabriel Garcia** | **Application Layer (Server)** | Server Command Parsing (`PLAY`, `404` handling) and **Concurrency** (Threading). |
| **Francisco Morales** | **Client and Frame Handling** | Client request generation, receiving/buffering frames, and calculating **Dropped Frames / Stall Time**. |
| **Daniel Villafranco** | **Testing and Metrics** | Designing and implementing **network loss simulation** (Random and Burst Loss) and calculating **Throughput / Retransmissions**. |
