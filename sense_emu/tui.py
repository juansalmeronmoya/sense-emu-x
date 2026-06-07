from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical
from textual.widgets import Header, Footer, Static, Input, Label
from textual.reactive import reactive

import numpy as np

from .core import EmulatorController
from .screen import screen_filename
import io

# Total size of the screen frame-buffer file: 64 RGB565 pixels (2 bytes each)
# followed by a 32-entry gamma lookup table (1 byte each).
SCREEN_SIZE = 160

# Final gamma correction applied to the RGB LEDs. This mirrors
# ScreenClient._gamma_rgbled: the HAT's LEDs are far brighter than an LCD, and
# the non-zero starting point means LEDs that are off appear gray rather than
# black.
_GAMMA_RGBLED = (np.sqrt(np.sqrt(np.linspace(0.05, 1, 32))) * 255).astype(np.uint8)


class LEDMatrix(Static):
    def on_mount(self):
        self.set_interval(0.1, self.update_matrix)
        try:
            self.screen_file = io.open(screen_filename(), 'rb')
        except:
            self.screen_file = None

    def update_matrix(self):
        if not self.screen_file:
            try:
                self.screen_file = io.open(screen_filename(), 'rb')
            except:
                return

        self.screen_file.seek(0)
        data = self.screen_file.read(SCREEN_SIZE)
        if len(data) < SCREEN_SIZE:
            return

        # Decode the RGB565 pixels and per-user gamma table, then apply the
        # same conversion the GUI/ScreenClient use so colours match exactly.
        screen = np.frombuffer(data[:128], dtype=np.uint16).reshape((8, 8))
        gamma = np.frombuffer(data[128:160], dtype=np.uint8)

        rgb = np.empty((8, 8, 3), dtype=np.uint8)
        rgb[..., 0] = ((screen & 0xF800) >> 11).astype(np.uint8)
        rgb[..., 1] = ((screen & 0x07E0) >> 6).astype(np.uint8)
        rgb[..., 2] = (screen & 0x001F).astype(np.uint8)
        rgb = np.take(gamma, rgb)
        rgb = np.take(_GAMMA_RGBLED, rgb)

        lines = []
        for y in range(8):
            line = ""
            for x in range(8):
                r, g, b = (int(v) for v in rgb[y, x])
                line += f"[rgb({r},{g},{b})]██[/]"
            lines.append(line)
        self.update("\n".join(lines))

class SenseEmuTUI(App):
    CSS = """
    Grid {
        grid-size: 2;
        grid-columns: 1fr 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid():
            with Vertical():
                yield Label("LED Matrix")
                yield LEDMatrix()
            with Vertical():
                yield Label("Pitch")
                yield Input(value="0", id="pitch")
                yield Label("Roll")
                yield Input(value="0", id="roll")
                yield Label("Yaw")
                yield Input(value="0", id="yaw")
                yield Label("Pressure (millibars)")
                yield Input(value="1013", id="pressure")
                yield Label("Temperature (Celsius)")
                yield Input(value="20", id="temp")
                yield Label("Humidity (% rH)")
                yield Input(value="45", id="humidity")
        yield Footer()

    def on_mount(self):
        self.controller = EmulatorController()
        
    def on_unmount(self):
        self.controller.close()

    def on_input_changed(self, event: Input.Changed) -> None:
        if not hasattr(self, "controller"):
            return
            
        input_id = event.input.id
        try:
            val = float(event.value)
        except ValueError:
            return
        
        try:
            if input_id in ("pitch", "roll", "yaw"):
                pitch = float(self.query_one("#pitch").value)
                roll = float(self.query_one("#roll").value)
                yaw = float(self.query_one("#yaw").value)
                self.controller.imu.set_orientation((roll, pitch, yaw))
            elif input_id in ("pressure", "temp"):
                pressure = float(self.query_one("#pressure").value)
                temp = float(self.query_one("#temp").value)
                self.controller.pressure.set_values(pressure, temp)
            elif input_id in ("humidity", "temp"):
                humidity = float(self.query_one("#humidity").value)
                temp = float(self.query_one("#temp").value)
                self.controller.humidity.set_values(humidity, temp)
        except ValueError:
            pass

def main():
    app = SenseEmuTUI()
    app.run()
    
if __name__ == "__main__":
    main()
