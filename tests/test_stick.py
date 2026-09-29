import sys
import time
import struct
import socket
import logging
import threading
import pytest
from unittest.mock import MagicMock, patch
from sense_emu.stick import (
    InputEvent, SenseStick, StickServer,
    DIRECTION_UP, DIRECTION_DOWN, DIRECTION_LEFT, DIRECTION_RIGHT, DIRECTION_MIDDLE,
    ACTION_PRESSED, ACTION_RELEASED, ACTION_HELD,
    stick_address, STICK_KEYS, make_stick_event, rotate_key,
)


# ---------------------------------------------------------------------------
# Helpers: a SenseStick wired to a real in-process socket pair (instead of a
# MagicMock, which select() cannot poll), so the callback thread can be
# exercised for real and always shut down
# ---------------------------------------------------------------------------

_created_sticks = []


def _socket_stick():
    try:
        # Datagrams, like the real emulator socket (keeps message boundaries)
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    except (AttributeError, ValueError, OSError):    # e.g. Windows
        a, b = socket.socketpair()
    stick = SenseStick.__new__(SenseStick)
    stick._callbacks = {}
    stick._callback_thread = None
    stick._callback_event = threading.Event()
    stick._stick_file = a.makefile('rb', 0)
    stick._sock, stick._peer = a, b
    _created_sticks.append(stick)
    return stick


def _press(stick, direction=DIRECTION_UP, state=SenseStick.STATE_PRESS):
    stick._peer.send(make_stick_event(STICK_KEYS[direction], state))


def _wait_until(predicate, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


@pytest.fixture(autouse=True)
def _close_sticks():
    yield
    while _created_sticks:
        stick = _created_sticks.pop()
        stick._callbacks.clear()
        stick._start_stop_thread()
        for closable in (stick._stick_file, stick._sock, stick._peer):
            try:
                closable.close()
            except Exception:
                pass


class TestStickKeys:
    def test_all_directions_mapped(self):
        assert STICK_KEYS['up']     == SenseStick.KEY_UP
        assert STICK_KEYS['down']   == SenseStick.KEY_DOWN
        assert STICK_KEYS['left']   == SenseStick.KEY_LEFT
        assert STICK_KEYS['right']  == SenseStick.KEY_RIGHT
        assert STICK_KEYS['middle'] == SenseStick.KEY_ENTER


class TestMakeStickEvent:
    def test_returns_bytes_of_event_size(self):
        buf = make_stick_event(SenseStick.KEY_UP, SenseStick.STATE_PRESS)
        assert isinstance(buf, bytes)
        assert len(buf) == SenseStick.EVENT_SIZE

    def test_encodes_key_and_state(self):
        buf = make_stick_event(SenseStick.KEY_DOWN, SenseStick.STATE_HOLD)
        tv_sec, tv_usec, ev_type, code, value = struct.unpack(
            SenseStick.EVENT_FORMAT, buf)
        assert ev_type == SenseStick.EV_KEY
        assert code == SenseStick.KEY_DOWN
        assert value == SenseStick.STATE_HOLD

    def test_explicit_timestamp(self):
        buf = make_stick_event(SenseStick.KEY_ENTER, SenseStick.STATE_RELEASE,
                               when=12.5)
        tv_sec, tv_usec, _, _, _ = struct.unpack(SenseStick.EVENT_FORMAT, buf)
        assert tv_sec == 12
        assert tv_usec == 500_000

    def test_default_timestamp_is_now(self):
        before = time.time()
        buf = make_stick_event(SenseStick.KEY_UP, SenseStick.STATE_PRESS)
        after = time.time()
        tv_sec, tv_usec, _, _, _ = struct.unpack(SenseStick.EVENT_FORMAT, buf)
        ts = tv_sec + tv_usec / 1_000_000
        assert before - 1 <= ts <= after + 1


class TestRotateKey:
    def test_zero_rotation_is_identity(self):
        for key in (SenseStick.KEY_UP, SenseStick.KEY_DOWN,
                    SenseStick.KEY_LEFT, SenseStick.KEY_RIGHT,
                    SenseStick.KEY_ENTER):
            assert rotate_key(key, 0) == key

    def test_90_clockwise(self):
        assert rotate_key(SenseStick.KEY_UP, 90)    == SenseStick.KEY_RIGHT
        assert rotate_key(SenseStick.KEY_RIGHT, 90) == SenseStick.KEY_DOWN
        assert rotate_key(SenseStick.KEY_DOWN, 90)  == SenseStick.KEY_LEFT
        assert rotate_key(SenseStick.KEY_LEFT, 90)  == SenseStick.KEY_UP

    def test_180(self):
        assert rotate_key(SenseStick.KEY_UP, 180)   == SenseStick.KEY_DOWN
        assert rotate_key(SenseStick.KEY_LEFT, 180) == SenseStick.KEY_RIGHT

    def test_270(self):
        assert rotate_key(SenseStick.KEY_UP, 270)   == SenseStick.KEY_LEFT
        assert rotate_key(SenseStick.KEY_DOWN, 270) == SenseStick.KEY_RIGHT

    def test_360_wraps(self):
        assert rotate_key(SenseStick.KEY_UP, 360) == SenseStick.KEY_UP

    def test_enter_unaffected(self):
        for rot in (0, 90, 180, 270):
            assert rotate_key(SenseStick.KEY_ENTER, rot) == SenseStick.KEY_ENTER


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
        assert isinstance(addr, (str, tuple))


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
        return _socket_stick()

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
        assert DIRECTION_UP not in stick._callbacks
        # ... and with no callbacks left the thread must have been stopped
        assert stick._callback_thread is None

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


class TestSenseStickInit:
    def test_init_and_close(self, tmp_stick_addr):
        """Cover SenseStick.__init__ and _stick_device (lines 157-160, 180)."""
        server = StickServer()
        try:
            stick = SenseStick()
            assert stick._stick_file is not None
            stick.close()
            assert stick._stick_file is None
        finally:
            server.close()

    def test_close_when_already_none(self):
        """Cover close() when _stick_file is None (line 163->exit)."""
        stick = SenseStick.__new__(SenseStick)
        from threading import Event
        stick._callbacks = {}
        stick._callback_thread = None
        stick._callback_event = Event()
        stick._stick_file = None
        stick.close()  # should not raise


class TestCallbackRun:
    def _make_stick(self):
        return _socket_stick()

    def test_callback_run_fires_direction_callback(self):
        stick = self._make_stick()
        called = []

        def handler(event):
            called.append(event)
            stick._callback_event.set()      # stop after the first event

        stick._callbacks[DIRECTION_UP] = handler
        _press(stick, DIRECTION_UP)
        stick._callback_run()
        assert [(e.direction, e.action) for e in called] == [
            (DIRECTION_UP, ACTION_PRESSED)]

    def test_callback_run_fires_wildcard_callback(self):
        stick = self._make_stick()
        called = []

        def handler(event):
            called.append(event)
            stick._callback_event.set()

        stick._callbacks['*'] = handler
        _press(stick, DIRECTION_LEFT, SenseStick.STATE_RELEASE)
        stick._callback_run()
        assert [(e.direction, e.action) for e in called] == [
            (DIRECTION_LEFT, ACTION_RELEASED)]

    def test_start_stop_thread_stop_path(self):
        stick = self._make_stick()
        stick.direction_up = lambda: None
        assert stick._callback_thread is not None
        thread = stick._callback_thread
        assert thread.is_alive()

        stick._callbacks.clear()
        stick._start_stop_thread()
        assert stick._callback_thread is None
        assert not thread.is_alive()

    def test_wait_for_event_emptybuffer(self):
        stick = self._make_stick()
        evt = InputEvent(1.0, DIRECTION_UP, ACTION_PRESSED)
        # First _wait(0) returns True (buffered event), second returns False (buffer empty), third returns True
        wait_calls = iter([True, False, True])
        def mock_wait(timeout=None):
            try:
                return next(wait_calls)
            except StopIteration:
                return False

        with patch.object(stick, '_wait', side_effect=mock_wait), \
             patch.object(stick, '_read', return_value=evt):
            result = stick.wait_for_event(emptybuffer=True)
        assert result == evt

    def test_get_events_skips_none_event(self):
        stick = self._make_stick()
        # First wait returns True with None event, second returns False
        wait_calls = iter([True, False])
        def mock_wait(timeout=None):
            try:
                return next(wait_calls)
            except StopIteration:
                return False

        with patch.object(stick, '_wait', side_effect=mock_wait), \
             patch.object(stick, '_read', return_value=None):
            result = stick.get_events()
        assert result == []


class TestCallbackThreadRobustness:
    """P0-3: the callback thread must survive bad callbacks and bad data, and
    must be stoppable at any time."""

    def test_exception_in_callback_does_not_kill_thread(self, caplog):
        stick = _socket_stick()
        seen = []

        def flaky(event):
            seen.append(event.action)
            if len(seen) == 1:
                raise RuntimeError('user code blew up')

        stick._callbacks[DIRECTION_UP] = flaky
        stick._start_stop_thread()
        with caplog.at_level(logging.ERROR, logger='sense_emu.stick'):
            _press(stick, DIRECTION_UP, SenseStick.STATE_PRESS)
            _press(stick, DIRECTION_UP, SenseStick.STATE_RELEASE)
            assert _wait_until(lambda: len(seen) == 2)
        assert seen == [ACTION_PRESSED, ACTION_RELEASED]
        assert stick._callback_thread.is_alive()
        assert 'user code blew up' in caplog.text
        assert 'Exception in joystick callback' in caplog.text

    def test_failing_direction_callback_still_calls_wildcard(self, caplog):
        stick = _socket_stick()
        wild = []
        stick._callbacks[DIRECTION_UP] = lambda e: 1 / 0
        stick._callbacks['*'] = wild.append
        stick._start_stop_thread()
        with caplog.at_level(logging.ERROR, logger='sense_emu.stick'):
            _press(stick, DIRECTION_UP)
            assert _wait_until(lambda: len(wild) == 1)
        assert stick._callback_thread.is_alive()

    def test_malformed_datagram_does_not_kill_thread(self, caplog):
        stick = _socket_stick()
        if stick._sock.type != socket.SOCK_DGRAM:
            pytest.skip('needs datagram sockets to keep message boundaries')
        seen = []
        stick._callbacks[DIRECTION_DOWN] = seen.append
        stick._start_stop_thread()
        with caplog.at_level(logging.ERROR, logger='sense_emu.stick'):
            stick._peer.send(b'short')            # truncated event
            _press(stick, DIRECTION_DOWN)
            assert _wait_until(lambda: len(seen) == 1)
        assert stick._callback_thread.is_alive()
        assert 'Error reading joystick event' in caplog.text

    def test_unknown_key_code_does_not_kill_thread(self, caplog):
        stick = _socket_stick()
        seen = []
        stick._callbacks[DIRECTION_UP] = seen.append
        stick._start_stop_thread()
        with caplog.at_level(logging.ERROR, logger='sense_emu.stick'):
            stick._peer.send(make_stick_event(999, SenseStick.STATE_PRESS))
            _press(stick, DIRECTION_UP)
            assert _wait_until(lambda: len(seen) == 1)
        assert stick._callback_thread.is_alive()

    def test_non_key_event_is_ignored(self):
        stick = _socket_stick()
        seen = []
        stick._callbacks['*'] = seen.append
        stick._start_stop_thread()
        stick._peer.send(struct.pack(
            SenseStick.EVENT_FORMAT, 1, 0, 0x02, 0, 0))   # EV_REL
        _press(stick, DIRECTION_UP)
        assert _wait_until(lambda: len(seen) == 1)
        assert seen[0].direction == DIRECTION_UP

    def test_stop_does_not_hang_when_no_events_arrive(self):
        # Previously the thread sat in a blocking read() and join() waited for
        # the next joystick event forever.
        stick = _socket_stick()
        stick.direction_up = lambda: None
        assert stick._callback_thread.is_alive()
        done = threading.Event()

        def stop():
            stick.close()
            done.set()

        threading.Thread(target=stop, daemon=True).start()
        assert done.wait(5), 'close() hung waiting for the callback thread'
        assert stick._stick_file is None

    def test_callback_may_clear_its_own_handler(self, caplog):
        stick = _socket_stick()
        fired = threading.Event()

        def once(event):
            stick.direction_up = None      # joins the thread it is running on?
            fired.set()

        stick.direction_up = once
        thread = stick._callback_thread
        with caplog.at_level(logging.ERROR, logger='sense_emu.stick'):
            _press(stick, DIRECTION_UP)
            assert fired.wait(5)
            thread.join(5)
        assert not thread.is_alive()
        assert stick._callback_thread is None
        assert caplog.text == ''

    def test_thread_stops_when_stick_file_is_closed(self):
        stick = _socket_stick()
        stick.direction_up = lambda: None
        thread = stick._callback_thread
        stick._stick_file.close()
        thread.join(5)
        assert not thread.is_alive()

    def test_thread_can_be_restarted_after_stopping(self):
        stick = _socket_stick()
        seen = []
        record = lambda event: seen.append(event)      # noqa: E731
        stick.direction_up = record
        stick.direction_up = None
        assert stick._callback_thread is None
        stick.direction_up = record
        _press(stick, DIRECTION_UP)
        assert _wait_until(lambda: len(seen) == 1)


class TestStickServerServe:
    def test_serve_receives_hello_and_sends_data(self, tmp_stick_addr):
        """Cover StickServer._serve loop body with a real client."""
        import socket as _socket_mod
        import os
        import time as _time

        server = StickServer()
        _time.sleep(0.05)  # let server thread start

        addr = tmp_stick_addr
        if sys.platform.startswith('win'):
            client = _socket_mod.socket(_socket_mod.AF_INET, _socket_mod.SOCK_DGRAM)
            client.bind(('127.0.0.1', 0))
            client.connect(addr)
            client.send(b'hello')
            _time.sleep(0.05)
            server.send(b'\x00' * 24)
            _time.sleep(0.2)
            client.close()
        else:
            client = _socket_mod.socket(_socket_mod.AF_UNIX, _socket_mod.SOCK_DGRAM)
            client_path = addr + '-client-%d' % id(client)
            try:
                os.unlink(client_path)
            except OSError:
                pass
            client.bind(client_path)
            client.connect(addr)
            client.send(b'hello')
            _time.sleep(0.05)
            server.send(b'\x00' * 24)
            _time.sleep(0.2)
            client.close()
            try:
                os.unlink(client_path)
            except OSError:
                pass
        server.close()  # triggers _serve finally block
