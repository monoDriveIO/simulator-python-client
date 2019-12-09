"""base_sensor.py
Base sensor class for processing data from the simulator
"""

# lib
import struct
import threading
import traceback
import sys
import rx
import objectfactory

from monodrive.common.client import Client


class DataFrame(object):
    """Base data frame class"""
    pass


@objectfactory.Factory.register_class
class SensorLocation(objectfactory.Serializable):
    """Data model for sensor location"""
    x = objectfactory.Field()
    y = objectfactory.Field()
    z = objectfactory.Field()


@objectfactory.Factory.register_class
class SensorRotation(objectfactory.Serializable):
    """Data model for sensor rotation"""
    pitch = objectfactory.Field()
    yaw = objectfactory.Field()
    roll = objectfactory.Field()


class Sensor(objectfactory.Serializable):
    """Base sensor class for processing sensor data from the simulator."""

    sensor_type = objectfactory.Field(name='type')
    listen_port = objectfactory.Field()
    packet_size = objectfactory.Field()
    fps = objectfactory.Field()
    location = objectfactory.Nested(field_type=SensorLocation)
    rotation = objectfactory.Nested(field_type=SensorRotation)

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.framing = False
        self.expected_frames_per_step = 1

    def configure(self):
        """Function called after deserializing sensor to do any setup/config"""
        pass

    def parse(self, data: bytes, package_length: int, time: int, game_time: int) -> DataFrame:
        """
        Parse raw data into data frame object

        Args:
            data(bytes):
            package_length(int):
            time(int):
            game_time(int):

        Returns:
            Parsed data frame object
        """
        raise NotImplementedError('parse method must be implemented')

    @property
    def id(self):
        """Get the unique ID of this sensor.

        Returns:
            The string representation of the unique id.
        """
        return self.sensor_type + "_" + str(self.listen_port)


class SensorThread(threading.Thread):
    """Thread for processing sensor data from the simulator"""

    def __init__(self, host: str, sensor: Sensor, verbose: bool = False):
        super().__init__()

        # The sensor associated with this thread
        self.__sensor = sensor

        # The client that is connected to the simulator
        self.__client = Client(host, sensor.listen_port)

        # The event that is fired off when the sensor data arrives
        self.__source = rx.Observable.create(self._init_rx).publish().auto_connect(0)

        # Flag to determine if the sensor should be connected
        self.__running = False

        self.__verbose = verbose

        self.frame_buffer = []

    def _init_rx(self, observer):
        """Initialize the reactive publisher"""
        self.observer = observer

    def subscribe(self, callback):
        """Subscribe to the output of this sensor.

        Args:
            callback(func): The function that will be called when the sensor's
            data arrives. Should be of the format:
                def my_callback(data):
            The data will be a tuple of size 3. The first element is the time
            the data arrived, the second element is the game time the data
            occurred, and the third element is the data message.
        """
        self.__source.subscribe(lambda data: callback(data))

    def start(self):
        """Start the client connection for this sensor"""
        if self.__verbose:
            print("Starting {0} on {1}".format(self.__sensor.id, self.name))
        self.__running = True
        self.__client.connect()
        super().start()

    def stop(self):
        """Stop the client connection for this sensor"""
        self.__running = False
        self.__client.disconnect()
        self.join()

    def run(self):
        """Overwrite the base Thread run to start the main read loop for this
        sensor"""
        if self.__verbose:
            print("Running main sensor thread: {} - {}".format(self.__sensor.id, self.name))
        HEADER_SIZE = 12
        while self.__running:
            try:
                # Check socket for data available
                if not self.__client.data_ready():
                    continue
                # Read the header type of the message
                header = self.__client.read(HEADER_SIZE)
                length, time, game_time = struct.unpack("!IIf", header)
                data = self.__client.read(length - HEADER_SIZE)
                # Publish the message to everyone else
                package_length = length - HEADER_SIZE
                frame = self.__sensor.parse(data, package_length, time, game_time)
                self.frame_buffer.append(frame)

                if not self.__sensor.framing:
                    self.observer.on_next(self.frame_buffer)
                    self.frame_buffer = []
                elif self.__sensor.expected_frames_per_step == len(self.frame_buffer):
                    self.observer.on_next(self.frame_buffer)
                    self.frame_buffer = []

            except Exception as e:
                print("{0}: exception {1}".format(self.__sensor.id, str(e)))
                traceback.print_exc()
                break

        # Log that this sensor has stopped running
        if self.__verbose:
            print("{0}: disconnected".format(self.__sensor.id))
