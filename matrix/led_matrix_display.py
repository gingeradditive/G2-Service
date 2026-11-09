#!/usr/bin/env python3
"""
LED Matrix Text Display for Raspberry Pi
Uses MAX7219 LED matrix connected via SPI (GPIO8/CE0 as chip select).

Wiring (matching https://pinout.xyz/pinout/pin24_gpio8/):
  - VCC  -> 5V (Pin 2)
  - GND  -> GND (Pin 6)
  - DIN  -> MOSI / GPIO10 (Pin 19)
  - CS   -> CE0 / GPIO8 (Pin 24)
  - CLK  -> SCLK / GPIO11 (Pin 23)
"""

import argparse
import atexit
import os
import signal
import sys
import time

from luma.core.interface.serial import noop, spi
from luma.core.legacy import text, textsize
from luma.core.legacy.font import CP437_FONT, proportional
from luma.led_matrix.device import max7219
from PIL import Image, ImageDraw

PID_FILE = "/tmp/led_matrix_display.pid"

# Clock SPI in kHz. Il default di luma è 8 MHz, troppo per i cavi lunghi della G2: i fronti di
# CLK/DIN arrivano degradati, i MAX7219 leggono dati sporchi e la matrice si accende tutta rossa.
# Per un messaggio statico la velocità non conta, quindi si sta al minimo che luma accetta.
SPI_SPEEDS_KHZ = (500, 1000, 2000, 4000, 8000)
DEFAULT_SPI_SPEED_KHZ = 500


def get_text_size(message, font):
    return textsize(message, font=proportional(font))


def create_device(cascaded=1, block_orientation=-90, rotate=0, spi_speed_khz=DEFAULT_SPI_SPEED_KHZ):
    """Create and return a MAX7219 device instance."""
    serial = spi(port=0, device=0, gpio=noop(), bus_speed_hz=spi_speed_khz * 1000)
    device = max7219(
        serial,
        cascaded=cascaded,
        block_orientation=block_orientation,
        rotate=rotate,
    )
    device.contrast(16)
    return device


def display_static(device, message, font=None):
    """Display static centered text on the matrix."""
    if font is None:
        font = CP437_FONT
    image = Image.new("1", (device.width, device.height))
    draw = ImageDraw.Draw(image)
    text_width, text_height = get_text_size(message, font)
    x = max(0, (device.width - text_width) // 2)
    y = max(0, (device.height - text_height) // 2)
    text(draw, (x, y), message, fill="white", font=proportional(font))
    device.display(image)


def stop_previous_instance():
    if not os.path.exists(PID_FILE):
        return
    try:
        with open(PID_FILE, "r", encoding="utf-8") as pid_file:
            pid = int(pid_file.read().strip())
        if pid != os.getpid():
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.2)
    except (OSError, ValueError, ProcessLookupError):
        pass
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


def write_pid_file():
    with open(PID_FILE, "w", encoding="utf-8") as pid_file:
        pid_file.write(str(os.getpid()))


def remove_pid_file():
    try:
        if os.path.exists(PID_FILE):
            with open(PID_FILE, "r", encoding="utf-8") as pid_file:
                pid = int(pid_file.read().strip())
            if pid == os.getpid():
                os.remove(PID_FILE)
    except (OSError, ValueError):
        pass


def keep_alive():
    while True:
        time.sleep(3600)


def main():
    parser = argparse.ArgumentParser(
        description="Display static centered text on a MAX7219 LED matrix via SPI (GPIO8/CE0)."
    )
    parser.add_argument(
        "text",
        nargs="?",
        default=None,
        help="Text to display. If omitted, reads from stdin.",
    )
    parser.add_argument(
        "--cascaded",
        "-n",
        type=int,
        default=8,
        help="Number of cascaded MAX7219 modules (default: 8).",
    )
    parser.add_argument(
        "--brightness",
        "-b",
        type=int,
        default=16,
        choices=range(0, 256),
        metavar="[0-255]",
        help="Display brightness (default: 16).",
    )
    parser.add_argument(
        "--spi-speed",
        type=int,
        default=DEFAULT_SPI_SPEED_KHZ,
        choices=SPI_SPEEDS_KHZ,
        metavar="KHZ",
        help=f"SPI clock in kHz, one of {SPI_SPEEDS_KHZ} (default: {DEFAULT_SPI_SPEED_KHZ}).",
    )

    args = parser.parse_args()

    # Determine message source
    message = args.text if args.text else sys.stdin.read().strip()
    if not message:
        parser.error("No text provided.")

    stop_previous_instance()
    write_pid_file()
    atexit.register(remove_pid_file)

    # Create device
    device = create_device(cascaded=args.cascaded, spi_speed_khz=args.spi_speed)
    device.contrast(args.brightness)

    # Display static centered text
    display_static(device, message)
    print(f"Displaying: '{message}'")
    keep_alive()


if __name__ == "__main__":
    main()
