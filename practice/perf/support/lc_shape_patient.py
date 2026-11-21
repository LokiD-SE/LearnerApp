"""The same plan as lc_shape_slowramp.py, but a stage starts its clock only when its users are running.

``hold`` is how long each stage lasts AFTER the target user count is reached (get_current_user_count()).
"""

from locust import LoadTestShape


class PatientShape(LoadTestShape):
    stages = [
        {"users": 10, "spawn_rate": 1, "hold": 3},
        {"users": 4, "spawn_rate": 10, "hold": 3},
        {"users": 2, "spawn_rate": 10, "hold": 3},
    ]

    def __init__(self):
        super().__init__()
        self.index = 0
        self.reached_at = None  # run time at which this stage's user count was first seen

    def tick(self):
        if self.index >= len(self.stages):
            return None
        stage = self.stages[self.index]
        now = self.get_run_time()
        if self.reached_at is None:
            if self.get_current_user_count() == stage["users"]:
                self.reached_at = now
        elif now - self.reached_at >= stage["hold"]:
            self.index += 1
            self.reached_at = None
            return self.tick()
        return stage["users"], stage["spawn_rate"]
