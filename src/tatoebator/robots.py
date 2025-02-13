import time
import requests
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

from tatoebator.util import CircularBuffer


class RobotsAwareSession(requests.Session):
    def __init__(self, base_url, user_agent="*"):
        super().__init__()
        self.base_url = base_url
        self.user_agent = user_agent
        self.robots_parser = RobotFileParser()
        self._load_robots_txt()

        self._setup_rate_constraints()

    def _setup_rate_constraints(self):
        self.crawl_delay = self.robots_parser.crawl_delay(self.user_agent) or 0
        request_rate = self.robots_parser.request_rate(self.user_agent)
        if request_rate is None:
            self.last_request_time = time.time() - self.crawl_delay
            self.request_buffer = None
            return
        self.last_request_time = time.time()-max(self.crawl_delay, request_rate.seconds)
        self.request_buffer = CircularBuffer(request_rate.requests, initial_value=self.last_request_time)
        self.request_rate_seconds = request_rate.seconds

    def _wait_for_rate_constraints(self):
        now = time.time()
        waiting_time = self.crawl_delay-(now-self.last_request_time)
        if self.request_buffer is not None:
            waiting_time = max(waiting_time, self.request_rate_seconds-(now-self.request_buffer.peek()))

        if waiting_time>0: time.sleep(waiting_time)
        self.last_request_time = time.time()
        if self.request_buffer is not None:
            self.request_buffer.push(self.last_request_time)


    def _load_robots_txt(self):
        robots_url = f"{self.base_url}/robots.txt"
        self.robots_parser.set_url(robots_url)
        self.robots_parser.read()

    def request(self, method, url, *args, **kwargs):
        # Parse the URL to get the path
        parsed_url = urlparse(url)
        path = parsed_url.path

        # Check if the path is allowed by robots.txt
        if not self.robots_parser.can_fetch(self.user_agent, url):
            raise Exception(f"Access to {url} is disallowed by robots.txt")

        self._wait_for_rate_constraints()

        # Proceed with the request
        return super().request(method, url, *args, **kwargs)

