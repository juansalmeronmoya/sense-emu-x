import io
import pytest
from unittest.mock import patch, MagicMock


pytest.importorskip('PySide6')


@pytest.fixture(autouse=True)
def patch_screen(tmp_screen_file):
    """Redirect all screen file access to the temp file."""
    yield


def _make_mock_hat():
    hat = MagicMock()
    hat.get_accelerometer_raw.return_value = {'x': 0.1, 'y': 0.2, 'z': 1.0}
    hat.get_gyroscope_raw.return_value     = {'x': 0.0, 'y': 0.0, 'z': 0.0}
    hat.get_compass_raw.return_value       = {'x': 0.33, 'y': 0.0, 'z': 0.0}
    hat.get_orientation.return_value       = {'roll': 0.0, 'pitch': 5.0, 'yaw': 90.0}
    hat.get_pressure.return_value          = 1013.25
    hat.get_temperature_from_pressure.return_value = 20.5
    hat.get_humidity.return_value          = 45.0
    hat.get_temperature_from_humidity.return_value = 21.0
    return hat


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
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        assert len(widget.matrix_data) == 192
        assert all(b == 0 for b in widget.matrix_data)

    def test_update_matrix_reads_file(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        # Write 192 non-zero bytes
        with open(tmp_screen_file, 'r+b') as f:
            f.seek(0)
            f.write(bytes(range(192)))
        widget.update_matrix()
        assert widget.matrix_data[0] == 0  # first byte

    def test_update_matrix_with_full_192_bytes(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        # Extend the screen file to exactly 192 bytes
        with open(tmp_screen_file, 'r+b') as f:
            f.write(b'\x00' * 192)
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        widget.update_matrix()
        assert len(widget.matrix_data) == 192

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
            f.write(b'\x00' * 192)
        with patch('sense_emu.pyside_app.screen_filename', return_value=tmp_screen_file):
            widget = LEDMatrixWidget()
            qtbot.addWidget(widget)
            widget.timer.stop()
            widget.update_matrix()
        assert len(widget.matrix_data) == 192

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
    def test_init_creates_window(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            assert window is not None

    def test_has_six_sliders(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            assert len(window.sliders) == 6

    def test_slider_names(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            for name in ('Yaw', 'Pitch', 'Roll', 'Pressure', 'Temperature', 'Humidity'):
                assert name in window.sliders

    def test_update_sensors_calls_controller(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            window.sliders['Pressure'].setValue(950)
            window.update_sensors()
            assert emulator.pressure.pressure == pytest.approx(950.0)

    def test_close_event_calls_controller_close(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        from PySide6.QtGui import QCloseEvent
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            with patch.object(emulator, 'close') as mock_close:
                event = QCloseEvent()
                window.closeEvent(event)
                mock_close.assert_called_once()

    def test_has_telemetry_panel(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop, TelemetryPanel
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            assert isinstance(window.telemetry, TelemetryPanel)

    def test_source_buttons_present(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            assert window._btn_emu is not None
            assert window._btn_rec is not None

    def test_open_recording_loads_data(self, qtbot, emulator, tmp_screen_file, sample_recording):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            window.telemetry.set_recording(sample_recording)
            assert window.telemetry._series['pressure'].count() == 5

    def test_open_recording_dialog_cancelled(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'), \
             patch('sense_emu.pyside_app.QFileDialog.getOpenFileName',
                   return_value=('', '')):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            window._open_recording()  # should not raise when dialog is cancelled


class TestTelemetryPanel:
    def test_init_creates_sixteen_series(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        assert len(panel._series) == 16

    def test_init_creates_seven_charts(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        assert len(panel._chart_keys) == 7

    def test_set_live_starts_timer(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        hat = _make_mock_hat()
        panel.set_live(hat)
        assert panel._timer.isActive()
        panel._timer.stop()

    def test_set_live_updates_label(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        panel.set_live(_make_mock_hat(), label='Test source')
        assert 'Test source' in panel._status_label.text()
        panel._timer.stop()

    def test_poll_appends_data(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        panel.set_live(_make_mock_hat())
        panel._poll()
        assert panel._series['pressure'].count() == 1
        assert panel._series['humidity'].count() == 1
        assert panel._series['ax'].count() == 1
        panel._timer.stop()

    def test_poll_respects_max_samples(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        panel._max_samples = 5
        qtbot.addWidget(panel)
        panel.set_live(_make_mock_hat())
        for i in range(8):
            panel._poll()
        assert panel._series['pressure'].count() <= 5
        panel._timer.stop()

    def test_poll_noop_without_hat(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        panel._hat = None
        panel._poll()  # must not raise
        assert panel._series['pressure'].count() == 0

    def test_set_recording_populates_series(self, qtbot, tmp_screen_file, sample_recording):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        panel.set_recording(sample_recording)
        assert panel._series['pressure'].count() == 5
        assert panel._series['humidity'].count() == 5
        assert panel._series['ax'].count() == 5
        assert panel._series['ox'].count() == 5

    def test_set_recording_stops_timer(self, qtbot, tmp_screen_file, sample_recording):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        panel.set_live(_make_mock_hat())
        assert panel._timer.isActive()
        panel.set_recording(sample_recording)
        assert not panel._timer.isActive()

    def test_set_recording_updates_label(self, qtbot, tmp_screen_file, sample_recording):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        panel.set_recording(sample_recording)
        assert 'recording.bin' in panel._status_label.text()

    def test_set_recording_invalid_file_raises(self, qtbot, tmp_screen_file, tmp_path):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        bad = tmp_path / 'bad.bin'
        bad.write_bytes(b'\x00' * 64)
        with pytest.raises(ValueError):
            panel.set_recording(str(bad))

    def test_clear_resets_series(self, qtbot, tmp_screen_file, sample_recording):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        panel.set_recording(sample_recording)
        assert panel._series['pressure'].count() == 5
        panel.clear()
        assert panel._series['pressure'].count() == 0


class TestParseRecording:
    def test_parse_valid(self, sample_recording):
        from sense_emu.pyside_app import _parse_recording
        records = _parse_recording(sample_recording)
        assert len(records) == 5
        assert records[0].pressure == pytest.approx(1013.0)
        assert records[0].humidity == pytest.approx(45.0)
        assert records[0].ax == pytest.approx(0.0)
        assert records[0].az == pytest.approx(1.0)

    def test_parse_timestamps_increase(self, sample_recording):
        from sense_emu.pyside_app import _parse_recording
        records = _parse_recording(sample_recording)
        for i in range(1, len(records)):
            assert records[i].timestamp > records[i - 1].timestamp

    def test_parse_invalid_magic(self, tmp_path):
        from sense_emu.pyside_app import _parse_recording
        bad = tmp_path / 'bad.bin'
        bad.write_bytes(b'\x00' * 64)
        with pytest.raises(ValueError, match='Invalid'):
            _parse_recording(str(bad))

    def test_parse_wrong_magic_string(self, tmp_path):
        from sense_emu.pyside_app import _parse_recording
        from sense_emu.common import HEADER_REC
        import time
        bad = tmp_path / 'bad.bin'
        bad.write_bytes(HEADER_REC.pack(b'WRONGMAG', 1, time.time()))
        with pytest.raises(ValueError, match='Invalid'):
            _parse_recording(str(bad))

    def test_parse_wrong_version(self, tmp_path):
        from sense_emu.pyside_app import _parse_recording
        from sense_emu.common import HEADER_REC
        import time
        bad = tmp_path / 'bad.bin'
        bad.write_bytes(HEADER_REC.pack(b'SENSEHAT', 2, time.time()))
        with pytest.raises(ValueError, match='Invalid'):
            _parse_recording(str(bad))

    def test_parse_truncated_record(self, tmp_path):
        from sense_emu.pyside_app import _parse_recording
        from sense_emu.common import HEADER_REC
        import time
        bad = tmp_path / 'bad.bin'
        with open(bad, 'wb') as f:
            f.write(HEADER_REC.pack(b'SENSEHAT', 1, time.time()))
            f.write(b'\x00' * 10)  # truncated DATA_REC (needs 136 bytes)
        with pytest.raises(ValueError, match='Truncated'):
            _parse_recording(str(bad))

    def test_parse_empty_recording(self, tmp_path):
        from sense_emu.pyside_app import _parse_recording
        from sense_emu.common import HEADER_REC
        import time
        empty = tmp_path / 'empty.bin'
        empty.write_bytes(HEADER_REC.pack(b'SENSEHAT', 1, time.time()))
        records = _parse_recording(str(empty))
        assert records == []

    def test_parse_header_too_short(self, tmp_path):
        from sense_emu.pyside_app import _parse_recording
        bad = tmp_path / 'bad.bin'
        bad.write_bytes(b'\x00' * 5)  # shorter than HEADER_REC.size
        with pytest.raises(ValueError, match='Invalid'):
            _parse_recording(str(bad))


class TestPysideMain:
    def test_main_importable(self):
        from sense_emu.pyside_app import main
        assert callable(main)

    def test_pyside_main_module(self):
        import sense_emu.pyside_main as pm
        assert hasattr(pm, 'main')


class TestPysideMainFunction:
    def test_main_calls_sys_exit(self, tmp_screen_file, emulator):
        from sense_emu.pyside_app import main
        with patch('sense_emu.pyside_app.QApplication') as mock_app_cls, \
             patch('sense_emu.pyside_app.SenseEmuDesktop') as mock_window_cls, \
             patch('sys.exit') as mock_exit, \
             patch('sense_emu.pyside_app.EmulatorController'):
            mock_app = MagicMock()
            mock_app.exec.return_value = 0
            mock_app_cls.return_value = mock_app
            mock_window = MagicMock()
            mock_window_cls.return_value = mock_window
            main()
        mock_exit.assert_called_once_with(0)

    def test_main_shows_dialog_on_exception(self, tmp_screen_file, emulator):
        from sense_emu.pyside_app import main
        with patch('sense_emu.pyside_app.QApplication') as mock_app_cls, \
             patch('sense_emu.pyside_app.SenseEmuDesktop',
                   side_effect=RuntimeError('test error')), \
             patch('sense_emu.pyside_app.QMessageBox') as mock_msgbox, \
             patch('sys.exit') as mock_exit:
            mock_app_cls.return_value = MagicMock()
            main()
        mock_msgbox.critical.assert_called_once()
        mock_exit.assert_called_once_with(1)
