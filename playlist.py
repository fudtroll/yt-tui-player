"""YT TUI Player — playlist manager (playlist.md)."""
import json
import subprocess
from datetime import date
from dataclasses import dataclass
from pathlib import Path

from config import PLAYLIST_FILE


@dataclass
class PlaylistEntry:
    url: str = ""
    title: str = ""
    duration: int = 0       # seconds
    added: str = ""         # date string


def fmt_duration(sec: int) -> str:
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fetch_metadata(url: str) -> tuple[str, int]:
    """Fetch title and duration from yt-dlp. Returns (title, duration_sec)."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", url],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return (url, 0)
        data = json.loads(result.stdout)
        title = data.get("title") or data.get("webpage_url_basename", url)
        duration = data.get("duration") or 0
        return (title, int(duration))
    except Exception:
        return (url, 0)


def expand_playlist_url(url: str) -> list[dict]:
    """If url is a playlist, return list of {url, title} entries.
    If single video, return [{url, title}]."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--dump-json", url],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            return [{"url": url, "title": ""}]
        entries = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            data = json.loads(line)
            # yt-dlp gives either 'url' (full URL) or just video ID
            vid_url = data.get("webpage_url") or data.get("url", url)
            entries.append({
                "url": vid_url,
                "title": data.get("title", ""),
            })
        return entries if entries else [{"url": url, "title": ""}]
    except Exception:
        return [{"url": url, "title": ""}]


class Playlist:
    """Manages playlist.md — one entry per line: url | title | duration | date"""

    def __init__(self, path: str | Path = PLAYLIST_FILE):
        self.path = Path(path)

    def load(self) -> list[PlaylistEntry]:
        """Read playlist.md, return list of entries."""
        if not self.path.exists():
            return []
        entries = []
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            url = parts[0]
            title = parts[1] if len(parts) > 1 else url
            duration = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            added = parts[3] if len(parts) > 3 else ""
            entries.append(PlaylistEntry(url=url, title=title, duration=duration, added=added))
        return entries

    def save_entry(self, url: str, title: str, duration: int = 0):
        """Append a single entry to playlist.md."""
        today = str(date.today())
        line = f"{url} | {title} | {duration} | {today}\n"
        if self.path.exists() and self.path.read_text().strip():
            with self.path.open("a") as f:
                f.write(line)
        else:
            self.path.write_text("# YT TUI Player — Playlist\n" + line)

    def add_url(self, url: str) -> str:
        """Fetch metadata and add to playlist. Returns status message."""
        entries = expand_playlist_url(url)
        if len(entries) > 1:
            for e in entries:
                title = e["title"] or fetch_metadata(e["url"])[0]
                self.save_entry(e["url"], title)
            return f"Added {len(entries)} tracks from playlist"
        else:
            title, dur = fetch_metadata(url)
            self.save_entry(url, title, dur)
            return f"Saved: {title}"

    def remove_entry(self, index: int) -> str:
        """Remove entry at index (0-based) from playlist.md. Returns title."""
        entries = self.load()
        if index < 0 or index >= len(entries):
            return ""
        removed = entries.pop(index)
        self._rewrite(entries)
        return removed.title or removed.url

    def _rewrite(self, entries: list[PlaylistEntry]):
        lines = ["# YT TUI Player — Playlist"]
        for e in entries:
            lines.append(f"{e.url} | {e.title} | {e.duration} | {e.added}")
        self.path.write_text("\n".join(lines) + "\n")
