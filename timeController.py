import time


class TimeController:
    def __init__(self):
        self.started = False
        self.start_time = time.time()
        self.stopped = False

    def start(self):
        self.started = True
        self.stopped = False
        self.start_time = time.time()

    def stop(self):
        self.started = False
        self.stopped = True

    def is_stopped(self):
        return self.stopped