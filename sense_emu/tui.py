from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical
from textual.widgets import Header, Footer, Static, Input, Label
from textual.reactive import reactive

from .core import EmulatorController
from .screen import screen_filename
import io

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
        data = self.screen_file.read(192) # 64 pixels * 3 bytes (RGB)
        if len(data) == 192:
            lines = []
            for y in range(8):
                line = ""
                for x in range(8):
                    offset = (y * 8 + x) * 3
                    r, g, b = data[offset], data[offset+1], data[offset+2]
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
