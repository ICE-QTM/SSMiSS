# -*- coding: utf-8 -*-
"""
Module to interact with a NI PCI-6036E.
Eases the process of configuring and closing tasks.

Version 1.0 (2025-02-04)
Kylian van Dam - Master student at ICE/QTM
University of Twente
"""

import nidaqmx
import nidaqmx.constants as nidaqc
import nidaqmx.stream_writers as nidaqw

#NI 6046E has bipolar input range with variable gain of 0.5, 1.0, 10, 100 and 
#16-bit analog-to-digital converter (ADC) resolution:
#   Gain ; Input range   ; Precision
#   0.5  ; [-10, 10 V]   ; 305.2 uV
#   1.0  ; [-5, 5 V]     ; 152.6 uV
#   10.0 ; [-500, 500 mV]; 15.3 uV
#   100.0; [-50, 50 mV]  ; 1.53 uV
#Sampling frequency can be 200 kS/s. Analog input is DC coupling

#Analog output, 2 voltage channels with 16-bit ADC converter resolution at [-10, 10 V].
#Precision of 302.5 uV after calibration. Noise level (DC - 400 kHz) 110 uVrms.

class NIpci6036E:
    type = 'NI PCI-6036E'

    # Set the device name and make a dictionary linking task name to task object
    def __init__(self, DEVname=''):
        self.DEVname = DEVname
        self.tasks = dict()

    # Create a task for reading from channels, and add channels to the task
    def make_read_task(self, name='', channels=set()):
        task =  nidaqmx.Task(name)
        self.tasks[task.name] = task
        for channel in channels:
            task.ai_channels.add_ai_voltage_chan(self.DEVname + '/' + channel)
        return task
    
    # Create a task for writing to channels, and add channels to the task
    def make_write_task(self, name='', channels=set(), lowerV = -10, upperV = 10):
        task =  nidaqmx.Task(name)
        self.tasks[task.name] = task
        for channel in channels:
            task.ao_channels.add_ao_voltage_chan(self.DEVname + '/' + channel, min_val = lowerV, max_val = upperV)
        # Instead of looping old data when sending from python can't keep up, give an error
        task.out_stream.regen_mode = nidaqc.RegenerationMode.DONT_ALLOW_REGENERATION
        return task
    
    # Configure logging settings
    def set_log(task, filename, groupname='', mode=nidaqc.LoggingMode.LOG_AND_READ, operation=nidaqc.LoggingOperation.OPEN_OR_CREATE):
        task.in_stream.configure_logging(filename, mode, groupname, operation)
    
    # Configure a continuous clock on a task, samps_per_chan is the buffer size for reading tasks
    def set_continuous_hardware_clock(task, freq, acquisition_type=nidaqc.AcquisitionType.CONTINUOUS, samps_per_chan=1000):
        task.timing.cfg_samp_clk_timing(freq, sample_mode=acquisition_type, samps_per_chan=samps_per_chan)
    
    # Configure a finite clock on a task, samps_per_chan is the total number of samples read/written
    def set_finite_hardware_clock(task, freq, acquisition_type=nidaqc.AcquisitionType.FINITE, samps_per_chan=1):
        task.timing.cfg_samp_clk_timing(freq, sample_mode=acquisition_type, samps_per_chan=samps_per_chan)
    
    # Set a start trigger for a task
    def set_start_trigger(target_task, origin_task):
        target_task.triggers.start_trigger.cfg_dig_edge_start_trig(f"/{origin_task.devices[0].name}/ai/StartTrigger")
    
    # Commit a task
    def commit(task):
        task.control(nidaqc.TaskMode.TASK_COMMIT)
    
    # Make a multi-channel-writer for a task
    def make_multi_channel_writer(task):
        return nidaqw.AnalogMultiChannelWriter(task.out_stream)
    
    # Read all available samples
    def read_available(task):
        return task.read(nidaqc.READ_ALL_AVAILABLE)
    
    # Ensures a task is closed, by possibly closing it
    def close_task(task):
        if task._handle == None: return
        task.close()
    
    # Ensures all tasks are closed, by possibly closing them
    def close(self):
        for task in self.tasks.values():
            NIpci6036E.close_task(task)