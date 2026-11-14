import logging
import threading

import requests


class DiscordWebhookHandler(logging.Handler):
    """Forward log records to a Discord webhook (no-op when no URL is set)."""

    def __init__(self, webhook_url=None):
        super().__init__()
        self.webhook_url = webhook_url

    def emit(self, record):
        if not self.webhook_url:
            return
        try:
            payload = {"content": f"```{self.format(record)[:1900]}```"}
            # Post off-thread so logging never blocks the event loop.
            threading.Thread(target=requests.post, args=(self.webhook_url,),
                             kwargs={"json": payload, "timeout": 10}, daemon=True).start()
        except Exception:
            self.handleError(record)
