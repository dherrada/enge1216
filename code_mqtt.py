# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-FileCopyrightText: 2021 Dylan Herrada for Adafruit Industries
# SPDX-FileCopyrightText: 2021 Hayden Perry
#
# SPDX-License-Identifier: MIT

import time

import math
import board
import busio
from digitalio import DigitalInOut, Direction, Pull
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

year = 0
month = 0
day = 0
hour = 0
minute = 0
second = 0
wday = 0

# UTC timezone difference
tz = -4

skip = True
ready = False
alarm = False
# Define callback functions which will be called when certain events happen.
# pylint: disable=unused-argument
def connected(client):
    # Connected function will be called when the client is connected to Adafruit IO.
    # This is a good place to subscribe to feed changes.  The client parameter
    # passed to this function is the Adafruit IO MQTT client so you can make
    # calls against it easily.
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
    # This method is called when the client subscribes to a new feed.
    print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))


def unsubscribe(client, userdata, topic, pid):
    # This method is called when the client unsubscribes from a feed.
    print("Unsubscribed from {0} with PID {1}".format(topic, pid))


# pylint: disable=unused-argument
def disconnected(client):
    # Disconnected function will be called when the client disconnects.
    print("Disconnected from Adafruit IO!")


# pylint: disable=unused-argument
def on_message(client, feed_id, payload):
    # Message function will be called when a subscribed feed has a new value.
    # The feed_id parameter identifies the feed, and the payload parameter has
    # the new value.
    print("Feed {0} received new value: {1}".format(feed_id, payload))


def on_digital_msg(client, topic, message):
    print(f"Feed {topic}: {message}")
    if message == "ON":
        RELAY.value = True
    elif message == "OFF":
        RELAY.value = False
    else:
        print("Well, that wasn't supposed to happen")

def on_iso_msg(client, topic, message):
    # Sorry about that, globals were honestly the best way to do this
    global year, month, day, hour, minute, second, wday
    print(message)
    date, time = message.split("T")
    year, month, day = [int(i) for i in date.split("-")]
    hour, minute, second = time.split(":")
    second = second.split('.')[0]
    hour = int(hour)
    minute = int(minute)
    second = int(second)

    #hour = hour - 2
    if hour + tz < 0:
        day -= 1
        if day == 0:
            if month % 2:
                day = 31
            else:
                day = 30
            month -= 1
            if month == 0:
                month = 12
            elif month == 2:
                if not year % 4:
                    if not year % 400:
                        day = 29
                else:
                    day = 28
                
    hour = (int(hour) + tz + 24) % 24

    # could add something for UTC+X

    k = day
    m = month - 2
    if month < 2:
        m = month + 10
    year1 = str(year)
    y = int(year1[2:])
    c = int(year1[:2])
    # 0.001 is band-aid fix for likely error at math.floor or lower
    wday = (k + math.floor(2.6*m - 0.2 + 0.01) - 2*c + y + math.floor(y / 4) + math.floor(c / 4)) % 7
    #print(year, month, day, hour, minute, second, wday)
    #print(alarm_time[0], type(alarm_time[0]), hour, type(hour))
    #print(alarm_time[1], type(alarm_time[1]), minute, type(minute))
    if alarm_time[0] == hour and alarm_time[1] == minute:
        print("RING")
        ring()
    elif alarm:
        io.publish("enge-1216.alarm", 0)

def ring():
    if ready:
        if ring_today:
            if not alarm:
                io.publish("enge-1216.alarm", 1)
            if not skip:
                RELAY.value = not RELAY.value
            if skip:
                io.publish("enge-1216.skip-next-alarm", "OFF")
                time.sleep(60)

def on_time(client, topic, message):
    global alarm_time
    alarm_time = [int(i) for i in message.split(':')]
    print(f"Feed {topic}: {message}")

weekdays = {0: "Su", 1: "Mo", 2: "Tu", 3: "We", 4: "Th", 5: "Fr", 6: "Sa"}
reversed_weekdays = {value : key for (key, value) in weekdays.items()}

def on_days(client, topic, message):
    global alarm_days, ring_today
    print(message)
    alarm_days = message.split(',')
    if weekdays[wday] in alarm_days:
        ring_today = True
    else:
        ring_today = False

def on_skip(client, topic, message):
    global skip
    if message == "SKIP":
        skip = True
    elif message == "OFF":
        skip = False

def on_hours(client, topic, message):
    io.get("enge-1216.digital")

def on_alarm(client, topic, message):
    global alarm
    if message == "1":
        alarm = True
    else:
        alarm = False

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

ready = True
# Start a blocking loop to check for new messages
while True:
    try:
        io.loop()
        splash[0].text = "Lamp: " + str(RELAY.value)
        splash[1].text = "Alarm time: " + ":".join([str(i) for i in alarm_time])
        splash[2].text = ",".join([str(i) for i in alarm_days])
    except (ValueError, RuntimeError) as e:
        print("Failed to get data, retrying\n", e)
        wifi.reset()
        io.reconnect()
        continue
