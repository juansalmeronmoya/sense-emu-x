.. _changelog:

==========
Change log
==========


Release 2.0 (unreleased)
========================

The distribution is now published as ``sense-emu-x`` (the import name is still
``sense_emu``) and requires Python 3.11 or later.

**Breaking fix: the gyroscope is now reported in rad/s**

* The simulated gyroscope reported the rate of change of the orientation in
  degrees per second, while :meth:`~sense_emu.SenseHat.get_gyroscope_raw` (like
  the real Sense HAT and recordings made with ``sense_rec``) is documented in
  radians per second. Simulated readings were therefore 57.3 times too large,
  and did not agree with a replayed recording of the same movement.
* Readings no longer spike when an angle wraps around at +/-180 degrees.
* ``GYRO_FACTOR`` (LSB per unit in the IMU file) changed accordingly. A
  ``sense_emu_gui`` or ``sense_play`` from an older version must not be run
  against a newer library: restart both after upgrading.
* Scripts that compensated for the old scaling must drop the compensation.

**Fixes**

* Only one emulator can run at a time: the lock is now arbitrated by the
  operating system (``flock`` / ``LockFileEx``), removing a race in which two
  simultaneous launches could both start after a crash. A lock is released
  automatically if its owner dies, and ``release()`` can no longer delete a lock
  that belongs to another process.
* An exception raised by a joystick callback no longer silently stops all
  further joystick events; it is logged instead. Stopping the callback thread
  (including ``SenseStick.close()``) no longer waits for the next joystick
  event, and setting a direction to ``None`` now really removes the handler.
* ``EmulatorController`` releases the lock and closes everything it opened if
  construction fails for any reason, and always closes all subsystems.
* The GUI and the TUI lock the sensor controls while a recording is replayed
  and restore them (and the emulator state) when it ends; the GUI stops all of
  its timers before shutting the emulator down.
* ``sense_rec``, ``sense_play`` and ``sense_csv`` no longer use
  ``locale.getdefaultlocale()``, which was removed in Python 3.15.
* Fixed a ``NameError`` when loading ``intl.dll`` for translations on Windows.


Release 1.2 (2021-09-03)
========================

* Updated code to work with later Gtk3 versions
* Added configuration option for the editor launched for examples


Release 1.1 (2018-07-07)
========================

* Enforce a minimum width of window to ensure orientation sliders are never
  excessively small (`#9`_)
* Various documentation updates (`#12`_ etc.)
* Resizing of the display for high-resolution displays (`#14`_)
* Orientation sliders had no effect when world simulation was disabled (`#19`_)
* When the emulator was spawned by instantiating ``SenseHat()`` in an
  interpreter, pressing Ctrl+C in the interpreter would affect the emulator
  (`#22`_)
* Make :program:`sense_rec` interval configurable (`#24`_)

Many thanks to everyone who reported bugs and provided patches!

.. _#9: https://github.com/RPi-Distro/python-sense-emu/issues/9
.. _#12: https://github.com/RPi-Distro/python-sense-emu/issues/12
.. _#14: https://github.com/RPi-Distro/python-sense-emu/issues/14
.. _#19: https://github.com/RPi-Distro/python-sense-emu/issues/19
.. _#22: https://github.com/RPi-Distro/python-sense-emu/issues/22
.. _#24: https://github.com/RPi-Distro/python-sense-emu/issues/24


Release 1.0 (2016-08-31)
========================

* Initial release
