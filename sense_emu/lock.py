# vim: set et sw=4 sts=4 fileencoding=utf-8:
#
# Raspberry Pi Sense HAT Emulator library for the Raspberry Pi
# Copyright (c) 2016 Raspberry Pi Foundation <info@raspberrypi.org>
#
# This package is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# This package is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>

import sys
import os
import io
import errno
from time import time, sleep

_LOCK_MAGIC = 'sense-emu-lock'


if sys.platform.startswith('win'):
    import ctypes
    kernel32 = ctypes.windll.kernel32
    DWORD = ctypes.c_ulong
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    ERROR_ACCESS_DENIED = 0x5
    ERROR_INVALID_PARAMETER = 0x57
    STILL_ACTIVE = 259

    class _FILETIME(ctypes.Structure):
        _fields_ = [('dwLowDateTime', DWORD), ('dwHighDateTime', DWORD)]

    def pid_exists(pid):
        if pid == 0:
            return True
        h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
        try:
            if not h:
                if kernel32.GetLastError() == ERROR_ACCESS_DENIED:
                    # If access is denied, there's obviously a process denying
                    # access...
                    return True
                elif kernel32.GetLastError() == ERROR_INVALID_PARAMETER:
                    # Invalid parameter is no such process
                    return False
                raise OSError('unable to get handle for pid %d' % pid)
            out = DWORD()
            if kernel32.GetExitCodeProcess(h, ctypes.byref(out)):
                return out.value == STILL_ACTIVE
            raise OSError('unable to query exit code for pid %d' % pid)
        finally:
            kernel32.CloseHandle(h)

    def process_start_time(pid):
        """
        Return an opaque, stable token identifying *when* *pid* started, or
        ``None`` if it cannot be determined. Used to detect PID recycling: a
        recycled PID reports a different creation time than the one recorded
        when the lock was taken.
        """
        if pid == 0:
            return None
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
        if not h:
            h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
        if not h:
            return None
        try:
            creation = _FILETIME()
            exit_t = _FILETIME()
            kernel_t = _FILETIME()
            user_t = _FILETIME()
            if kernel32.GetProcessTimes(
                    h, ctypes.byref(creation), ctypes.byref(exit_t),
                    ctypes.byref(kernel_t), ctypes.byref(user_t)):
                return (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            return None
        finally:
            kernel32.CloseHandle(h)
else:
    def pid_exists(pid):
        if pid == 0:
            return True
        try:
            os.kill(pid, 0)
        except OSError as e:
            if e.errno == errno.ESRCH:
                return False
            elif e.errno == errno.EPERM:
                return True
            else:
                raise
        else:
            return True

    def process_start_time(pid):
        """
        Return an opaque, stable token identifying *when* *pid* started, or
        ``None`` if it cannot be determined (e.g. on systems without
        ``/proc``). Used to detect PID recycling.
        """
        if pid == 0:
            return None
        try:
            with io.open('/proc/%d/stat' % pid, 'rb') as f:
                data = f.read()
        except (IOError, OSError):
            return None
        try:
            # Field 2 (comm) is wrapped in parens and may itself contain spaces
            # or parens, so split after the final ')'. starttime is field 22
            # overall, i.e. index 19 of the remaining whitespace-split fields.
            rparen = data.rfind(b')')
            fields = data[rparen + 2:].split()
            return int(fields[19])
        except (IndexError, ValueError):
            return None


def lock_filename():
    """
    Return the filename used as a lock-file by applications that can drive the
    emulation (currently sense_emu_gui and sense_play). On UNIX we try
    ``/dev/shm`` then fall back to ``/tmp``; on Windows we use whatever
    ``%TEMP%`` contains
    """
    fname = 'rpi-sense-emu-pid'
    if sys.platform.startswith('win'):
        # just use a temporary file on Windows
        return os.path.join(os.environ['TEMP'], fname)
    else:
        if os.path.exists('/dev/shm'):
            return os.path.join('/dev/shm', fname)
        else:
            return os.path.join('/tmp', fname)


# The emulator lock is arbitrated by the operating system: the process that
# drives the emulation keeps the lock file open for its whole lifetime and holds
# an exclusive, non-blocking advisory lock on it. The kernel drops that lock
# when the process dies (however it dies), so there is no window in which two
# emulators can both believe they own it and no need to guess whether a PID
# file is stale. The PID / magic / start-time contents are kept purely as
# information for readers (:meth:`EmulatorLock.wait`) and older versions.
if sys.platform.startswith('win'):
    import msvcrt

    # Windows byte-range locks are mandatory: locking the first bytes would
    # stop other processes *reading* the PID. Lock a byte far beyond the data.
    _LOCK_OFFSET = 1 << 20

    def _os_lock(fd):
        """Take the exclusive lock on *fd*; raise OSError if already held."""
        os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        finally:
            os.lseek(fd, 0, os.SEEK_SET)

    def _os_unlock(fd):
        os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.lseek(fd, 0, os.SEEK_SET)
else:
    import fcntl

    def _os_lock(fd):
        """Take the exclusive lock on *fd*; raise OSError if already held."""
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _os_unlock(fd):
        fcntl.flock(fd, fcntl.LOCK_UN)


class EmulatorLock:
    def __init__(self, name):
        self._filename = lock_filename()
        self._fd = None
        self.name = name # XXX not currently used

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.release()

    def __del__(self):
        # Never leave the lock held by an object nobody can release any more.
        try:
            self.release()
        except Exception:
            pass

    def acquire(self, timeout=None):
        """
        Acquire the emulator lock. This is expected to be called by anything
        wishing to drive the emulator's registers (sense_emu_gui and sense_play
        currently).

        If another live process holds the lock, :exc:`FileExistsError` is
        raised immediately (*timeout* is ``None``, the default) or once
        *timeout* seconds have elapsed without the lock becoming free. A lock
        left behind by a process that died is simply taken over: the operating
        system released it when that process exited.
        """
        if self._fd is not None:
            raise FileExistsError(
                errno.EEXIST, 'this process already holds the emulator lock',
                self._filename)
        end = None if timeout is None else time() + timeout
        while True:
            try:
                self._try_acquire()
            except FileExistsError:
                if end is None or time() >= end:
                    raise
                sleep(0.05)
            else:
                return

    def _try_acquire(self):
        for _ in range(10):
            # O_BINARY: on Windows os.open() defaults to text mode, which would
            # translate the newlines in the lock file
            fd = os.open(
                self._filename,
                os.O_RDWR | os.O_CREAT | getattr(os, 'O_BINARY', 0), 0o666)
            try:
                _os_lock(fd)
            except OSError as e:
                os.close(fd)
                if e.errno in (errno.EAGAIN, errno.EACCES, errno.EDEADLK,
                               errno.EWOULDBLOCK):
                    raise FileExistsError(
                        errno.EEXIST,
                        'the emulator lock is held by another process',
                        self._filename)
                raise
            if not self._same_file(fd):
                # The previous holder unlinked the file between our open() and
                # lock(): we locked an orphan inode. Start again.
                os.close(fd)
                continue
            if not self._legacy_holder_is_alive():
                self._fd = fd
                try:
                    self._write_pid()
                except BaseException:
                    self._close_fd(unlink=False)
                    raise
                return
            os.close(fd)
            raise FileExistsError(
                errno.EEXIST,
                'the emulator lock is held by another process', self._filename)
        raise FileExistsError(
            errno.EEXIST, 'unable to acquire the emulator lock', self._filename)

    def _same_file(self, fd):
        if sys.platform.startswith('win'):
            # Windows cannot unlink a file that is open, so the race above
            # cannot happen
            return True
        try:
            on_disk = os.stat(self._filename)
        except FileNotFoundError:
            return False
        held = os.fstat(fd)
        return (held.st_dev, held.st_ino) == (on_disk.st_dev, on_disk.st_ino)

    def _legacy_holder_is_alive(self):
        # Versions that predate the OS-level lock only wrote a PID file. If the
        # file names a live process other than us, that process holds the lock
        # even though the kernel cannot tell us so.
        pid = self._read_pid()
        return (
            pid is not None and pid != os.getpid() and not self._is_stale())

    def release(self):
        """
        Release the emulator lock (presumably after :meth:`acquire`). Does
        nothing if this object does not hold the lock, so it can never remove
        a lock that belongs to another process.
        """
        if self._fd is not None:
            self._close_fd(unlink=True)

    def _close_fd(self, unlink):
        fd, self._fd = self._fd, None
        try:
            if unlink:
                # Empty the file first: if it cannot be unlinked below (Windows
                # keeps files that another process has open), readers will see
                # an invalid lock file instead of our still-running PID.
                try:
                    os.ftruncate(fd, 0)
                except OSError:
                    pass
                if not sys.platform.startswith('win') and self._same_file(fd):
                    # POSIX: unlink while still holding the lock so nobody can
                    # lock the file we are deleting
                    self._break_lock()
        finally:
            try:
                _os_unlock(fd)
            except OSError:
                pass
            os.close(fd)
        if unlink and sys.platform.startswith('win'):
            try:
                self._break_lock()
            except OSError:
                pass  # another process has it open; harmless, file is empty

    def wait(self, timeout=None):
        """
        Wait for a process to acquire the lock. This is expected to be called
        by anything wishing to read the registers and wanting to ensure there's
        something driving them (i.e. any consumer of SenseHat).

        Returns ``True`` if the lock was acquired before *timeout* seconds
        elapsed, or ``False`` otherwise. If *timeout* is ``None`` (the default)
        wait indefinitely.
        """
        # XXX Either add a "launch" param to this method, or add a launch
        # method to the class so that consumers can use the lock to launch
        # an appropriate emulation
        end = time()
        if timeout is not None:
            end += timeout
        while not self._is_held() or self._is_stale():
            if time() > end:
                return False
            sleep(0.1)
        return True

    @property
    def mine(self):
        """
        Returns True if this object holds the lock.
        """
        return self._fd is not None

    def _is_held(self):
        return os.path.exists(self._filename)

    def _is_stale(self):
        # True if the lock file exists but is invalid, the PID it references
        # doesn't exist, or that PID has been recycled to a different process.
        if not self._is_held():
            return False
        pid = self._read_pid()
        if pid is None:
            # File exists but has no valid sense_emu magic — treat as stale
            # (handles garbage/foreign files and recycled PIDs on Windows)
            return True
        if not pid_exists(pid):
            return True
        # The PID is alive, but on Windows (and elsewhere) PIDs are recycled.
        # If the lock recorded the holder's start time, make sure the live
        # process is the *same* one — otherwise an unrelated process that
        # happened to inherit the PID would wedge the lock forever.
        stored = self._read_start_time()
        if stored is not None:
            current = process_start_time(pid)
            if current is not None and current != stored:
                return True
        return False

    def _break_lock(self):
        # Unconditionally delete the file
        try:
            os.unlink(self._filename)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    def _read_pid(self):
        try:
            with io.open(self._filename, 'rb') as lockfile:
                pid_line = lockfile.readline().decode('ascii').strip()
                magic_line = lockfile.readline().decode('ascii').strip()
                if magic_line != _LOCK_MAGIC:
                    return None
                return int(pid_line)
        except (IOError, ValueError):
            return None

    def _read_start_time(self):
        # The recorded start time lives on the third line. Returns None for
        # older two-line lock files or anything unparseable, in which case the
        # recycled-PID check is simply skipped.
        try:
            with io.open(self._filename, 'rb') as lockfile:
                lockfile.readline()  # pid
                magic_line = lockfile.readline().decode('ascii').strip()
                if magic_line != _LOCK_MAGIC:
                    return None
                start_line = lockfile.readline().decode('ascii').strip()
                if not start_line:
                    return None
                return int(start_line)
        except (IOError, ValueError):
            return None

    def _write_pid(self):
        # Record who holds the lock in the (already locked) lock file
        start = process_start_time(os.getpid())
        data = ('%d\n%s\n%s\n' % (
            os.getpid(), _LOCK_MAGIC, '' if start is None else start
        )).encode('ascii')
        os.lseek(self._fd, 0, os.SEEK_SET)
        os.write(self._fd, data)
        os.ftruncate(self._fd, len(data))
