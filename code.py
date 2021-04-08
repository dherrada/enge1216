# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

# Turn on and off a LED from your Adafruit IO Dashboard.
# adafruit_circuitpython_adafruitio with an esp32spi_socket
import time
import board
import busio
from digitalio import DigitalInOut, Direction
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError
from adafruit_magtag.magtag import MagTag

# Add a secrets.py to your filesystem that has a dictionary called secrets with "ssid" and
# "password" keys with your WiFi credentials. DO NOT share that file or commit it into Git or other
# source control.
# pylint: disable=no-name-in-module,wrong-import-order
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

magtag = MagTag()
magtag.network.connect()
magtag.peripherals.neopixel_disable = False
#socket.set_interface(esp)

# Set your Adafruit IO Username and Key in secrets.py
# (visit io.adafruit.com if you need to create an account,
# or if you need your Adafruit IO key.)
aio_username = secrets["aio_username"]
aio_key = secrets["aio_key"]

# Initialize an Adafruit IO HTTP API object
io = IO_HTTP(aio_username, aio_key, magtag.network.requests)

try:
    # Get the 'digital' feed from Adafruit IO
    digital_feed = io.get_feed("digital")
    print("found feed")
except AdafruitIO_RequestError:
    # If no 'digital' feed exists, create one
    digital_feed = io.create_new_feed("digital")

print(digital_feed["key"])
print(io.receive_time())
# Set up LED
#LED = DigitalInOut(board.D13)
#LED.direction = Direction.OUTPUT

while True:
    # Get data from 'digital' feed
    print("getting data from IO...")
    feed_data = io.receive_data(digital_feed["key"])

    # Check if data is ON or OFF
    if feed_data["value"] == "ON":
        print("received <- ON\n")
        magtag.peripherals.neopixels.fill((128, 0, 0))
    elif feed_data["value"] == "OFF":
        print("received <= OFF\n")
        magtag.peripherals.neopixels.fill((0, 0, 0))
    else:
        print(feed_data["value"])


    time.sleep(5)
