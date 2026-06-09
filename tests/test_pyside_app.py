import io
import pytest
from unittest.mock import patch, MagicMock


pytest.importorskip('PySide6')

from PySide6.QtCore import Qt


@pytest.fixture(autouse=True)
def patch_screen(tmp_screen_file):
    """Redirect all screen file access to the temp file."""
    yield


@pytest.fixture(autouse=True)
def isolate_qsettings(tmp_path):
    """Redirect QSettings writes to tmp_path so tests never touch real user config."""
    from PySide6.QtCore import QSettings
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
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
        with open(tmp_screen_file, 'r+b') as f:
            f.seek(0)
            f.write(bytes(range(192)))
        widget.update_matrix()
        assert widget.matrix_data[0] == 0  # first byte

    def test_update_matrix_with_full_192_bytes(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
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

    def test_has_height_for_width(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        assert widget.hasHeightForWidth() is True

    def test_height_for_width_returns_width(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        assert widget.heightForWidth(200) == 200
        assert widget.heightForWidth(400) == 400

    def test_set_cell_size_updates_minimum(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        widget.set_cell_size(20)
        assert widget.minimumWidth() == 160
        assert widget.minimumHeight() == 160

    def test_set_cell_size_clamps_minimum(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        widget = LEDMatrixWidget()
        qtbot.addWidget(widget)
        widget.set_cell_size(1)  # below minimum
        assert widget.cell_size() == 10

    def test_custom_cell_size_at_init(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        widget = LEDMatrixWidget(cell_size=30)
        qtbot.addWidget(widget)
        assert widget.minimumWidth() == 240
        assert widget.minimumHeight() == 240

    def test_size_hint_is_square(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import LEDMatrixWidget
        widget = LEDMatrixWidget(cell_size=40)
        qtbot.addWidget(widget)
        hint = widget.sizeHint()
        assert hint.width() == hint.height() == 320


class TestPreferencesDialog:
    def test_init_creates_dialog(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import PreferencesDialog
        dlg = PreferencesDialog()
        qtbot.addWidget(dlg)
        assert dlg is not None

    def test_default_settings(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import PreferencesDialog
        dlg = PreferencesDialog()
        qtbot.addWidget(dlg)
        s = dlg.get_settings()
        assert s['poll_interval_ms'] == 200
        assert s['max_samples'] == 300
        assert s['time_window_s'] == 60
        assert s['cell_size'] == 40
        assert s['led_refresh_ms'] == 100

    def test_custom_settings_applied(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import PreferencesDialog
        settings = {
            'poll_interval_ms': 500,
            'max_samples': 150,
            'time_window_s': 30,
            'cell_size': 25,
            'led_refresh_ms': 200,
        }
        dlg = PreferencesDialog(settings=settings)
        qtbot.addWidget(dlg)
        s = dlg.get_settings()
        assert s['poll_interval_ms'] == 500
        assert s['max_samples'] == 150
        assert s['time_window_s'] == 30
        assert s['cell_size'] == 25
        assert s['led_refresh_ms'] == 200

    def test_get_settings_returns_dict(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import PreferencesDialog
        dlg = PreferencesDialog()
        qtbot.addWidget(dlg)
        s = dlg.get_settings()
        assert isinstance(s, dict)
        assert 'poll_interval_ms' in s
        assert 'max_samples' in s
        assert 'time_window_s' in s
        assert 'cell_size' in s
        assert 'led_refresh_ms' in s

    def test_spinbox_ranges_poll_interval(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import PreferencesDialog
        dlg = PreferencesDialog()
        qtbot.addWidget(dlg)
        assert dlg._poll_interval.minimum() == 50
        assert dlg._poll_interval.maximum() == 5000

    def test_spinbox_ranges_max_samples(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import PreferencesDialog
        dlg = PreferencesDialog()
        qtbot.addWidget(dlg)
        assert dlg._max_samples.minimum() == 10
        assert dlg._max_samples.maximum() == 10000

    def test_spinbox_ranges_cell_size(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import PreferencesDialog
        dlg = PreferencesDialog()
        qtbot.addWidget(dlg)
        assert dlg._cell_size.minimum() == 10
        assert dlg._cell_size.maximum() == 80


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

    def test_has_led_matrix_widget(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop, LEDMatrixWidget
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            assert isinstance(window.matrix, LEDMatrixWidget)

    def test_has_matrix_size_spinbox(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            assert window._matrix_size_spin is not None

    def test_matrix_size_spin_changes_cell_size(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            window._matrix_size_spin.setValue(20)
            assert window.matrix.cell_size() == 20

    def test_default_settings_keys(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            for key in ('poll_interval_ms', 'max_samples', 'time_window_s',
                        'cell_size', 'led_refresh_ms'):
                assert key in window._settings

    def test_apply_settings_updates_matrix(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            window._settings['cell_size'] = 30
            window._apply_settings()
            assert window.matrix.cell_size() == 30

    def test_apply_settings_updates_led_refresh(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            window._settings['led_refresh_ms'] = 250
            window._apply_settings()
            assert window.matrix.timer.interval() == 250

    def test_open_preferences_dialog_cancelled(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            original_cell = window._settings['cell_size']
            with patch('sense_emu.pyside_app.PreferencesDialog') as mock_dlg_cls:
                mock_dlg = MagicMock()
                mock_dlg.exec.return_value = 0  # QDialog.Rejected
                mock_dlg_cls.return_value = mock_dlg
                window._open_preferences()
            # Settings should not change when dialog is cancelled
            assert window._settings['cell_size'] == original_cell

    def test_open_preferences_dialog_accepted(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        from PySide6.QtWidgets import QDialog
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            new_settings = {
                'poll_interval_ms': 400,
                'max_samples': 200,
                'time_window_s': 45,
                'cell_size': 35,
                'led_refresh_ms': 150,
            }
            with patch('sense_emu.pyside_app.PreferencesDialog') as mock_dlg_cls:
                mock_dlg = MagicMock()
                mock_dlg.exec.return_value = QDialog.Accepted
                mock_dlg.get_settings.return_value = new_settings
                mock_dlg_cls.return_value = mock_dlg
                window._open_preferences()
            assert window._settings['cell_size'] == 35
            assert window._settings['max_samples'] == 200

    def test_settings_roundtrip(self, qtbot, emulator, tmp_screen_file):
        """Settings saved on close are restored when a new window opens."""
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            win1 = SenseEmuDesktop()
            qtbot.addWidget(win1)
            win1._matrix_size_spin.setValue(55)   # triggers _on_matrix_size_changed
            win1._save_settings()                  # flush to disk

        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            win2 = SenseEmuDesktop()
            qtbot.addWidget(win2)
            assert win2._settings['cell_size'] == 55
            assert win2.matrix.cell_size() == 55

    def test_has_qsettings(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        from PySide6.QtCore import QSettings
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
            assert isinstance(window._qsettings, QSettings)


class TestSingleInstanceError:
    """GUI main() must show a friendly warning when emulator is already running."""

    def test_runtime_error_shows_warning_and_exits(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import main
        with patch('sense_emu.pyside_app.QApplication') as mock_app_cls, \
             patch('sense_emu.pyside_app.SenseEmuDesktop',
                   side_effect=RuntimeError('already running')), \
             patch('sense_emu.pyside_app.QMessageBox') as mock_msgbox, \
             patch('sys.exit') as mock_exit:
            mock_app_cls.return_value = MagicMock()
            main()
        mock_msgbox.warning.assert_called_once()
        mock_msgbox.critical.assert_not_called()
        warn_args = mock_msgbox.warning.call_args[0]
        body = warn_args[2]
        assert 'running' in body.lower() or 'emulator' in body.lower()
        mock_exit.assert_called_once_with(1)

    def test_other_exception_shows_critical(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import main
        with patch('sense_emu.pyside_app.QApplication') as mock_app_cls, \
             patch('sense_emu.pyside_app.SenseEmuDesktop',
                   side_effect=OSError('disk full')), \
             patch('sense_emu.pyside_app.QMessageBox') as mock_msgbox, \
             patch('sys.exit') as mock_exit:
            mock_app_cls.return_value = MagicMock()
            main()
        mock_msgbox.critical.assert_called_once()
        mock_exit.assert_called_once_with(1)


class TestJoystickEvents:
    """The GUI joystick must send real evdev events to the StickServer."""

    def _make_window(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
        return window

    def _sent_events(self, mock_stick):
        import struct
        from sense_emu.stick import SenseStick
        return [struct.unpack(SenseStick.EVENT_FORMAT, c[0][0])
                for c in mock_stick.send.call_args_list]

    @pytest.mark.parametrize('direction,key_attr', [
        ('UP', 'KEY_UP'), ('DOWN', 'KEY_DOWN'), ('LEFT', 'KEY_LEFT'),
        ('RIGHT', 'KEY_RIGHT'), ('MIDDLE', 'KEY_ENTER'),
    ])
    def test_press_sends_press_and_release(self, qtbot, emulator,
                                           tmp_screen_file, direction, key_attr):
        from sense_emu.stick import SenseStick
        window = self._make_window(qtbot, emulator, tmp_screen_file)
        with patch.object(window.controller, 'stick') as mock_stick:
            window._on_stick_press(direction)
            events = self._sent_events(mock_stick)
        assert len(events) == 2
        expected_key = getattr(SenseStick, key_attr)
        (_, _, t1, code1, val1), (_, _, t2, code2, val2) = events
        assert t1 == t2 == SenseStick.EV_KEY
        assert code1 == code2 == expected_key
        assert val1 == SenseStick.STATE_PRESS
        assert val2 == SenseStick.STATE_RELEASE

    def test_keyboard_arrow_sends_real_events(self, qtbot, emulator, tmp_screen_file):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        from sense_emu.stick import SenseStick
        window = self._make_window(qtbot, emulator, tmp_screen_file)
        with patch.object(window.controller, 'stick') as mock_stick:
            event = QKeyEvent(QEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
            window.keyPressEvent(event)
            events = self._sent_events(mock_stick)
        assert len(events) == 2
        assert events[0][3] == SenseStick.KEY_UP


class TestKeyboardJoystick:
    def _make_window(self, qtbot, emulator, tmp_screen_file):
        from sense_emu.pyside_app import SenseEmuDesktop
        with patch('sense_emu.pyside_app.EmulatorController', return_value=emulator), \
             patch.object(SenseEmuDesktop, '_use_emulator'):
            window = SenseEmuDesktop()
            qtbot.addWidget(window)
        return window

    def _press_key(self, window, qt_key):
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        event = QKeyEvent(QEvent.KeyPress, qt_key, Qt.NoModifier)
        window.keyPressEvent(event)
        return event

    def test_arrow_up_calls_stick(self, qtbot, emulator, tmp_screen_file):
        window = self._make_window(qtbot, emulator, tmp_screen_file)
        with patch.object(window, '_on_stick_press') as mock:
            self._press_key(window, Qt.Key_Up)
            mock.assert_called_once_with("UP")

    def test_arrow_down_calls_stick(self, qtbot, emulator, tmp_screen_file):
        window = self._make_window(qtbot, emulator, tmp_screen_file)
        with patch.object(window, '_on_stick_press') as mock:
            self._press_key(window, Qt.Key_Down)
            mock.assert_called_once_with("DOWN")

    def test_arrow_left_calls_stick(self, qtbot, emulator, tmp_screen_file):
        window = self._make_window(qtbot, emulator, tmp_screen_file)
        with patch.object(window, '_on_stick_press') as mock:
            self._press_key(window, Qt.Key_Left)
            mock.assert_called_once_with("LEFT")

    def test_arrow_right_calls_stick(self, qtbot, emulator, tmp_screen_file):
        window = self._make_window(qtbot, emulator, tmp_screen_file)
        with patch.object(window, '_on_stick_press') as mock:
            self._press_key(window, Qt.Key_Right)
            mock.assert_called_once_with("RIGHT")

    def test_return_calls_stick_middle(self, qtbot, emulator, tmp_screen_file):
        window = self._make_window(qtbot, emulator, tmp_screen_file)
        with patch.object(window, '_on_stick_press') as mock:
            self._press_key(window, Qt.Key_Return)
            mock.assert_called_once_with("MIDDLE")

    def test_enter_calls_stick_middle(self, qtbot, emulator, tmp_screen_file):
        window = self._make_window(qtbot, emulator, tmp_screen_file)
        with patch.object(window, '_on_stick_press') as mock:
            self._press_key(window, Qt.Key_Enter)
            mock.assert_called_once_with("MIDDLE")

    def test_other_key_does_not_call_stick(self, qtbot, emulator, tmp_screen_file):
        window = self._make_window(qtbot, emulator, tmp_screen_file)
        with patch.object(window, '_on_stick_press') as mock:
            self._press_key(window, Qt.Key_Space)
            mock.assert_not_called()

    def test_arrow_key_event_accepted(self, qtbot, emulator, tmp_screen_file):
        window = self._make_window(qtbot, emulator, tmp_screen_file)
        with patch.object(window, '_on_stick_press'):
            from PySide6.QtGui import QKeyEvent
            from PySide6.QtCore import QEvent
            event = QKeyEvent(QEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
            window.keyPressEvent(event)
            assert event.isAccepted()


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

    def test_apply_settings_max_samples(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        panel.apply_settings({'max_samples': 50})
        assert panel._max_samples == 50

    def test_apply_settings_poll_interval(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        panel.apply_settings({'poll_interval_ms': 500})
        assert panel._poll_interval_ms == 500

    def test_apply_settings_time_window(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        panel.apply_settings({'time_window_s': 30})
        assert panel._time_window_s == 30

    def test_apply_settings_updates_active_timer(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        panel.set_live(_make_mock_hat())
        panel.apply_settings({'poll_interval_ms': 400})
        assert panel._timer.interval() == 400
        panel._timer.stop()

    def test_default_poll_interval(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        assert panel._poll_interval_ms == 200

    def test_default_time_window(self, qtbot, tmp_screen_file):
        from sense_emu.pyside_app import TelemetryPanel
        panel = TelemetryPanel()
        qtbot.addWidget(panel)
        assert panel._time_window_s == 60


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

    def test_main_shows_critical_on_non_runtime_exception(self, tmp_screen_file, emulator):
        from sense_emu.pyside_app import main
        with patch('sense_emu.pyside_app.QApplication') as mock_app_cls, \
             patch('sense_emu.pyside_app.SenseEmuDesktop',
                   side_effect=OSError('disk full')), \
             patch('sense_emu.pyside_app.QMessageBox') as mock_msgbox, \
             patch('sys.exit') as mock_exit:
            mock_app_cls.return_value = MagicMock()
            main()
        mock_msgbox.critical.assert_called_once()
        mock_exit.assert_called_once_with(1)

    def test_main_shows_warning_on_runtime_error(self, tmp_screen_file, emulator):
        from sense_emu.pyside_app import main
        with patch('sense_emu.pyside_app.QApplication') as mock_app_cls, \
             patch('sense_emu.pyside_app.SenseEmuDesktop',
                   side_effect=RuntimeError('already running')), \
             patch('sense_emu.pyside_app.QMessageBox') as mock_msgbox, \
             patch('sys.exit') as mock_exit:
            mock_app_cls.return_value = MagicMock()
            main()
        mock_msgbox.warning.assert_called_once()
        mock_msgbox.critical.assert_not_called()
        mock_exit.assert_called_once_with(1)
