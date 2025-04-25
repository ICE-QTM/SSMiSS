# -*- coding: utf-8 -*-
"""
SSMiSS module to perform approaches.

Version 1.0 (2025/04/03)
Kylian van Dam - Master Student at ICE/QTM
University of Twente
"""

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt.QtCore import QThread, QTimer, Qt
from pyqtgraph.Qt.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QCheckBox
import threading
from time import sleep

from Modules.TabLayout import TabLayout
from Instruments.NIpci6036E import NIpci6036E
from utils import addVdtQLineEdit, addQBtn


#%% Defaults and standards (most of which can be freely changed at runtime), packed in one neat class

class approachVars():
    # Set up default values for a scan
    def __init__(self):
        self.threshold = [-5e-7, -5e-7]                 # Threshold for stopping aproach
        self.stepcounts = [1000, 200]                   # Lists retreat steps per cycle during approach stages
        self.approach_stages = len(self.stepcounts)     # Number of stages in the approach
        self.voltages = [12, 12]                        # (V) Lists approach voltage during approach stages
        self.frequencies = [200, 50]                    # (Hz) Lists approach frequency during approach stages
        self.rate = 10                                  # (Hz) Data query rate
        self.consec_req = 3                             # Defines how many times in a row the thershold must be met


#%% Classes

# Class that takes care of approaches. Adds itself to a QStackedLayout, and creates accompanying PushButton tab.
class approachUI(TabLayout, QVBoxLayout):
    def __init__(self, parent, anc, anc_z, sr, daq, channel):
        # Ensure this is actually a QVBoxLayout
        super(approachUI, self).__init__(parent)
        self.makeTab('Approach')
        
        # Create a variable storage object
        self.av = approachVars()
        
        # Assigning variables
        self.anc = anc
        self.z = anc_z
        self.sr = sr
        self.daq = daq
        self.chan = channel
        self.__dumpData()
        
        # Set up a data refresh timer
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.__dataLoop)
        self.data_timer.setInterval(int(1000/self.av.rate))
        
        # Create thread for switching appraoch stage. This needs to happen before app.exec_()
        self.approach = ApproachThread(self.av, self, self.anc, self.z)
        
        # Make a bar for info
        info = QHBoxLayout(); self.addLayout(info)
        # Add widget for starting approaches
        self.startButton = addQBtn(info, 'Start approach', self.__startApproach)
        self.startButton.setFixedSize(140, 23)
        # Add a panic button
        self.closeButton = addQBtn(info, 'Stop approach!', (lambda: self.approach.endApproachStage(True)))
        self.closeButton.setFixedSize(140, 23)
        # Add a label (textbox) for displaying *stuff*
        self.doc = QLabel('No active approach.')
        self.doc.setAlignment(Qt.AlignHCenter)
        info.addWidget(self.doc)
        
        self.__makeMenu()
        self.__makeGraphs()

    # Extension of __init__
    def __makeMenu(self):
        # Add a horizontal bar, for stage 1 related text boxes
        stage1 = QHBoxLayout()
        self.addLayout(stage1)
        # Add text boxes and labels
        stage1.addWidget(QLabel("Stage 1: "))
        self.step1box = addVdtQLineEdit(stage1, "Steps", 1, 10000, self.av.stepcounts[0], False)
        self.volt1box = addVdtQLineEdit(stage1, "Voltage", 0, 70, self.av.voltages[0], False)
        self.freq1box = addVdtQLineEdit(stage1, "Frequency", 1, 8000, self.av.frequencies[0], False)
        self.threshold1box = addVdtQLineEdit(stage1, "Threshold", None, None, self.av.threshold[0], scientific=True)
        
        # Add a horizontal bar, for stage 1 related text boxes
        stage2 = QHBoxLayout()
        self.addLayout(stage2)
        # Add text boxes and labels
        stage2.addWidget(QLabel("Stage 2: "))
        self.step2box = addVdtQLineEdit(stage2, "Steps", 1, 10000, self.av.stepcounts[1], False)
        self.volt2box = addVdtQLineEdit(stage2, "Voltage", 0, 70, self.av.voltages[1], False)
        self.freq2box = addVdtQLineEdit(stage2, "Frequency", 1, 8000, self.av.frequencies[1], False)
        self.threshold2box = addVdtQLineEdit(stage2, "Threshold", None, None, self.av.threshold[1], scientific=True)
        
        # Add another horizontal bar, for general text boxes
        params = QHBoxLayout()
        self.addLayout(params)
        # Add text boxes and labels
        self.stagebox = QCheckBox('Perform 2nd stage')
        params.addWidget(self.stagebox)
        self.ratebox = addVdtQLineEdit(params, "Data rate (Hz)", 1, 10000, self.av.rate)
        self.consecbox = addVdtQLineEdit(params, "Consecutive threshold exceedings", 1, None, self.av.consec_req, False)

    # Extension of __init__
    def __makeGraphs(self):
        # Set graphical window for putting graphs in
        graphs = pg.GraphicsLayoutWidget()
        self.addWidget(graphs)
        
        # Enable antialiasing for prettier plots
        pg.setConfigOptions(antialias=True)
        
        # Prepare actual plots
        self.p1 = graphs.addPlot(title="Strain gauge voltage", row = 0, col = 0)
        self.p1.setLabel('bottom', "Sample #"); self.p1.setLabel('left', "Strain")
        self.p2 = graphs.addPlot(title="dV/dT", row = 0, col = 1)
        self.p2.setLabel('bottom', "Sample #"); self.p2.setLabel('left', "Derivative of strain")
        
        # Give lines fancy colours
        self.curve1 = self.p1.plot(pen='y', symbol='o', symbolPen=pg.mkPen(color='y', width=1), symbolBrush=None)
        self.curve1.setSymbolSize(5)
        self.curve2 = self.p2.plot(pen='r', symbol='o', symbolPen=pg.mkPen(color='r', width=1), symbolBrush=None)
        self.curve2.setSymbolSize(5)

    # Acquire all available data, add timestamps, and calculate derivatives
    def __acquireData(self):
        # Read strain gauge value
        data_n = NIpci6036E.read_available(self.read_task)              
        # Allocate memory for the derivatives
        der_arr_n = np.zeros((len(data_n)))
        # Is this the first data we collect?
        if np.size(self.data) == 0:
            # Calculate timestamps for the data
            time_n = np.linspace(0, len(data_n)-1, len(data_n)) * (0.2 / self.av.rate)
        else:
            # Calculate timestamps for the data
            time_n = np.linspace(1, len(data_n), len(data_n)) * (0.2 / self.av.rate) + self.data[0, -1]
            # Calculate the derivative between the first of this chunk of data and the last of the previous one
            der_arr_n[0] = (data_n[0] - self.data[1, -1]) / (time_n[0] - self.data[0, -1])
        # Add everything to existing data
        self.data = np.append(self.data, np.vstack((time_n, data_n)), 1)
        
        # Calculate the other derivaties
        for i in range(-1, -np.size(der_arr_n), -1):
            der_arr_n[i] = (data_n[i] - data_n[i-1]) / (time_n[i] - time_n[i-1])
        # Add everything to the array
        self.der_arr = np.append(self.der_arr, der_arr_n)

    # Get new data, calculate derivative and update plots
    def __updateApproachPlots(self):
        self.__acquireData()
        
        # Update plots
        self.curve1.setData(self.data[0], self.data[1])
        self.curve2.setData(self.data[0], self.der_arr)

    # Check if we reached the threshold, and if so, end the approach stage
    def __checkThreshold(self):
        if self.der_arr[-1] < self.av.threshold[self.approach.stage]:
            self.consec += 1                        # The threshold was consecutively reached once more
            if self.consec == self.av.consec_req:   # The threhsold was consecutively reached often enough
                self.approach.endApproachStage()
        else:
            self.consec = 0                         # The threshold was not consecutively reached

    # Gets executed whenever the data QTimer fires
    def __dataLoop(self):
        self.__updateApproachPlots()
        # Prevents checking the threshold when we've already reached the consecutive requirement
        if self.consec != self.av.consec_req:
            self.__checkThreshold()

    # Start the approach
    def __startApproach(self):
        self.parent.disableTabs(self.tabs)              # Prevent leaving this module
        self.startButton.setEnabled(False)              # Prevent starting another approach
        
        self.doc.setText('Preaparing approach...')
        self.__snapshot()
        
        # Instrument prep
        self.anc.write_mode(self.z, 'stp')
        self.sr.write_offset('1')
        
        # Creating storage variables
        self.__dumpData()
        self.consec = self.av.consec_req
        self.approach.stage = -1
        
        # Make a read task
        self.read_task = self.daq.make_read_task('read', self.chan)
        NIpci6036E.set_continuous_hardware_clock(self.read_task, 5 * self.av.rate)
        
        # Start doing stuff
        self.read_task.start()
        self.data_timer.start()
        self.approach.start()
    
    # Empty data variables
    def __dumpData(self):
        self.data = np.empty((2, 0))
        self.der_arr = np.array([])
    
    # Make a snapshot of all values currently on screen, and put them in the approachVars object
    def __snapshot(self):
        if self.stagebox.isChecked():
            self.av.threshold = [float(self.threshold1box.text()), float(self.threshold2box.text())]
            self.av.stepcounts = [int(self.step1box.text()), int(self.step2box.text())]
            self.av.voltages = [int(self.volt1box.text()), int(self.volt2box.text())]
            self.av.frequencies = [int(self.freq1box.text()), int(self.freq2box.text())]
            self.av.approach_stages = 2
        else:
            self.av.threshold = [float(self.threshold1box.text())]
            self.av.stepcounts = [int(self.step1box.text())]
            self.av.voltages = [int(self.volt1box.text())]
            self.av.frequencies = [int(self.freq1box.text())]
            self.av.approach_stages = 1
        self.av.rate = float(self.ratebox.text())
        self.av.consec_req = int(self.consecbox.text())
    
    # Forcefully stop approach movement
    def stopAll(self):
        self.anc.write_mode(self.z, 'gnd')
        self.approach.endApproachStage(True)

# Thread that handles changing approach stages. It does not itself know when to change.
class ApproachThread(QThread):
    def __init__(self, approach_vars, win, anc, anc_z):
        super(ApproachThread, self).__init__()
        self.av = approach_vars
        self.win = win
        self.anc = anc
        self.z = anc_z
        self.stage = -1
    
    # Starts the next approach stage
    def run(self):
        print('Next approach thread {}'.format(threading.get_ident()))
        self.win.doc.setText('Changin to stage {}'.format((self.stage + 2)))
        
        # If there was a stage before this one
        if self.stage != -1:
            self.win.doc.setText('Backing off a bit...')
            self.anc.step_down_and_wait(self.z, self.steps)
        
        # Change settings to finer ones
        self.__nextStage()
        self.win.doc.setText('Stabilisation sleep...')
        sleep(5)
        self.win.consec = 0
        
        # Start moving forwards
        self.__writeSteps('c')
        self.win.doc.setText('Approach stage {} in progress'.format((self.stage + 1)))

    # Load variables of the next scanning stage
    def __nextStage(self):
        self.stage += 1
        self.anc.write_volt(self.z, self.av.voltages[self.stage])
        self.anc.write_freq(self.z, self.av.frequencies[self.stage])
        self.steps = self.av.stepcounts[self.stage]
    
    # Tell the anc to step
    def __writeSteps(self, steps=''):
        if steps == 'c':
            self.anc.step_up(self.z, steps)
        else:
            if steps > 0:
                self.anc.step_up(self.z, steps)
            elif steps < 0:
                self.anc.step_down(self.z, -steps)
    
    # End the current approach stage
    def endApproachStage(self, end_all=False):
        self.terminate()
        
        # Stop movement
        self.anc.stop_axis(self.z)
        
        # Do we have more stages left?
        if (self.stage + 1) < self.av.approach_stages and not end_all:
            # Move the actual backing off and waiting for stabilisation to a different thread
            print('Creating next approach thread from {}'.format(threading.get_ident()))
            self.start()
        else:
            # Do some turning off
            self.win.data_timer.stop()
            # Only try to close the read_task if it actually exists, it might not have been made yet...
            if hasattr(self.win, 'read_task'):
                NIpci6036E.close_task(self.win.read_task)
            
            # If forcibly ended
            if end_all:
                self.win.doc.setText('Approach stopped')
            else:
                self.win.doc.setText('Approach complete')
            
            # Allow starting new things again
            self.win.startButton.setEnabled(True)
            self.win.parent.enableTabs()
