import io
import os
from time import monotonic

from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Input, Label, Button, Rule
from textual.binding import Binding
from textual.screen import ModalScreen

from .core import EmulatorController
from .screen import screen_filename
from .stick import SenseStick, make_stick_event
from .recfile import parse_recording
from .playback import Player
from .recorder import Recorder

_parse_recording = parse_recording


# ── Joystick event constants (canonical values live in stick.SenseStick) ──────

_EV_KEY       = SenseStick.EV_KEY
_KEY_UP       = SenseStick.KEY_UP
_KEY_LEFT     = SenseStick.KEY_LEFT
_KEY_RIGHT    = SenseStick.KEY_RIGHT
_KEY_DOWN     = SenseStick.KEY_DOWN
_KEY_ENTER    = SenseStick.KEY_ENTER
_EVENT_FORMAT = SenseStick.EVENT_FORMAT
_make_joystick_event = make_stick_event


# ── LED Matrix ────────────────────────────────────────────────────────────────

class LEDMatrix(Static):
    """Renders the 8×8 LED matrix using Unicode block characters."""

    def on_mount(self):
        self._screen_client = None
        self.set_interval(0.1, self._refresh_matrix)

    def set_screen_client(self, client):
        self._screen_client = client

    def _refresh_matrix(self):
        if self._screen_client is None:
            self.update("[dim]Waiting for emulator…[/dim]")
            return
        try:
            rgb   = self._screen_client.rgb_array  # (8, 8, 3) uint8
            lines = []
            for y in range(8):
                row = "".join(
                    f"[rgb({int(rgb[y,x,0])},{int(rgb[y,x,1])},{int(rgb[y,x,2])})]██[/]"
                    for x in range(8)
                )
                lines.append(row)
            self.update("\n".join(lines))
        except Exception:
            pass


# ── Live Sensor Readings ──────────────────────────────────────────────────────

class SensorReadings(Static):
    """Shows live sensor values from the emulator or a recording."""

    def on_mount(self):
        self._hat     = None
        self._records = []
        self._rec_t0  = 0.0
        self._label   = "—"
        self.set_interval(0.5, self._refresh)

    def set_live(self, hat, label="Emulator"):
        self._hat     = hat
        self._records = []
        self._label   = label

    def set_recording(self, records, label="Recording"):
        self._hat     = None
        self._records = records
        self._rec_t0  = monotonic()
        self._label   = label

    def _refresh(self):
        if self._hat is not None:
            self._render_live()
        elif self._records:
            self._render_recording()
        else:
            self.update(f"[bold]Source:[/bold] {self._label}\n\nNo data.")

    def _render_live(self):
        try:
            ac  = self._hat.get_accelerometer_raw()
            gy  = self._hat.get_gyroscope_raw()
            co  = self._hat.get_compass_raw()
            ori = self._hat.get_orientation()
            self.update(
                f"[bold]Source:[/bold] {self._label}\n\n"
                f"[bold]Accelerometer[/bold] (G)\n"
                f"  X:{ac.get('x',0):+.3f}  Y:{ac.get('y',0):+.3f}  Z:{ac.get('z',0):+.3f}\n\n"
                f"[bold]Gyroscope[/bold] (rad/s)\n"
                f"  X:{gy.get('x',0):+.3f}  Y:{gy.get('y',0):+.3f}  Z:{gy.get('z',0):+.3f}\n\n"
                f"[bold]Compass[/bold] (µT)\n"
                f"  X:{co.get('x',0):+.3f}  Y:{co.get('y',0):+.3f}  Z:{co.get('z',0):+.3f}\n\n"
                f"[bold]Orientation[/bold] (°)\n"
                f"  Roll:{ori.get('roll',0):.1f}  "
                f"Pitch:{ori.get('pitch',0):.1f}  "
                f"Yaw:{ori.get('yaw',0):.1f}\n\n"
                f"[bold]Pressure:[/bold]  {self._hat.get_pressure():.2f} mbar\n"
                f"[bold]Temp (P):[/bold]  {self._hat.get_temperature_from_pressure():.2f} °C\n"
                f"[bold]Humidity:[/bold]  {self._hat.get_humidity():.2f} %RH\n"
                f"[bold]Temp (H):[/bold]  {self._hat.get_temperature_from_humidity():.2f} °C"
            )
        except Exception:
            pass

    def _render_recording(self):
        elapsed = monotonic() - self._rec_t0
        t0      = self._records[0].timestamp
        t_end   = self._records[-1].timestamp - t0
        idx     = len(self._records) - 1
        for i, rec in enumerate(self._records):
            if rec.timestamp - t0 >= elapsed:
                idx = i
                break
        rec = self._records[idx]
        self.update(
            f"[bold]Source:[/bold] {self._label}\n"
            f"t = {rec.timestamp - t0:.1f}s / {t_end:.1f}s\n\n"
            f"[bold]Accelerometer[/bold] (G)\n"
            f"  X:{rec.ax:+.3f}  Y:{rec.ay:+.3f}  Z:{rec.az:+.3f}\n\n"
            f"[bold]Gyroscope[/bold] (rad/s)\n"
            f"  X:{rec.gx:+.3f}  Y:{rec.gy:+.3f}  Z:{rec.gz:+.3f}\n\n"
            f"[bold]Compass[/bold] (µT)\n"
            f"  X:{rec.cx:+.3f}  Y:{rec.cy:+.3f}  Z:{rec.cz:+.3f}\n\n"
            f"[bold]Orientation[/bold] (°)\n"
            f"  Roll:{rec.ox:.1f}  Pitch:{rec.oy:.1f}  Yaw:{rec.oz:.1f}\n\n"
            f"[bold]Pressure:[/bold]  {rec.pressure:.2f} mbar\n"
            f"[bold]Temp (P):[/bold]  {rec.ptemp:.2f} °C\n"
            f"[bold]Humidity:[/bold]  {rec.humidity:.2f} %RH\n"
            f"[bold]Temp (H):[/bold]  {rec.htemp:.2f} °C"
        )


# ── Recording path dialog ─────────────────────────────────────────────────────

class RecordingPathScreen(ModalScreen):
    """Modal dialog to enter the path to a .bin recording file."""

    CSS = """
    RecordingPathScreen {
        align: center middle;
    }
    #rec-dialog {
        width: 60;
        height: 11;
        border: double $primary;
        padding: 1 2;
        background: $surface;
    }
    #rec-buttons {
        margin-top: 1;
        align: right middle;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title="Open recording file", **kwargs):
        super().__init__(**kwargs)
        self._dialog_title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="rec-dialog"):
            yield Label(self._dialog_title)
            yield Rule()
            yield Label("Path to .bin file:")
            yield Input(placeholder="/path/to/recording.bin", id="rec-path-input")
            with Horizontal(id="rec-buttons"):
                yield Button("Open", variant="primary", id="rec-open")
                yield Button("Cancel",                  id="rec-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rec-open":
            self.dismiss(self.query_one("#rec-path-input").value.strip())
        else:
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


# ── Main TUI application ──────────────────────────────────────────────────────

class SenseEmuTUI(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3;
        grid-columns: 24 1fr 1fr;
    }

    #left-panel {
        height: 100%;
        border: solid $primary;
        padding: 1;
    }

    #controls-panel {
        height: 100%;
        border: solid $primary;
        padding: 1;
        overflow-y: auto;
    }

    #telemetry-panel {
        height: 100%;
        border: solid $primary;
        padding: 1;
        overflow-y: auto;
    }

    .panel-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .section-title {
        text-style: bold;
        color: $text-muted;
        margin-top: 1;
    }

    .field-label {
        margin-top: 1;
        color: $text-muted;
    }

    #joystick-grid {
        layout: grid;
        grid-size: 3;
        grid-columns: 1fr 1fr 1fr;
        height: 9;
        margin-top: 1;
    }

    .joy-btn { height: 3; }

    #source-row {
        layout: horizontal;
        margin-top: 1;
        height: 3;
    }

    .source-btn { margin-right: 1; }

    #source-status { margin-top: 1; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit",             "Quit",        show=True),
        Binding("ctrl+o", "open_recording",   "View",        show=True),
        Binding("ctrl+p", "replay_recording", "Replay",      show=True),
        Binding("ctrl+r", "toggle_recording", "Rec",         show=True),
        Binding("ctrl+e", "use_emulator",     "Emulator",    show=True),
        # priority=True so these fire even when an Input widget has focus
        Binding("up",    "joy_up",    "↑", show=True, priority=True),
        Binding("down",  "joy_down",  "↓", show=True, priority=True),
        Binding("left",  "joy_left",  "←", show=True, priority=True),
        Binding("right", "joy_right", "→", show=True, priority=True),
        Binding("enter", "joy_enter", "●", show=True, priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # ── Left: LED Matrix + Joystick ───────────────────────────────────────
        with Vertical(id="left-panel"):
            yield Label("LED Matrix (8×8)", classes="panel-title")
            yield LEDMatrix(id="led-matrix")
            yield Rule()
            yield Label("Joystick", classes="panel-title")
            with Grid(id="joystick-grid"):
                yield Static()
                yield Button("↑", id="joy-up",    classes="joy-btn")
                yield Static()
                yield Button("←", id="joy-left",  classes="joy-btn")
                yield Button("●", id="joy-enter", variant="primary", classes="joy-btn")
                yield Button("→", id="joy-right", classes="joy-btn")
                yield Static()
                yield Button("↓", id="joy-down",  classes="joy-btn")
                yield Static()

        # ── Center: Controls ──────────────────────────────────────────────────
        with Vertical(id="controls-panel"):
            yield Label("Controls", classes="panel-title")

            yield Label("── IMU (Orientation) ──", classes="section-title")
            yield Label("Pitch (-180…180°):", classes="field-label")
            yield Input(value="0",    id="pitch",    placeholder="-180 … 180")
            yield Label("Roll (-180…180°):",  classes="field-label")
            yield Input(value="0",    id="roll",     placeholder="-180 … 180")
            yield Label("Yaw (0…360°):",      classes="field-label")
            yield Input(value="0",    id="yaw",      placeholder="0 … 360")

            yield Label("── Environment ──", classes="section-title")
            yield Label("Temperature (°C):",  classes="field-label")
            yield Input(value="20",   id="temp",     placeholder="-40 … 120")
            yield Label("Pressure (mbar):",   classes="field-label")
            yield Input(value="1013", id="pressure", placeholder="260 … 1260")
            yield Label("Humidity (%RH):",    classes="field-label")
            yield Input(value="45",   id="humidity", placeholder="0 … 100")

            yield Label("── Source ──", classes="section-title")
            with Horizontal(id="source-row"):
                yield Button("Emulator",   id="btn-emu", variant="success", classes="source-btn")
                yield Button("Recording…", id="btn-rec", variant="default", classes="source-btn")
            yield Label("", id="source-status")

        # ── Right: Live Telemetry ─────────────────────────────────────────────
        with Vertical(id="telemetry-panel"):
            yield Label("Sensor Readings", classes="panel-title")
            yield SensorReadings(id="sensor-readings")

        yield Footer()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self):
        try:
            self.controller = EmulatorController()
        except RuntimeError:
            self.exit(
                message='Another instance of the Sense HAT emulator is already running.\n'
                        'Please close it before starting a new one.')
            return
        self._player = None
        self._playback_timer = None
        self._recorder = None
        self._rec_timer = None
        self.query_one(LEDMatrix).set_screen_client(self.controller.screen)
        self._activate_emulator()

    def on_unmount(self):
        if hasattr(self, '_player') and self._player and self._player.running:
            self._player.stop()
        if hasattr(self, '_recorder') and self._recorder and self._recorder.running:
            self._recorder.stop()
        self.controller.close()

    def _activate_emulator(self):
        from .sense_hat import SenseHat
        hat = SenseHat()
        self.query_one(SensorReadings).set_live(hat, label="Emulator")
        self._set_status("[green]Emulator active[/green]")

    def _set_status(self, markup):
        try:
            self.query_one("#source-status").update(markup)
        except Exception:
            pass

    # ── Input handlers ────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        if not hasattr(self, "controller"):
            return
        try:
            float(event.value)  # validate before reading other fields
        except ValueError:
            return
        try:
            imu_ids = ("pitch", "roll", "yaw")
            env_ids = ("pressure", "temp", "humidity")
            if event.input.id in imu_ids:
                pitch    = float(self.query_one("#pitch").value)
                roll     = float(self.query_one("#roll").value)
                yaw      = float(self.query_one("#yaw").value)
                self.controller.imu.set_orientation((roll, pitch, yaw))
            elif event.input.id in env_ids:
                pressure = float(self.query_one("#pressure").value)
                temp     = float(self.query_one("#temp").value)
                humidity = float(self.query_one("#humidity").value)
                self.controller.pressure.set_values(pressure, temp)
                self.controller.humidity.set_values(humidity, temp)
        except ValueError:
            pass

    # ── Button handlers ───────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        mapping = {
            "joy-up":    _KEY_UP,
            "joy-down":  _KEY_DOWN,
            "joy-left":  _KEY_LEFT,
            "joy-right": _KEY_RIGHT,
            "joy-enter": _KEY_ENTER,
        }
        btn_id = event.button.id
        if btn_id in mapping:
            self._send_joystick(mapping[btn_id])
        elif btn_id == "btn-emu":
            self.action_use_emulator()
        elif btn_id == "btn-rec":
            self.action_open_recording()

    # ── Joystick ──────────────────────────────────────────────────────────────

    def _send_joystick(self, key_code):
        if not hasattr(self, "controller"):
            return
        self.controller.stick.send(_make_joystick_event(key_code, 1))  # press
        self.controller.stick.send(_make_joystick_event(key_code, 0))  # release

    def action_joy_up(self):    self._send_joystick(_KEY_UP)
    def action_joy_down(self):  self._send_joystick(_KEY_DOWN)
    def action_joy_left(self):  self._send_joystick(_KEY_LEFT)
    def action_joy_right(self): self._send_joystick(_KEY_RIGHT)
    def action_joy_enter(self): self._send_joystick(_KEY_ENTER)

    # ── Source switching ──────────────────────────────────────────────────────

    def action_use_emulator(self):
        self._activate_emulator()

    def action_open_recording(self):
        self.push_screen(RecordingPathScreen(), self._on_recording_path)

    def action_replay_recording(self):
        self.push_screen(RecordingPathScreen(), self._on_replay_path)

    def action_toggle_recording(self):
        if self._recorder and self._recorder.running:
            self._stop_recording()
        else:
            self.push_screen(RecordingPathScreen(title="Save recording"),
                             self._on_record_path)

    def _on_record_path(self, path):
        if not path:
            return
        if self._player and self._player.running:
            self._set_status("[red]Stop replay before recording[/red]")
            return
        self._recorder = Recorder(path)
        self._recorder.start()
        self._set_status("[red]● REC  0 records[/red]")
        self._rec_timer = self.set_interval(0.5, self._poll_recording)

    def _stop_recording(self):
        if self._recorder:
            self._recorder.stop()
        if self._rec_timer:
            self._rec_timer.stop()
            self._rec_timer = None
        self._set_status("[green]Recording saved[/green]")

    def _poll_recording(self):
        if self._recorder is None:
            return
        n = self._recorder.record_count
        if self._recorder.running:
            self._set_status(f"[red]● REC  {n} records[/red]")
        else:
            if self._rec_timer:
                self._rec_timer.stop()
                self._rec_timer = None
            self._set_status("[green]Recording saved[/green]")

    def _on_replay_path(self, path):
        if not path:
            return
        if self._player and self._player.running:
            self._player.stop()
        self._player = Player(
            self.controller.imu,
            self.controller.pressure,
            self.controller.humidity,
        )
        try:
            self._player.play(path)
        except (ValueError, OSError) as e:
            self._set_status(f"[red]Replay error: {e}[/red]")
            return
        if self._player.total == 0:
            self._set_status("[yellow]Recording has no data[/yellow]")
            return
        self._set_status("[cyan]Playing… 0%[/cyan]")
        self._playback_timer = self.set_interval(0.2, self._poll_playback)

    def _poll_playback(self):
        if self._player is None:
            return
        pct = int(self._player.progress * 100)
        if self._player.running:
            self._set_status(f"[cyan]Playing… {pct}%[/cyan]")
        else:
            if self._playback_timer:
                self._playback_timer.stop()
                self._playback_timer = None
            self._set_status("[green]Replay finished[/green]")

    def _on_recording_path(self, path):
        if not path:
            return
        try:
            records = _parse_recording(path)
            self.query_one(SensorReadings).set_recording(
                records, label=os.path.basename(path))
            self._set_status(
                f"[yellow]Recording:[/yellow] {os.path.basename(path)}")
        except (ValueError, OSError) as e:
            self._set_status(f"[red]Error: {e}[/red]")


def main():
    app = SenseEmuTUI()
    app.run()


if __name__ == "__main__":
    main()
