#!/usr/bin/env python3
"""
Example script to demonstrate sense_emu library usage.
Tests sensor readings and LED matrix operations.
"""

import time
from sense_emu import SenseHat

def print_sensors(hat):
    """Read and display all sensor values."""
    print("\n=== SENSOR READINGS ===")

    # Environmental sensors
    temp = hat.get_temperature()
    pressure = hat.get_pressure()
    humidity = hat.get_humidity()

    print(f"Temperature: {temp:.2f}°C")
    print(f"Pressure: {pressure:.2f} mb")
    print(f"Humidity: {humidity:.2f}%")

    # IMU (Inertial Measurement Unit)
    orientation = hat.get_orientation()
    print(f"\nOrientation (degrees):")
    print(f"  Pitch: {orientation['pitch']:.2f}°")
    print(f"  Roll: {orientation['roll']:.2f}°")
    print(f"  Yaw: {orientation['yaw']:.2f}°")

def test_led_matrix(hat):
    """Test LED matrix with various patterns."""
    print("\n=== LED MATRIX TEST ===")

    # Clear screen
    print("Clearing matrix...")
    hat.clear()
    time.sleep(0.5)

    # Set individual pixels in different colors
    print("Setting individual pixels...")
    hat.set_pixel(0, 0, 255, 0, 0)      # Red at (0,0)
    hat.set_pixel(7, 0, 0, 255, 0)      # Green at (7,0)
    hat.set_pixel(0, 7, 0, 0, 255)      # Blue at (0,7)
    hat.set_pixel(7, 7, 255, 255, 0)    # Yellow at (7,7)
    time.sleep(1)

    # Create a pattern (checkerboard)
    print("Drawing checkerboard pattern...")
    hat.clear()
    for x in range(8):
        for y in range(8):
            if (x + y) % 2 == 0:
                hat.set_pixel(x, y, 255, 255, 255)  # White
    time.sleep(1)

    # Fill entire matrix with a color
    print("Filling matrix with cyan...")
    hat.clear()
    pixels = [[0, 255, 255] for _ in range(64)]  # 64 pixels, all cyan
    hat.set_pixels(pixels)
    time.sleep(1)

    # Display a message (scrolling text)
    print("Scrolling message...")
    hat.clear()
    hat.show_message("HOLA", text_colour=[255, 0, 0])  # Red text

    # Display a single letter
    print("Displaying letter...")
    hat.clear()
    hat.show_letter("A", text_colour=[0, 255, 0])  # Green text
    time.sleep(1)

    # Test rotation
    print("Testing rotation...")
    hat.clear()
    # Create an 'L' shape
    pixels = [
        [255, 0, 0] if (x == 0 or y == 7) else [0, 0, 0]
        for y in range(8)
        for x in range(8)
    ]
    hat.set_pixels(pixels)

    for rotation in [0, 90, 180, 270]:
        print(f"  Rotation: {rotation}°")
        hat.set_rotation(rotation)
        time.sleep(0.5)

    hat.clear()

def test_gamma(hat):
    """Test LED brightness/gamma correction."""
    print("\n=== GAMMA CORRECTION TEST ===")

    # Fill with white
    hat.clear()
    pixels = [[255, 255, 255] for _ in range(64)]
    hat.set_pixels(pixels)

    print("Normal brightness")
    time.sleep(1)

    print("Low light mode")
    hat.low_light = True
    time.sleep(1)

    print("Back to normal")
    hat.low_light = False

    hat.clear()

def test_joystick(hat):
    """Test joystick events (if available)."""
    print("\n=== JOYSTICK TEST ===")
    print("Trying to read joystick events (timeout 3 seconds)...")

    try:
        # Set up a simple callback for joystick events
        press_count = [0]  # Use list to modify in nested function

        def on_pressed(event):
            press_count[0] += 1
            print(f"  Button pressed: {event.direction} (total: {press_count[0]})")

        hat.stick.direction_pressed = on_pressed

        # Wait a bit to see if any joystick events occur
        time.sleep(3)

        print(f"Received {press_count[0]} joystick events")
    except Exception as e:
        print(f"  Could not test joystick: {e}")
    finally:
        # Clear callbacks
        hat.stick.direction_pressed = None

def main():
    """Main example function."""
    print("=" * 50)
    print("Sense HAT Emulator - Example Script")
    print("=" * 50)

    # Initialize Sense HAT
    print("\nInitializing Sense HAT emulator...")
    hat = SenseHat()

    try:
        # Test sensor readings
        print_sensors(hat)

        # Test LED matrix
        test_led_matrix(hat)

        # Test gamma correction
        test_gamma(hat)

        # Test joystick (optional, may not work in all environments)
        test_joystick(hat)

        # Final sensor reading
        print("\n=== FINAL SENSOR READING ===")
        print_sensors(hat)

        print("\n" + "=" * 50)
        print("Example completed successfully!")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        hat.clear()
        print("LED matrix cleared. Goodbye!")

if __name__ == "__main__":
    main()
