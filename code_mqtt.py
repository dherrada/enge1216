# DOESN'T CURRENTLY WORK

# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-FileCopyrightText: 2021 Dylan Herrada for Adafruit Industries
# SPDX-License-Identifier: MIT
import time
from random import randint

import ssl
import socketpool
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_io.adafruit_io import IO_MQTT

# from adafruit_magtag.magtag import MagTag
### WiFi ###

# Add a secrets.py to your filesystem that has a dictionary called secrets with "ssid" and
# "password" keys with your WiFi credentials. DO NOT share that file or commit it into Git or other # source control.
# pylint: disable=no-name-in-module,wrong-import-order
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# Set your Adafruit IO Username and Key in secrets.py
# (visit io.adafruit.com if you need to create an account,
# or if you need your Adafruit IO key.)
aio_username = secrets["aio_username"]
aio_key = secrets["aio_key"]

print("Connecting to %s" % secrets["ssid"])
wifi.radio.connect(secrets["ssid"], secrets["password"])
print("Connected to %s!" % secrets["ssid"])

# Define callback functions which will be called when certain events happen.
# pylint: disable=unused-argument
def connected(client):
    # Connected function will be called when the client is connected to Adafruit IO.
    # This is a good place to subscribe to feed changes.  The client parameter
    # passed to this function is the Adafruit IO MQTT client so you can make
    # calls against it easily.
    print("Connected to Adafruit IO!  Listening for enge-1216.digital changes...")
    # Subscribe to changes on a feed named enge-1216.digital.
    client.subscribe(group_key="enge-1216")
    print("Subscribed to feed")


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
def message(client, feed_id, payload):
    # Message function will be called when a subscribed feed has a new value.
    # The feed_id parameter identifies the feed, and the payload parameter has
    # the new value.
    print("Feed {0} received new value: {1}".format(feed_id, payload))


def on_digital_msg(client, topic, message):
    print(f"Feed {topic}: {message}")


# Create a socket pool
pool = socketpool.SocketPool(wifi.radio)

# Initialize a new MQTT Client object
mqtt_client = MQTT.MQTT(
    broker="io.adafruit.com",
    username=secrets["aio_username"],
    password=secrets["aio_key"],
    socket_pool=pool,
    ssl_context=ssl.create_default_context(),
)

# Initialize an Adafruit IO MQTT Client
io = IO_MQTT(mqtt_client)

# Connect to Adafruit IO
print("Connecting to Adafruit IO...")
io.connect()

io.on_subscribe = subscribe
io.on_disconnect = disconnected
io.on_unsubscribe = unsubscribe
io.on_message = message

io.subscribe("enge-1216.digital", qos=1)
io.subscribe("enge-1216.alarm", qos=1)

io.add_feed_callback("enge1216.digital", on_digital_msg)

io.publish("enge-1216.alarm", 1)
io.publish("enge-1216.digital", "ON")

a = True
last = 0
print("Publishing a new message every 10 seconds...")
while True:
    io.get("enge1216.alarm")
    io.get("enge1216.digital")
    time.sleep(5)
    value = io.loop()
    if value:
        print(type(value))
        print(value)
    # Send a new message every 5 seconds.
    # time.sleep(5)
    """
    if (time.monotonic() - last) >= 5:
        a = not a
        if a:
            value = "ON"
        else:
            value = "OFF"
        print("Publishing {0} to enge-1216.digital.".format(value))
        io.publish("enge-1216.digital", value)
        #data = io.get("digital")
        #print(data["value"])
        #if data["value"] == "ON":
        #    magtag.peripherals.neopixels.fill((128, 0, 0))
        #elif data["value"] == "OFF":
        #    magtag.peripherals.neopixels.fill((0, 0, 0))
        last = time.monotonic()
    """
