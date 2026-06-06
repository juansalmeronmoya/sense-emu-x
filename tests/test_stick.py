import time
import struct
import socket
import pytest
from unittest.mock import MagicMock, patch
from sense_emu.stick import (
    InputEvent, SenseStick, StickServer,
    DIRECTION_UP, DIRECTION_DOWN, DIRECTION_LEFT, DIRECTION_RIGHT, DIRECTION_MIDDLE,
    ACTION_PRESSED, ACTION_RELEASED, ACTION_HELD,
    stick_address,
)


class TestConstants:
    def test_directions(self):
        assert DIRECTION_UP == 'up'
        assert DIRECTION_DOWN == 'down'
        assert DIRECTION_LEFT == 'left'
        assert DIRECTION_RIGHT == 'right'
        assert DIRECTION_MIDDLE == 'middle'

    def test_actions(self):
        assert ACTION_PRESSED == 'pressed'
        assert ACTION_RELEASED == 'released'
        assert ACTION_HELD == 'held'


class TestInputEvent:
    def test_fields(self):
        evt = InputEvent(timestamp=1.0, direction=DIRECTION_UP, action=ACTION_PRESSED)
        assert evt.timestamp == 1.0
        assert evt.direction == DIRECTION_UP
        assert evt.action == ACTION_PRESSED

    def test_namedtuple_fields(self):
        assert InputEvent._fields == ('timestamp', 'direction', 'action')


class TestStickAddress:
    def test_returns_three_tuple(self):
        family, sock_type, addr = stick_address()
        assert isinstance(addr, str)


class TestStickServer:
    def test_init_and_close(self, tmp_stick_addr):
        server = StickServer()
        server.close()

    def test_close_is_idempotent(self, tmp_stick_addr):
        server = StickServer()
        server.close()

    def test_send_enqueues(self, tmp_stick_addr):
        server = StickServer()
        buf = b'\x00' * 16
        server.send(buf)  # should not raise
        server.close()


class TestSenseStickWrapCallback:
    def _make_stick(self):
        stick = SenseStick.__new__(SenseStick)
        from threading import Event
        stick._callbacks = {}
        stick._callback_thread = None
        stick._callback_event = Event()
        stick._stick_file = MagicMock()
        return stick

    def test_wrap_none_returns_none(self):
        stick = self._make_stick()
        assert stick._wrap_callback(None) is None

    def test_wrap_non_callable_raises(self):
        stick = self._make_stick()
        with pytest.raises(ValueError):
            stick._wrap_callback('not_callable')

    def test_wrap_zero_arg_callable(self):
        stick = self._make_stick()
        called = []
        def fn(): called.append(True)
        wrapped = stick._wrap_callback(fn)
        wrapped(InputEvent(0.0, DIRECTION_UP, ACTION_PRESSED))
        assert called == [True]

    def test_wrap_one_arg_callable(self):
        stick = self._make_stick()
        received = []
        def fn(event): received.append(event)
        wrapped = stick._wrap_callback(fn)
        evt = InputEvent(0.0, DIRECTION_UP, ACTION_PRESSED)
        wrapped(evt)
        assert received == [evt]

    def test_wrap_two_mandatory_args_raises(self):
        stick = self._make_stick()
        with pytest.raises(ValueError):
            stick._wrap_callback(lambda x, y: None)


class TestSenseStickRead:
    def _make_event_buf(self, sec, usec, type_, code, value):
        fmt = 'llHHI'
        return struct.pack(fmt, sec, usec, type_, code, value)

    def test_read_key_up_pressed(self):
        stick = SenseStick.__new__(SenseStick)
        from threading import Event
        stick._callbacks = {}
        stick._callback_thread = None
        stick._callback_event = Event()
        EV_KEY = 0x01
        KEY_UP = 103
        STATE_PRESS = 1
        buf = self._make_event_buf(1000, 500000, EV_KEY, KEY_UP, STATE_PRESS)
        mock_file = MagicMock()
        mock_file.read.return_value = buf
        stick._stick_file = mock_file
        event = stick._read()
        assert event is not None
        assert event.direction == DIRECTION_UP
        assert event.action == ACTION_PRESSED

    def test_read_non_key_event_returns_none(self):
        stick = SenseStick.__new__(SenseStick)
        from threading import Event
        stick._callbacks = {}
        stick._callback_thread = None
        stick._callback_event = Event()
        EV_SYN = 0x00
        buf = self._make_event_buf(1000, 0, EV_SYN, 0, 0)
        mock_file = MagicMock()
        mock_file.read.return_value = buf
        stick._stick_file = mock_file
        assert stick._read() is None


class TestSenseStickCallbacks:
    def _make_stick(self):
        stick = SenseStick.__new__(SenseStick)
        from threading import Event
        stick._callbacks = {}
        stick._callback_thread = None
        stick._callback_event = Event()
        stick._stick_file = MagicMock()
        return stick

    def test_direction_up_setter(self):
        stick = self._make_stick()
        fn = lambda: None
        stick.direction_up = fn
        assert DIRECTION_UP in stick._callbacks

    def test_direction_down_setter(self):
        stick = self._make_stick()
        stick.direction_down = lambda: None
        assert DIRECTION_DOWN in stick._callbacks

    def test_direction_left_setter(self):
        stick = self._make_stick()
        stick.direction_left = lambda: None
        assert DIRECTION_LEFT in stick._callbacks

    def test_direction_right_setter(self):
        stick = self._make_stick()
        stick.direction_right = lambda: None
        assert DIRECTION_RIGHT in stick._callbacks

    def test_direction_middle_setter(self):
        stick = self._make_stick()
        stick.direction_middle = lambda: None
        assert DIRECTION_MIDDLE in stick._callbacks

    def test_direction_any_setter(self):
        stick = self._make_stick()
        stick.direction_any = lambda: None
        assert '*' in stick._callbacks

    def test_direction_up_getter_none_by_default(self):
        stick = self._make_stick()
        assert stick.direction_up is None

    def test_direction_down_getter_none_by_default(self):
        stick = self._make_stick()
        assert stick.direction_down is None

    def test_direction_left_getter_none_by_default(self):
        stick = self._make_stick()
        assert stick.direction_left is None

    def test_direction_right_getter_none_by_default(self):
        stick = self._make_stick()
        assert stick.direction_right is None

    def test_direction_middle_getter_none_by_default(self):
        stick = self._make_stick()
        assert stick.direction_middle is None

    def test_direction_any_getter_none_by_default(self):
        stick = self._make_stick()
        assert stick.direction_any is None

    def test_set_callback_to_none_removes(self):
        stick = self._make_stick()
        stick.direction_up = lambda: None
        stick.direction_up = None
        assert stick._callbacks.get(DIRECTION_UP) is None

    def test_close_clears_callbacks_and_file(self):
        stick = self._make_stick()
        stick._callbacks[DIRECTION_UP] = lambda: None
        stick.close()
        assert stick._stick_file is None

    def test_context_manager(self):
        stick = self._make_stick()
        with stick:
            pass
        assert stick._stick_file is None

    def test_wrap_builtin_callable(self):
        stick = self._make_stick()
        wrapped = stick._wrap_callback(print)
        evt = InputEvent(0.0, DIRECTION_UP, ACTION_PRESSED)
        wrapped(evt)  # print() with no args is valid

    def test_get_events_empty(self):
        stick = self._make_stick()
        with patch.object(stick, '_wait', return_value=False):
            result = stick.get_events()
        assert result == []

    def test_get_events_with_event(self):
        stick = self._make_stick()
        evt = InputEvent(1.0, DIRECTION_UP, ACTION_PRESSED)
        calls = [True, False]
        def mock_wait(timeout=None):
            return calls.pop(0) if calls else False
        with patch.object(stick, '_wait', side_effect=mock_wait), \
             patch.object(stick, '_read', return_value=evt):
            result = stick.get_events()
        assert result == [evt]

    def test_wait_for_event_returns_event(self):
        stick = self._make_stick()
        evt = InputEvent(1.0, DIRECTION_UP, ACTION_PRESSED)
        wait_calls = [True]
        def mock_wait(timeout=None):
            return wait_calls.pop(0) if wait_calls else False
        with patch.object(stick, '_wait', side_effect=mock_wait), \
             patch.object(stick, '_read', return_value=evt):
            result = stick.wait_for_event()
        assert result == evt

    def test_wait_returns_false_for_timeout(self):
        stick = self._make_stick()
        with patch('select.select', return_value=([], [], [])):
            result = stick._wait(0.0)
        assert result is False
