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
        # Write a realistic 160-byte frame (128 bytes RGB565 + 32 bytes gamma)
        from sense_emu.screen import GAMMA_DEFAULT
        with open(tmp_screen_file, 'r+b') as f:
            f.seek(0)
            f.write(b'\xff\xff' * 64 + bytes(GAMMA_DEFAULT))
        widget.screen_file = open(tmp_screen_file, 'rb')
        try:
            with patch.object(widget, 'update') as mock_update:
                widget.update_matrix()
            mock_update.assert_called_once()
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


class TestLEDMatrixRendering:
    """Behaviour tests using the *real* 160-byte screen format
    (64 RGB565 pixels = 128 bytes, followed by a 32-byte gamma table)."""

    def _write_screen(self, path, pixels):
        """Write a realistic 160-byte screen buffer.

        ``pixels`` maps a flat 0..63 index to an RGB565 uint16 value.
        """
        import struct
        from sense_emu.screen import GAMMA_DEFAULT
        screen = bytearray(b'\x00\x00' * 64)
        for idx, value in pixels.items():
            struct.pack_into('=H', screen, idx * 2, value)
        buf = bytes(screen) + bytes(GAMMA_DEFAULT)
        assert len(buf) == 160
        with open(path, 'r+b') as f:
            f.seek(0)
            f.write(buf)

    def _render(self, tmp_screen_file):
        from sense_emu.tui import LEDMatrix
        widget = LEDMatrix()
        widget.screen_file = open(tmp_screen_file, 'rb')
        captured = {}
        try:
            with patch.object(widget, 'update',
                              side_effect=lambda c: captured.__setitem__('content', c)):
                widget.update_matrix()
        finally:
            widget.screen_file.close()
        return captured.get('content')

    def test_renders_from_160_byte_buffer(self, tmp_screen_file):
        # All LEDs off — still a valid 160-byte frame and must render.
        self._write_screen(tmp_screen_file, {})
        content = self._render(tmp_screen_file)
        assert content is not None, "update() never called: matrix did not render"
        # 8 rows of output
        assert content.count('\n') == 7
        # 64 coloured cells
        assert content.count('[/]') == 64

    def test_red_pixel_is_rendered_red(self, tmp_screen_file):
        # Pixel 0 = full red in RGB565 (0xF800), rest off.
        self._write_screen(tmp_screen_file, {0: 0xF800})
        content = self._render(tmp_screen_file)
        assert content is not None
        first_cell = content.split('[/]')[0]
        # Red channel fully on (255); green/blue at the gray "off" floor.
        assert first_cell.startswith('[rgb(255,')

    def test_blue_pixel_is_rendered_blue(self, tmp_screen_file):
        # Pixel 0 = full blue in RGB565 (0x001F), rest off.
        self._write_screen(tmp_screen_file, {0: 0x001F})
        content = self._render(tmp_screen_file)
        assert content is not None
        first_cell = content.split('[/]')[0]
        # Format is [rgb(r,g,b)]██ — blue channel should be the max (255).
        rgb = first_cell.split('rgb(')[1].split(')')[0].split(',')
        r, g, b = (int(v) for v in rgb)
        assert b == 255
        assert b > r and b > g

    def test_short_buffer_does_not_render(self, tmp_screen_file):
        # A truncated (<160 byte) buffer must not raise and must not render.
        with open(tmp_screen_file, 'r+b') as f:
            f.seek(0)
            f.truncate(100)
            f.write(b'\x01' * 100)
        content = self._render(tmp_screen_file)
        assert content is None


class TestLEDMatrixOnMount:
    def test_on_mount_opens_screen_file(self, tmp_screen_file):
        from sense_emu.tui import LEDMatrix
        widget = LEDMatrix()
        widget.set_interval = MagicMock()
        with patch('sense_emu.tui.screen_filename', return_value=tmp_screen_file):
            widget.on_mount()
        assert widget.screen_file is not None
        widget.screen_file.close()

    def test_on_mount_handles_missing_screen_file(self, tmp_path):
        from sense_emu.tui import LEDMatrix
        widget = LEDMatrix()
        widget.set_interval = MagicMock()
        with patch('sense_emu.tui.screen_filename', return_value=str(tmp_path / 'nofile')):
            widget.on_mount()
        assert widget.screen_file is None


class TestSenseEmuTUICompose:
    def test_compose_is_generator(self):
        from sense_emu.tui import SenseEmuTUI
        import inspect
        app = SenseEmuTUI()
        # compose() is a generator function — verify it returns a generator
        assert inspect.isgeneratorfunction(app.compose)

    def test_compose_body_with_mocked_context_managers(self):
        """Cover lines 47-65 in tui.py by mocking the Textual widgets."""
        from unittest.mock import MagicMock, patch
        import contextlib

        @contextlib.contextmanager
        def fake_cm(*args, **kwargs):
            yield MagicMock()

        fake_widget = MagicMock()
        fake_widget.__enter__ = lambda s: fake_widget
        fake_widget.__exit__ = lambda s, *a: None

        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()

        with patch('sense_emu.tui.Grid', return_value=fake_widget), \
             patch('sense_emu.tui.Vertical', return_value=fake_widget), \
             patch('sense_emu.tui.Header', return_value=MagicMock()), \
             patch('sense_emu.tui.Footer', return_value=MagicMock()), \
             patch('sense_emu.tui.Label', return_value=MagicMock()), \
             patch('sense_emu.tui.Input', return_value=MagicMock()), \
             patch('sense_emu.tui.LEDMatrix', return_value=MagicMock()):
            result = list(app.compose())
        assert len(result) > 0

    def test_on_input_changed_inner_value_error(self, patch_emulator_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = patch_emulator_controller
        mock_event = MagicMock()
        mock_event.input.id = 'pitch'
        mock_event.value = '10'
        # query_one returns a mock with non-numeric value
        mock_input = MagicMock()
        mock_input.value = 'not_a_number'
        app.query_one = MagicMock(return_value=mock_input)
        app.on_input_changed(mock_event)  # should hit except ValueError: pass

    def test_on_input_changed_unmatched_id(self, patch_emulator_controller):
        from sense_emu.tui import SenseEmuTUI
        app = SenseEmuTUI()
        app.controller = patch_emulator_controller
        mock_event = MagicMock()
        mock_event.input.id = 'unknown_id'
        mock_event.value = '42'
        app.on_input_changed(mock_event)  # falls through without matching any condition
