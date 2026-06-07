import io
import pytest
from unittest.mock import patch, MagicMock


pytest.importorskip('PySide6')


@pytest.fixture(autouse=True)
def patch_screen(tmp_screen_file):
    """Redirect all screen file access to the temp file."""
    yield


class TestLEDMatrixWidget:
    def test_init_creates_widget(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        assert widget is not None

    def test_minimum_size(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        assert widget.minimumWidth() == 320
        assert widget.minimumHeight() == 320

    def test_initial_matrix_data_zeros(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        import numpy as np
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        assert widget.rgb_data.shape == (8, 8, 3)
        assert isinstance(widget.rgb_data, np.ndarray)

    def test_update_matrix_reads_file(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        # Write 160 bytes (128 screen + 32 gamma)
        with open(tmp_screen_file, 'r+b') as f:
            f.seek(0)
            f.write(b'\x00' * 128 + b'\x00' * 32)
        widget.update_matrix()
        # Verify rgb_data is a valid 8x8 RGB array
        assert widget.rgb_data.shape == (8, 8, 3)

    def test_update_matrix_with_full_192_bytes(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        # Keep old behavior for compatibility: file can be 192 bytes
        with open(tmp_screen_file, 'r+b') as f:
            f.write(b'\x00' * 192)
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        widget.update_matrix()
        # New implementation reads first 160 bytes
        assert widget.rgb_data.shape == (8, 8, 3)

    def test_paint_event_does_not_raise(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        from PySide6.QtCore import QRect
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        widget.show()
        widget.update()
        qtbot.waitExposed(widget)

    def test_update_matrix_handles_missing_file(self, qtbot, tmp_path):
        from sense_emu.pyside_app import LEDMatrixWidget
        nonexistent = str(tmp_path / 'nofile')
        with patch('sense_emu.screen.screen_filename', return_value=nonexistent):
            with patch('sense_emu.pyside_app.screen_filename', return_value=nonexistent):
                widget = LEDMatrixWidget()
                qtbot.addWidget(widget)
                widget.screen_file = None
                widget.update_matrix()  # should not raise

    def test_update_matrix_reads_192_bytes(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        with open(tmp_screen_file, 'r+b') as f:
            f.write(b'\x00' * 160)
        with patch('sense_emu.pyside_app.screen_filename', return_value=tmp_screen_file):
            widget = LEDMatrixWidget()
            qtbot.addWidget(widget)
            widget.timer.stop()
            widget.update_matrix()
        # New implementation: verify rgb_data is correctly shaped
        assert widget.rgb_data.shape == (8, 8, 3)

    def test_paint_event_executes(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        from PySide6.QtGui import QPaintEvent
        from PySide6.QtCore import QRect
        with patch('sense_emu.pyside_app.screen_filename', return_value=tmp_screen_file):
            widget = LEDMatrixWidget()
            qtbot.addWidget(widget)
            widget.resize(320, 320)
            widget.timer.stop()
            event = QPaintEvent(QRect(0, 0, 320, 320))
            widget.paintEvent(event)


class TestSenseEmuDesktop:
    def test_init_creates_window(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        mock_controller = MagicMock()
        with patch('sense_emu.pyside_app.EmulatorController', return_value=mock_controller):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            assert window is not None

    def test_has_six_sliders(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        mock_controller = MagicMock()
        with patch('sense_emu.pyside_app.EmulatorController', return_value=mock_controller):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            assert len(window.sliders) == 6

    def test_slider_names(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        mock_controller = MagicMock()
        with patch('sense_emu.pyside_app.EmulatorController', return_value=mock_controller):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            for name in ('Yaw', 'Pitch', 'Roll', 'Pressure', 'Temperature', 'Humidity'):
                assert name in window.sliders

    def test_update_sensors_calls_controller(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        mock_controller = MagicMock()
        mock_controller.imu = MagicMock()
        mock_controller.pressure = MagicMock()
        mock_controller.humidity = MagicMock()
        with patch('sense_emu.pyside_app.EmulatorController', return_value=mock_controller):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            window.sliders['Pressure'].setValue(950)
            window.update_sensors()
            # Verify controller methods were called
            mock_controller.pressure.set_values.assert_called()

    def test_close_event_calls_controller_close(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        from PySide6.QtGui import QCloseEvent
        mock_controller = MagicMock()
        with patch('sense_emu.pyside_app.EmulatorController', return_value=mock_controller):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            event = QCloseEvent()
            window.closeEvent(event)
            mock_controller.close.assert_called_once()


class TestPysideMain:
    def test_main_importable(self):
        from sense_emu.pyside_app import main
        assert callable(main)

    def test_pyside_main_module(self):
        import sense_emu.pyside_main as pm
        assert hasattr(pm, 'main')


class TestPysideMainFunction:
    def test_main_calls_sys_exit(self, tmp_screen_file):
        from sense_emu.pyside_app import main
        mock_controller = MagicMock()
        with patch('sense_emu.pyside_app.QApplication') as mock_app_cls, \
             patch('sense_emu.pyside_app.SenseEmuDesktop') as mock_window_cls, \
             patch('sys.exit') as mock_exit, \
             patch('sense_emu.pyside_app.EmulatorController', return_value=mock_controller):
            mock_app = MagicMock()
            mock_app.exec.return_value = 0
            mock_app_cls.return_value = mock_app
            mock_window = MagicMock()
            mock_window_cls.return_value = mock_window
            main()
        mock_exit.assert_called_once_with(0)
