"""A spike: a quiet baseline, a sudden burst, then back to the baseline. Pair with lc_shape_users.py."""

from locust import LoadTestShape


class SpikeShape(LoadTestShape):
    # "duration" is the END of the stage, in seconds since the start of the test
    stages = [
        {"duration": 6, "users": 2, "spawn_rate": 50},    # baseline
        {"duration": 16, "users": 24, "spawn_rate": 50},  # the spike
        {"duration": 26, "users": 2, "spawn_rate": 50},   # recovery
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None
