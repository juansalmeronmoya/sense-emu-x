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

"The Raspberry Pi Sense HAT Emulator library"

from .sense_hat import SenseHat, SenseHat as AstroPi
from .stick import (
    SenseStick,
    InputEvent,
    DIRECTION_UP,
    DIRECTION_DOWN,
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
    DIRECTION_MIDDLE,
    ACTION_PRESSED,
    ACTION_RELEASED,
    ACTION_HELD,
    )

# NB: __project__ is the gettext domain (matches the compiled .mo files),
# not the PyPI distribution name (sense-emu-x). All other packaging metadata
# lives in pyproject.toml.
__project__      = 'sense-emu'
__version__      = '1.2.1'
__author__       = 'Raspberry Pi Foundation'
__author_email__ = 'info@raspberrypi.org'
__url__          = 'https://github.com/juansalmeronmoya/sense-emu-x'
