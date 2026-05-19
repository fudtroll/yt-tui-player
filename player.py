"""YT TUI Player — mpv/yt-dlp backend."""
import os
import signal
import subprocess
import json


class YTPlayer:
    """Manages mpv process for YouTube audio streaming."""

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self.current_url: str = ""
        self.current_title: str = "—"
        self.current_duration: int = 0

    def play(self, url: str, title: str = "", duration: int = 0):
        """Play YouTube audio via mpv + yt-dlp (bestaudio)."""
        self.stop()
        self.current_url = url
        self.current_title = title or url
        self.current_duration = duration

        cmd = [
            "mpv",
            "--ytdl-format=bestaudio",
            "--no-video",
            "--quiet",
            "--no-terminal",
            url,
        ]
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )

    def stop(self):
        """Kill the current mpv process."""
        if self._process:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                self._process.wait(timeout=3)
            except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
                try:
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
            self._process = None
        self.current_url = ""
        self.current_title = "—"
        self.current_duration = 0

    def is_alive(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None


def kill_all_mpv():
    """Kill any lingering mpv processes."""
    try:
        subprocess.run(["pkill", "-f", "mpv"], capture_output=True)
    except FileNotFoundError:
        # Fallback for Termux / systems without pkill
        subprocess.run(["killall", "mpv"], capture_output=True)
