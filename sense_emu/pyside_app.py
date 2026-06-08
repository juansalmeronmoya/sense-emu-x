import sys
import io
import math
import os
from time import monotonic
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QSlider, QLabel, QGridLayout,
                               QPushButton, QScrollArea, QGroupBox, QSplitter,
                               QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor
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
    ('Acelerómetro', 'G',
     [('ax', '#e74c3c', 'X'), ('ay', '#2ecc71', 'Y'), ('az', '#3498db', 'Z')]),
    ('Giroscopio',   'rad/s',
     [('gx', '#e74c3c', 'X'), ('gy', '#2ecc71', 'Y'), ('gz', '#3498db', 'Z')]),
    ('Brújula',      'µT',
     [('cx', '#e74c3c', 'X'), ('cy', '#2ecc71', 'Y'), ('cz', '#3498db', 'Z')]),
    ('Orientación',  '°',
     [('ox', '#e74c3c', 'Roll'), ('oy', '#2ecc71', 'Pitch'), ('oz', '#3498db', 'Yaw')]),
    ('Presión',      'mbar',
     [('pressure', '#9b59b6', 'P')]),
    ('Temperatura',  '°C',
     [('ptemp', '#e74c3c', 'Pres'), ('htemp', '#2ecc71', 'Hum')]),
    ('Humedad',      '%RH',
     [('humidity', '#3498db', 'H')]),
]


# ── LED Matrix ────────────────────────────────────────────────────────────────

class LEDMatrixWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 320)
        self.matrix_data = bytearray(192)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_matrix)
        self.timer.start(100)

        try:
            self.screen_file = io.open(screen_filename(), 'rb')
        except Exception:
            self.screen_file = None

    def update_matrix(self):
        if not self.screen_file:
            try:
                self.screen_file = io.open(screen_filename(), 'rb')
            except Exception:
                return

        self.screen_file.seek(0)
        data = self.screen_file.read(192)
        if len(data) == 192:
            self.matrix_data = data
            self.update()

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

        self._status_label = QLabel('Fuente: -')
        root.addWidget(self._status_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        charts_widget = QWidget()
        charts_layout = QHBoxLayout(charts_widget)
        charts_layout.setSpacing(4)
        charts_layout.setContentsMargins(2, 2, 2, 2)

        for i, (title, y_label, series_defs) in enumerate(_CHART_GROUPS):
            chart = QChart()
            chart.setTitle(title)
            chart.legend().setVisible(len(series_defs) > 1)

            x_axis = QValueAxis()
            x_axis.setTitleText('t (s)')
            x_axis.setRange(0, 60)
            chart.addAxis(x_axis, Qt.AlignBottom)

            y_axis = QValueAxis()
            y_axis.setTitleText(y_label)
            y_axis.setRange(-1, 1)
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

            view = QChartView(chart)
            view.setMinimumWidth(200)
            view.setMinimumHeight(160)
            charts_layout.addWidget(view)

        scroll.setWidget(charts_widget)
        root.addWidget(scroll)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_live(self, hat, label='Emulador'):
        self._timer.stop()
        self._hat = hat
        self.clear()
        self._t0 = monotonic()
        self._status_label.setText(f'Fuente: {label}')
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
        self._status_label.setText(f'Grabación: {os.path.basename(path)}')

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
        self.matrix = LEDMatrixWidget()
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
        source_group = QGroupBox("Fuente de telemetría")
        source_layout = QHBoxLayout(source_group)
        self._btn_emu = QPushButton("Emulador")
        self._btn_hat = QPushButton("Sense HAT real")
        self._btn_rec = QPushButton("Abrir grabación...")
        source_layout.addWidget(self._btn_emu)
        source_layout.addWidget(self._btn_hat)
        source_layout.addWidget(self._btn_rec)
        try:
            import sense_hat as _sh
            _sh.SenseHat()
        except Exception:
            self._btn_hat.setEnabled(False)
            self._btn_hat.setToolTip("Sense HAT no detectada")
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

        # Start live from emulator by default
        self._use_emulator()

    # ── Source actions ────────────────────────────────────────────────────────

    def _use_emulator(self):
        from sense_emu.sense_hat import SenseHat
        self.telemetry.set_live(SenseHat(), label='Emulador')

    def _use_real_hat(self):
        try:
            import sense_hat as sh
            self.telemetry.set_live(sh.SenseHat(), label='Sense HAT real')
        except (ImportError, OSError) as e:
            QMessageBox.critical(self, 'Error',
                                 f'No se pudo conectar a la Sense HAT: {e}')

    def _open_recording(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Abrir grabación', '',
            'Grabaciones (*.bin);;Todos los ficheros (*)')
        if path:
            try:
                self.telemetry.set_recording(path)
            except ValueError as e:
                QMessageBox.critical(self, 'Error al abrir grabación', str(e))

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
