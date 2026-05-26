"""core/data/alerts_repository.py"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class AlertLevel(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"

@dataclass
class Alert:
    level:     AlertLevel
    category:  str
    title:     str
    message:   str
    timestamp: datetime = field(default_factory=datetime.now)
    dismissed: bool     = False
    def age_seconds(self): return (datetime.now() - self.timestamp).total_seconds()

_MAX_ALERTS = 200
_alert_store: deque[Alert] = deque(maxlen=_MAX_ALERTS)

def add_alert(level, category, title, message):
    a = Alert(level=level, category=category, title=title, message=message)
    _alert_store.appendleft(a); return a

def fetch_alerts(*, include_dismissed=False, max_count=100):
    return [a for a in _alert_store if include_dismissed or not a.dismissed][:max_count]

def dismiss_alert(alert): alert.dismissed = True
def dismiss_all():
    for a in _alert_store: a.dismissed = True
def clear_all(): _alert_store.clear()
def count_active(level=None):
    return sum(1 for a in _alert_store if not a.dismissed and (level is None or a.level == level))
