import os
import sys
import time
import pytest
from unittest.mock import patch
from sense_emu.lock import (
    EmulatorLock, pid_exists, lock_filename, process_start_time, _LOCK_MAGIC,
)


class TestPidExists:
    def test_current_process_exists(self):
        assert pid_exists(os.getpid()) is True

    def test_dead_process_does_not_exist(self):
        assert pid_exists(999999999) is False

    def test_pid_zero(self):
        # PID 0 is special — kernel; always considered "exists"
        assert pid_exists(0) is True


class TestLockFilename:
    def test_returns_string(self):
        result = lock_filename()
        assert isinstance(result, str)
        assert 'rpi-sense-emu-pid' in result


class TestEmulatorLock:
    def test_acquire_writes_pid(self, tmp_lock_file):
        lock = EmulatorLock('test')
        lock.acquire()
        assert os.path.exists(tmp_lock_file)
        with open(tmp_lock_file, 'r') as f:
            pid = int(f.readline().strip())
        assert pid == os.getpid()
        lock.release()

    def test_release_removes_file(self, tmp_lock_file):
        lock = EmulatorLock('test')
        lock.acquire()
        lock.release()
        assert not os.path.exists(tmp_lock_file)

    def test_mine_after_acquire(self, tmp_lock_file):
        lock = EmulatorLock('test')
        lock.acquire()
        assert lock.mine is True
        lock.release()

    def test_mine_after_release(self, tmp_lock_file):
        lock = EmulatorLock('test')
        lock.acquire()
        lock.release()
        assert lock.mine is False

    def test_context_manager(self, tmp_lock_file):
        with EmulatorLock('test') as lock:
            assert lock.mine is True
        assert not os.path.exists(tmp_lock_file)

    def test_stale_lock_broken_on_acquire(self, tmp_lock_file):
        # Write a stale lock with a dead PID
        with open(tmp_lock_file, 'w') as f:
            f.write('999999999\n%s\n' % _LOCK_MAGIC)
        lock = EmulatorLock('test')
        lock.acquire()  # should break stale lock and acquire
        assert lock.mine is True
        lock.release()

    def test_wait_timeout_false_when_nobody_holds(self, tmp_lock_file):
        lock = EmulatorLock('test')
        result = lock.wait(timeout=0.1)
        assert result is False

    def test_wait_returns_true_when_held(self, tmp_lock_file):
        # Write our own PID as if we hold the lock
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n%s\n' % (os.getpid(), _LOCK_MAGIC))
        lock = EmulatorLock('test')
        result = lock.wait(timeout=0.2)
        assert result is True
        lock.release()

    def test_release_nonexistent_file_is_noop(self, tmp_lock_file):
        lock = EmulatorLock('test')
        lock.release()  # file doesn't exist — should not raise

    def test_read_pid_returns_none_for_missing_file(self, tmp_lock_file):
        lock = EmulatorLock('test')
        assert lock._read_pid() is None

    def test_read_pid_returns_none_for_corrupt_file(self, tmp_lock_file):
        with open(tmp_lock_file, 'w') as f:
            f.write('not_a_number\n')
        lock = EmulatorLock('test')
        assert lock._read_pid() is None

    def test_is_held_false_when_no_file(self, tmp_lock_file):
        lock = EmulatorLock('test')
        assert lock._is_held() is False

    def test_is_held_true_when_file_exists(self, tmp_lock_file):
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n%s\n' % (os.getpid(), _LOCK_MAGIC))
        lock = EmulatorLock('test')
        assert lock._is_held() is True
        lock.release()

    def test_is_stale_false_when_no_file(self, tmp_lock_file):
        lock = EmulatorLock('test')
        assert lock._is_stale() is False

    def test_is_stale_false_for_live_pid(self, tmp_lock_file):
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n%s\n' % (os.getpid(), _LOCK_MAGIC))
        lock = EmulatorLock('test')
        assert lock._is_stale() is False
        lock.release()

    def test_is_stale_true_for_dead_pid(self, tmp_lock_file):
        with open(tmp_lock_file, 'w') as f:
            f.write('999999999\n%s\n' % _LOCK_MAGIC)
        lock = EmulatorLock('test')
        assert lock._is_stale() is True

    def test_break_lock_removes_file(self, tmp_lock_file):
        with open(tmp_lock_file, 'w') as f:
            f.write('123\n')
        lock = EmulatorLock('test')
        lock._break_lock()
        assert not os.path.exists(tmp_lock_file)

    def test_write_pid_creates_file(self, tmp_lock_file):
        lock = EmulatorLock('test')
        lock.acquire()
        assert os.path.exists(tmp_lock_file)
        with open(tmp_lock_file) as f:
            assert int(f.readline().strip()) == os.getpid()
            assert f.readline().strip() == _LOCK_MAGIC
        lock.release()


class TestLockFilenameWindows:
    def test_lock_filename_on_noshm_system(self, tmp_path):
        # Simulate a system where /dev/shm doesn't exist
        with patch('os.path.exists', return_value=False):
            result = lock_filename()
        assert 'rpi-sense-emu-pid' in result


class TestPidExistsEPERM:
    @pytest.mark.skipif(sys.platform == 'win32', reason='Uses os.kill, not available on Windows pid_exists')
    def test_eperm_means_exists(self):
        import errno
        with patch('os.kill', side_effect=OSError(errno.EPERM, 'not permitted')):
            from sense_emu.lock import pid_exists
            assert pid_exists(1) is True


import errno
from sense_emu.lock import pid_exists, lock_filename, EmulatorLock, _LOCK_MAGIC


class TestPidExistsRaise:
    @pytest.mark.skipif(sys.platform == 'win32', reason='Uses os.kill, not available on Windows pid_exists')
    def test_raises_on_unexpected_oserror(self):
        with patch('os.kill', side_effect=OSError(errno.EACCES, 'permission denied')):
            with pytest.raises(OSError):
                pid_exists(1)


class TestLockFilenameWindowsExtended:
    def test_windows_path(self):
        with patch('sys.platform', 'win32'), \
             patch.dict('os.environ', {'TEMP': '/tmp/wintemp'}):
            result = lock_filename()
        assert 'rpi-sense-emu-pid' in result


class TestLockWaitNoneTimeout:
    def test_wait_none_timeout_returns_true_if_held(self, tmp_lock_file):
        import os
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n%s\n' % (os.getpid(), _LOCK_MAGIC))
        lock = EmulatorLock('test')
        result = lock.wait(timeout=None)
        assert result is True
        lock.release()


class TestBreakLockRaises:
    def test_break_lock_reraises_non_enoent(self, tmp_lock_file):
        lock = EmulatorLock('test')
        with patch('os.unlink', side_effect=OSError(errno.EACCES, 'denied')):
            with pytest.raises(OSError):
                lock._break_lock()


class TestRecycledPid:
    """Regression test: lock file with a live PID but no magic must be treated as stale.

    This covers the Windows PID-recycling bug where a previous sense_emu crash
    leaves a lock file whose PID is later reused by an unrelated process.
    """

    def test_is_stale_true_for_no_magic(self, tmp_lock_file):
        # File exists, PID is live (current process), but no magic line
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n' % os.getpid())
        lock = EmulatorLock('test')
        assert lock._is_stale() is True

    def test_acquire_breaks_no_magic_lock(self, tmp_lock_file):
        # Should be able to acquire even when PID-only file exists
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n' % os.getpid())
        lock = EmulatorLock('test')
        lock.acquire()
        assert lock.mine is True
        lock.release()


class TestProcessStartTime:
    def test_current_process_has_start_time(self):
        st = process_start_time(os.getpid())
        assert st is not None
        assert isinstance(st, int)

    def test_dead_process_has_no_start_time(self):
        assert process_start_time(999999999) is None

    def test_pid_zero_has_no_start_time(self):
        assert process_start_time(0) is None

    def test_start_time_is_stable(self):
        # Same process must report the same start time on repeated calls
        assert process_start_time(os.getpid()) == process_start_time(os.getpid())


class TestRecycledPidStartTime:
    """A lock whose PID is *alive* but belongs to a different process (recycled
    PID) must be detected as stale via the recorded process start time."""

    def test_write_pid_records_start_time(self, tmp_lock_file):
        lock = EmulatorLock('test')
        lock.acquire()
        with open(tmp_lock_file) as f:
            assert int(f.readline().strip()) == os.getpid()
            assert f.readline().strip() == _LOCK_MAGIC
            assert int(f.readline().strip()) == process_start_time(os.getpid())
        lock.release()

    def test_read_start_time_roundtrip(self, tmp_lock_file):
        lock = EmulatorLock('test')
        lock.acquire()
        assert lock._read_start_time() == process_start_time(os.getpid())
        lock.release()

    def test_read_start_time_none_for_two_line_file(self, tmp_lock_file):
        # Legacy two-line lock (pid + magic, no start time)
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n%s\n' % (os.getpid(), _LOCK_MAGIC))
        lock = EmulatorLock('test')
        assert lock._read_start_time() is None

    def test_is_stale_true_when_start_time_differs(self, tmp_lock_file):
        # Live PID (ours) + magic, but a recorded start time that does NOT match
        # our actual one => the PID was recycled => stale.
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n%s\n%d\n' % (os.getpid(), _LOCK_MAGIC, 1))
        lock = EmulatorLock('test')
        assert lock._is_stale() is True

    def test_is_stale_false_when_start_time_matches(self, tmp_lock_file):
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n%s\n%d\n' % (
                os.getpid(), _LOCK_MAGIC, process_start_time(os.getpid())))
        lock = EmulatorLock('test')
        assert lock._is_stale() is False

    def test_is_stale_false_for_legacy_two_line_live_pid(self, tmp_lock_file):
        # Backward compat: a two-line lock with a live PID is NOT stale
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n%s\n' % (os.getpid(), _LOCK_MAGIC))
        lock = EmulatorLock('test')
        assert lock._is_stale() is False

    def test_acquire_breaks_recycled_pid_lock(self, tmp_lock_file):
        # A live PID with a mismatched start time must not wedge the lock
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n%s\n%d\n' % (os.getpid(), _LOCK_MAGIC, 1))
        lock = EmulatorLock('test')
        lock.acquire()
        assert lock.mine is True
        # After acquire the file records OUR real start time
        assert lock._read_start_time() == process_start_time(os.getpid())
        lock.release()

    def test_wait_ignores_recycled_pid_lock(self, tmp_lock_file):
        # wait() must not report a recycled-PID lock as a live emulator
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n%s\n%d\n' % (os.getpid(), _LOCK_MAGIC, 1))
        lock = EmulatorLock('test')
        assert lock.wait(timeout=0.2) is False


# ---------------------------------------------------------------------------
# OS-arbitrated locking (regression tests for the TOCTOU race and for release()
# deleting a lock that belongs to somebody else)
# ---------------------------------------------------------------------------

import subprocess
import textwrap


def _spawn_holder(lock_path, mode='hold'):
    """
    Start a child Python process that acquires the emulator lock (with
    lock_filename() pointed at *lock_path*) and then, depending on *mode*,
    waits for stdin to close ('hold') or dies without cleaning up ('crash').
    Returns the Popen once the child reports that it holds the lock.
    """
    code = textwrap.dedent("""
        import os, sys
        from unittest.mock import patch
        from sense_emu.lock import EmulatorLock
        with patch('sense_emu.lock.lock_filename', return_value=sys.argv[1]):
            lock = EmulatorLock('child')
            lock.acquire()
            print('locked', flush=True)
            if sys.argv[2] == 'crash':
                os._exit(0)    # no release(), no atexit, no __del__
            sys.stdin.read()
    """)
    child = subprocess.Popen(
        [sys.executable, '-c', code, lock_path, mode],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert child.stdout.readline().strip() == 'locked'
    return child


def _reap(child):
    """Close a child's pipes and wait for it to exit."""
    for pipe in (child.stdin, child.stdout):
        if pipe is not None:
            try:
                pipe.close()
            except OSError:
                pass
    child.wait()


class TestOSArbitratedLock:
    def test_second_acquire_in_same_process_fails(self, tmp_lock_file):
        first = EmulatorLock('one')
        second = EmulatorLock('two')
        first.acquire()
        try:
            with pytest.raises(FileExistsError):
                second.acquire()
            assert second.mine is False
        finally:
            first.release()

    def test_acquire_twice_on_same_object_fails(self, tmp_lock_file):
        lock = EmulatorLock('one')
        lock.acquire()
        try:
            with pytest.raises(FileExistsError):
                lock.acquire()
            assert lock.mine is True
        finally:
            lock.release()

    def test_failed_acquire_leaves_holder_untouched(self, tmp_lock_file):
        first = EmulatorLock('one')
        first.acquire()
        try:
            with open(tmp_lock_file) as f:
                before = f.read()
            with pytest.raises(FileExistsError):
                EmulatorLock('two').acquire()
            with open(tmp_lock_file) as f:
                assert f.read() == before
        finally:
            first.release()

    def test_lock_file_content_is_exact(self, tmp_lock_file):
        # Guards against newline translation (text-mode fd on Windows)
        lock = EmulatorLock('one')
        lock.acquire()
        try:
            with open(tmp_lock_file, 'rb') as f:
                raw = f.read()
            start = process_start_time(os.getpid())
            expected = ('%d\n%s\n%s\n' % (
                os.getpid(), _LOCK_MAGIC, '' if start is None else start)).encode('ascii')
            assert raw == expected
            assert b'\r' not in raw
        finally:
            lock.release()

    def test_release_never_removes_a_foreign_lock(self, tmp_lock_file):
        # A lock file written by someone else (e.g. an older version) must
        # survive release() on an object that never acquired it.
        with open(tmp_lock_file, 'w') as f:
            f.write('%d\n%s\n' % (os.getpid(), _LOCK_MAGIC))
        EmulatorLock('bystander').release()
        assert os.path.exists(tmp_lock_file)

    def test_release_is_idempotent(self, tmp_lock_file):
        lock = EmulatorLock('one')
        lock.acquire()
        lock.release()
        lock.release()
        assert not os.path.exists(tmp_lock_file)

    def test_reacquire_after_release(self, tmp_lock_file):
        lock = EmulatorLock('one')
        lock.acquire()
        lock.release()
        lock.acquire()
        assert lock.mine is True
        lock.release()

    def test_acquire_timeout_waits_for_release(self, tmp_lock_file):
        import threading
        first = EmulatorLock('one')
        first.acquire()
        threading.Timer(0.3, first.release).start()
        second = EmulatorLock('two')
        start = time.monotonic()
        second.acquire(timeout=5)
        assert 0.2 < time.monotonic() - start < 4
        second.release()

    def test_acquire_timeout_expires(self, tmp_lock_file):
        first = EmulatorLock('one')
        first.acquire()
        try:
            start = time.monotonic()
            with pytest.raises(FileExistsError):
                EmulatorLock('two').acquire(timeout=0.2)
            assert time.monotonic() - start >= 0.2
        finally:
            first.release()

    def test_garbage_collected_lock_is_released(self, tmp_lock_file):
        import gc
        lock = EmulatorLock('one')
        lock.acquire()
        del lock
        gc.collect()
        again = EmulatorLock('two')
        again.acquire()
        again.release()

    @pytest.mark.skipif(sys.platform.startswith('win'),
                        reason='Windows cannot unlink a file that is open')
    def test_orphan_inode_is_retried(self, tmp_lock_file):
        # If the previous holder unlinks the file between our open() and
        # lock(), we hold a lock on a deleted inode. acquire() must notice and
        # start again rather than report success.
        lock = EmulatorLock('one')
        real = lock._same_file
        calls = []

        def flaky(fd):
            calls.append(fd)
            if len(calls) == 1:
                os.unlink(tmp_lock_file)   # holder released behind our back
                return real(fd)            # -> False on POSIX
            return real(fd)

        with patch.object(lock, '_same_file', side_effect=flaky):
            lock.acquire()
        try:
            assert lock.mine is True
            assert os.path.exists(tmp_lock_file)
            if not sys.platform.startswith('win'):
                assert len(calls) >= 2
        finally:
            lock.release()

    def test_outdated_stale_verdict_cannot_steal_live_lock(self, tmp_lock_file):
        # The TOCTOU race, made deterministic: B decided the lock was stale
        # (holder dead) and, before B acts, A acquires it. With the old
        # "check staleness, delete, recreate" protocol B would delete A's live
        # lock and write its own -> two emulators. With an OS-level lock the
        # stale verdict is irrelevant.
        holder = EmulatorLock('A')
        holder.acquire()
        try:
            intruder = EmulatorLock('B')
            with patch.object(EmulatorLock, '_is_stale', return_value=True), \
                 patch('sense_emu.lock.pid_exists', return_value=False):
                with pytest.raises(FileExistsError):
                    intruder.acquire()
            assert intruder.mine is False
            assert holder.mine is True
            with open(tmp_lock_file) as f:
                assert int(f.readline()) == os.getpid()
        finally:
            holder.release()

    def test_live_legacy_holder_blocks_acquire(self, tmp_lock_file):
        # An older version (PID file only, no OS lock) that is still running
        # must not be trampled.
        child = subprocess.Popen(
            [sys.executable, '-c', 'import sys; sys.stdin.read()'],
            stdin=subprocess.PIPE)
        try:
            start = process_start_time(child.pid)
            with open(tmp_lock_file, 'w') as f:
                f.write('%d\n%s\n%s\n' % (
                    child.pid, _LOCK_MAGIC, '' if start is None else start))
            with pytest.raises(FileExistsError):
                EmulatorLock('one').acquire()
        finally:
            _reap(child)

    def test_other_process_holding_lock_blocks_acquire(self, tmp_lock_file):
        child = _spawn_holder(tmp_lock_file)
        try:
            with pytest.raises(FileExistsError):
                EmulatorLock('one').acquire()
            # ... and readers see a live emulator
            assert EmulatorLock('reader').wait(timeout=1) is True
        finally:
            _reap(child)

    def test_lock_is_free_once_holder_exits_cleanly(self, tmp_lock_file):
        child = _spawn_holder(tmp_lock_file)
        _reap(child)
        lock = EmulatorLock('one')
        lock.acquire()
        lock.release()

    def test_lock_of_crashed_holder_is_taken_over(self, tmp_lock_file):
        # The holder dies without release(): the file is left behind naming a
        # dead PID, but the OS has dropped the lock, so we can take it.
        child = _spawn_holder(tmp_lock_file, mode='crash')
        _reap(child)
        assert os.path.exists(tmp_lock_file)
        lock = EmulatorLock('one')
        lock.acquire()
        assert lock.mine is True
        lock.release()

    def test_concurrent_acquire_has_exactly_one_winner(self, tmp_lock_file):
        # Many processes race for a lock left behind by a crashed holder (the
        # scenario that used to let two emulators run at once).
        crashed = _spawn_holder(tmp_lock_file, mode='crash')
        _reap(crashed)
        code = textwrap.dedent("""
            import sys, time
            from unittest.mock import patch
            from sense_emu.lock import EmulatorLock
            with patch('sense_emu.lock.lock_filename', return_value=sys.argv[1]):
                lock = EmulatorLock('racer')
                start_at = float(sys.argv[2])
                while time.time() < start_at:     # spin: near-simultaneous start
                    pass
                try:
                    lock.acquire()
                except FileExistsError:
                    print('lost', flush=True)
                else:
                    print('won', flush=True)
                    time.sleep(2)                 # keep holding while others try
        """)
        start_at = time.time() + 2.0
        racers = [
            subprocess.Popen([sys.executable, '-c', code, tmp_lock_file,
                              repr(start_at)],
                             stdout=subprocess.PIPE, text=True)
            for _ in range(8)]
        try:
            results = [r.stdout.readline().strip() for r in racers]
        finally:
            for r in racers:
                _reap(r)
        assert results.count('won') == 1, results
        assert results.count('lost') == 7, results
