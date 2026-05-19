"""YT TUI Player — Textual TUI App."""
import threading
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, Footer, Header, Input, ListItem, ListView, Static

from config import *
from playlist import Playlist, PlaylistEntry, fmt_duration
from player import YTPlayer, kill_all_mpv


# ── Playlist Item Widget ──

class PlaylistItem(Static):
    """A single playlist row."""

    def __init__(self, entry: PlaylistEntry, is_active: bool = False):
        self.entry = entry
        self.is_active = is_active
        super().__init__()

    def render(self) -> str:
        dur = fmt_duration(self.entry.duration) if self.entry.duration else ""
        dur_part = f"  [#888888]{dur:>7}[/]" if dur else ""
        mark = "[#00ff00]▶[/] " if self.is_active else "  "
        name = self.entry.title or self.entry.url
        # Truncate long titles
        if len(name) > 50:
            name = name[:47] + "..."
        return (
            f"{mark}[#e0e0e0]{name:<50}[/]{dur_part}"
        )


# ── Player Info Formatter ──

def fmt_player_line(entry: PlaylistEntry | None, playing: bool) -> str:
    """Compact one-liner: ▶ title duration."""
    if not entry or not playing:
        return (
            f"  [#888888]■ stopped[/]"
            f"  [#888888]vol —[/]"
        )
    dur_total = fmt_duration(entry.duration) if entry.duration else "--:--"
    name = entry.title or entry.url
    if len(name) > 40:
        name = name[:37] + "..."
    return (
        f"  [#00ff00]▶[/] [#e0e0e0]{name:<40}[/]"
        f"  [#888888]{dur_total}[/]"
    )


# ── Main App ──

class YTTUIApp(App):
    """YT TUI Player."""

    CSS = """
    Screen, #app-container {
        background: #121212;
        color: #e0e0e0;
    }

    Header {
        background: #121212;
        color: #888888;
        border-bottom: solid #333333;
    }

    Footer {
        background: #121212;
        color: #888888;
        border-top: solid #333333;
    }

    /* ── PLAYLIST PANEL ── */
    #playlist-panel {
        height: 1fr;
        border: solid #333333;
        border-bottom: none;
        padding: 0 1;
        background: #1e1e1e;
    }

    #panel-header {
        height: 1;
        padding: 0;
        margin: 1 1 0 1;
        color: #888888;
        text-style: bold;
    }

    #playlist-list {
        height: 1fr;
        margin: 0;
        background: #1e1e1e;
        border: none;
    }

    #playlist-list > ListItem {
        height: 1;
        padding: 0;
    }

    #playlist-list > ListItem:hover {
        background: #2a2a2a;
    }

    #playlist-list > ListItem.-active {
        background: #1b3a2f;
    }

    #playlist-list:focus {
        border: none;
    }

    /* ── PLAYER BAR ── */
    #player-zone {
        height: auto;
        padding: 0 1;
        background: #1e1e1e;
        border: solid #333333;
    }

    #player-line {
        height: 1;
        align: left middle;
        padding: 0;
        margin: 1 0 0 0;
    }

    #player-info {
        height: 1;
        color: #e0e0e0;
        padding: 0 0 0 1;
    }

    /* ── CONTROLS ── */
    #controls-bar {
        height: 3;
        align: center middle;
    }

    #controls-bar Button {
        margin: 0 1;
        min-width: 4;
    }

    Button {
        background: #21262d;
        color: #e0e0e0;
        border: none;
    }

    Button:hover {
        background: #30363d;
        color: #ffffff;
    }

    Button:focus {
        background: #00ffff;
        color: #121212;
    }

    Button.variant-success {
        background: #1b3624;
        color: #00ff00;
    }

    Button.variant-success:hover {
        background: #00ff00;
        color: #121212;
    }

    Button.variant-error {
        background: #361b22;
        color: #ff0000;
    }

    Button.variant-error:hover {
        background: #ff0000;
        color: #121212;
    }

    Button.variant-primary {
        background: #1b2736;
        color: #00ffff;
    }

    Button.variant-primary:hover {
        background: #00ffff;
        color: #121212;
    }

    /* ── URL INPUT ── */
    #url-row {
        height: 3;
        align: center middle;
        margin: 0 0;
    }

    #url-input {
        margin: 0 1;
        background: #121212;
        color: #e0e0e0;
        border: solid #333333;
        width: 1fr;
    }

    #url-input:focus {
        border: solid #00ffff;
    }

    #btn-save {
        min-width: 6;
    }

    #btn-play-url {
        min-width: 6;
    }

    /* ── STATUS BAR ── */
    #status-bar {
        height: 1;
        padding: 0 1;
        background: #121212;
        color: #666666;
        text-style: italic;
    }
    """

    BINDINGS = [
        Binding("p", "play_selected", "Play", priority=True),
        Binding("s", "stop", "Stop", priority=True),
        Binding("n", "next", "Next", priority=True),
        Binding("d", "delete_selected", "Del", priority=True),
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("q", "quit", "Quit", priority=True),
    ]

    TITLE = APP_TITLE

    def __init__(self):
        super().__init__()
        self.playlist = Playlist()
        self.player = YTPlayer()
        self.entries: list[PlaylistEntry] = []
        self.current_entry: PlaylistEntry | None = None

    # ── Compose ──

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="app-container"):
            # ── Playlist ──
            with Vertical(id="playlist-panel"):
                yield Static("PLAYLIST", id="panel-header")
                yield ListView(id="playlist-list")
            # ── Player + Controls ──
            with Vertical(id="player-zone"):
                with Horizontal(id="player-line"):
                    yield Static(id="player-info")
                with Horizontal(id="controls-bar"):
                    yield Button("Play", id="btn-play", variant="success")
                    yield Button("Stop", id="btn-stop", variant="error")
                    yield Button("Next", id="btn-next")
                    yield Button("Del", id="btn-del", variant="error")
                with Horizontal(id="url-row"):
                    yield Button("▶URL", id="btn-play-url", variant="primary")
                    yield Input(placeholder="Paste YouTube URL here...", id="url-input")
                    yield Button("Save", id="btn-save", variant="primary")
        yield Static(id="status-bar")
        yield Footer()

    # ── Lifecycle ──

    def on_mount(self):
        kill_all_mpv()
        self.load_playlist()
        self.set_status("Ready — p to play, s to stop, URL to add")

    def set_status(self, msg: str):
        try:
            self.query_one("#status-bar", Static).update(f" {msg}")
        except NoMatches:
            pass

    # ── Playlist ──

    def load_playlist(self):
        self.entries = self.playlist.load()
        self._update_playlist_ui()

    def _update_playlist_ui(self):
        try:
            lv = self.query_one("#playlist-list", ListView)
            lv.clear()
            for i, e in enumerate(self.entries):
                is_active = (
                    self.current_entry is not None
                    and e.url == self.current_entry.url
                )
                item = ListItem(PlaylistItem(e, is_active=is_active))
                if is_active:
                    item.classes = "-active"
                lv.append(item)

            try:
                self.query_one("#panel-header", Static).update(
                    f"PLAYLIST ({len(self.entries)})"
                )
            except NoMatches:
                pass
        except NoMatches:
            pass

        self._update_player_info()

    def _update_player_info(self):
        try:
            line = fmt_player_line(
                self.current_entry if self.player.is_alive() else None,
                self.player.is_alive(),
            )
            self.query_one("#player-info", Static).update(line)
        except NoMatches:
            pass

    def refresh_display(self):
        self._update_playlist_ui()
        self._update_player_info()

    def get_selected_entry(self) -> PlaylistEntry | None:
        try:
            lv = self.query_one("#playlist-list", ListView)
            idx = lv.index
            if idx is not None and 0 <= idx < len(self.entries):
                return self.entries[idx]
        except NoMatches:
            pass
        return None

    # ── Actions ──

    def action_play_selected(self):
        entry = self.get_selected_entry()
        if entry:
            self.play_entry(entry)
        else:
            self.set_status("No items in playlist")

    def action_stop(self):
        self.player.stop()
        self.current_entry = None
        self.refresh_display()
        self.set_status("Stopped")

    def action_next(self):
        if not self.entries or self.current_entry is None:
            return
        try:
            lv = self.query_one("#playlist-list", ListView)
            idx = lv.index
            if idx is not None:
                next_idx = (idx + 1) % len(self.entries)
                lv.index = next_idx
                self.play_entry(self.entries[next_idx])
        except NoMatches:
            pass

    def action_delete_selected(self):
        entry = self.get_selected_entry()
        if not entry:
            return
        title = self.playlist.remove_entry(self.entries.index(entry))
        self.load_playlist()
        self.set_status(f"Deleted: {title}")

    def action_refresh(self):
        self.load_playlist()
        self.set_status("Refreshed")

    def action_quit(self):
        self.player.stop()
        self.exit()

    def play_entry(self, entry: PlaylistEntry):
        try:
            self.player.play(entry.url, entry.title, entry.duration)
            self.current_entry = entry
            self.refresh_display()
            self.set_status(f"▶ {entry.title or 'Playing...'}")
        except Exception as e:
            self.set_status(f"Failed: {e}")

    # ── Handlers ──

    def on_list_view_selected(self, event: ListView.Selected):
        """Play on Enter."""
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self.entries):
            self.play_entry(self.entries[idx])

    @on(Button.Pressed, "#btn-play")
    def btn_play(self):
        self.action_play_selected()

    @on(Button.Pressed, "#btn-stop")
    def btn_stop(self):
        self.action_stop()

    @on(Button.Pressed, "#btn-next")
    def btn_next(self):
        self.action_next()

    @on(Button.Pressed, "#btn-del")
    def btn_del(self):
        self.action_delete_selected()

    @on(Button.Pressed, "#btn-save")
    def btn_save(self):
        url = self.query_one("#url-input", Input).value.strip()
        if not url:
            self.set_status("Paste a URL first")
            return
        msg = self.playlist.add_url(url)
        self.load_playlist()
        self.query_one("#url-input", Input).value = ""
        self.set_status(msg)

    @on(Button.Pressed, "#btn-play-url")
    def btn_play_url(self):
        url = self.query_one("#url-input", Input).value.strip()
        if not url:
            self.set_status("Paste a URL first")
            return
        # Create a temporary entry and play directly
        from playlist import fetch_metadata
        title, dur = fetch_metadata(url)
        entry = PlaylistEntry(url=url, title=title, duration=dur)
        self.play_entry(entry)
