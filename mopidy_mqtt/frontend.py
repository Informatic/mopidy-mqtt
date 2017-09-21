# future imports
from __future__ import absolute_import
from __future__ import unicode_literals

# stdlib imports
import logging

from mopidy import core

import paho.mqtt.client as mqtt

# third-party imports
import pykka

logger = logging.getLogger(__name__)

class MQTTFrontend(pykka.ThreadingActor, core.CoreListener):
    def on_stop(self):
        logger.info("mopidy_mqtt shutting down ... ")
        self.mqtt.disconnect()

    def __init__(self, config, core):
        logger.info("mopidy_mqtt initializing ... ")
        self.core = core
        self.mqtt = mqtt.Client(client_id="mopidy", clean_session=True)
        self.mqtt.on_message = self.mqtt_on_message
        self.mqtt.on_connect = self.mqtt_on_connect
        print(config)
        self.config = config['mqtt']
        self.topic = self.config['topic']
        self.mqtt.connect_async(self.config['host'], self.config['port'], 60)
        self.mqtt.loop_start()

        super(MQTTFrontend, self).__init__()

    def mqtt_on_connect(self, client, userdata, flags, rc):
        logger.info("Connected with result code %s" % rc)

        rc = self.mqtt.subscribe(self.set_topic('+'))
        if rc[0] != mqtt.MQTT_ERR_SUCCESS:
            logger.warn("Error during subscribe: " + str(rc[0]))

    def notify_topic(self, t):
        # mopidy -> mqtt topic
        return self.topic + '/' + t

    def set_topic(self, t):
        # mqtt -> mopidy topic
        return self.topic + '/' + t + '/set'

    def notify(self, prop, value):
        # Use lowercase true/false, or raw string otherwise
        if isinstance(value, bool):
            value = str(value).lower()
        else:
            value = str(value)
        logger.info('notifying %s -> %s', prop, value)
        self.mqtt.publish(self.notify_topic(prop), value)

    def mqtt_on_message(self, mqttc, obj, msg):
        logger.info("received a message on " + msg.topic+" with payload "+str(msg.payload))

        if msg.topic == self.set_topic('playing'):
            if msg.payload == 'true':
                self.core.playback.play()
            else:
                self.core.playback.pause()
        elif msg.topic == self.set_topic('volume'):
            self.core.mixer.set_volume(int(msg.payload))
        elif msg.topic == self.set_topic('control'):
            actions = {
                b'play': self.core.playback.play,
                b'stop': self.core.playback.stop,
                b'pause': self.core.playback.pause,
                b'resume': self.core.playback.resume,
                b'next': self.core.playback.next,
                b'previous': self.core.playback.previous,
                }

            if msg.payload in actions:
                actions[msg.payload]()


    def stream_title_changed(self, title):
        self.notify('title', title)

    def volume_changed(self, volume):
        self.notify('volume', volume)

    def track_playback_started(self, tl_track):
        track = tl_track.track
        artists = ', '.join(sorted([a.name for a in track.artists]))

        self.notify('title', artists + ' - ' + track.name)

    def playback_state_changed(self, old_state, new_state):
        self.notify('playing', new_state == 'playing')
