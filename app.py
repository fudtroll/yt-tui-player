"""YT TUI Player — Textual TUI App."""
import random
import subprocess
import time
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Footer, Header, Input, Label, ListItem,
    ListView, SelectionList, Static,
)

from config import *
from playlist import Playlist, PlaylistEntry, fmt_duration, search_youtube, fetch_metadata
from player import YTPlayer, kill_all_mpv


# ── Playlist Item ──

class PlaylistItem(Static):
    """A single playlist row with [✓]/[+] tag."""

    def __init__(self, entry: PlaylistEntry, is_active: bool = False):
        self.entry = entry
        self.is_active = is_active
        super().__init__()

    def render(self) -> str:
        dur = fmt_duration(self.entry.duration) if self.entry.duration else ""
        dur_part = f"  [#888888]{dur:>7}[/]" if dur else ""
        playing_mark = "[#00ff00]▶[/] " if self.is_active else "  "

        if self.entry.saved:
            # [DB] = already in database
            tag = "[#888888][✓][/] "
            name_color = "#e0e0e0"
        else:
            # [+] = new, needs saving
            tag = "[#00ff00][+][/] "
            name_color = "#aaaaaa"

        name = self.entry.title or self.entry.url
        if len(name) > 46:
            name = name[:43] + "..."

        return (
            f"{playing_mark}{tag}[{name_color}]{name:<46}[/]{dur_part}"
        )


# ── Search Screen (checkboxes multi-select) ──

class SearchScreen(ModalScreen):
    """Search YouTube with multi-select checkboxes."""

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("q", "close", "Close", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="search-container"):
            yield Static("Search YouTube", classes="search-title")
            yield Input(placeholder="Search query...", id="search-input")
            yield Label("Enter to search  |  space to toggle  |  Esc close", classes="search-hint")
            yield SelectionList(id="search-results")
            with Horizontal(id="search-buttons"):
                yield Button("Play", id="search-play", variant="success")
                yield Button("Add to Playlist", id="search-add", variant="primary")
                yield Button("Close", id="search-close", variant="error")

    def on_mount(self):
        self.styles.background = "#121212"
        self.styles.border = ("solid", "#333333")
        self.query_one("#search-input", Input).focus()
        self._results: list[dict] = []

    @on(Input.Submitted, "#search-input")
    def do_search(self):
        query = self.query_one("#search-input", Input).value.strip()
        if not query:
            return
        self._results = search_youtube(query)
        sl = self.query_one("#search-results", SelectionList)
        sl.clear_options()
        if not self._results:
            self.dismiss(None)
            return
        for i, r in enumerate(self._results):
            dur = fmt_duration(r["duration"]) if r["duration"] else "—:—"
            title = r["title"]
            if len(title) > 40:
                title = title[:37] + "..."
            ch = r.get("channel", "")
            if len(ch) > 20:
                ch = ch[:17] + "..."
            label = f"{title:<40}  {dur:>7}  {ch:<20}"
            sl.add_option((label, i, False))  # (prompt, value, initial_selected)

    @on(SelectionList.SelectionToggled, "#search-results")
    def selection_changed(self):
        pass  # visual feedback handled by widget

    @on(Button.Pressed, "#search-play")
    def play_first_selected(self):
        sl = self.query_one("#search-results", SelectionList)
        selected = sl.selected
        if selected:
            self.dismiss({"action": "play", "results": self._results, "indices": selected})
        else:
            self.set_status("Check items first")

    @on(Button.Pressed, "#search-add")
    def add_selected(self):
        sl = self.query_one("#search-results", SelectionList)
        selected = sl.selected
        if selected:
            self.dismiss({"action": "add", "results": self._results, "indices": selected})
        else:
            self.set_status("Check items first")

    @on(Button.Pressed, "#search-close")
    def close(self):
        self.dismiss(None)

    def action_close(self):
        self.dismiss(None)

    def set_status(self, msg: str):
        try:
            self.query_one("#search-results", Static).update(f"  [#888888]{msg}[/]")
        except NoMatches:
            pass


# ── Player Info Formatter ──

def fmt_player_line(entry: PlaylistEntry | None, playing: bool, elapsed: int = 0) -> str:
    """Show title + elapsed / total."""
    if not entry or not playing:
        return (
            "  [#888888]■ stopped[/]  [#888888]— / —[/]"
        )
    name = entry.title or entry.url
    if len(name) > 40:
        name = name[:37] + "..."
    cur = fmt_duration(elapsed)
    total = fmt_duration(entry.duration) if entry.duration else "--:--"
    return (
        f"  [#00ff00]▶[/] [#e0e0e0]{name:<40}[/]"
        f"  [#888888]{cur} / {total}[/]"
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
        /* Playing item: only ▶ icon distinguishes it */
    }

    #playlist-list:focus {
        border: none;
    }

    #playlist-list > ListItem.-highlight {
        background: #1b3a2f;
    }

    #playlist-list:focus > ListItem.-highlight {
        background: #1b3a2f;
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

    /* ── SLIDER / PROGRESS ── */
    #slider-row {
        height: 1;
        margin: 0 1;
        align: center middle;
    }

    #player-slider {
        width: 1fr;
        height: 1;
        color: #e0e0e0;
        padding: 0 1;
    }

    #btn-vol-down, #btn-vol-up {
        min-width: 4;
        background: #21262d;
        color: #888888;
        border: none;
        padding: 0;
    }

    #btn-vol-down:hover, #btn-vol-up:hover {
        background: #30363d;
        color: #00ffff;
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

    #btn-repeat, #btn-shuffle {
        min-width: 2;
        background: #21262d;
        color: #666666;
        border: none;
    }

    #btn-repeat:hover, #btn-shuffle:hover {
        color: #e0e0e0;
    }

    #btn-repeat:focus, #btn-shuffle:focus {
        background: #21262d;
        color: #666666;
    }

    #btn-repeat.active, #btn-shuffle.active {
        color: #e0e0e0;
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
        background: #30363d;
        color: #e0e0e0;
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

    #btn-add {
        min-width: 6;
    }

    #btn-play-url {
        min-width: 6;
    }

    /* ── SEARCH MODAL ── */
    #search-container {
        align: center top;
        padding: 1 2;
        background: #1e1e1e;
        border: solid #333333;
        margin: 0 2;
    }

    .search-title {
        text-style: bold;
        color: #00ffff;
        height: 3;
        content-align: center middle;
    }

    .search-hint {
        height: 1;
        content-align: center middle;
        color: #888888;
    }

    #search-input {
        margin: 1 0;
        background: #121212;
        color: #e0e0e0;
        border: solid #333333;
    }

    #search-results {
        height: 1fr;
        margin: 1 0;
        background: #121212;
        border: solid #333333;
    }

    SelectionList {
        background: #121212;
        color: #e0e0e0;
    }

    SelectionList > ListItem:hover {
        background: #2a2a2a;
    }

    #search-buttons {
        height: 3;
        align: center middle;
    }

    #search-buttons Button {
        margin: 0 1;
        min-width: 10;
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
        Binding("delete", "delete_selected", show=False, priority=True),
        Binding("+", "save_selected", "+Save", priority=True),
        Binding("-", "delete_selected", "−Del", priority=True),
        Binding("/", "search", "Search", priority=True),
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("q", "quit", "Quit", priority=True),
        Binding("l", "toggle_repeat", "Loop", priority=True),
        Binding("z", "toggle_shuffle", "Shuf", priority=True),
        Binding("[", "vol_down", "Vol-", priority=True),
        Binding("]", "vol_up", "Vol+", priority=True),
    ]

    TITLE = APP_TITLE

    def __init__(self):
        super().__init__()
        self.playlist = Playlist()
        self.player = YTPlayer()
        self.entries: list[PlaylistEntry] = []
        self.current_entry: PlaylistEntry | None = None
        # Playback modes
        self.repeat: bool = False
        self.shuffle: bool = False
        self._was_playing: bool = False
        # Live timer
        self._play_start: float = 0.0
        self._elapsed: int = 0
        self._timer = None

    # ── Compose ──

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="app-container"):
            with Vertical(id="playlist-panel"):
                yield Static("PLAYLIST", id="panel-header")
                yield ListView(id="playlist-list")
            with Vertical(id="player-zone"):
                with Horizontal(id="player-line"):
                    yield Static(id="player-info")
                with Horizontal(id="slider-row"):
                    yield Button("−Vol", id="btn-vol-down")
                    yield Static(id="player-slider")
                    yield Button("+Vol", id="btn-vol-up")
                with Horizontal(id="controls-bar"):
                    yield Button("↻", id="btn-repeat")
                    yield Button("⇄", id="btn-shuffle")
                    yield Button("Play", id="btn-play", variant="success")
                    yield Button("Stop", id="btn-stop", variant="error")
                    yield Button("Next", id="btn-next")
                    yield Button("+Save", id="btn-save-entry", variant="primary")
                    yield Button("−Del", id="btn-del-entry", variant="error")
                    yield Button("Search", id="btn-search")
                with Horizontal(id="url-row"):
                    yield Button("▶URL", id="btn-play-url", variant="primary")
                    yield Input(placeholder="Paste YouTube URL here...", id="url-input")
                    yield Button("Add", id="btn-add", variant="primary")
        yield Static(id="status-bar")
        yield Footer()

    # ── Lifecycle ──

    def on_mount(self):
        kill_all_mpv()
        self.load_playlist()
        self._timer = self.set_interval(1, self._timer_tick)
        self._update_mode_ui()
        self.set_status("Ready — ↑↓ pick, p play, s stop, / search, l loop, z shuffle, [ ] vol")

    def set_status(self, msg: str):
        try:
            self.query_one("#status-bar", Static).update(f" {msg}")
        except NoMatches:
            pass

    def _timer_tick(self):
        """Update elapsed time every second; auto-advance on song end."""
        if self.player.is_alive():
            if self._play_start > 0:
                self._elapsed = int(time.time() - self._play_start)
                self._update_player_info()
                self._update_slider()
            self._was_playing = True
        elif self._was_playing:
            # Song just ended — auto-advance
            self._was_playing = False
            self.current_entry = None
            self._play_start = 0
            self._elapsed = 0
            self._update_player_info()
            self._update_slider()
            self._auto_advance()

    def _update_slider(self):
        try:
            bar = self.query_one("#player-slider", Static)
            if self.player.is_alive() and self.current_entry and self.current_entry.duration > 0:
                pct = min(100, int(self._elapsed / self.current_entry.duration * 100))
                avail = bar.size.width
                bar_w = max(5, avail)
                filled = int(pct / 100 * bar_w)
                bar.update(
                    f"[#00ff00]{'█' * filled}{'░' * (bar_w - filled)}[/]"
                )
            else:
                bar.update("")
        except NoMatches:
            pass

    # ── Volume ──

    def _get_vol(self) -> float:
        """Get current volume (0.0–1.0)."""
        try:
            r = subprocess.run(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                capture_output=True, text=True, timeout=5,
            )
            # Output: "Volume: 0.75"
            parts = r.stdout.strip().split()
            if parts:
                return float(parts[-1])
        except Exception:
            pass
        return 0.75

    def action_vol_up(self):
        subprocess.run(
            ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "5%+"],
            timeout=5,
        )
        vol = self._get_vol()
        self.set_status(f"Volume: {int(vol * 100)}%")

    def action_vol_down(self):
        subprocess.run(
            ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"],
            timeout=5,
        )
        vol = self._get_vol()
        self.set_status(f"Volume: {int(vol * 100)}%")

    # ── Playback Modes (Repeat / Shuffle) ──

    def _auto_advance(self):
        """Auto-play next song when current ends (Winamp style)."""
        if not self.entries:
            return
        try:
            lv = self.query_one("#playlist-list", ListView)
            if self.shuffle:
                idx = random.randint(0, len(self.entries) - 1)
            elif self.repeat:
                cur = lv.index if lv.index is not None else -1
                idx = (cur + 1) % len(self.entries)
            else:
                cur = lv.index if lv.index is not None else -1
                idx = cur + 1
                if idx >= len(self.entries):
                    self.set_status("♪ End of playlist")
                    return
            lv.index = idx
            self.play_entry(self.entries[idx])
        except NoMatches:
            pass

    def action_toggle_repeat(self):
        self.repeat = not self.repeat
        self._update_mode_ui()
        self.set_status(f"Repeat {'ON' if self.repeat else 'OFF'}")

    def action_toggle_shuffle(self):
        self.shuffle = not self.shuffle
        self._update_mode_ui()
        self.set_status(f"Shuffle {'ON' if self.shuffle else 'OFF'}")

    def _update_mode_ui(self):
        """Update mode button active state."""
        try:
            self.query_one("#btn-repeat", Button).set_class(self.repeat, "active")
            self.query_one("#btn-shuffle", Button).set_class(self.shuffle, "active")
        except NoMatches:
            pass

    # ── Playlist ──

    def load_playlist(self):
        saved = self.playlist.load()
        # Keep unsaved entries (from search/URL) + merge saved ones
        unsaved = [e for e in self.entries if not e.saved]
        # Mark any saved entries that match unsaved URLs
        saved_urls = {e.url for e in saved}
        unsaved = [e for e in unsaved if e.url not in saved_urls]
        self.entries = saved + unsaved
        self._update_playlist_ui()
        self._ensure_focus_on_list()

    def _update_playlist_ui(self):
        try:
            lv = self.query_one("#playlist-list", ListView)
            current_children = list(lv.children)
            n_entries = len(self.entries)
            n_children = len(current_children)

            # Reuse existing ListItems by updating PlaylistItem in-place
            for i, e in enumerate(self.entries):
                is_active = (
                    self.current_entry is not None
                    and e.url == self.current_entry.url
                )
                if i < n_children:
                    # Update existing ListItem
                    li = current_children[i]
                    # Find the PlaylistItem widget inside
                    pi = li.query_one(PlaylistItem)
                    pi.entry = e
                    pi.is_active = is_active
                    pi.refresh()
                    li.set_class(is_active, "-active")
                else:
                    # New item needed
                    item = ListItem(PlaylistItem(e, is_active=is_active))
                    if is_active:
                        item.classes = "-active"
                    lv.append(item)

            # Remove excess items (reverse order)
            for li in reversed(current_children[n_entries:]):
                li.remove()

            self._update_playlist_header()

        except NoMatches:
            pass
        self._update_player_info()

    def _update_playlist_header(self):
        try:
            self.query_one("#panel-header", Static).update(
                f"PLAYLIST ({len(self.entries)})"
            )
        except NoMatches:
            pass

    def _update_player_info(self):
        try:
            line = fmt_player_line(
                self.current_entry if self.player.is_alive() else None,
                self.player.is_alive(),
                self._elapsed if self.player.is_alive() else 0,
            )
            self.query_one("#player-info", Static).update(line)
        except NoMatches:
            pass

    def refresh_display(self):
        self._update_playlist_ui()
        self._update_player_info()
        self._update_slider()
        # Ensure ListView keeps focus after any update
        self._ensure_focus_on_list()

    def _ensure_focus_on_list(self):
        """Focus the playlist ListView and ensure a valid index."""
        try:
            lv = self.query_one("#playlist-list", ListView)
            if self.entries:
                # Set index if missing
                if lv.index is None or lv.index >= len(self.entries):
                    if self.current_entry:
                        play_idx = next(
                            (i for i, e in enumerate(self.entries)
                             if e.url == self.current_entry.url),
                            0,
                        )
                        lv.index = play_idx
                    else:
                        lv.index = 0
                lv.focus()
        except NoMatches:
            pass

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
        self._play_start = 0
        self._elapsed = 0
        self._was_playing = False
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
        """Remove selected entry from playlist.md and list."""
        entry = self.get_selected_entry()
        if not entry:
            return
        if entry.saved:
            # Remove from playlist.md
            try:
                idx = self.entries.index(entry)
                self.playlist.remove_entry(idx)
            except (ValueError, IndexError):
                pass
        # Remove from current entries list
        self.entries = [e for e in self.entries if e.url != entry.url]
        self.refresh_display()
        self.set_status(f"Removed: {entry.title}")

    def action_save_selected(self):
        """Save the selected unsaved entry to playlist.md."""
        entry = self.get_selected_entry()
        if not entry:
            return
        if entry.saved:
            self.set_status("Already in playlist")
            return
        self.playlist.save_entry(entry.url, entry.title, entry.duration)
        entry.saved = True
        self.refresh_display()
        self.set_status(f"Saved: {entry.title}")

    def action_search(self):
        screen = SearchScreen()
        self.push_screen(screen, self._on_search_done)

    def _on_search_done(self, result):
        if not result or not isinstance(result, dict):
            self._ensure_focus_on_list()
            return
        action = result["action"]
        results = result["results"]
        indices = result["indices"]
        for i in indices:
            r = results[i]
            entry = PlaylistEntry(
                url=r["url"],
                title=r["title"],
                duration=r.get("duration", 0),
                saved=False,
            )
            if action == "play" and i == indices[0]:
                # Play the first selected, add all to playlist
                self.play_entry(entry)
            # Add to entries if not already there
            if not any(e.url == entry.url for e in self.entries):
                self.entries.append(entry)
        self._update_playlist_ui()
        self._ensure_focus_on_list()
        count = len(indices)
        self.set_status(f"Added {count} track{'s' if count > 1 else ''} to playlist (+ to save)")

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
            self._play_start = time.time()
            self._elapsed = 0
            self._was_playing = True
            self.refresh_display()
            self.set_status(f"▶ {entry.title or 'Playing...'}")
        except Exception as e:
            self.set_status(f"Failed: {e}")

    # ── Handlers ──
    # No on_list_view_selected — Winamp style: ↑↓ to pick, p/Play to play

    @on(Button.Pressed, "#btn-play")
    def btn_play(self):
        self.action_play_selected()

    @on(Button.Pressed, "#btn-stop")
    def btn_stop(self):
        self.action_stop()

    @on(Button.Pressed, "#btn-next")
    def btn_next(self):
        self.action_next()

    @on(Button.Pressed, "#btn-save-entry")
    def btn_save_entry(self):
        self.action_save_selected()

    @on(Button.Pressed, "#btn-del-entry")
    def btn_del_entry(self):
        self.action_delete_selected()

    @on(Button.Pressed, "#btn-search")
    def btn_search(self):
        self.action_search()

    @on(Button.Pressed, "#btn-vol-down")
    def btn_vol_down(self):
        self.action_vol_down()

    @on(Button.Pressed, "#btn-vol-up")
    def btn_vol_up(self):
        self.action_vol_up()

    @on(Button.Pressed, "#btn-repeat")
    def btn_repeat(self):
        self.action_toggle_repeat()

    @on(Button.Pressed, "#btn-shuffle")
    def btn_shuffle(self):
        self.action_toggle_shuffle()

    @on(Button.Pressed, "#btn-add")
    def btn_add(self):
        """Add URL as unsaved entry (doesn't write to playlist.md yet)."""
        url = self.query_one("#url-input", Input).value.strip()
        if not url:
            self.set_status("Paste a URL first")
            return
        title, dur = fetch_metadata(url)
        entry = PlaylistEntry(url=url, title=title, duration=dur, saved=False)
        if any(e.url == entry.url for e in self.entries):
            self.set_status("Already in playlist")
            return
        self.entries.append(entry)
        self._update_playlist_ui()
        self.query_one("#url-input", Input).value = ""
        self.set_status(f"Added: {title}  (+ to save to playlist)")

    @on(Button.Pressed, "#btn-play-url")
    def btn_play_url(self):
        url = self.query_one("#url-input", Input).value.strip()
        if not url:
            self.set_status("Paste a URL first")
            return
        title, dur = fetch_metadata(url)
        entry = PlaylistEntry(url=url, title=title, duration=dur, saved=False)
        self.play_entry(entry)
        if not any(e.url == entry.url for e in self.entries):
            self.entries.append(entry)
            self._update_playlist_ui()
