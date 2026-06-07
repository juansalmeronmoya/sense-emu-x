#!/usr/bin/env python3
"""Test script to display colors in the LED matrix."""
from sense_emu import SenseHat
import time

hat = SenseHat()

# Clear the display (all black)
hat.clear()
time.sleep(0.5)

# Set some pixels with different colors
print("Setting up test pattern...")

# Top-left corner: Red
hat.set_pixel(0, 0, (255, 0, 0))
hat.set_pixel(1, 0, (255, 0, 0))
hat.set_pixel(0, 1, (255, 0, 0))

# Top-right corner: Green
hat.set_pixel(7, 0, (0, 255, 0))
hat.set_pixel(6, 0, (0, 255, 0))
hat.set_pixel(7, 1, (0, 255, 0))

# Bottom-left corner: Blue
hat.set_pixel(0, 7, (0, 0, 255))
hat.set_pixel(1, 7, (0, 0, 255))
hat.set_pixel(0, 6, (0, 0, 255))

# Bottom-right corner: Yellow
hat.set_pixel(7, 7, (255, 255, 0))
hat.set_pixel(6, 7, (255, 255, 0))
hat.set_pixel(7, 6, (255, 255, 0))

# Center: White
hat.set_pixel(3, 3, (255, 255, 255))
hat.set_pixel(4, 3, (255, 255, 255))
hat.set_pixel(3, 4, (255, 255, 255))
hat.set_pixel(4, 4, (255, 255, 255))

print("Test pattern set! You should see colored squares in the corners and center.")
print("The GUI window should display an 8x8 grid with color squares.")
print("Press Ctrl+C to exit...")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nCleaning up...")
    hat.clear()
