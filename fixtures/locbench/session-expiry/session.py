import time


class SessionManager:
    def __init__(self, ttl_seconds=3600):
        self.ttl_seconds = ttl_seconds
        self.started = {}

    def validate_session(self, user):
        # BUG: expiry comparison uses creation time of the manager, not the session.
        return user in self.started and time.time() - self.ttl_seconds < time.time()
