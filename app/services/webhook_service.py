import json
import logging
import threading
import time
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

class WebhookService:
    def __init__(self, max_history: int = 100):
        self._lock = threading.Lock()
        self._webhooks: list[dict] = []
        self._history: deque = deque(maxlen=max_history)

    def register(self, url: str, events: list[str] = None, name: str = '') -> dict:
        webhook = {
            'id': f'wh_{int(time.time())}_{len(self._webhooks)}',
            'url': url,
            'events': events or ['*'],
            'name': name or url,
            'active': True,
            'created_at': time.time()
        }
        with self._lock:
            self._webhooks.append(webhook)
            return webhook

    def unregister(self, webhook_id: str) -> bool:
        with self._lock:
            self._webhooks = [w for w in self._webhooks if w['id'] != webhook_id]
            return True

    def list_webhooks(self) -> list:
        with self._lock:
            return list(self._webhooks)

    def notify(self, event: str, payload: dict) -> int:
        with self._lock:
            targets = [
                w for w in self._webhooks
                if w['active'] and ('*' in w['events'] or event in w['events'])
            ]
            notified = 0
            for w in targets:
                entry = {
                    'webhook_id': w['id'],
                    'event': event,
                    'payload': payload,
                    'timestamp': time.time(),
                    'url': w['url'],
                    'status': 'queued'
                }
                self._history.append(entry)
                notified += 1
                logger.info('Webhook bildirim: %s -> %s', event, w['url'])
            return notified

    def history(self, limit: int = 50) -> list:
        with self._lock:
            items = list(self._history)
            return items[-limit:]
