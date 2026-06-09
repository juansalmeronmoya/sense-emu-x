import os
import time
import struct
import pytest
from unittest.mock import patch, MagicMock, call

pytest.importorskip('textual')


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_screen(tmp_screen_file):
    yield


@pytest.fixture
def mock_controller():
    ctl = MagicMock()
    ctl.imu      = MagicMock()
    ctl.pressure = MagicMock()
    ctl.humidity = MagicMock()
    ctl.screen   = MagicMock()
    ctl.stick    = MagicMock()
    return ctl


@pytest.fixture(autouse=True)
def patch_emulator(mock_controller):
    with patch('sense_emu.tui.EmulatorController', return_value=mock_controller):
        yield mock_controller


@pytest.fixture
def app(mock_controller):
    from sense_emu.tui import SenseEmuTUI
    instance = SenseEmuTUI()
    instance.controller = mock_controller
    return instance


# ── _parse_recording ──────────────────────────────────────────────────────────

class TestParseRecording:
    def test_parse_valid(self, sample_recording):
        from sense_emu.tui import _parse_recording
        records = _parse_recording(sample_recording)
        assert len(records) == 5
        assert records[0].pressure == pytest.approx(1013.0)

    def test_parse_invalid_magic(self, tmp_path):
        from sense_emu.tui import _parse_recording
        bad = tmp_path / 'bad.bin'
        bad.write_bytes(b'\x00' * 64)
        with pytest.raises(ValueError, match='Invalid'):
            _parse_recording(str(bad))

    def test_parse_wrong_version(self, tmp_path):
        from sense_emu.tui import _parse_recording
        from sense_emu.common import HEADER_REC
        bad = tmp_path / 'bad.bin'
        bad.write_bytes(HEADER_REC.pack(b'SENSEHAT', 2, time.time()))
        with pytest.raises(ValueError, match='Invalid'):
            _parse_recording(str(bad))

    def test_parse_truncated(self, tmp_path):
        from sense_emu.tui import _parse_recording
        from sense_emu.common import HEADER_REC
        bad = tmp_path / 'bad.bin'
        with open(bad, 'wb') as f:
            f.write(HEADER_REC.pack(b'SENSEHAT', 1, time.time()))
            f.write(b'\x00' * 10)
        with pytest.raises(ValueError, match='Truncated'):
            _parse_recording(str(bad))

    def test_parse_empty(self, tmp_path):
        from sense_emu.tui import _parse_recording
        from sense_emu.common import HEADER_REC
        empty = tmp_path / 'empty.bin'
        empty.write_bytes(HEADER_REC.pack(b'SENSEHAT', 1, time.time()))
        assert _parse_recording(str(empty)) == []

    def test_parse_header_too_short(self, tmp_path):
        from sense_emu.tui import _parse_recording
        bad = tmp_path / 'bad.bin'
        bad.write_bytes(b'\x00' * 5)
        with pytest.raises(ValueError, match='Invalid'):
            _parse_recording(str(bad))


# ── _make_joystick_event ──────────────────────────────────────────────────────

class TestMakeJoystickEvent:
    def test_returns_bytes(self):
        from sense_emu.tui import _make_joystick_event, _KEY_UP
        buf = _make_joystick_event(_KEY_UP, 1)
        assert isinstance(buf, bytes)

    def test_correct_size(self):
        from sense_emu.tui import _make_joystick_event, _KEY_UP, _EVENT_FORMAT
        buf = _make_joystick_event(_KEY_UP, 1)
        assert len(buf) == struct.calcsize(_EVENT_FORMAT)

    def test_key_code_and_state_encoded(self):
        from sense_emu.tui import _make_joystick_event, _KEY_DOWN, _EVENT_FORMAT, _EV_KEY
        buf = _make_joystick_event(_KEY_DOWN, 1)
        tv_sec, tv_usec, ev_type, code, value = struct.unpack(_EVENT_FORMAT, buf)
        assert ev_type == _EV_KEY
        assert code   == _KEY_DOWN
        assert value  == 1

    def test_release_state(self):
        from sense_emu.tui import _make_joystick_event, _KEY_ENTER, _EVENT_FORMAT
        buf = _make_joystick_event(_KEY_ENTER, 0)
        _, _, _, _, value = struct.unpack(_EVENT_FORMAT, buf)
        assert value == 0

    def test_all_key_codes(self):
        from sense_emu.tui import (_make_joystick_event, _EVENT_FORMAT,
                                   _KEY_UP, _KEY_DOWN, _KEY_LEFT,
                                   _KEY_RIGHT, _KEY_ENTER)
        for key in (_KEY_UP, _KEY_DOWN, _KEY_LEFT, _KEY_RIGHT, _KEY_ENTER):
            buf = _make_joystick_event(key, 1)
            _, _, _, code, _ = struct.unpack(_EVENT_FORMAT, buf)
            assert code == key


# ── LEDMatrix ─────────────────────────────────────────────────────────────────

class TestLEDMatrix:
    def test_class_exists(self):
        from sense_emu.tui import LEDMatrix
        assert LEDMatrix is not None

    def test_set_screen_client(self):
        from sense_emu.tui import LEDMatrix
        widget = LEDMatrix()
        mock_client = MagicMock()
        widget.set_screen_client(mock_client)
        assert widget._screen_client is mock_client

    def test_refresh_matrix_no_client(self):
        from sense_emu.tui import LEDMatrix
        widget = LEDMatrix()
        widget._screen_client = None
        widget.update = MagicMock()
        widget._refresh_matrix()
        widget.update.assert_called_once()
        call_args = widget.update.call_args[0][0]
        assert 'Waiting' in call_args or 'dim' in call_args

    def test_refresh_matrix_with_client(self):
        import numpy as np
        from sense_emu.tui import LEDMatrix
        widget = LEDMatrix()
        mock_client = MagicMock()
        mock_client.rgb_array = np.zeros((8, 8, 3), dtype='uint8')
        widget._screen_client = mock_client
        widget.update = MagicMock()
        widget._refresh_matrix()
        widget.update.assert_called_once()
        rendered = widget.update.call_args[0][0]
        assert '██' in rendered

    def test_refresh_matrix_exception_does_not_raise(self):
        from sense_emu.tui import LEDMatrix
        widget = LEDMatrix()
        mock_client = MagicMock()
        mock_client.rgb_array = MagicMock(side_effect=RuntimeError("oops"))
        widget._screen_client = mock_client
        widget.update = MagicMock()
        widget._refresh_matrix()  # must not raise

    def test_rgb_values_appear_in_output(self):
        import numpy as np
        from sense_emu.tui import LEDMatrix
        widget = LEDMatrix()
        rgb = np.zeros((8, 8, 3), dtype='uint8')
        rgb[0, 0] = [255, 0, 0]
        mock_client = MagicMock()
        mock_client.rgb_array = rgb
        widget._screen_client = mock_client
        widget.update = MagicMock()
        widget._refresh_matrix()
        output = widget.update.call_args[0][0]
        assert 'rgb(255,0,0)' in output


# ── SensorReadings ────────────────────────────────────────────────────────────

class TestSensorReadings:
    def _make_widget(self):
        from sense_emu.tui import SensorReadings
        widget = SensorReadings()
        widget._hat     = None
        widget._records = []
        widget._rec_t0  = 0.0
        widget._label   = "—"
        widget.update   = MagicMock()
        return widget

    def _make_mock_hat(self):
        hat = MagicMock()
        hat.get_accelerometer_raw.return_value          = {'x': 0.1, 'y': 0.2, 'z': 1.0}
        hat.get_gyroscope_raw.return_value              = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        hat.get_compass_raw.return_value                = {'x': 0.33,'y': 0.0, 'z': 0.0}
        hat.get_orientation.return_value                = {'roll': 0.0, 'pitch': 5.0, 'yaw': 90.0}
        hat.get_pressure.return_value                   = 1013.25
        hat.get_temperature_from_pressure.return_value  = 20.5
        hat.get_humidity.return_value                   = 45.0
        hat.get_temperature_from_humidity.return_value  = 21.0
        return hat

    def test_set_live(self):
        widget = self._make_widget()
        hat = self._make_mock_hat()
        widget.set_live(hat, label="Test")
        assert widget._hat is hat
        assert widget._label == "Test"
        assert widget._records == []

    def test_set_recording(self, sample_recording):
        from sense_emu.tui import _parse_recording
        widget = self._make_widget()
        records = _parse_recording(sample_recording)
        widget.set_recording(records, label="test.bin")
        assert widget._hat is None
        assert len(widget._records) == 5
        assert widget._label == "test.bin"

    def test_refresh_with_live_hat(self):
        widget = self._make_widget()
        widget.set_live(self._make_mock_hat())
        widget._refresh()
        widget.update.assert_called_once()
        text = widget.update.call_args[0][0]
        assert 'Accelerometer' in text
        assert 'Gyroscope' in text
        assert 'Pressure' in text

    def test_refresh_without_data(self):
        widget = self._make_widget()
        widget._refresh()
        widget.update.assert_called_once()
        text = widget.update.call_args[0][0]
        assert 'No data' in text

    def test_refresh_with_recording(self, sample_recording):
        from sense_emu.tui import _parse_recording
        widget = self._make_widget()
        records = _parse_recording(sample_recording)
        widget.set_recording(records)
        widget._refresh()
        widget.update.assert_called_once()
        text = widget.update.call_args[0][0]
        assert 'Accelerometer' in text

    def test_live_render_exception_does_not_raise(self):
        widget = self._make_widget()
        bad_hat = MagicMock()
        bad_hat.get_accelerometer_raw.side_effect = RuntimeError('broken')
        widget.set_live(bad_hat)
        widget._refresh()  # must not raise

    def test_source_label_appears_in_output(self):
        widget = self._make_widget()
        widget.set_live(self._make_mock_hat(), label="MySource")
        widget._refresh()
        text = widget.update.call_args[0][0]
        assert 'MySource' in text

    def test_recording_timestamp_in_output(self, sample_recording):
        from sense_emu.tui import _parse_recording
        widget = self._make_widget()
        records = _parse_recording(sample_recording)
        widget.set_recording(records)
        widget._refresh()
        text = widget.update.call_args[0][0]
        assert '/' in text  # "t = X.Xs / Y.Ys"


# ── SenseEmuTUI ───────────────────────────────────────────────────────────────

class TestSenseEmuTUI:
    def test_class_has_compose(self):
        from sense_emu.tui import SenseEmuTUI
        assert hasattr(SenseEmuTUI, 'compose')

    def test_class_has_css(self):
        from sense_emu.tui import SenseEmuTUI
        assert hasattr(SenseEmuTUI, 'CSS')
        assert SenseEmuTUI.CSS

    def test_class_has_bindings(self):
        from sense_emu.tui import SenseEmuTUI
        assert hasattr(SenseEmuTUI, 'BINDINGS')
        assert len(SenseEmuTUI.BINDINGS) > 0

    def test_binding_keys(self):
        from sense_emu.tui import SenseEmuTUI
        keys = {b.key for b in SenseEmuTUI.BINDINGS}
        assert 'ctrl+q' in keys
        assert 'ctrl+o' in keys
        assert 'up'     in keys
        assert 'down'   in keys
        assert 'left'   in keys
        assert 'right'  in keys
        assert 'enter'  in keys

    def test_main_callable(self):
        from sense_emu.tui import main
        assert callable(main)

    def test_main_calls_run(self):
        from sense_emu.tui import main, SenseEmuTUI
        with patch.object(SenseEmuTUI, 'run') as mock_run:
            main()
        mock_run.assert_called_once()

    def test_on_mount_creates_controller(self, patch_emulator):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        mock_led  = MagicMock()
        mock_sens = MagicMock()
        mock_hat  = MagicMock()
        with patch.object(app, 'query_one', side_effect=[mock_led, mock_sens]), \
             patch('sense_emu.tui.SenseHat', return_value=mock_hat, create=True), \
             patch('sense_emu.tui.EmulatorController', return_value=patch_emulator):
            app.on_mount()
        assert app.controller is patch_emulator

    def test_on_unmount_closes_controller(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        app.on_unmount()
        mock_controller.close.assert_called_once()

    def test_on_input_changed_no_controller(self):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        if hasattr(app, 'controller'):
            delattr(app, 'controller')
        event = MagicMock()
        event.input.id = 'pitch'
        event.value    = '10'
        app.on_input_changed(event)  # must not raise

    def test_on_input_changed_invalid_float(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        event = MagicMock()
        event.input.id = 'pitch'
        event.value    = 'xyz'
        app.on_input_changed(event)
        mock_controller.imu.set_orientation.assert_not_called()

    def test_on_input_changed_pitch_calls_imu(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        event = MagicMock()
        event.input.id = 'pitch'
        event.value    = '10'
        mock_input = MagicMock()
        mock_input.value = '0'
        app.query_one = MagicMock(return_value=mock_input)
        app.on_input_changed(event)
        mock_controller.imu.set_orientation.assert_called_once()

    def test_on_input_changed_roll_calls_imu(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        event = MagicMock()
        event.input.id = 'roll'
        event.value    = '45'
        mock_input = MagicMock()
        mock_input.value = '0'
        app.query_one = MagicMock(return_value=mock_input)
        app.on_input_changed(event)
        mock_controller.imu.set_orientation.assert_called_once()

    def test_on_input_changed_pressure_calls_pressure_and_humidity(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        event = MagicMock()
        event.input.id = 'pressure'
        event.value    = '950'
        mock_input = MagicMock()
        mock_input.value = '20'
        app.query_one = MagicMock(return_value=mock_input)
        app.on_input_changed(event)
        mock_controller.pressure.set_values.assert_called_once()
        mock_controller.humidity.set_values.assert_called_once()

    def test_on_input_changed_temp_updates_both(self, mock_controller):
        """Temperature changes must update BOTH pressure and humidity servers."""
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        event = MagicMock()
        event.input.id = 'temp'
        event.value    = '25'
        mock_input = MagicMock()
        mock_input.value = '0'
        app.query_one = MagicMock(return_value=mock_input)
        app.on_input_changed(event)
        mock_controller.pressure.set_values.assert_called_once()
        mock_controller.humidity.set_values.assert_called_once()

    def test_on_input_changed_humidity_updates_both(self, mock_controller):
        """Humidity changes must also update the pressure server (shared temp)."""
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        event = MagicMock()
        event.input.id = 'humidity'
        event.value    = '60'
        mock_input = MagicMock()
        mock_input.value = '0'
        app.query_one = MagicMock(return_value=mock_input)
        app.on_input_changed(event)
        mock_controller.pressure.set_values.assert_called_once()
        mock_controller.humidity.set_values.assert_called_once()

    def test_on_input_changed_unknown_id(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        event = MagicMock()
        event.input.id = 'unknown'
        event.value    = '42'
        app.on_input_changed(event)  # must not raise

    def test_send_joystick_no_controller(self):
        from sense_emu.tui import SenseEmuTUI, _KEY_UP
        app = SenseEmuTUI()
        if hasattr(app, 'controller'):
            delattr(app, 'controller')
        app._send_joystick(_KEY_UP)  # must not raise

    def test_send_joystick_sends_press_and_release(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI, _KEY_UP, _EVENT_FORMAT
        app = SenseEmuTUI()
        app.controller = mock_controller
        app._send_joystick(_KEY_UP)
        assert mock_controller.stick.send.call_count == 2
        # First call = press (value=1), second call = release (value=0)
        press_buf   = mock_controller.stick.send.call_args_list[0][0][0]
        release_buf = mock_controller.stick.send.call_args_list[1][0][0]
        _, _, _, code_p, val_p = struct.unpack(_EVENT_FORMAT, press_buf)
        _, _, _, code_r, val_r = struct.unpack(_EVENT_FORMAT, release_buf)
        assert code_p == _KEY_UP and val_p == 1
        assert code_r == _KEY_UP and val_r == 0

    def test_action_joy_up(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI, _KEY_UP, _EVENT_FORMAT
        app = SenseEmuTUI()
        app.controller = mock_controller
        app.action_joy_up()
        bufs = [c[0][0] for c in mock_controller.stick.send.call_args_list]
        codes = [struct.unpack(_EVENT_FORMAT, b)[3] for b in bufs]
        assert all(c == _KEY_UP for c in codes)

    def test_action_joy_down(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI, _KEY_DOWN, _EVENT_FORMAT
        app = SenseEmuTUI()
        app.controller = mock_controller
        app.action_joy_down()
        bufs = [c[0][0] for c in mock_controller.stick.send.call_args_list]
        codes = [struct.unpack(_EVENT_FORMAT, b)[3] for b in bufs]
        assert all(c == _KEY_DOWN for c in codes)

    def test_action_joy_left(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI, _KEY_LEFT, _EVENT_FORMAT
        app = SenseEmuTUI()
        app.controller = mock_controller
        app.action_joy_left()
        bufs = [c[0][0] for c in mock_controller.stick.send.call_args_list]
        codes = [struct.unpack(_EVENT_FORMAT, b)[3] for b in bufs]
        assert all(c == _KEY_LEFT for c in codes)

    def test_action_joy_right(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI, _KEY_RIGHT, _EVENT_FORMAT
        app = SenseEmuTUI()
        app.controller = mock_controller
        app.action_joy_right()
        bufs = [c[0][0] for c in mock_controller.stick.send.call_args_list]
        codes = [struct.unpack(_EVENT_FORMAT, b)[3] for b in bufs]
        assert all(c == _KEY_RIGHT for c in codes)

    def test_action_joy_enter(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI, _KEY_ENTER, _EVENT_FORMAT
        app = SenseEmuTUI()
        app.controller = mock_controller
        app.action_joy_enter()
        bufs = [c[0][0] for c in mock_controller.stick.send.call_args_list]
        codes = [struct.unpack(_EVENT_FORMAT, b)[3] for b in bufs]
        assert all(c == _KEY_ENTER for c in codes)

    def test_button_joy_up_sends_event(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI, _KEY_UP, _EVENT_FORMAT
        app = SenseEmuTUI()
        app.controller = mock_controller
        event = MagicMock()
        event.button.id = 'joy-up'
        app.on_button_pressed(event)
        assert mock_controller.stick.send.call_count == 2

    def test_button_joy_enter_sends_event(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI, _KEY_ENTER, _EVENT_FORMAT
        app = SenseEmuTUI()
        app.controller = mock_controller
        event = MagicMock()
        event.button.id = 'joy-enter'
        app.on_button_pressed(event)
        assert mock_controller.stick.send.call_count == 2

    def test_button_btn_emu_calls_activate(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        event = MagicMock()
        event.button.id = 'btn-emu'
        mock_hat = MagicMock()
        with patch.object(app, 'action_use_emulator') as mock_action:
            app.on_button_pressed(event)
            mock_action.assert_called_once()

    def test_button_btn_rec_calls_open_recording(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        event = MagicMock()
        event.button.id = 'btn-rec'
        with patch.object(app, 'action_open_recording') as mock_action:
            app.on_button_pressed(event)
            mock_action.assert_called_once()

    def test_on_recording_path_none_is_noop(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        app._on_recording_path(None)  # must not raise

    def test_on_recording_path_empty_string_is_noop(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        app._on_recording_path("")  # must not raise

    def test_on_recording_path_bad_file(self, mock_controller, tmp_path):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        mock_label = MagicMock()
        app.query_one = MagicMock(return_value=mock_label)
        bad = str(tmp_path / 'bad.bin')
        with open(bad, 'wb') as f:
            f.write(b'\x00' * 10)
        app._on_recording_path(bad)  # must not raise; sets error status

    def test_on_recording_path_valid(self, mock_controller, sample_recording):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        mock_readings = MagicMock()
        mock_label    = MagicMock()
        app.query_one = MagicMock(side_effect=[mock_readings, mock_label])
        app._on_recording_path(sample_recording)
        mock_readings.set_recording.assert_called_once()
        args = mock_readings.set_recording.call_args
        assert len(args[0][0]) == 5  # 5 records

    def test_set_status_helper(self, mock_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = mock_controller
        mock_label = MagicMock()
        app.query_one = MagicMock(return_value=mock_label)
        app._set_status("[green]OK[/green]")
        mock_label.update.assert_called_once_with("[green]OK[/green]")


# ── RecordingPathScreen ───────────────────────────────────────────────────────

class TestRecordingPathScreen:
    def test_class_exists(self):
        from sense_emu.tui import RecordingPathScreen
        assert RecordingPathScreen is not None

    def test_has_compose(self):
        from sense_emu.tui import RecordingPathScreen
        assert hasattr(RecordingPathScreen, 'compose')

    def test_has_escape_binding(self):
        from sense_emu.tui import RecordingPathScreen
        keys = {b.key for b in RecordingPathScreen.BINDINGS}
        assert 'escape' in keys

    def test_cancel_button_calls_dismiss_none(self):
        from sense_emu.tui import RecordingPathScreen
        screen = RecordingPathScreen()
        screen.dismiss = MagicMock()
        event = MagicMock()
        event.button.id = 'rec-cancel'
        screen.on_button_pressed(event)
        screen.dismiss.assert_called_once_with(None)

    def test_open_button_calls_dismiss_path(self):
        from sense_emu.tui import RecordingPathScreen
        screen = RecordingPathScreen()
        screen.dismiss = MagicMock()
        mock_input = MagicMock()
        mock_input.value = '  /path/to/file.bin  '
        screen.query_one = MagicMock(return_value=mock_input)
        event = MagicMock()
        event.button.id = 'rec-open'
        screen.on_button_pressed(event)
        screen.dismiss.assert_called_once_with('/path/to/file.bin')

    def test_action_cancel_dismisses_none(self):
        from sense_emu.tui import RecordingPathScreen
        screen = RecordingPathScreen()
        screen.dismiss = MagicMock()
        screen.action_cancel()
        screen.dismiss.assert_called_once_with(None)
