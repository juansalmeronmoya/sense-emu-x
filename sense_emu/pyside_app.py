import sys
import io
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QSlider, QLabel, QGridLayout)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor

from .core import EmulatorController
from .screen import screen_filename

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
        except:
            self.screen_file = None

    def update_matrix(self):
        if not self.screen_file:
            try:
                self.screen_file = io.open(screen_filename(), 'rb')
            except:
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
                painter.fillRect(x * cell_w + 1, y * cell_h + 1, 
                               cell_w - 2, cell_h - 2, 
                               QColor(r, g, b))

class SenseEmuDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sense HAT Emulator")
        self.controller = EmulatorController()
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        # Left side: LED Matrix
        self.matrix = LEDMatrixWidget()
        layout.addWidget(self.matrix)
        
        # Right side: Controls
        controls_layout = QVBoxLayout()
        layout.addLayout(controls_layout)
        
        self.sliders = {}
        
        def create_slider(name, min_val, max_val, default):
            lbl = QLabel(f"{name}: {default}")
            controls_layout.addWidget(lbl)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(default)
            controls_layout.addWidget(slider)
            
            def on_change(val):
                lbl.setText(f"{name}: {val}")
                self.update_sensors()
                
            slider.valueChanged.connect(on_change)
            self.sliders[name] = slider
            
        create_slider("Yaw", 0, 360, 0)
        create_slider("Pitch", 0, 360, 0)
        create_slider("Roll", 0, 360, 0)
        create_slider("Pressure", 260, 1260, 1013)
        create_slider("Temperature", -40, 120, 20)
        create_slider("Humidity", 0, 100, 45)
        
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
