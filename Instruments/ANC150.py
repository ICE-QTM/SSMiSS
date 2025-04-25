# -*- coding: utf-8 -*-
"""
Module to interact with an Attocube ANC150 piezo step controller.
Uses pyvisa to communicate with the device via a COM port (RS232-null modem).

Based on the instrument scripts in the QTMtoolbox by Daan Wielens.

Version 1.0 (2025-02-04)
Kylian van Dam - Master student at ICE/QTM
University of Twente
"""

import pyvisa as visa
from time import sleep

class WrongInstrErr(Exception):
    """
    A connection was established to the instrument, but the instrument
    is not an Attocube ANC150. Please retry with the correct
    COM address. Make sure that each device has a unique address.
    
    Normal port = COM1 (string)
    """
    pass

class ANC150:
    type = 'Attocube ANC150'
    MODES = {'ext', 'stp', 'gnd', 'cap'}        # Valid axis modes
    AXES = {1, 2, 3, '1', '2', '3'}
    
    def __init__(self, com):
        rm = visa.ResourceManager()
        self.__freq = [None, None, None]
        self.visa = rm.open_resource('ASRL{}::INSTR'.format(com))
        self.visa.baud_rate = 38400
        # self.visa.write_termination = '\r\n'
        # self.visa.read_termination = None
        # self.visa.data_bits = 8
        # self.visa.parity = visa.constants.Parity.none
        # self.visa.stop_bits = visa.constants.StopBits.one
        # self.visa..flow_control = visa.constants.ControlFlow.none
        
        # Discard any leftovers from old communication
        self.visa.flush(visa.constants.BufferOperation.discard_read_buffer_no_io)  
        
        # Check if device is really an Attocube ANC150 by making an identify request
        resp = self.visa.query('ver')
        while not ('OK' in resp or 'ERROR' in resp):  
            try:
                resp += self.visa.read()
            except visa.VisaIOError:
                raise WrongInstrErr('Last line of output not correctly terminated. Likely a wrong instrument: {}'.format(resp))
            
        if not 'attocube controller' in resp:
            raise WrongInstrErr('Expected Attocube controller, got {}'.format(resp))
    
    # The ANC terminates with OK or ERROR, so we read and append until we find either.
    def query(self, query):
        resp = self.visa.query(query.rstrip('\n'))
        while not ('OK' in resp or 'ERROR' in resp):  
            resp += self.visa.read()
        return resp
    
    def read_iden(self):
        return self.query('ver')
    
    # Stop all mmovement and set everything to ground, then close the connection
    def close(self):
        self.stop_axes()
        self.write_mode1('gnd')
        self.write_mode2('gnd')
        self.write_mode3('gnd')
        self.visa.close()
        return 'Closed successfully'
    
    def read_mode1(self):
        return self.read_mode(1)
    
    def read_mode2(self):
        return self.read_mode(2)
    
    def read_mode3(self):
        return self.read_mode(3)
    
    # Read what mode the axis is in
    def read_mode(self, axis):
        ANC150.__is_axis(axis)
        return self.query('getm {}'.format(axis))
    
    def write_mode1(self, mode):
        return self.write_mode(1, mode)
    
    def write_mode2(self, mode):
        return self.write_mode(2, mode)
    
    def write_mode3(self, mode):
        return self.write_mode(3, mode)
    
    # Set the mode of the axis
    def write_mode(self, axis, mode):
        ANC150.__is_axis(axis); ANC150.__is_mode(mode)
        return self.query('setm {} {}'.format(axis, mode))
    
    def read_volt1(self):
        return self.read_volt(1)
    
    def read_volt2(self):
        return self.read_volt(2)
    
    def read_volt3(self):
        return self.read_volt(3)
    
    # Read what voltage the axis is set at
    def read_volt(self, axis):
        ANC150.__is_axis(axis);
        return int(self.query('getv {}'.format(axis)).split('=')[1].split('V')[0])
    
    def write_volt1(self, voltage):
        return self.write_volt(1)
    
    def write_volt2(self, voltage):
        return self.write_volt(2)
    
    def write_volt3(self, voltage):
        return self.write_volt(3)
    
    # Set the axis to the specified voltage
    def write_volt(self, axis, voltage):
        ANC150.__is_axis(axis); ANC150.__is_volt(voltage)
        return self.query('setv {} {}'.format(axis, voltage))
    
    def read_freq1(self):
        return self.read_freq(1)
    
    def read_freq2(self):
        return self.read_freq(2)
    
    def read_freq3(self):
        return self.read_freq(3)
    
    # Read what voltage the axis is set at
    def read_freq(self, axis):
        ANC150.__is_axis(axis)
        return int(self.query('getf {}'.format(axis)).split('=')[1].split('H')[0])
    
    def write_freq1(self, frequency):
        return self.write_freq(1, frequency)
    
    def write_freq2(self, frequency):
        return self.write_freq(2, frequency)
    
    def write_freq3(self, frequency):
        return self.write_freq(3, frequency)
    
    # Set the axis to the specified voltage
    def write_freq(self, axis, frequency):
        ANC150.__is_axis(axis); ANC150.__is_freq(frequency)
        self.__freq[int(axis) - 1] = frequency
        return self.query('setf {} {}'.format(axis, frequency))
    
    def stop_axis1(self):
        return self.stop_axis(1)
    
    def stop_axis2(self):
        return self.stop_axis(2)
    
    def stop_axis3(self):
        return self.stop_axis(3)
    
    # Stop the movement of the axis
    def stop_axis(self, axis):
        ANC150.__is_axis(axis)
        return self.query('stop {}'.format(axis))
    
    # Stop the movement of all axes
    def stop_axes(self):
        for i in range(1, 4):
            self.stop_axis(i)

    def step_up1(self, steps):
        return self.step_up(1, steps)
    
    def step_up2(self, steps):
        return self.step_up(2, steps)
    
    def step_up3(self, steps):
        return self.step_up(3, steps)
    
    # Make the axis step up the specified number of steps
    def step_up(self, axis, steps):
        ANC150.__is_axis(axis); ANC150.__is_step(str(steps))
        return self.query('stepu {} {}'.format(axis, steps))
    
    def step_up_and_wait1(self, steps):
        return self.step_up_and_wait(1, steps)
    
    def step_up_and_wait2(self, steps):
        return self.step_up_and_wait(2, steps)
    
    def step_up_and_wait3(self, steps):
        return self.step_up_and_wait(3, steps)
    
    # Make the axis step up the specified number of steps, sleep until done
    def step_up_and_wait(self, axis, steps):
        ANC150.__is_axis(axis); ANC150.__is_step(str(steps));
        if str(steps) == 'c': raise ValueError('Not possible to wait for infinite movement. Use step_up() instead?')
        temp = self.step_up(axis, steps)
        sleep(int(steps) / self.__freq[int(axis) - 1])
        return temp
    
    def step_down1(self, steps):
        return self.step_down(1, steps)
    
    def step_down2(self, steps):
        return self.step_down(2, steps)
    
    def step_down3(self, steps):
        return self.step_down(3, steps)
    
    # Make the axis step up the specified number of steps
    def step_down(self, axis, steps):
        ANC150.__is_axis(axis); ANC150.__is_step(str(steps))
        return self.query('stepd {} {}'.format(axis, steps))
    
    def step_down_and_wait1(self, steps):
        return self.step_down_and_wait(1, steps)
    
    def step_down_and_wait2(self, steps):
        return self.step_down_and_wait(2, steps)
    
    def step_down_and_wait3(self, steps):
        return self.step_down_and_wait(3, steps)
    
    # Make the axis step up the specified number of steps, sleep until done
    def step_down_and_wait(self, axis, steps):
        ANC150.__is_axis(axis); ANC150.__is_step(str(steps));
        if str(steps) == 'c': raise ValueError('Not possible to wait for infinite movement. Use step_up() instead?')
        temp = self.step_down(axis, steps)
        sleep(int(steps) / self.__freq[int(axis) - 1])
        return temp


    # Functions to check validity of input arguments

    def __is_axis(axis):
        if not axis in ANC150.AXES:
           raise ValueError('Invalid axis value; axis does not exist')

    def __is_mode(mode):
        if not mode in ANC150.MODES:
           raise ValueError('Invalid mode value; mode does not exist')
            
    def __is_step(step):
        if not ((step.isnumeric() or step == 'c') and step != '0'):
            raise ValueError('Invalid step value; must be numeric or "c"')
    
    def __is_freq(freq):
        if not (isinstance(freq, int) and freq >= 0 and freq <= 8000):
            raise ValueError('Invalid freq value; must be integer 0..8000')
    
    def __is_volt(volt):
        if not (isinstance(volt, int) and volt >= 0 and volt <= 70):
            raise ValueError('Invalid freq value; must be integer 0..70')