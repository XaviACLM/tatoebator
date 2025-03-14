import json
import os
import threading
import time
from datetime import datetime, timedelta
from queue import Empty, Queue


class TimedResourceManager:
    """
    Abstract base class for managing a resource that should be stopped
    after a period of inactivity.
    """

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.last_request_time = None
        self.is_resource_running = False
        self._lock = threading.Lock()
        self._monitor_thread = None

    def _start_monitor_thread(self):
        def monitor():
            while True:
                if not self.is_resource_running:
                    # got killed externally, time to leave
                    return
                with self._lock:
                    time_until_timeout = timedelta(seconds=self.timeout) - (
                            datetime.now() - self.last_request_time
                    )

                    if time_until_timeout <= timedelta():
                        self._stop_resource_managed()
                        return

                sleep_time = max(0.1, time_until_timeout.total_seconds())
                time.sleep(sleep_time)

        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()

    def process_request_managed(self, *args, **kwargs):
        """
        Handles a request. Starts the resource if necessary, and resets the timeout.
        """
        with self._lock:
            if not self.is_resource_running:
                self._start_resource_managed()
                self.last_request_time = datetime.now()
                self._start_monitor_thread()
            else:
                # Update the last request time to extend the timeout
                self.last_request_time = datetime.now()
        return self._process_request(*args, **kwargs)

    def shutdown(self):
        with self._lock:
            if self.is_resource_running:
                self._stop_resource_managed()
            # it's a daemon, no need to wait for it to en
            # if self._monitor_thread: self._monitor_thread.join()

    def __del__(self):
        self.shutdown()

    # Resource lifecycle methods
    def _start_resource_managed(self):
        self.is_resource_running = True
        self._start_resource()

    def _start_resource(self):
        raise NotImplementedError()

    def _stop_resource_managed(self):
        self.is_resource_running = False
        self._stop_resource()

    def _stop_resource(self):
        raise NotImplementedError()

    def _process_request(self, *args, **kwargs):
        raise NotImplementedError()


class BackgroundProcessor:
    def __init__(self, task_file: str):
        self._task_file = task_file
        self._task_queue = Queue()
        self._lock = threading.Lock()
        self._worker_thread = None
        self._load_pending_tasks()
        self._start_worker()

    def process_task(self, task):
        raise NotImplementedError()

    def enqueue_task(self, task):
        print("task enqueued")
        self._task_queue.put(task)
        self._save_pending_tasks()
        self._start_worker()

    def is_task_in_queue(self, task):
        return task in self._task_queue.queue  # hrmm

    def enqueue_if_not_duplicate(self, task):
        if not self.is_task_in_queue(task):
            self.enqueue_task(task)

    def _start_worker(self):
        with self._lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._worker_thread = threading.Thread(target=self._process_tasks, daemon=True)
                self._worker_thread.start()

    def _process_tasks(self):
        while not self._task_queue.empty():
            try:
                task = self._task_queue.get(timeout=2)
                self.process_task(task)
                self._save_pending_tasks()
                self._task_queue.task_done()
            except Empty:
                break

        with self._lock:
            self._worker_thread = None  # Allow restarting

    def _load_pending_tasks(self):
        if os.path.exists(self._task_file):
            try:
                with open(self._task_file, "r") as f:
                    tasks = json.load(f)
                    for task in tasks:
                        self._task_queue.put(task)
            except Exception:
                pass  # Ignore corrupted file

    def _save_pending_tasks(self):
        tasks = list(self._task_queue.queue)
        with open(self._task_file, "w") as f:
            json.dump(tasks, f)
