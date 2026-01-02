import argparse
from health_agent.main import check_disk

class DummyArgs:
    def __init__(self, path="/", threshold=0):
        self.disk_path = path
        self.disk_threshold = threshold
        self.service = None
        self.restart_cmd = None

def test_disk_ok():
    args = DummyArgs(threshold=0)
    result = check_disk(args, webhook=None)
    assert result is True

def test_disk_low(monkeypatch):
    def fake_disk_usage(path):
        # total, used, free (free = 1 GB)
        return (100, 99, 1 * 1024**3)

    monkeypatch.setattr("shutil.disk_usage", fake_disk_usage)

    args = DummyArgs(threshold=10)
    result = check_disk(args, webhook=None)
    assert result is False

