import sys
import io
import math
import os
from time import monotonic
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QSlider, QLabel, QGridLayout,
                               QPushButton, QScrollArea, QGroupBox, QSplitter,
                               QFileDialog, QMessageBox, QDialog, QFormLayout,
                               QSpinBox, QDialogButtonBox, QSizePolicy,
                               QDoubleSpinBox, QProgressBar)
from PySide6.QtCore import Qt, QTimer, QMargins, QSize, QSettings
from PySide6.QtGui import QPainter, QColor, QAction, QKeySequence
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

from .core import EmulatorController
from .screen import screen_filename
from .stick import SenseStick, STICK_KEYS, make_stick_event
from .recfile import parse_recording
from .playback import Player
from .recorder import Recorder

_parse_recording = parse_recording


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
    def __init__(self, screen_client=None, cell_size=40):
        super().__init__()
        self._cell_size = cell_size
        self._update_size()
        self.matrix_data = bytearray(192)
        self._screen_client = screen_client

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_matrix)
        self.timer.start(100)

    def _update_size(self):
        side = self._cell_size * 8
        self.setMinimumSize(side, side)
        self.setMaximumSize(side, side)

    def set_cell_size(self, cell_size):
        self._cell_size = max(10, int(cell_size))
        self._update_size()
        self.updateGeometry()
        self.update()

    def cell_size(self):
        return self._cell_size

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return width

    def sizeHint(self):
        side = self._cell_size * 8
        return QSize(side, side)

    def update_matrix(self):
        if self._screen_client is None:
            return
        try:
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
    _poll_interval_ms = 200
    _time_window_s = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hat = None
        self._t0 = 0.0
        self._series = {}
        self._x_axes = []
        self._y_axes = []
        self._chart_keys = []
        self._key_to_chart = {}

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
            x_axis.setRange(0, self._time_window_s)
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

    def apply_settings(self, settings):
        self._max_samples = settings.get('max_samples', self._max_samples)
        self._poll_interval_ms = settings.get('poll_interval_ms', self._poll_interval_ms)
        self._time_window_s = settings.get('time_window_s', self._time_window_s)
        if self._timer.isActive():
            self._timer.setInterval(self._poll_interval_ms)

    def set_live(self, hat, label='Emulator'):
        self._timer.stop()
        self._hat = hat
        self.clear()
        self._t0 = monotonic()
        self._status_label.setText(f'Source: {label}')
        self._timer.start(self._poll_interval_ms)

    def set_recording(self, path):
        self._timer.stop()
        self._hat = None
        records = _parse_recording(path)
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
            x_axis.setRange(0, self._time_window_s)
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

            x_min = max(0.0, t - self._time_window_s)
            x_max = max(x_min + self._time_window_s, t)
            for x_axis in self._x_axes:
                x_axis.setRange(x_min, x_max)
        except Exception:
            pass

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


# ── Preferences dialog ────────────────────────────────────────────────────────

class PreferencesDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(360)

        if settings is None:
            settings = {}
        self._settings = dict(settings)

        layout = QVBoxLayout(self)

        # ── Charts section ────────────────────────────────────────────────────
        charts_group = QGroupBox("Charts")
        charts_form = QFormLayout(charts_group)

        self._poll_interval = QSpinBox()
        self._poll_interval.setRange(50, 5000)
        self._poll_interval.setSuffix(" ms")
        self._poll_interval.setValue(settings.get('poll_interval_ms', 200))
        charts_form.addRow("Update interval:", self._poll_interval)

        self._max_samples = QSpinBox()
        self._max_samples.setRange(10, 10000)
        self._max_samples.setValue(settings.get('max_samples', 300))
        charts_form.addRow("Max samples:", self._max_samples)

        self._time_window = QSpinBox()
        self._time_window.setRange(5, 600)
        self._time_window.setSuffix(" s")
        self._time_window.setValue(settings.get('time_window_s', 60))
        charts_form.addRow("Time window:", self._time_window)

        layout.addWidget(charts_group)

        # ── LED Matrix section ────────────────────────────────────────────────
        matrix_group = QGroupBox("LED Matrix")
        matrix_form = QFormLayout(matrix_group)

        self._cell_size = QSpinBox()
        self._cell_size.setRange(10, 80)
        self._cell_size.setSuffix(" px/cell")
        self._cell_size.setValue(settings.get('cell_size', 40))
        matrix_form.addRow("Cell size:", self._cell_size)

        layout.addWidget(matrix_group)

        # ── Emulator section ──────────────────────────────────────────────────
        emu_group = QGroupBox("Emulator")
        emu_form = QFormLayout(emu_group)

        self._led_refresh = QSpinBox()
        self._led_refresh.setRange(50, 2000)
        self._led_refresh.setSuffix(" ms")
        self._led_refresh.setValue(settings.get('led_refresh_ms', 100))
        emu_form.addRow("LED refresh interval:", self._led_refresh)

        layout.addWidget(emu_group)

        # ── Buttons ───────────────────────────────────────────────────────────
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        return {
            'poll_interval_ms': self._poll_interval.value(),
            'max_samples': self._max_samples.value(),
            'time_window_s': self._time_window.value(),
            'cell_size': self._cell_size.value(),
            'led_refresh_ms': self._led_refresh.value(),
        }


# ── Main window ───────────────────────────────────────────────────────────────

class SenseEmuDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sense HAT Emulator")
        self.setGeometry(100, 100, 1200, 800)
        self.controller = EmulatorController()

        self._qsettings = QSettings(QSettings.IniFormat, QSettings.UserScope,
                                    'sense-emu', 'sense-emu-gui')
        self._settings = {
            'poll_interval_ms': self._qsettings.value('poll_interval_ms', 200, type=int),
            'max_samples':      self._qsettings.value('max_samples', 300, type=int),
            'time_window_s':    self._qsettings.value('time_window_s', 60, type=int),
            'cell_size':        self._qsettings.value('cell_size', 40, type=int),
            'led_refresh_ms':   self._qsettings.value('led_refresh_ms', 100, type=int),
        }

        # ── Top section ───────────────────────────────────────────────────────
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setSpacing(8)

        # Left: LED Matrix in a GroupBox
        matrix_group = QGroupBox("LED Matrix (8×8)")
        matrix_vbox = QVBoxLayout(matrix_group)
        matrix_vbox.setAlignment(Qt.AlignHCenter)

        self.matrix = LEDMatrixWidget(
            self.controller.screen,
            cell_size=self._settings['cell_size'],
        )
        self.matrix.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        matrix_vbox.addWidget(self.matrix, 0, Qt.AlignHCenter)

        # Cell size control below the matrix
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Size:"))
        self._matrix_size_spin = QSpinBox()
        self._matrix_size_spin.setRange(10, 80)
        self._matrix_size_spin.setSuffix(" px")
        self._matrix_size_spin.setValue(self._settings['cell_size'])
        self._matrix_size_spin.valueChanged.connect(self._on_matrix_size_changed)
        size_row.addWidget(self._matrix_size_spin)
        size_row.addStretch()
        matrix_vbox.addLayout(size_row)

        top_layout.addWidget(matrix_group, 0)

        # Right: scrollable controls
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setSpacing(8)

        self.sliders = {}

        def create_slider_row(layout, name, min_val, max_val, default):
            row = QHBoxLayout()
            lbl = QLabel(f"{name}:")
            lbl.setFixedWidth(90)
            val_lbl = QLabel(str(default))
            val_lbl.setFixedWidth(40)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default)

            def on_change(val):
                val_lbl.setText(str(val))
                self.update_sensors()

            slider.valueChanged.connect(on_change)
            self.sliders[name] = slider
            row.addWidget(lbl)
            row.addWidget(slider)
            row.addWidget(val_lbl)
            layout.addLayout(row)

        # IMU group
        imu_group = QGroupBox("IMU (Orientation)")
        imu_layout = QVBoxLayout(imu_group)
        create_slider_row(imu_layout, "Pitch", -180, 180, 0)
        create_slider_row(imu_layout, "Roll", -180, 180, 0)
        create_slider_row(imu_layout, "Yaw", 0, 360, 0)
        controls_layout.addWidget(imu_group)

        # Environmental sensors + Joystick on the same row
        env_joy_row = QHBoxLayout()
        env_joy_row.setSpacing(8)

        env_group = QGroupBox("Environmental Sensors")
        env_layout = QVBoxLayout(env_group)
        create_slider_row(env_layout, "Temperature", -40, 120, 20)
        create_slider_row(env_layout, "Pressure", 260, 1260, 1013)
        create_slider_row(env_layout, "Humidity", 0, 100, 45)
        env_joy_row.addWidget(env_group, 2)

        joy_group = QGroupBox("Joystick")
        joy_layout = QGridLayout(joy_group)
        joy_layout.setSpacing(4)
        up_btn    = QPushButton("↑")
        down_btn  = QPushButton("↓")
        left_btn  = QPushButton("←")
        right_btn = QPushButton("→")
        mid_btn   = QPushButton("OK")
        for btn in (up_btn, down_btn, left_btn, right_btn, mid_btn):
            btn.setFixedSize(42, 32)
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
        env_joy_row.addWidget(joy_group, 1)

        controls_layout.addLayout(env_joy_row)

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

        controls_layout.addStretch()

        scroll.setWidget(controls_container)
        top_layout.addWidget(scroll, 1)

        # ── Bottom section: TelemetryPanel ────────────────────────────────────
        self.telemetry = TelemetryPanel()

        # ── Splitter ──────────────────────────────────────────────────────────
        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.addWidget(top_widget)
        self._splitter.addWidget(self.telemetry)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([420, 330])

        # ── Playback status bar ───────────────────────────────────────────────
        self._playback_bar = QWidget()
        pb_layout = QHBoxLayout(self._playback_bar)
        pb_layout.setContentsMargins(4, 2, 4, 2)
        self._playback_progress = QProgressBar()
        self._playback_progress.setRange(0, 100)
        self._playback_progress.setValue(0)
        self._playback_stop_btn = QPushButton("Stop")
        self._playback_stop_btn.clicked.connect(self._stop_playback)
        self._playback_label = QLabel("Playing recording…")
        pb_layout.addWidget(self._playback_label)
        pb_layout.addWidget(self._playback_progress, 1)
        pb_layout.addWidget(self._playback_stop_btn)
        self._playback_bar.setVisible(False)

        self._player = None
        self._playback_poll = QTimer(self)
        self._playback_poll.setInterval(200)
        self._playback_poll.timeout.connect(self._poll_playback)

        # ── Recording status bar ──────────────────────────────────────────────
        self._rec_bar = QWidget()
        rec_layout = QHBoxLayout(self._rec_bar)
        rec_layout.setContentsMargins(4, 2, 4, 2)
        self._rec_label = QLabel("● REC  0 records")
        self._rec_label.setStyleSheet("color: red; font-weight: bold;")
        self._rec_stop_btn = QPushButton("Stop recording")
        self._rec_stop_btn.clicked.connect(self._stop_recording)
        rec_layout.addWidget(self._rec_label, 1)
        rec_layout.addWidget(self._rec_stop_btn)
        self._rec_bar.setVisible(False)
        self._recorder = None
        self._rec_poll = QTimer(self)
        self._rec_poll.setInterval(200)
        self._rec_poll.timeout.connect(self._poll_recording)

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(self._splitter)
        main_layout.addWidget(self._playback_bar)
        main_layout.addWidget(self._rec_bar)
        self.setCentralWidget(main_widget)

        geom = self._qsettings.value('geometry')
        if geom is not None:
            self.restoreGeometry(geom)
        splitter_state = self._qsettings.value('splitter_state')
        if splitter_state is not None:
            self._splitter.restoreState(splitter_state)

        self._build_menu()

        # Start live from emulator by default
        self._use_emulator()

    # ── Menu ─────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")

        act_open = QAction("&View trace in charts…", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.setStatusTip("Load a recording into the telemetry charts")
        act_open.triggered.connect(self._open_recording)
        file_menu.addAction(act_open)

        act_replay = QAction("&Replay recording…", self)
        act_replay.setShortcut(QKeySequence("Ctrl+R"))
        act_replay.setStatusTip("Replay a recording into the emulator")
        act_replay.triggered.connect(self._start_playback)
        file_menu.addAction(act_replay)

        self._act_record = QAction("&Start recording…", self)
        self._act_record.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self._act_record.setStatusTip("Record emulator output to a file")
        self._act_record.triggered.connect(self._toggle_recording)
        file_menu.addAction(self._act_record)

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

        # Settings
        settings_menu = mb.addMenu("&Settings")
        act_prefs = QAction("&Preferences…", self)
        act_prefs.setShortcut(QKeySequence("Ctrl+,"))
        act_prefs.triggered.connect(self._open_preferences)
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

    def _save_settings(self):
        for key, val in self._settings.items():
            self._qsettings.setValue(key, val)
        self._qsettings.setValue('geometry', self.saveGeometry())
        self._qsettings.setValue('splitter_state', self._splitter.saveState())
        self._qsettings.sync()

    def _open_preferences(self):
        dlg = PreferencesDialog(self, settings=self._settings)
        if dlg.exec() == QDialog.Accepted:
            new_settings = dlg.get_settings()
            self._settings.update(new_settings)
            self._apply_settings()
            self._save_settings()

    def _apply_settings(self):
        self.telemetry.apply_settings(self._settings)
        cell_size = self._settings.get('cell_size', 40)
        self.matrix.set_cell_size(cell_size)
        self._matrix_size_spin.blockSignals(True)
        self._matrix_size_spin.setValue(cell_size)
        self._matrix_size_spin.blockSignals(False)
        led_refresh = self._settings.get('led_refresh_ms', 100)
        self.matrix.timer.setInterval(led_refresh)

    def _on_matrix_size_changed(self, value):
        self._settings['cell_size'] = value
        self.matrix.set_cell_size(value)
        self._qsettings.setValue('cell_size', value)
        self._qsettings.sync()

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

    # ── Playback ──────────────────────────────────────────────────────────────

    def _start_playback(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Replay recording', '',
            'Recordings (*.bin);;All files (*)')
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
            QMessageBox.critical(self, 'Error replaying recording', str(e))
            return
        if self._player.total == 0:
            QMessageBox.information(self, 'Replay', 'Recording contains no data.')
            return
        self._playback_bar.setVisible(True)
        self._playback_poll.start()

    def _stop_playback(self):
        if self._player:
            self._player.stop()
        self._playback_poll.stop()
        self._playback_bar.setVisible(False)

    def _poll_playback(self):
        if self._player is None:
            return
        pct = int(self._player.progress * 100)
        self._playback_progress.setValue(pct)
        if not self._player.running:
            self._playback_poll.stop()
            self._playback_bar.setVisible(False)

    # ── Recording ─────────────────────────────────────────────────────────────

    def _toggle_recording(self):
        if self._recorder and self._recorder.running:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if self._player and self._player.running:
            QMessageBox.warning(self, 'Cannot record',
                                'Stop the active replay before recording.')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save recording', '',
            'Recordings (*.bin);;All files (*)')
        if not path:
            return
        self._recorder = Recorder(path)
        self._recorder.start()
        self._rec_bar.setVisible(True)
        self._rec_poll.start()
        self._act_record.setText("&Stop recording")

    def _stop_recording(self):
        if self._recorder:
            self._recorder.stop()
        self._rec_poll.stop()
        self._rec_bar.setVisible(False)
        self._act_record.setText("&Start recording…")

    def _poll_recording(self):
        if self._recorder is None:
            return
        n = self._recorder.record_count
        self._rec_label.setText(f"● REC  {n} records")
        if not self._recorder.running:
            self._rec_poll.stop()
            self._rec_bar.setVisible(False)
            self._act_record.setText("&Start recording…")

    # ── Sensor control ────────────────────────────────────────────────────────

    def _on_stick_press(self, direction):
        key = STICK_KEYS[direction.lower()]
        self.controller.stick.send(
            make_stick_event(key, SenseStick.STATE_PRESS))
        self.controller.stick.send(
            make_stick_event(key, SenseStick.STATE_RELEASE))

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

    def keyPressEvent(self, event):
        _arrow_map = {
            Qt.Key_Up:     "UP",
            Qt.Key_Down:   "DOWN",
            Qt.Key_Left:   "LEFT",
            Qt.Key_Right:  "RIGHT",
            Qt.Key_Return: "MIDDLE",
            Qt.Key_Enter:  "MIDDLE",
        }
        direction = _arrow_map.get(event.key())
        if direction is not None:
            self._on_stick_press(direction)
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self._save_settings()
        if self._player and self._player.running:
            self._player.stop()
        if self._recorder and self._recorder.running:
            self._recorder.stop()
        self.telemetry._timer.stop()
        self.controller.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    try:
        window = SenseEmuDesktop()
    except RuntimeError as e:
        QMessageBox.warning(
            None, 'Sense HAT Emulator — Already running',
            'Another instance of the Sense HAT emulator is already running.\n\n'
            'Please close it before starting a new one.')
        sys.exit(1)
    except Exception:
        import traceback
        QMessageBox.critical(
            None, 'Sense HAT Emulator — Error',
            f'Could not start the emulator:\n\n{traceback.format_exc()}')
        sys.exit(1)
    else:
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
