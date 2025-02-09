import logging
import requests

class DiscordWebhookHandler(logging.Handler):
    def __init__(self, webhook_url):
        super().__init__()
        self.webhook_url = webhook_url

    def emit(self, record):
        try:
            message = self.format(record)
            payload = {"content": f"```{message}```"}
            requests.post(self.webhook_url, json=payload)
        except Exception:
            self.handleError(record)