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
        if self.burst_loss_rate > 0:
            # Get time in ms
            now = int(time.time() * 1000)
            pos = now % self.burst_interval_ms
            if pos < self.burst_duration_ms:
                # nested if statements
                if rd.random() < self.burst_loss_rate:
                    return False

        if rd.random() < self.random_loss_rate:
            return False

        return True