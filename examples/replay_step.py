"""example.py
An example of creating a simulator and processing the sensor outputs.
"""
# lib
import json
import os
import time
import signal
import matplotlib.pyplot as plt

# src
from monodrive.simulator.simulator import Simulator
from monodrive.sensors.collision import Collision
from monodrive.sensors.gps import GPS
from monodrive.sensors.imu import IMU
from monodrive.sensors.rpm import RPM
from monodrive.sensors.radar import Radar
from monodrive.sensors.state import State
from monodrive.sensors.ultrasonic import Ultrasonic
from monodrive.sensors.camera import Camera
from monodrive.sensors.lidar import Lidar


def perception_on_update(frame):
    if frame:
        print("Perception system with image size {0}".format(len(frame[0].image)))
        plt.imshow(frame[0].image)
        plt.draw()
        plt.pause(0.0001)
        plt.clf()
    else:
        print("no image")


def reporting_on_update(data):
    print("Reporting Data *********** {0}".format(data[0].frame))


if __name__ == "__main__":
    root = os.path.dirname(__file__)

    # Flag to allow user to stop the simulation from SIGINT
    running = True


    def handler(signum, frame):
        """"Signal handler to turn off the simulator with ctl+c"""
        global running
        running = False


    signal.signal(signal.SIGINT, handler)

    # Load the trajectory, simulator and sensor configurations
    trajectory = json.load(open(os.path.join(root, 'trajectories', 'HighWayExitReplay.json')))
    sim_config = json.load(open(os.path.join(root, 'configurations', 'simulator.json')))
    sensor_config = json.load(open(os.path.join(root, 'configurations', 'all_sensors.json')))

    # configure this simulator client
    # Load the reporting sensor configuration and software under test
    # reporting_config = json.load(open(os.path.join(root, 'monodrive', 'reporting_config.json')))
    simulator = Simulator(sim_config, trajectory, sensor_config)

    # Load and configure the weather conditions for the simulator
    weather = json.load(open(os.path.join(root, 'configurations', 'weather.json')))
    profile = weather['profiles'][10]
    profile['id'] = 'test'

    # Start the simulation
    simulator.start()

    # Subscribe to sensors of interest
    # simulator.subscribe_to_sensor('Camera_8000', perception_on_update)
    simulator.subscribe_to_sensor('Collision_8800', reporting_on_update)

    # Start stepping the simulator
    time_steps = []
    for i in range(0, len(trajectory) - 1):
        start_time = time.time()
        response = simulator.step()
        dt = time.time() - start_time
        time_steps.append(dt)
        print("Step = {0} completed in {1:.2f}ms".format(i, (dt * 1000), 2))
        # time.sleep(1)
        if running is False:
            break

    fps = 1.0 / (sum(time_steps) / len(time_steps))
    print('Average FPS: {}'.format(fps))

    print("Stopping the simulator.")
    simulator.stop()