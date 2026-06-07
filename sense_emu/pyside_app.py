import sys
import io
import math
import struct
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QSlider, QLabel, QGridLayout,
                               QPushButton, QScrollArea, QGroupBox)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor

from .core import EmulatorController
from .screen import screen_filename, GAMMA_DEFAULT, GAMMA_LOW

class LEDMatrixWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 320)
        self.rgb_data = np.zeros((8, 8, 3), dtype=np.uint8)

        self.gamma_rgbled = (
            np.sqrt(np.sqrt(np.linspace(0.05, 1, 32))) * 255
        ).astype(np.uint8)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_matrix)
        self.timer.start(100)

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

        try:
            self.screen_file.seek(0)
            raw_data = self.screen_file.read(160)
            if len(raw_data) >= 128:
                screen_raw = np.frombuffer(raw_data[:128], dtype=np.uint16).reshape((8, 8))
                gamma_data = np.frombuffer(raw_data[128:160], dtype=np.uint8)

                rgb = np.empty((8, 8, 3), dtype=np.uint8)
                rgb[..., 0] = ((screen_raw & 0xF800) >> 11).astype(np.uint8)
                rgb[..., 1] = ((screen_raw & 0x07E0) >> 6).astype(np.uint8)
                rgb[..., 2] = (screen_raw & 0x001F).astype(np.uint8)

                rgb = np.take(gamma_data, rgb)
                rgb = np.take(self.gamma_rgbled, rgb)

                self.rgb_data = rgb
                self.update()
        except:
            pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)

        w, h = self.width(), self.height()
        cell_w, cell_h = w / 8, h / 8

        for y in range(8):
            for x in range(8):
                r, g, b = self.rgb_data[y, x]
                painter.fillRect(int(x * cell_w) + 1, int(y * cell_h) + 1,
                               int(cell_w) - 2, int(cell_h) - 2,
                               QColor(int(r), int(g), int(b)))

class SenseEmuDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sense HAT Emulator")
        self.setGeometry(100, 100, 1000, 600)
        self.controller = EmulatorController()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Left side: LED Matrix
        self.matrix = LEDMatrixWidget()
        layout.addWidget(self.matrix, 1)

        # Right side: Scrollable controls
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setSpacing(10)

        self.sliders = {}

        def create_slider(name, min_val, max_val, default):
            self.sliders[name] = {}
            lbl = QLabel(f"{name}: {default}")
            self.sliders[name]['label'] = lbl

            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default)
            self.sliders[name]['slider'] = slider

            def on_change(val):
                lbl.setText(f"{name}: {val}")
                self.update_sensors()

            slider.valueChanged.connect(on_change)

            # Add to layout
            controls_layout.addWidget(lbl)
            controls_layout.addWidget(slider)

        # IMU Section
        imu_group = QGroupBox("IMU (Orientation)")
        imu_layout = QVBoxLayout(imu_group)
        self.sliders = {}

        # Create sliders with proper function that captures imu_layout
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

        create_slider_in_group(imu_layout, "Pitch", -180, 180, 0)
        create_slider_in_group(imu_layout, "Roll", -180, 180, 0)
        create_slider_in_group(imu_layout, "Yaw", 0, 360, 0)
        controls_layout.addWidget(imu_group)

        # Environmental Sensors Section
        env_group = QGroupBox("Environmental Sensors")
        env_layout = QVBoxLayout(env_group)

        create_slider_in_group(env_layout, "Temperature", -40, 120, 20)
        create_slider_in_group(env_layout, "Pressure", 260, 1260, 1013)
        create_slider_in_group(env_layout, "Humidity", 0, 100, 45)
        controls_layout.addWidget(env_group)

        # Joystick Section
        joy_group = QGroupBox("Joystick")
        joy_layout = QGridLayout(joy_group)

        # D-pad layout
        #     UP
        # L  MID  R
        #    DOWN
        up_btn = QPushButton("↑ UP")
        down_btn = QPushButton("↓ DOWN")
        left_btn = QPushButton("← LEFT")
        right_btn = QPushButton("RIGHT →")
        middle_btn = QPushButton("ENTER")

        up_btn.clicked.connect(lambda: self._on_stick_press("UP"))
        down_btn.clicked.connect(lambda: self._on_stick_press("DOWN"))
        left_btn.clicked.connect(lambda: self._on_stick_press("LEFT"))
        right_btn.clicked.connect(lambda: self._on_stick_press("RIGHT"))
        middle_btn.clicked.connect(lambda: self._on_stick_press("MIDDLE"))

        joy_layout.addWidget(up_btn, 0, 1)
        joy_layout.addWidget(left_btn, 1, 0)
        joy_layout.addWidget(middle_btn, 1, 1)
        joy_layout.addWidget(right_btn, 1, 2)
        joy_layout.addWidget(down_btn, 2, 1)

        controls_layout.addWidget(joy_group)
        controls_layout.addStretch()

        scroll.setWidget(controls_container)
        layout.addWidget(scroll, 1)

    def _on_stick_press(self, direction):
        """Handle joystick button press (currently visual feedback only)."""
        # Note: Actual joystick event emission requires socket communication
        # This is reserved for future implementation
        print(f"Joystick {direction} pressed")

    def update_sensors(self):
        pitch = self.sliders["Pitch"].value()
        roll = self.sliders["Roll"].value()
        yaw = self.sliders["Yaw"].value()
        self.controller.imu.set_orientation((roll, pitch, yaw))

        temp = self.sliders["Temperature"].value()
        pressure = self.sliders["Pressure"].value()
        self.controller.pressure.set_values(pressure, temp)

        humidity = self.sliders["Humidity"].value()
        self.controller.humidity.set_values(humidity, temp)

    def closeEvent(self, event):
        self.controller.close()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    window = SenseEmuDesktop()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
