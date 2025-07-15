# -*- coding: utf-8 -*-
"""
SSMiSS module to perform loose steps.

Version 1.2 (2025/05/14)
Kylian van Dam - Master Student at ICE/QTM
University of Twente
"""

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt.QtCore import QTimer, QThread
from pyqtgraph.Qt.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QFormLayout

from Modules.TabLayout import TabLayout
from Instruments.NIpci6036E import NIpci6036E
from utils import addVdtQLineEdit, addQBtn, addHLine


# Class that takes care of single steps. Adds itself to a QStackedLayout, and creates accompanying PushButton tab.
class stepUI(TabLayout, QVBoxLayout):
    def __init__(self, parent, anc, anc_axes, daq, channel, advance):
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
        self.stepmanager = StepManager(anc, anc_axes, advance)
        
        # Set up a data refresh timer
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.update_plot)
        self.data_timer.setInterval(int(1000/self.rate))
        
        # Make a layout for the meny
        self.menu = QHBoxLayout()
        self.addLayout(self.menu)
        
        self.__makeMenu(35)
        self.__makeGraph(65)

    # Extension of __init__
    def __makeMenu(self, stretchFactor):
        # Add all of the text fields and buttons vertically
        layout = QVBoxLayout()
        self.menu.addLayout(layout, stretchFactor)
        
        # Make a bar for info
        info = QHBoxLayout(); layout.addLayout(info)
        # Add a panic button
        self.closeButton = addQBtn(info, 'Stop moving!', self.stepmanager.stopAll, "quit")
        self.closeButton.setFixedSize(140, 23)
        # Add a toggle for the plot
        self.plotbox = QCheckBox('Live strain plot')
        self.plotbox.stateChanged.connect(self.__plotToggle)
        info.addWidget(self.plotbox)
        
        addHLine(layout, 10)
        
        # Store the text fields in lists, for easy access by index
        self.stepboxes = []
        self.voltboxes = []
        self.freqboxes = []
        
        directions = ["X", "Y", "Z"]
        for i in range(0, 3):
            l = QFormLayout(); layout.addLayout(l);
            stepUI.makeBoxes(l, i, directions[i])
            addQBtn(layout, 'Step {}'.format(directions[i]), (lambda d = l: self.__step(d)))
            addHLine(layout, 10)
        
        layout.addWidget(QLabel("Most recent action:"))
        self.log = QLabel("-"); layout.addWidget(self.log)
        
        layout.addStretch()
    
    # Make the menu for a single direction, extension of __init__
    def makeBoxes(layout, direction, label):
        layout.direction = direction
        layout.stepbox = addVdtQLineEdit(layout, "{} steps".format(label), -10000, 10000, 0, False)
        layout.voltbox = addVdtQLineEdit(layout, "{} voltage".format(label), 0, 70, 12, False)
        layout.freqbox = addVdtQLineEdit(layout, "{} frequency".format(label), 1, 8000, 1000, False)
        return

    # Extension of __init__
    def __makeGraph(self, stretchFactor):
        # Set graphical window for putting graphs in
        graphs = pg.GraphicsLayoutWidget()
        self.menu.addWidget(graphs, stretchFactor)
        
        # Enable antialiasing for prettier plots
        pg.setConfigOptions(antialias=True)
        
        # Prepare actual plots
        self.p1 = graphs.addPlot(title="Strain gauge voltage", row = 0, col = 0)
        self.p1.setLabel('left', "Strain (mV)")

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
        
    # Make a dictionary of variables by taking a snapshot of current values in the passed layout
    def snapshot(layout):
        settings = {}
        settings["axis"] = layout.direction
        settings["steps"] = int(layout.stepbox.text())
        settings["volt"] = int(layout.voltbox.text())
        settings["freq"] = int(layout.freqbox.text())
        return settings

    # Read data from screen and tell stepmanager to make steps
    def __step(self, i):
        settings = stepUI.snapshot(i);
        self.stepmanager.step(**settings)
        self.log.setText("Direction: {}, Stepcount: {}, Voltage: {}, Frequency: {}".format((["x", "y", "z"])[settings["axis"]], settings["steps"], settings["volt"], settings["freq"]))

    # Step according to passed settings, and wait for steps to finish
    def step(self, settings):
        self.stepmanager.stepAndWait(**settings)

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
class StepManager(QThread):
    def __init__(self, anc, anc_axes, advance):
        super(StepManager, self).__init__()
        self.anc = anc
        self.axes = anc_axes
        self.advance = advance

    # Takes steps and wait (in a thread, so the GUI does not freeze)
    def run(self):
        if self.steps > 0:
            self.anc.step_up_and_wait(self.axes[self.axis], self.steps)
        elif self.steps < 0:
            self.anc.step_down_and_wait(self.axes[self.axis], -self.steps)
        self.advance.emit()

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
    
    # Tell the anc to step
    def stepAndWait(self, axis, steps, volt, freq):
        # Write settings
        self.anc.write_mode(self.axes[axis], 'stp')
        self.anc.write_volt(self.axes[axis], volt)
        self.anc.write_freq(self.axes[axis], freq)
        self.axis = axis
        self.steps = steps
        self.start()
        
    # Perform closing statements on the ANC
    def stopAll(self):
        # Stop movement
        self.anc.stop_axes()
        # Set all axes to ground
        for i in self.axes:
            self.anc.write_mode(i, 'gnd')

