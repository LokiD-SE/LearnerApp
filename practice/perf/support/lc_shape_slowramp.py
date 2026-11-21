"""A plan that cannot work: stage 1 wants 10 users at 1 user per second but lasts 3 seconds."""

from locust import LoadTestShape


class SlowRampShape(LoadTestShape):
    stages = [
        {"duration": 3, "users": 10, "spawn_rate": 1},
        {"duration": 6, "users": 4, "spawn_rate": 10},
        {"duration": 9, "users": 2, "spawn_rate": 10},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None
