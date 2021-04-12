# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

# Turn on and off a LED from your Adafruit IO Dashboard.
# adafruit_circuitpython_adafruitio with an esp32spi_socket
import time
import board
import busio

from digitalio import DigitalInOut, Direction, Pull

import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_requests as requests
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError

import displayio
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306

# pylint: disable=no-name-in-module,wrong-import-order
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise


def ring(relay, snooze, stop):
    start = time.monotonic

    while not stop:
        if snooze:
            time.sleep(0.1)
            if not stop:
                time.sleep(300)
        if time.monotonic - start >= 2:
            relay.value = not relay.value


displayio.release_displays()

esp32_cs = DigitalInOut(board.D13)
esp32_ready = DigitalInOut(board.D11)
esp32_reset = DigitalInOut(board.D12)

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

print(f"Connecting to AP {secrets['ssid']}...")
while not esp.is_connected:
    try:
        esp.connect_AP(secrets["ssid"], secrets["password"])
    except RuntimeError as e:
        print("could not connect to AP, retrying: ", e)
        continue
print("Connected to", str(esp.ssid, "utf-8"), "\tRSSI:", esp.rssi)

socket.set_interface(esp)
requests.set_socket(socket, esp)

aio_username = secrets["aio_username"]
aio_key = secrets["aio_key"]

# Initialize an Adafruit IO HTTP API object
io = IO_HTTP(aio_username, aio_key, requests)

# Get the 'enge-1216.digital' feed from Adafruit IO
digital_feed = io.get_feed("enge-1216.digital")

# Get the 'enge-1216.alarm' feed from Adafruit IO
alarm_feed = io.get_feed("enge-1216.alarm")

# Get the 'enge-1216.alarm-default-days' feed from Adafruit IO
days_feed = io.get_feed("enge-1216.alarm-default-days")

# Get the 'enge-1216.alarm-time' feed from Adafruit IO
time_feed = io.get_feed("enge-1216.alarm-time")

# Get the 'enge-1216.skip-next-alarm' feed from Adafruit IO
skip_feed = io.get_feed("enge-1216.skip-next-alarm")

i2c = board.I2C()
display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)

WIDTH = 128
HEIGHT = 32
BORDER = 2

display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=WIDTH, height=HEIGHT)

splash = displayio.Group(max_size=10)
display.show(splash)

digital_label = label.Label(terminalio.FONT, text="digital: ", color=0xFFFFFF, x=4, y=4)
splash.append(digital_label)
alarm_label = label.Label(terminalio.FONT, text="Next: ", color=0xFFFFFF, x=4, y=14)
splash.append(alarm_label)
time_label = label.Label(terminalio.FONT, text=" ", color=0xFFFFFF, x=4, y=24)
splash.append(time_label)

display.refresh()

# Set up Relay
RELAY = DigitalInOut(board.D10)
RELAY.direction = Direction.OUTPUT

# Set up buttons
BTN_A = DigitalInOut(board.D9)
BTN_A.direction = Direction.INPUT
BTN_A.pull = Pull.UP
BTN_B = DigitalInOut(board.D6)
BTN_B.direction = Direction.INPUT
BTN_C = DigitalInOut(board.D5)
BTN_C.direction = Direction.INPUT

weekdays = {0: "Su", 1: "Mo", 2: "Tu", 3: "We", 4: "Th", 5: "Fr", 6: "Sa"}
last = 0
last_1 = 0
while True:
    if time.monotonic() - last >= 5:
        print("getting data from IO...")
        if time.monotonic() - last_1 >= 1800:
            # get data from alarm days feed
            days = io.receive_data(days_feed["key"])["value"].split(",")
            print(days)
            # get data from alarm time feed
            alarm_time = io.receive_data(time_feed["key"])["value"].split(":")
            print(alarm_time)
            # get data from skip alarm feed
            skip = io.receive_data(skip_feed["key"])["value"]
            print(skip)
            last_1 = time.monotonic()

        # Get data from digital feed
        digital_feed_data = io.receive_data(digital_feed["key"])
        digital = digital_feed_data["value"]

        # Get the datetime
        dt = io.receive_time()
        print(dt)

        # Format the datetime to iso8601
        iso_8601 = (
            f"{dt[0]:04d}-{dt[1]:02d}-{dt[2]:02d}T{dt[3]:02d}:{dt[4]:02d}:{dt[5]:02d}Z"
        )
        _time = (int(dt[3]), int(dt[4]), int(dt[5]))
        print(iso_8601)

        # Check if data is ON or OFF
        if digital == "ON":
            print("received <= ON\n")
            RELAY.value = 1
        elif digital == "OFF":
            print("received <= OFF\n")
            RELAY.value = 0
        last = time.monotonic()

        if int(alarm_time[0]) == _time[0] and int(alarm_time[1]) == _time[0]:
            if weekdays[dt[6]] in days:
                if skip == "OFF":
                    ring(RELAY, BTN_A, (BTN_A, BTN_B, BTN_C))
                if skip == "SKIP":
                    io.send_data(skip_feed["key"], "OFF")
                    time.sleep(60)

        print(weekdays[dt[6]], alarm_time[0], alarm_time[1])

        next_alarm = "{} @ {:02d}:{:02d}".format(
            str(weekdays[dt[6] + 1]), int(alarm_time[0]), int(alarm_time[1])
        )

        splash[0].text = "digital: " + digital
        splash[1].text = "Next:" + next_alarm
        splash[2].text = iso_8601

        time.sleep(0.5)

        display.refresh()

    if any((not BTN_A.value, not BTN_B.value, not BTN_C.value)):
        print(f"A: {not BTN_A.value}, B: {not BTN_B.value}, C: {not BTN_C.value}")
