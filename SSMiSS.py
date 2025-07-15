# -*- coding: utf-8 -*-
"""
Main script of the Scanning Squid Microscopy Software Suite.

Version 1.2 (2025/05/14)
Kylian van Dam - Master Student at ICE/QTM
University of Twente
"""

name = 'SSMiSS'
version = 'v1.2'
stylesheet = "style.qss"

#%% Imports and environment setup

from pyqtgraph.Qt.QtCore import Signal
from pyqtgraph.Qt.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QApplication, QStackedLayout, QLabel
from pyqtgraph.Qt.QtGui import QIcon
import sys
import os
import ctypes

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from Modules.scanUI import scanUI
from Modules.approachUI import approachUI
from Modules.stepUI import stepUI
from Modules.TDMSplotUI import TDMSplotUI
from Modules.programUI import programUI
from Instruments.NIpci6036E import NIpci6036E
from Instruments.ANC150 import ANC150
from Instruments.sr830 import sr830
from utils import addHLine

app = QApplication(sys.argv)
# Fix the styling
app.setStyle('Fusion')
with open(stylesheet, 'r') as style:
    app.setStyleSheet(style.read())
# Tell windows that yes, this process is its own thing. Necessary to give it its icon in the taskbar
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("{} {}".format(name, version))

#%% Setup - ALWAYS CHECK THESE VALUES

setup_approach = False
setup_scanner = False
setup_stepper = False
setup_TDMSplot = True
setup_program = False

if setup_scanner or setup_stepper or setup_approach:
    daq = NIpci6036E('Dev1')
    meas_list = ["ai0", "ai1"]      # [Strain gauge, _]
    write_list = ["ao0", "ao1"]     # [y-scanner, x-scanner]
    folder = 'piezo testing'        # Folder to put files into. Will be prefixed with 'Data/'

if setup_approach or setup_stepper:
    anc = ANC150(12)
    anc_axes = [1, 2, 3]            # [x, y, z]

if setup_approach:
    sr = sr830(8)

#%% Classes and functions

# The main window of the application, serving as the central class of the script for data gathering and visualisation.
class UI(QMainWindow):
    # A load of setup stuff
    
    # Why is this signal in this class rather than outside of it or in programUI, you ask? Order of operations, mostly.
    advanceTrigger = Signal()
    
    def __init__(self):
        # Take care of actually making this a QMainWindow by calling that constructor
        super(UI, self).__init__()
        
        # Set some parameters
        self.setWindowTitle("{} {}".format(name, version))
        self.setWindowIcon(QIcon("Icons/SSMiSS_icon.svg"))
        
        # The main layout is vertical stacking
        self.win = QVBoxLayout()
        # Some stuff that aparently needs to happen?
        widget = QWidget(); widget.setLayout(self.win); self.setCentralWidget(widget)
        
        # Make layout for putting switch-to-tab buttons in
        self.tabs = QHBoxLayout()
        self.win.addLayout(self.tabs)
        self.exclusions = []
        self.activeBtn = None
        
        self.doc = QLabel(""); self.win.addWidget(self.doc)
        
        addHLine(self.win)
        
        # Add QStackedLayout for the tabs to actually point somewhere
        self.stack = QStackedLayout()
        self.win.addLayout(self.stack)
    
    # Getter for the QStackedLayout that holds the modules
    def getStack(self):
        return self.stack
    
    # Getter for the QLayout that holds the switch-to-tab buttons
    def getTabs(self):
        return self.tabs
    
    def setActive(self, btn):
        if self.activeBtn:
            self.activeBtn.setStyleSheet("")
        self.activeBtn = btn
        self.activeBtn.setStyleSheet("background-color : darkCyan")

    # Buttons in the list btn will not be disabled when calling disableTabs
    def addExclusion(self, btn):
        self.exclusions.extend(btn)
    
    # Disable all switch-to-tab buttons not in [exceptions]
    def disableTabs(self, exceptions=[]):
        for i in range(0, self.getTabs().count()):
            w = self.getTabs().itemAt(i).widget()
            if not w in exceptions and not w in self.exclusions:
                w.setEnabled(False)
    
    # Enable all switch-to-tab buttons
    def enableTabs(self):
        for i in range(0, win.getTabs().count()):
            self.getTabs().itemAt(i).widget().setEnabled(True)
            
    def setDoc(self, text):
        self.doc.setText(text)


#%% Body

# Make the requested directory if it doesn't exist
if setup_scanner and not os.path.isdir('Data/' + folder):
    os.mkdir('Data/' + folder)

# Create the main window
win = UI()

# Add the selected modules to the window
if setup_stepper: stepui = stepUI(win, anc, anc_axes, daq, [meas_list[0]], win.advanceTrigger)
if setup_approach: approachui = approachUI(win, anc, anc_axes[2], sr, daq, [meas_list[0]], win.advanceTrigger)
if setup_scanner: scanui = scanUI(win, daq, meas_list, write_list, folder, win.advanceTrigger)
if setup_program: programui = programUI(win, win.advanceTrigger, scanui, approachui, stepui)
if setup_TDMSplot: tdmsui = TDMSplotUI(win)

win.showMaximized()

# Start the main event loop
app.exec_()

# Call stopAll on all included modules
for i in range(0, win.stack.count()):
    win.stack.widget(i).layout.stopAll()
QApplication.closeAllWindows()
