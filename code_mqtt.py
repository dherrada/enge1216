# pylint: disable=global-statement
# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-FileCopyrightText: 2021 Dylan Herrada for Adafruit Industries
# SPDX-FileCopyrightText: 2021 Hayden Perry
#
# SPDX-License-Identifier: MIT

import time

import math
import board
import busio
from digitalio import DigitalInOut, Direction
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
import neopixel
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_io.adafruit_io import IO_MQTT

import displayio
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306

### WiFi ###

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

displayio.release_displays()

# If you are using a board with pre-defined ESP32 Pins:
esp32_cs = DigitalInOut(board.D13)
esp32_ready = DigitalInOut(board.D11)
esp32_reset = DigitalInOut(board.D12)

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

status_light = neopixel.NeoPixel(
    board.NEOPIXEL, 1, brightness=0.2
)  # Uncomment for Most Boards

wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)

# Set up Relay
RELAY = DigitalInOut(board.D10)
RELAY.direction = Direction.OUTPUT

YEAR = 0
MONTH = 0
DAY = 0
HOUR = 0
MINUTE = 0
SECOND = 0
WDAY = 0

# UTC timezone difference
TZ = -4

SKIP = True
READY = False
ALARM = False
ALARM_TIME = None
ALARM_DAYS = None
RING_TODAY = None
# Define callback functions which will be called when certain events happen.
# pylint: disable=unused-argument
def connected(client):
    """Connected function will be called when the client is connected to Adafruit IO."""
    print("Connected to Adafruit IO!")

    # Subscribe to all messages in the enge-1216 group
    io.subscribe("enge-1216.digital")
    io.subscribe("enge-1216.alarm-default-days")
    io.subscribe("enge-1216.alarm-time")
    io.subscribe("enge-1216.skip-next-alarm")
    io.subscribe("enge-1216.alarm")

    # Subscribe to time/ISO-8601 topic
    # https://io.adafruit.com/api/docs/mqtt.html#time-iso-8601
    io.subscribe_to_time("iso")

    # Subscribe to time/hours topic
    # NOTE: This topic only publishes once every hour.
    # https://io.adafruit.com/api/docs/mqtt.html#adafruit-io-monitor
    io.subscribe_to_time("hours")


def subscribe(client, userdata, topic, granted_qos):
    """ This method is called when the client subscribes to a new feed."""
    print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))


def unsubscribe(client, userdata, topic, pid):
    """ This method is called when the client unsubscribes from a feed."""
    print("Unsubscribed from {0} with PID {1}".format(topic, pid))


# pylint: disable=unused-argument
def disconnected(client):
    """ Disconnected function will be called when the client disconnects. """
    print("Disconnected from Adafruit IO!")


# pylint: disable=unused-argument
def on_message(client, feed_id, payload):
    """ Message function will be called when a subscribed feed has a new value. """
    print("Feed {0} received new value: {1}".format(feed_id, payload))


def on_digital_msg(client, topic, message):
    """ Feed callback function that runs when the digital feed has a new value. """
    print(f"Feed {topic}: {message}")
    if message == "ON":
        RELAY.value = True
    elif message == "OFF":
        RELAY.value = False
    else:
        print("Well, that wasn't supposed to happen")


def on_iso_msg(client, topic, message):
    """ Feed callback function that runs when the time/ISO8601 feed has a new value. """
    # Sorry about that, globals were honestly the best way to do this
    global YEAR, MONTH, DAY, HOUR, MINUTE, SECOND, WDAY
    print(message)
    date, time_1 = message.split("T")
    YEAR, MONTH, DAY = [int(i) for i in date.split("-")]
    HOUR, MINUTE, SECOND = time_1.split(":")
    SECOND = SECOND.split(".")[0]
    HOUR = int(HOUR)
    MINUTE = int(MINUTE)
    SECOND = int(SECOND)

    if HOUR + TZ < 0:
        DAY -= 1
        if DAY == 0:
            if MONTH % 2:
                DAY = 31
            else:
                DAY = 30
            MONTH -= 1
            if MONTH == 0:
                MONTH = 12
            elif MONTH == 2:
                if not YEAR % 4:
                    if not YEAR % 400:
                        DAY = 29
                else:
                    DAY = 28

    HOUR = (int(HOUR) + TZ + 24) % 24

    # could add something for UTC+X

    _k = DAY
    _m = MONTH - 2
    if MONTH < 2:
        _m = MONTH + 10
    year1 = str(YEAR)
    _y = int(year1[2:])
    _c = int(year1[:2])
    # 0.001 is band-aid fix for likely error at math.floor or lower
    # fmt: off
    # pylint: disable=line-too-long
    WDAY = (_k + math.floor(2.6 * _m - 0.2 + 0.01) - 2 * _c + _y + math.floor(_y / 4) + math.floor(_c / 4)) % 7
    # pylint: enable=line-too-long
    # fmt: on
    # print(YEAR, MONTH, DAY, HOUR, MINUTE, SECOND, WDAY)
    if ALARM_TIME[0] == HOUR and ALARM_TIME[1] == MINUTE:
        print("RING")
        ring()
    elif ALARM:
        io.publish("enge-1216.alarm", 0)


def ring():
    """ Rings the alarm """
    if READY:
        if RING_TODAY:
            if not ALARM:
                io.publish("enge-1216.alarm", 1)
            if not SKIP:
                RELAY.value = not RELAY.value
            if SKIP:
                io.publish("enge-1216.skip-next-alarm", "OFF")
                time.sleep(60)


def on_time(client, topic, message):
    """ Feed callback function that runs when the alarm-time feed has a new value. """
    global ALARM_TIME
    ALARM_TIME = [int(i) for i in message.split(":")]
    print(f"Feed {topic}: {message}")


weekdays = {0: "Su", 1: "Mo", 2: "Tu", 3: "We", 4: "Th", 5: "Fr", 6: "Sa"}
reversed_weekdays = {value: key for (key, value) in weekdays.items()}


def on_days(client, topic, message):
    """ Feed callback function that runs when the alarm-default-days feed has a new value. """
    global ALARM_DAYS, RING_TODAY
    print(message)
    ALARM_DAYS = message.split(",")
    RING_TODAY = bool(weekdays[WDAY] in ALARM_DAYS)


def on_skip(client, topic, message):
    """ Feed callback function that runs when the skip-next-alarm feed has a new value. """
    global SKIP
    if message == "SKIP":
        SKIP = True
    elif message == "OFF":
        SKIP = False


def on_hours(client, topic, message):
    """ Feed callback function that runs when the time/hours feed has a new value. """
    io.get("enge-1216.digital")


def on_alarm(client, topic, message):
    """ Feed callback function that runs when the alarm feed has a new value. """
    global ALARM
    ALARM = bool(message == "1")


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

# Connect to WiFi
print("Connecting to WiFi...")
wifi.connect()
print("Connected!")

# Initialize MQTT interface with the esp interface
MQTT.set_socket(socket, esp)

# Initialize a new MQTT Client object
mqtt_client = MQTT.MQTT(
    broker="io.adafruit.com",
    username=secrets["aio_username"],
    password=secrets["aio_key"],
)

# Initialize an Adafruit IO MQTT Client
io = IO_MQTT(mqtt_client)

# Connect the callback methods defined above to Adafruit IO
io.on_connect = connected
io.on_disconnect = disconnected
io.on_subscribe = subscribe
io.on_unsubscribe = unsubscribe
io.on_message = on_message

# Connect to Adafruit IO
print("Connecting to Adafruit IO...")
io.connect()

# Set up a message handler for the battery feed
io.add_feed_callback("enge-1216.digital", on_digital_msg)
io.add_feed_callback("enge-1216.alarm-time", on_time)
io.add_feed_callback("enge-1216.alarm-default-days", on_days)
io.add_feed_callback("enge-1216.skip-next-alarm", on_skip)
io.add_feed_callback("enge-1216.alarm", on_alarm)

io.get("enge-1216.digital")
io.get("enge-1216.alarm-time")

io.loop()

io.subscribe_to_time("iso")
mqtt_client.add_topic_callback("time/ISO-8601", on_iso_msg)
mqtt_client.add_topic_callback("time/hours", on_hours)

io.loop()

io.get("enge-1216.alarm-default-days")
io.get("enge-1216.skip-next-alarm")

io.loop()

READY = True
# Start a blocking loop to check for new messages
while True:
    try:
        io.loop()
        splash[0].text = "Lamp: " + str(RELAY.value)
        splash[1].text = "Alarm time: " + ":".join([str(i) for i in ALARM_TIME])
        splash[2].text = ",".join([str(i) for i in ALARM_DAYS])
    except (ValueError, RuntimeError) as err:
        print("Failed to get data, retrying\n", err)
        wifi.reset()
        io.reconnect()
        continue
