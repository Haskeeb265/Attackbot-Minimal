import os
import sys
import datetime


class _Colors:
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    GRAY = "\033[90m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class ColorLogger:
    def __init__(self, show_timestamp: bool = True, use_color: bool = None):
        self.show_timestamp = show_timestamp
        # Auto-disable color if output isn't a real terminal (e.g. piped to a file)
        self.use_color = use_color if use_color is not None else sys.stdout.isatty()

        # Enable ANSI codes on older Windows terminals
        if os.name == "nt":
            os.system("")

    def _timestamp(self) -> str:
        if not self.show_timestamp:
            return ""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        return self._wrap(f"[{ts}] ", _Colors.GRAY)

    def _wrap(self, text: str, color: str) -> str:
        if not self.use_color:
            return text
        return f"{color}{text}{_Colors.RESET}"

    def _emit(self, tag: str, message: str, color: str):
        prefix = self._wrap(f"[{tag}]", color + _Colors.BOLD if self.use_color else color)
        print(f"{self._timestamp()}{prefix} {message}")

    def success(self, message: str):
        """Green — operation completed successfully."""
        self._emit("SUCCESS", message, _Colors.GREEN)

    def process(self, message: str):
        """Cyan — operation in progress."""
        self._emit("PROCESS", message, _Colors.CYAN)

    def failed(self, message: str):
        """Red — operation failed."""
        self._emit("FAILED", message, _Colors.RED)

    def info(self, message: str):
        """Blue — general info (bonus level)."""
        self._emit("INFO", message, _Colors.BLUE)

    def warn(self, message: str):
        """Yellow — warning (bonus level)."""
        self._emit("WARN", message, _Colors.YELLOW)


# Ready-to-use singleton — just `from colorlog import log`
log = ColorLogger()


if __name__ == "__main__":
    log.process("Running database migration...")
    log.success("Migration completed in 1.2s")
    log.warn("2 deprecated columns found")
    log.failed("Rollback failed: connection refused")
    log.info("Run with --verbose for more detail")