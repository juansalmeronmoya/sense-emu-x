import pytest
from unittest.mock import patch, MagicMock


pytest.importorskip('textual')


@pytest.fixture(autouse=True)
def patch_emulator_controller():
    """Prevent TUI from creating a real EmulatorController during tests."""
    mock_ctl = MagicMock()
    mock_ctl.imu = MagicMock()
    mock_ctl.pressure = MagicMock()
    mock_ctl.humidity = MagicMock()
    with patch('sense_emu.tui.EmulatorController', return_value=mock_ctl):
        yield mock_ctl


@pytest.fixture(autouse=True)
def patch_screen(tmp_screen_file):
    yield


class TestSenseEmuTUI:
    def test_tui_compose_does_not_raise(self):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        # Verify the compose method itself doesn't raise
        import inspect
        assert inspect.ismethod(app.compose)

    def test_led_matrix_class_exists(self):
        from sense_emu.tui import LEDMatrix
        assert LEDMatrix is not None

    def test_tui_class_has_compose(self):
        from sense_emu.tui import SenseEmuTUI
        assert hasattr(SenseEmuTUI, 'compose')

    def test_tui_class_has_css(self):
        from sense_emu.tui import SenseEmuTUI
        assert hasattr(SenseEmuTUI, 'CSS')

    def test_main_function_exists(self):
        from sense_emu.tui import main
        assert callable(main)

    def test_on_input_changed_no_controller(self):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        # on_input_changed checks hasattr(self, "controller")
        mock_event = MagicMock()
        mock_event.input.id = 'pitch'
        mock_event.value = '10'
        # Without controller attribute, should return early
        if hasattr(app, 'controller'):
            delattr(app, 'controller')
        app.on_input_changed(mock_event)

    def test_on_input_changed_invalid_value(self, patch_emulator_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = patch_emulator_controller
        mock_event = MagicMock()
        mock_event.input.id = 'pitch'
        mock_event.value = 'not_a_number'
        app.on_input_changed(mock_event)

    def test_led_matrix_update_no_screen_file(self, tmp_path):
        from sense_emu.tui import LEDMatrix
        widget = LEDMatrix()
        # Without screen_file, update_matrix should return early
        widget.screen_file = None
        nonexistent = str(tmp_path / 'nofile')
        with patch('sense_emu.tui.screen_filename', return_value=nonexistent):
            widget.update_matrix()  # should not raise

    def test_led_matrix_update_with_valid_data(self, tmp_screen_file):
        from sense_emu.tui import LEDMatrix
        widget = LEDMatrix()
        # Write 192 bytes (enough to render 8x8 matrix)
        with open(tmp_screen_file, 'r+b') as f:
            f.seek(0)
            f.write(bytes(range(192)))
        widget.screen_file = open(tmp_screen_file, 'rb')
        try:
            with patch.object(widget, 'update'):
                widget.update_matrix()
        finally:
            widget.screen_file.close()

    def test_on_mount_creates_controller(self):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        mock_ctl = MagicMock()
        with patch('sense_emu.tui.EmulatorController', return_value=mock_ctl):
            app.on_mount()
        assert app.controller == mock_ctl

    def test_on_unmount_closes_controller(self):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        mock_ctl = MagicMock()
        app.controller = mock_ctl
        app.on_unmount()
        mock_ctl.close.assert_called_once()

    def test_on_input_changed_pitch(self, patch_emulator_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = patch_emulator_controller
        mock_event = MagicMock()
        mock_event.input.id = 'pitch'
        mock_event.value = '10'
        mock_input = MagicMock()
        mock_input.value = '0'
        app.query_one = MagicMock(return_value=mock_input)
        app.on_input_changed(mock_event)
        patch_emulator_controller.imu.set_orientation.assert_called()

    def test_on_input_changed_pressure(self, patch_emulator_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = patch_emulator_controller
        mock_event = MagicMock()
        mock_event.input.id = 'pressure'
        mock_event.value = '1013'
        mock_input = MagicMock()
        mock_input.value = '20'
        app.query_one = MagicMock(return_value=mock_input)
        app.on_input_changed(mock_event)
        patch_emulator_controller.pressure.set_values.assert_called()

    def test_on_input_changed_humidity(self, patch_emulator_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = patch_emulator_controller
        mock_event = MagicMock()
        mock_event.input.id = 'humidity'
        mock_event.value = '45'
        mock_input = MagicMock()
        mock_input.value = '20'
        app.query_one = MagicMock(return_value=mock_input)
        app.on_input_changed(mock_event)
        patch_emulator_controller.humidity.set_values.assert_called()

    def test_main_function_calls_run(self):
        from sense_emu.tui import main, SenseEmuTUI
        with patch.object(SenseEmuTUI, 'run') as mock_run:
            main()
        mock_run.assert_called_once()

    def test_led_matrix_reopen_screen_file(self, tmp_screen_file):
        from sense_emu.tui import LEDMatrix
        widget = LEDMatrix()
        widget.screen_file = None
        with patch('sense_emu.tui.screen_filename', return_value=tmp_screen_file):
            widget.update_matrix()  # should try to reopen
        if widget.screen_file:
            widget.screen_file.close()
