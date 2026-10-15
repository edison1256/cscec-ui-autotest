"""Trace retention for explicitly managed metering browser contexts."""

from pathlib import Path


class MeteringTraces:
    def __init__(self, mode="off"):
        self.mode = mode
        self.failed = False
        self.contexts = {}
        self.files = []
        self.errors = []

    def start(self, context, path):
        if self.mode == "off":
            return
        try:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            self.contexts[context] = Path(path)
        except Exception as exc:
            self.errors.append(f"Trace start failed: {type(exc).__name__}")

    def stop(self, context):
        path = self.contexts.pop(context, None)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            context.tracing.stop(path=str(path))
            self.files.append(path)
        except Exception as exc:
            self.errors.append(f"Trace stop failed: {type(exc).__name__}")

    def finalize(self):
        if self.mode == "retain-on-failure" and not self.failed:
            for path in self.files:
                try:
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    self.errors.append(f"Trace cleanup failed: {type(exc).__name__}")
        return [str(path) for path in self.files if path.exists()]
