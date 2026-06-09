import sys
import io
import math
import os
from time import monotonic
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QSlider, QLabel, QGridLayout,
                               QPushButton, QScrollArea, QGroupBox, QSplitter,
                               QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, QTimer, QMargins
from PySide6.QtGui import QPainter, QColor, QAction, QKeySequence
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

from .core import EmulatorController
from .screen import screen_filename
from .common import HEADER_REC, DATA_REC, DataRecord


# ── Recording parser ──────────────────────────────────────────────────────────

def _parse_recording(path):
    records = []
    with open(path, 'rb') as f:
        header_buf = f.read(HEADER_REC.size)
        if len(header_buf) < HEADER_REC.size:
            raise ValueError('Invalid recording file')
        magic, ver, _ = HEADER_REC.unpack(header_buf)
        if magic != b'SENSEHAT' or ver != 1:
            raise ValueError('Invalid recording file')
        while True:
            buf = f.read(DATA_REC.size)
            if not buf:
                break
            if len(buf) < DATA_REC.size:
                raise ValueError('Truncated record')
            records.append(DataRecord(*DATA_REC.unpack(buf)))
    return records


# ── Chart group definitions ───────────────────────────────────────────────────

_CHART_GROUPS = [
    ('Accelerometer', 'G',
     [('ax', '#e74c3c', 'X'), ('ay', '#2ecc71', 'Y'), ('az', '#3498db', 'Z')]),
    ('Gyroscope',     'rad/s',
     [('gx', '#e74c3c', 'X'), ('gy', '#2ecc71', 'Y'), ('gz', '#3498db', 'Z')]),
    ('Compass',       'µT',
     [('cx', '#e74c3c', 'X'), ('cy', '#2ecc71', 'Y'), ('cz', '#3498db', 'Z')]),
    ('Orientation',   '°',
     [('ox', '#e74c3c', 'Roll'), ('oy', '#2ecc71', 'Pitch'), ('oz', '#3498db', 'Yaw')]),
    ('Pressure',      'mbar',
     [('pressure', '#9b59b6', 'P')]),
    ('Temperature',   '°C',
     [('ptemp', '#e74c3c', 'Pres'), ('htemp', '#2ecc71', 'Hum')]),
    ('Humidity',      '%RH',
     [('humidity', '#3498db', 'H')]),
]


# ── LED Matrix ────────────────────────────────────────────────────────────────

class LEDMatrixWidget(QWidget):
    def __init__(self, screen_client=None):
        super().__init__()
        self.setMinimumSize(320, 320)
        self.matrix_data = bytearray(192)
        self._screen_client = screen_client

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_matrix)
        self.timer.start(100)

    def update_matrix(self):
        if self._screen_client is None:
            return
        try:
            # rgb_array returns (8, 8, 3) uint8 with gamma correction applied
            rgb = self._screen_client.rgb_array
            self.matrix_data = rgb.flatten().tobytes()
            self.update()
        except Exception:
            pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)

        w, h = self.width(), self.height()
        cell_w, cell_h = w / 8, h / 8

        for y in range(8):
            for x in range(8):
                offset = (y * 8 + x) * 3
                r, g, b = self.matrix_data[offset:offset+3]
                painter.fillRect(
                    x * cell_w + 1, y * cell_h + 1,
                    cell_w - 2, cell_h - 2,
                    QColor(r, g, b))


# ── Telemetry panel ───────────────────────────────────────────────────────────

class TelemetryPanel(QWidget):
    _max_samples = 300

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hat = None
        self._t0 = 0.0
        self._series = {}
        self._x_axes = []     # one QValueAxis per chart
        self._y_axes = []     # one QValueAxis per chart
        self._chart_keys = [] # list[list[str]] — series keys per chart
        self._key_to_chart = {}  # key → chart index

        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(2)

        self._status_label = QLabel('Source: -')
        root.addWidget(self._status_label)

        _COLS = 3

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        charts_widget = QWidget()
        charts_layout = QGridLayout(charts_widget)
        charts_layout.setSpacing(4)
        charts_layout.setContentsMargins(2, 2, 2, 2)

        for i, (title, y_label, series_defs) in enumerate(_CHART_GROUPS):
            chart = QChart()
            chart.legend().hide()
            chart.setMargins(QMargins(0, 0, 0, 0))
            chart.layout().setContentsMargins(0, 0, 0, 0)
            chart.setBackgroundRoundness(0)

            x_axis = QValueAxis()
            x_axis.setLabelsVisible(True)
            x_axis.setTitleVisible(False)
            x_axis.setRange(0, 60)
            x_axis.setTickCount(4)
            chart.addAxis(x_axis, Qt.AlignBottom)

            y_axis = QValueAxis()
            y_axis.setTitleText(y_label)
            y_axis.setRange(-1, 1)
            y_axis.setTickCount(3)
            chart.addAxis(y_axis, Qt.AlignLeft)

            self._x_axes.append(x_axis)
            self._y_axes.append(y_axis)
            keys = []

            for key, color, name in series_defs:
                series = QLineSeries()
                series.setName(name)
                pen = series.pen()
                pen.setColor(QColor(color))
                pen.setWidth(1)
                series.setPen(pen)
                chart.addSeries(series)
                series.attachAxis(x_axis)
                series.attachAxis(y_axis)
                self._series[key] = series
                self._key_to_chart[key] = i
                keys.append(key)

            self._chart_keys.append(keys)

            # Compact header: "Title (unit)  ■ X  ■ Y  ■ Z"
            legend_parts = '&nbsp;&nbsp;'.join(
                f'<span style="color:{c};">&#9632;</span>&nbsp;{n}'
                for _, c, n in series_defs
            )
            header_html = (
                f'<span style="font-weight:bold;">{title}</span>'
                f'&nbsp;<span style="color:#888;">({y_label})</span>'
                + (f'&nbsp;&nbsp;&nbsp;{legend_parts}' if legend_parts else '')
            )
            header = QLabel()
            header.setText(header_html)
            header.setContentsMargins(2, 1, 2, 0)

            view = QChartView(chart)
            view.setMinimumWidth(200)
            view.setMinimumHeight(150)

            container = QWidget()
            c_layout = QVBoxLayout(container)
            c_layout.setContentsMargins(0, 0, 0, 0)
            c_layout.setSpacing(0)
            c_layout.addWidget(header)
            c_layout.addWidget(view)

            charts_layout.addWidget(container, i // _COLS, i % _COLS)

        scroll.setWidget(charts_widget)
        root.addWidget(scroll)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_live(self, hat, label='Emulator'):
        self._timer.stop()
        self._hat = hat
        self.clear()
        self._t0 = monotonic()
        self._status_label.setText(f'Source: {label}')
        self._timer.start(200)

    def set_recording(self, path):
        self._timer.stop()
        self._hat = None
        records = _parse_recording(path)  # raises ValueError on bad file
        self.clear()
        if records:
            t0 = records[0].timestamp
            for rec in records:
                t = rec.timestamp - t0
                self._append('ax', t, rec.ax)
                self._append('ay', t, rec.ay)
                self._append('az', t, rec.az)
                self._append('gx', t, rec.gx)
                self._append('gy', t, rec.gy)
                self._append('gz', t, rec.gz)
                self._append('cx', t, rec.cx)
                self._append('cy', t, rec.cy)
                self._append('cz', t, rec.cz)
                self._append('ox', t, rec.ox)
                self._append('oy', t, rec.oy)
                self._append('oz', t, rec.oz)
                self._append('pressure', t, rec.pressure)
                self._append('ptemp', t, rec.ptemp)
                self._append('humidity', t, rec.humidity)
                self._append('htemp', t, rec.htemp)
            duration = records[-1].timestamp - records[0].timestamp
            for x_axis in self._x_axes:
                x_axis.setRange(0, max(duration, 0.1))
        self._status_label.setText(f'Recording: {os.path.basename(path)}')

    def clear(self):
        for series in self._series.values():
            series.clear()
        for x_axis in self._x_axes:
            x_axis.setRange(0, 60)
        for y_axis in self._y_axes:
            y_axis.setRange(-1, 1)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _poll(self):
        if self._hat is None:
            return
        t = monotonic() - self._t0
        try:
            accel = self._hat.get_accelerometer_raw()
            self._append('ax', t, accel.get('x', 0))
            self._append('ay', t, accel.get('y', 0))
            self._append('az', t, accel.get('z', 0))

            gyro = self._hat.get_gyroscope_raw()
            self._append('gx', t, gyro.get('x', 0))
            self._append('gy', t, gyro.get('y', 0))
            self._append('gz', t, gyro.get('z', 0))

            compass = self._hat.get_compass_raw()
            self._append('cx', t, compass.get('x', 0))
            self._append('cy', t, compass.get('y', 0))
            self._append('cz', t, compass.get('z', 0))

            orientation = self._hat.get_orientation()
            self._append('ox', t, orientation.get('roll', 0))
            self._append('oy', t, orientation.get('pitch', 0))
            self._append('oz', t, orientation.get('yaw', 0))

            self._append('pressure', t, self._hat.get_pressure())
            self._append('ptemp', t, self._hat.get_temperature_from_pressure())
            self._append('humidity', t, self._hat.get_humidity())
            self._append('htemp', t, self._hat.get_temperature_from_humidity())

            x_min = max(0.0, t - 60.0)
            x_max = max(x_min + 60.0, t)
            for x_axis in self._x_axes:
                x_axis.setRange(x_min, x_max)
        except Exception:
            pass  # transient read errors must not crash the timer loop

    def _append(self, key, t, val):
        series = self._series[key]
        series.append(t, val)
        if series.count() > self._max_samples:
            series.remove(0)
        self._rescale_y(self._key_to_chart[key])

    def _rescale_y(self, chart_idx):
        keys = self._chart_keys[chart_idx]
        all_ys = []
        for k in keys:
            all_ys.extend(p.y() for p in self._series[k].points())
        if not all_ys:
            return
        lo, hi = min(all_ys), max(all_ys)
        margin = max((hi - lo) * 0.1, 0.1)
        self._y_axes[chart_idx].setRange(lo - margin, hi + margin)


# ── Main window ───────────────────────────────────────────────────────────────

class SenseEmuDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sense HAT Emulator")
        self.setGeometry(100, 100, 1200, 750)
        self.controller = EmulatorController()

        # ── Top section ───────────────────────────────────────────────────────
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)

        # Left: LED Matrix
        self.matrix = LEDMatrixWidget(self.controller.screen)
        top_layout.addWidget(self.matrix, 1)

        # Right: scrollable controls
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setSpacing(10)

        self.sliders = {}

        def create_slider_in_group(layout, name, min_val, max_val, default):
            lbl = QLabel(f"{name}: {default}")
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default)

            def on_change(val):
                lbl.setText(f"{name}: {val}")
                self.update_sensors()

            slider.valueChanged.connect(on_change)
            self.sliders[name] = slider
            layout.addWidget(lbl)
            layout.addWidget(slider)

        # IMU
        imu_group = QGroupBox("IMU (Orientation)")
        imu_layout = QVBoxLayout(imu_group)
        create_slider_in_group(imu_layout, "Pitch", -180, 180, 0)
        create_slider_in_group(imu_layout, "Roll", -180, 180, 0)
        create_slider_in_group(imu_layout, "Yaw", 0, 360, 0)
        controls_layout.addWidget(imu_group)

        # Environmental Sensors
        env_group = QGroupBox("Environmental Sensors")
        env_layout = QVBoxLayout(env_group)
        create_slider_in_group(env_layout, "Temperature", -40, 120, 20)
        create_slider_in_group(env_layout, "Pressure", 260, 1260, 1013)
        create_slider_in_group(env_layout, "Humidity", 0, 100, 45)
        controls_layout.addWidget(env_group)

        # Telemetry source selector
        source_group = QGroupBox("Telemetry source")
        source_layout = QHBoxLayout(source_group)
        self._btn_emu = QPushButton("Emulator")
        self._btn_hat = QPushButton("Real Sense HAT")
        self._btn_rec = QPushButton("Open recording…")
        source_layout.addWidget(self._btn_emu)
        source_layout.addWidget(self._btn_hat)
        source_layout.addWidget(self._btn_rec)
        try:
            import sense_hat as _sh
            _sh.SenseHat()
        except Exception:
            self._btn_hat.setEnabled(False)
            self._btn_hat.setToolTip("Sense HAT not detected")
        self._btn_emu.clicked.connect(self._use_emulator)
        self._btn_hat.clicked.connect(self._use_real_hat)
        self._btn_rec.clicked.connect(self._open_recording)
        controls_layout.addWidget(source_group)

        # Joystick
        joy_group = QGroupBox("Joystick")
        joy_layout = QGridLayout(joy_group)
        up_btn    = QPushButton("↑ UP")
        down_btn  = QPushButton("↓ DOWN")
        left_btn  = QPushButton("← LEFT")
        right_btn = QPushButton("RIGHT →")
        mid_btn   = QPushButton("ENTER")
        up_btn.clicked.connect(lambda:    self._on_stick_press("UP"))
        down_btn.clicked.connect(lambda:  self._on_stick_press("DOWN"))
        left_btn.clicked.connect(lambda:  self._on_stick_press("LEFT"))
        right_btn.clicked.connect(lambda: self._on_stick_press("RIGHT"))
        mid_btn.clicked.connect(lambda:   self._on_stick_press("MIDDLE"))
        joy_layout.addWidget(up_btn,    0, 1)
        joy_layout.addWidget(left_btn,  1, 0)
        joy_layout.addWidget(mid_btn,   1, 1)
        joy_layout.addWidget(right_btn, 1, 2)
        joy_layout.addWidget(down_btn,  2, 1)
        controls_layout.addWidget(joy_group)
        controls_layout.addStretch()

        scroll.setWidget(controls_container)
        top_layout.addWidget(scroll, 1)

        # ── Bottom section: TelemetryPanel ────────────────────────────────────
        self.telemetry = TelemetryPanel()

        # ── Splitter ──────────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(self.telemetry)
        splitter.setSizes([420, 280])

        main_widget = QWidget()
        QVBoxLayout(main_widget).addWidget(splitter)
        self.setCentralWidget(main_widget)

        self._build_menu()

        # Start live from emulator by default
        self._use_emulator()

    # ── Menu ─────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")

        act_open = QAction("&Open trace…", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.setStatusTip("Open a recorded trace file (.bin)")
        act_open.triggered.connect(self._open_recording)
        file_menu.addAction(act_open)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # View
        view_menu = mb.addMenu("&View")

        self._act_telemetry = QAction("&Telemetry charts", self)
        self._act_telemetry.setCheckable(True)
        self._act_telemetry.setChecked(True)
        self._act_telemetry.setShortcut(QKeySequence("Ctrl+T"))
        self._act_telemetry.setStatusTip("Show or hide the telemetry charts panel")
        self._act_telemetry.toggled.connect(self._toggle_telemetry)
        view_menu.addAction(self._act_telemetry)

        # Settings (stub)
        settings_menu = mb.addMenu("&Settings")
        act_prefs = QAction("Preferences…", self)
        act_prefs.setEnabled(False)
        settings_menu.addAction(act_prefs)

        # Help
        help_menu = mb.addMenu("&Help")

        act_about = QAction("&About…", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _toggle_telemetry(self, visible):
        self.telemetry.setVisible(visible)

    def _show_about(self):
        from PySide6 import __version__ as pyside_ver
        QMessageBox.about(
            self,
            'About Sense HAT Emulator',
            '<b>Sense HAT Emulator</b><br><br>'
            'Cross-platform emulator for the Raspberry Pi Sense HAT.<br>'
            'Compatible with the official <i>sense-hat</i> API.<br><br>'
            f'<small>PySide6 {pyside_ver} &nbsp;·&nbsp; '
            f'Python {sys.version.split()[0]}</small>',
        )

    # ── Source actions ────────────────────────────────────────────────────────

    def _use_emulator(self):
        from sense_emu.sense_hat import SenseHat
        self.telemetry.set_live(SenseHat(), label='Emulator')

    def _use_real_hat(self):
        try:
            import sense_hat as sh
            self.telemetry.set_live(sh.SenseHat(), label='Real Sense HAT')
        except (ImportError, OSError) as e:
            QMessageBox.critical(self, 'Error',
                                 f'Could not connect to Sense HAT: {e}')

    def _open_recording(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open recording', '',
            'Recordings (*.bin);;All files (*)')
        if path:
            try:
                self.telemetry.set_recording(path)
            except ValueError as e:
                QMessageBox.critical(self, 'Error opening recording', str(e))

    # ── Sensor control ────────────────────────────────────────────────────────

    def _on_stick_press(self, direction):
        print(f"Joystick {direction} pressed")

    def update_sensors(self):
        pitch    = self.sliders["Pitch"].value()
        roll     = self.sliders["Roll"].value()
        yaw      = self.sliders["Yaw"].value()
        self.controller.imu.set_orientation((roll, pitch, yaw))

        temp     = self.sliders["Temperature"].value()
        pressure = self.sliders["Pressure"].value()
        self.controller.pressure.set_values(pressure, temp)

        humidity = self.sliders["Humidity"].value()
        self.controller.humidity.set_values(humidity, temp)

    def closeEvent(self, event):
        self.telemetry._timer.stop()
        self.controller.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    try:
        window = SenseEmuDesktop()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        QMessageBox.critical(
            None, 'Sense HAT Emulator — Error',
            f'Could not start the emulator:\n\n{traceback.format_exc()}')
        sys.exit(1)


if __name__ == "__main__":
    main()
