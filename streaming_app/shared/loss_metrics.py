import random as rd
import time

class LossModel:
    def __init__(self,
                 random_loss_rate = 0.0,
                 burst_loss_rate = 0.0,
                 burst_duration_ms = 0.0,
                 burst_interval_ms = 0.0):
        self.random_loss_rate = random_loss_rate
        self.burst_loss_rate = burst_loss_rate
        self.burst_duration_ms = burst_duration_ms
        self.burst_interval_ms = burst_interval_ms

    def allow_packet(self):
        # 1. Burst Logic
        if self.burst_loss_rate > 0:
            now = int(time.time() * 1000)
            # Avoid division by zero if interval is not set
            if self.burst_interval_ms > 0:
                pos = now % self.burst_interval_ms
                
                # If we are inside the "Danger Zone" (Duration)
                if pos < self.burst_duration_ms:
                    if rd.random() < self.burst_loss_rate:
                        return False # DROP PACKET

        # 2. Random Logic
        if rd.random() < self.random_loss_rate:
            return False # DROP PACKET

        return True # SEND PACKET