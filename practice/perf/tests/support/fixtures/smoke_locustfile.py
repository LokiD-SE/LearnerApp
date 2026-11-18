from locust import HttpUser, constant, task


class Merchant(HttpUser):
    wait_time = constant(0)

    @task
    def health(self):
        self.client.get("/health")
