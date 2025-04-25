# -*- coding: utf-8 -*-
"""
SSMiSS module to perform loose steps.

Version 1.0 (2025/04/03)
Kylian van Dam - Master Student at ICE/QTM
University of Twente
"""

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt.QtCore import QTimer, Qt
from pyqtgraph.Qt.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QCheckBox

from Modules.TabLayout import TabLayout
from Instruments.NIpci6036E import NIpci6036E
from utils import addVdtQLineEdit, addQBtn, addHLine


# Class that takes care of single steps. Adds itself to a QStackedLayout, and creates accompanying PushButton tab.
class stepUI(TabLayout, QVBoxLayout):
    def __init__(self, parent, anc, anc_axes, daq, channel):
        # Ensure this is actually a QVBoxLayout
        super(stepUI, self).__init__(parent)
        self.makeTab('Step Control')
        
        # Assigning variables
        self.daq = daq
        self.chan = channel
        self.__dumpData()
        self.rate = 10
        self.memory = 30
        
        # Make a StepManager
        self.stepmanager = StepManager(anc, anc_axes)
        
        # Set up a data refresh timer
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.update_plot)
        self.data_timer.setInterval(int(1000/self.rate))
        
        # Make a bar for info
        info = QHBoxLayout(); self.addLayout(info)
        # Add a panic button
        self.closeButton = addQBtn(info, 'Stop moving!', self.stepmanager.stopAll)
        self.closeButton.setFixedSize(140, 23)
        # Add a toggle for the plot
        self.plotbox = QCheckBox('Live strain plot')
        self.plotbox.stateChanged.connect(self.__plotToggle)
        info.addWidget(self.plotbox)
        # Add a label (textbox) for displaying *stuff*
        self.doc = QLabel('Feel free to step around.')
        self.doc.setAlignment(Qt.AlignHCenter)
        info.addWidget(self.doc)
        
        # Make a layout for the meny
        self.menu = QHBoxLayout()
        self.addLayout(self.menu)
        
        self.__makeMenu()
        self.__makeGraph()

    # Extension of __init__
    def __makeMenu(self):
        # Add all of the text fields and buttons vertically
        layout = QVBoxLayout()
        self.menu.addLayout(layout)
        
        # Store the text fields in lists, for easy access by index
        self.stepboxes = []
        self.voltboxes = []
        self.freqboxes = []
        
        # X
        self.stepboxes.append(addVdtQLineEdit(layout, "X steps", -10000, 10000, 0, False))
        self.voltboxes.append(addVdtQLineEdit(layout, "X voltage", 0, 70, 12, False))
        self.freqboxes.append(addVdtQLineEdit(layout, "X frequency", 1, 8000, 1000, False))
        addQBtn(layout, 'Step X', (lambda: self.__step(0)))
        
        addHLine(layout)
        
        # Y
        self.stepboxes.append(addVdtQLineEdit(layout, "Y steps", -10000, 10000, 0, False))
        self.voltboxes.append(addVdtQLineEdit(layout, "Y voltage", 0, 70, 12, False))
        self.freqboxes.append(addVdtQLineEdit(layout, "Y frequency", 1, 8000, 1000, False))
        addQBtn(layout, 'Step Y', (lambda: self.__step(1)))
        
        addHLine(layout)
        
        # Z
        self.stepboxes.append(addVdtQLineEdit(layout, "Z steps", -10000, 10000, 0, False))
        self.voltboxes.append(addVdtQLineEdit(layout, "Z voltage", 0, 70, 12, False))
        self.freqboxes.append(addVdtQLineEdit(layout, "Z frequency", 1, 8000, 1000, False))
        addQBtn(layout, 'Step Z', (lambda: self.__step(2)))

    # Extension of __init__
    def __makeGraph(self):
        # Set graphical window for putting graphs in
        graphs = pg.GraphicsLayoutWidget()
        self.menu.addWidget(graphs)
        
        # Enable antialiasing for prettier plots
        pg.setConfigOptions(antialias=True)
        
        # Prepare actual plots
        self.p1 = graphs.addPlot(title="Strain gauge voltage", row = 0, col = 0)
        self.p1.setLabel('left', "Strain")

        # Give lines fancy colours
        self.curve1 = self.p1.plot(pen='y', symbol='o', symbolPen=pg.mkPen(color='y', width=1), symbolBrush=None)
        self.curve1.setSymbolSize(5)

    # Toggle whether the live plot is plotting
    def __plotToggle(self):
        if self.plotbox.isChecked():
            # Prevent leaving the tab without turning off the live plot
            self.parent.disableTabs(self.tabs)
            # Empty data variable
            self.__dumpData()
            # Set up and start a reader and update timer
            self.read_task = self.daq.make_read_task('read', self.chan)
            NIpci6036E.set_continuous_hardware_clock(self.read_task, 10 * self.rate)
            self.read_task.start()
            self.data_timer.start()
        else:
            # Stop data acquisition
            self.data_timer.stop()
            NIpci6036E.close_task(self.read_task)
            # Enable the user to leave the tab again
            self.parent.enableTabs()

    # Read data from screen and tell stepmanager to make steps
    def __step(self, i):
        self.stepmanager.step(i, int(self.stepboxes[i].text()), int(self.voltboxes[i].text()), int(self.freqboxes[i].text()))

    # Acquires all available data
    def __acquireData(self):
        # Get strain gauge value and append it to existing data variable
        data_n = NIpci6036E.read_available(self.read_task)
        self.data = np.append(self.data, data_n)
        # Delete data more [self.memory] seconds ago
        while len(self.data) > self.memory * (10 * self.rate):
            self.data = self.data[len(self.data) - self.memory * (10 * self.rate):]

    # Get new data and update plot
    def update_plot(self):
        self.__acquireData()
        time = np.linspace(0, len(self.data), len(self.data)) * (0.1 / self.rate)
        self.curve1.setData(time, self.data)
    
    # Empty data variable
    def __dumpData(self):
        self.data = np.empty((1, 0))

    # Forcefully stop all movement and data acquisition
    def stopAll(self):
        self.stepmanager.stopAll()
        self.data_timer.stop()
        
        # Only stop the read task if it has actually been made...
        if hasattr(self, 'read_task'):
            NIpci6036E.close_task(self.read_task)

# Class for telling the ANC what to do
class StepManager():
    def __init__(self, anc, anc_axes):
        self.anc = anc
        self.axes = anc_axes

    # Tell the anc to step
    def step(self, axis, steps, volt, freq):
        # Write settings
        self.anc.write_mode(self.axes[axis], 'stp')
        self.anc.write_volt(self.axes[axis], volt)
        self.anc.write_freq(self.axes[axis], freq)
        # Write steps
        if steps > 0:
            self.anc.step_up(self.axes[axis], steps)
        elif steps < 0:
            self.anc.step_down(self.axes[axis], -steps)
    
    # Perform closing statements on the ANC
    def stopAll(self):
        # Stop movement
        self.anc.stop_axes()
        # Set all axes to ground
        for i in self.axes:
            self.anc.write_mode(i, 'gnd')

