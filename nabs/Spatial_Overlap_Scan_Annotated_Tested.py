"""
General Setup and Imports
"""
get_ipython().run_line_magic('matplotlib', 'tk')
import matplotlib.pyplot as plt
from bluesky import RunEngine
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.plans import *
from bluesky.preprocessors import run_wrapper
from bluesky.utils import install_nb_kicker
from bluesky.plan_stubs import open_run, close_run, subscribe, unsubscribe
from functools import partial
from ophyd import Device, Component as Cpt
from ophyd.sim import SynAxis, SynSignal
from ophyd.signal import EpicsSignalRO
from bluesky.callbacks import LivePlot
from pswalker.plans import walk_to_pixel
import pcdsdevices 
import numpy as np
import random 
from bluesky.simulators import summarize_plan
from pcdsdevices.device_types import Newport
import argparse


def centroid_from_motor_cross(motor, motor2, size=640., scale=1., noise_scale = 1, cross_scale = .1):

    """
    Find the centroid from the current position of the motor 
    """
        
    noise = np.random.normal(scale = noise_scale)
    position = motor.position
    position2 = motor2.position
    centroid = position*scale + position2*cross_scale
    # If we are off the screen just return a value of 0.
    if centroid < 0. or centroid > size:
        return 0.
    # Otherwise give the result
    else:
        return centroid+noise


def plan_simultaneously(x_centroid, y_centroid, x, y, x_target=None, y_target= None):
    
    """
     
    This BlueSky plan aligns the laser's centroid with the x-ray's centroid.
     
    This plan implements 'walk_to_pixel' from the pswalker (a beam alignment module). The plan uses an iterative     procedure to  align any beam to a position on a screen, when two motors move the beam along the two axes.         Liveplots are updated and show the paths taken to achieve alignment.

    
    Parameters
    ----------
    x_centroid, y_centroid : 
        These are the x_centroid and y_centroid 
    x, y: 
        These are the x_motor and y_motor
    x_target, y_target : int
        Target value on the x-axis and y-axis
        
    """
    
    #Create a figure
    fig = plt.figure(figsize=(15,10))
    fig.subplots_adjust(hspace=0.3, wspace=0.4)
    
    #The first subplot, which plots the y_centroid vs x_centroid
    ax1 = fig.add_subplot(2, 2, 1)
    ax1.invert_yaxis()
    x_centroid_y_centroid = LivePlot(y_centroid.name, x_centroid.name, ax = ax1, marker='x', markersize=7,  color='orange')
     
    #The second subplot, which plots the y_centroid and x_centroid with same x-axis (y_motor)
    ax2 = fig.add_subplot(2, 2, 3)
    ax2.set_ylabel(y_centroid.name, color='red')
    ax3 = ax2.twinx()
#     ax2.invert_yaxis()
#     ax3.invert_yaxis()
    ax3.set_ylabel(x_centroid.name, color='blue')
    y_plot_y_centroid = LivePlot(y_centroid.name, y.name, ax = ax2, marker='x', markersize=6, color='red')
    y_plot_x_centroid = LivePlot(x_centroid.name, y.name, ax = ax3, marker='o', markersize=6,  color='blue')
    
    #The third subplot, which plots the y_centroid and x_centroid with same x-axis (x_motor)
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.set_ylabel(y_centroid.name, color='green')
    ax5 = ax4.twinx()
    ax5.set_ylabel(x_centroid.name, color='purple')
    x_plot_y_centroid = LivePlot(y_centroid.name, x.name, ax = ax4,  marker='x', markersize=6, color='green')
    x_plot_x_centroid = LivePlot(x_centroid.name, x.name, ax = ax5,  marker='o', markersize=6,  color='purple')
    
    #Subscribe the plots
    token_x_centroid_y_centroid = yield from subscribe('all', x_centroid_y_centroid)
    token_y_plot_x_centroid = yield from subscribe('all', y_plot_x_centroid)
    token_y_plot_y_centroid = yield from subscribe('all', y_plot_y_centroid)
    token_x_plot_x_centroid = yield from subscribe('all', x_plot_x_centroid)
    token_x_plot_y_centroid = yield from subscribe('all', x_plot_y_centroid)
    
    #Start a new run
    yield from open_run(md={'detectors': [(x_centroid.name), (y_centroid.name)],
                        'motors': [(x.name), (y.name)],
                        'hints': {'dimensions': [(x.hints['fields'], 'primary'),
                                                 (y.hints['fields'], 'primary')]}})
    
    #Ask for the target values
    if x_target is None:
        x_target = int(input('Enter the x value: '))
    if y_target is None:
        y_target = int(input('Enter the y value: '))
    
    #Iteratively move until x_target and x-centroid are within a certain threshold of each other
    while True:
        if not np.isclose(x_target, x_centroid.get(), atol=3):
            yield from walk_to_pixel(x_centroid, x, x_target, first_step=0.1, 
                                 target_fields=[x_centroid.name, x.name], tolerance = 3, average = 5, 
                                  system=[y, y_centroid]) 
        elif not np.isclose(y_target, y_centroid.get(), atol = 3):
            yield from walk_to_pixel(y_centroid, y, y_target, first_step=0.1, tolerance = 3, average = 5,
                                  target_fields=[y_centroid.name, y.name],
                                  system=[x, x_centroid])    
        else: 
            break
    
#     plt.show(block=True)

    #Close the run
    yield from close_run()
    #Unsubscribe the plots
    yield from unsubscribe(token_x_centroid_y_centroid)
    yield from unsubscribe(token_y_plot_x_centroid)
    yield from unsubscribe(token_y_plot_y_centroid)
    yield from unsubscribe(token_x_plot_x_centroid)
    yield from unsubscribe(token_x_plot_y_centroid)
    
    
if __name__ == '__main__':
    
    """
     This creates multiple dependencies that users can use when running the Spatial Overlap Scan
    """
        
    parser = argparse.ArgumentParser(description='Spatial overlap of timetool')
    parser.add_argument('--sim', action='store_true', default=False, help='Do a simulated scan')
    args = parser.parse_args()
        
    # Interactive matplotlib mode
    plt.ion()
    # Create a RunEngine
    RE = RunEngine()
    # Use BestEffortCallback for nice vizualizations during scans
    bec = BestEffortCallback()
    # Install our notebook kicker to have plots update during a scan
    install_nb_kicker()

    if args.sim:
        # Create our motors
        x_motor = SynAxis(name='x')
        y_motor = SynAxis(name='y')
        #Defines relationships between centroids and motors
        x_centroid = SynSignal(func=partial(centroid_from_motor_cross, x_motor,y_motor, noise_scale = 1), name='x_syn')
        y_centroid = SynSignal(func=partial(centroid_from_motor_cross, y_motor,x_motor), name='y_syn')
        print('Running Simulated Scan')
    else:
        #The Newport motors
        x_motor = Newport('XPP:LAS:MMN:13', name = 'real_x')
        y_motor = Newport('XPP:LAS:MMN:14', name = 'real_y')
        #Readback from actual beamline devices
        x_centroid = EpicsSignalRO('XPP:OPAL1K:01:Stats2:CentroidX_RBV', name = 'x_readback')
        y_centroid = EpicsSignalRO('XPP:OPAL1K:01:Stats2:CentroidY_RBV', name = 'y_readback')
        print('Running Real Scan')

    #Executes the plan
    RE(plan_simultaneously(x_centroid, y_centroid, x_motor, y_motor), md={'plan_name': 'special'})
    print('Spatial Overlap Scan is complete')
    
    
"""

Things to fix/consider:
        Lose ipython dependency
        User can set tolerance(Look at Spatial_Overlap_Scan_Annotated_Dependecoes.py)
        Solve edge case:
             Limits of the motor motion

"""