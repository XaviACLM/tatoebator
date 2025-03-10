import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from .util import CircularBuffer


class RobotsAwareSession(requests.Session):
    def __init__(self, base_url, user_agent="*"):
        super().__init__()
        self.base_url = base_url
        self.user_agent = user_agent#"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.3"
        self.headers['User-Agent'] = user_agent
        self._robots_parser = RobotFileParser()
        self._load_robots_txt()
        self._setup_rate_constraints()

    def _setup_rate_constraints(self):
        self.crawl_delay = self._robots_parser.crawl_delay(self.user_agent) or 0
        request_rate = self._robots_parser.request_rate(self.user_agent)
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
        robots_data = super().request("GET", robots_url)
        if robots_data.status_code in (401, 403):
            self._robots_parser.disallow_all = True
        elif robots_data.status_code in range(400,500):
            self._robots_parser.allow_all = True
        else:
            self._robots_parser.parse(robots_data.content.decode("utf-8").splitlines())

    def request(self, method, url, *args, **kwargs):
        # Parse the URL to get the path
        parsed_url = urlparse(url)
        path = parsed_url.path

        # Check if the path is allowed by robots.txt
        if not self._robots_parser.can_fetch(self.user_agent, url):
            raise Exception(f"Access to {url} is disallowed by robots.txt")

        self._wait_for_rate_constraints()

        # Proceed with the request
        return super().request(method, url, *args, **kwargs)

    def get_maximum_rate(self):
        delay = self.crawl_delay or 0
        if self.request_buffer:
            delay = max(delay, len(self.request_buffer.buffer) / self.request_rate_seconds)
        if delay == 0: return float("inf")
        return 1/delay
