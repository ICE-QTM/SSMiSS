# -*- coding: utf-8 -*-
"""
SSMiSS module to perform sequences of actions.

Version 1.1 (16-05-2025)
Kylian van Dam - Master Student at ICE/QTM
University of Twente
"""

from pyqtgraph.Qt.QtCore import Qt, QSize, pyqtSlot
from pyqtgraph.Qt.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFileDialog, QStackedLayout, QScrollArea, QFormLayout
from pyqtgraph.Qt.QtGui import QIcon
import os
import json

from Modules.TabLayout import TabLayout
from Modules.scanUI import scanUI, scanVars
from Modules.approachUI import approachUI, approachVars
from Modules.stepUI import stepUI
from utils import addQLineEdit, addQBtn, addHLine


#%% Classes

# Class that takes care of programs. Adds itself to a QStackedLayout, and creates accompanying PushButton tab.
class programUI(TabLayout, QVBoxLayout):
    def __init__(self, parent, signal, scan_module, approach_module, step_module):
        # Ensure this is actually a QVBoxLayout
        super(programUI, self).__init__(parent)
        self.makeTab('Program')
        
        # Connect the advance signal to the function
        self.signal = signal; self.signal.connect(self.__advance)
        self.parent = parent
        self.scan_module = scan_module
        self.approach_module = approach_module
        self.step_module = step_module
        self.i = -2                 # Keep track of which program we're currently running
        self.program = None         # Keep track of the current program
        self.type = None            # Keep track of what action is currently happening
        
        # Make a bar for info
        info = QHBoxLayout(); self.addLayout(info)
        # Add widget for starting line scans
        self.startButton = addQBtn(info, 'Start', self.__startProgram, 'confirm')
        self.startButton.setFixedSize(140, 23)
        # Add a panic button
        self.closeButton = addQBtn(info, 'Stop!', self.stopAll, 'quit')
        self.closeButton.setFixedSize(140, 23)
        # Add a label (textbox) for displaying *stuff*
        self.doc = QLabel('No active things.')
        self.doc.setAlignment(Qt.AlignHCenter)
        info.addWidget(self.doc)
        
        # Make a bar for the file selection
        file = QHBoxLayout(); self.addLayout(file)
        # Add button and text box
        self.jsonbox = addQLineEdit(file, "JSON:")
        fileButton = addQBtn(file, '', self.__openJSONFileDialog)
        fileButton.setIcon(QIcon('Icons/folder-horizontal-open.png'))
        fileButton.setIconSize(QSize(16, 16))
        self.loadButton = addQBtn(file, '(Re)load', self.__load, 'confirm')
        self.loadButton.setFixedSize(140, 23)
        
        addHLine(self)
        
        self.__makeMenu(0)
        
        # Add a box to display the current program
        self.scrollbox = QVBoxLayout(); widget = QWidget(); widget.setLayout(self.scrollbox)
        scroll = QScrollArea(); scroll.setWidget(widget)
        scroll.setWidgetResizable(True); self.addWidget(scroll, 100)
        
        # Add a textbox and button to save the current program to
        save = QHBoxLayout(); self.addLayout(save)
        self.savebox = addQLineEdit(save, "Save location:")
        saveButton = addQBtn(save, "Save to file", self.__save, 'confirm')
        saveButton.setFixedSize(140, 23)
        
        self.addStretch()

    # Extension of __init__ that creates the menu in a QStackedLayout
    def __makeMenu(self, stretchFactor):
        switchBtns = QHBoxLayout(); self.addLayout(switchBtns)
        menu = QStackedLayout(); self.addLayout(menu, stretchFactor)
        
        # Use the scanUI's functions to make the menu
        self.scanMenu = QVBoxLayout(); scanUI.makeMenu(self.scanMenu, scanVars(''), 0)
        scanWidget = QWidget(); scanWidget.setLayout(self.scanMenu); menu.addWidget(scanWidget)
        addQBtn(self.scanMenu, 'Add these settings to program!', self.__addScan, 'confirm')
        self.scanMenu.addStretch()
        
        # Use the approachUI's functions to make the menu
        self.approachMenu = QVBoxLayout(); approachUI.makeMenu(self.approachMenu, approachVars(), 0)
        approachWidget = QWidget(); approachWidget.setLayout(self.approachMenu), menu.addWidget(approachWidget)
        addQBtn(self.approachMenu, 'Add these settings to program!', self.__addApproach, 'confirm')
        self.approachMenu.addStretch()
        
        # Use the stepUI's functions to make the menu
        self.stepMenu = QHBoxLayout();
        d = ["X", "Y", "Z"]
        for i in range(0, 3):
            l = QFormLayout(); self.stepMenu.addLayout(l)
            stepUI.makeBoxes(l, i, d[i])
            addQBtn(l, 'Add these settings to program!', lambda d = l: self.__addStep(d), 'confirm')
        stepWidget = QWidget(); stepWidget.setLayout(self.stepMenu), menu.addWidget(stepWidget)
        self.stepMenu.addStretch()
        
        # Add buttons to switch between the different menus
        addQBtn(switchBtns, 'Scan settings', lambda: menu.setCurrentWidget(scanWidget))
        addQBtn(switchBtns, 'Approach settings', lambda: menu.setCurrentWidget(approachWidget))
        addQBtn(switchBtns, 'Step settings', lambda: menu.setCurrentWidget(stepWidget))

    # Opens a dialog for selecting a JSON file
    def __openJSONFileDialog(self):
        file, _ = QFileDialog.getOpenFileName(self.widget, "Open a JSON program file", "", "JSON files (*.json);;All files (*)")
        if file:
            self.jsonbox.setText(file)
            self.__load()
    
    # Fires when an action has finished. Removing the decorator breaks just about everything.
    @pyqtSlot()
    def __advance(self):
        # Is there a program?
        if self.i != -2:
            self.i += 1
            # Was this the last part of the program?
            if self.i == len(self.program):
                # Do closing stuff
                self.i = -1
                self.parent.getStack().setCurrentWidget(self.widget)
                self.startButton.setEnabled(True)
                self.parent.setDoc("")
                self.doc.setText('No active things.')
            else:
                # Start the next action
                self.startButton.setEnabled(False)
                self.type = self.program[self.i].pop("category")
                match self.type:
                    case "scan":
                        self.parent.setDoc("Started command {}/{}: line scan".format(self.i+1, len(self.program)))
                        self.parent.getStack().setCurrentWidget(self.scan_module.widget)
                        self.scan_module.startLineScan(self.program[self.i])
                    case "approach":
                        self.parent.setDoc("Started command {}/{}: approach".format(self.i+1, len(self.program)))
                        self.parent.getStack().setCurrentWidget(self.approach_module.widget)
                        self.approach_module.startApproach(self.program[self.i])
                    case "step":
                        self.parent.setDoc("Started command {}/{}: step".format(self.i+1, len(self.program)))
                        self.parent.getStack().setCurrentWidget(self.step_module.widget)
                        self.step_module.step(self.program[self.i])
    
    # Check whether a .json exists, then read it
    def __load(self):
        filename = self.jsonbox.text()
        if os.path.isfile(filename):
            with open(filename, 'r') as file:
                try:
                    self.program = json.load(file)
                    self.doc.setText('JSON loaded successfully')
                    self.__updateProgram()
                except (json.JSONDecodeError, KeyError):
                    self.program = None
                    self.doc.setText('File is not a valid JSON')
                    self.__clearProgram()
        else:
            self.program = None
            self.doc.setText('File does not exist')
            self.__clearProgram()
    
    # Save the current program to the file
    def __save(self):
        filename = self.savebox.text()
        try:
            with open(filename, 'w+') as file:
                file.write(json.dumps(self.program, indent=4))
            self.doc.setText("File saved successfully!")
        except FileNotFoundError:
            self.doc.setText("Could not open/create file")
    
    # Add a scan action to the current program
    def __addScan(self):
        if self.program is None:
            self.program = []
        temp = scanUI.snapshot(self.scanMenu)
        temp["category"] = "scan"
        self.program.append(temp)
        self.__updateProgram()
    
    # Add an approach action to the current program
    def __addApproach(self):
        if self.program is None:
            self.program = []
        temp = approachUI.snapshot(self.approachMenu)
        temp["category"] = "approach"
        self.program.append(temp)
        self.__updateProgram()
    
    # Add a step action to the current program
    def __addStep(self, layout):
        if self.program is None:
            self.program = []
        temp = stepUI.snapshot(layout)
        temp["category"] = "step"
        self.program.append(temp)
        self.__updateProgram()
    
    # Start the execution of a JSON file
    def __startProgram(self):
        if self.program is not None:
            self.i = -1
            self.doc.setText('Program started...')
            self.signal.emit()
        else:
            self.doc.setText("Please load a valid file first")
    
    # Clear the box that contains the program
    def __clearProgram(self):
        # For all widgets
        while self.scrollbox.count():
            temp = self.scrollbox.takeAt(0)
            if temp is not None:
                # If they are not a layout, catch the exception
                try:
                    # For all widgets in this layout, delete them
                    while temp.count():
                        t = temp.takeAt(0)
                        if t.widget() is not None:
                            t.widget().deleteLater()
                    temp.deleteLater()
                except AttributeError:
                    # Delete this
                    self.scrollbox.removeItem(temp)
    
    # Update the box that contians the program
    def __updateProgram(self):
        self.__clearProgram()
        
        # For every action, describe it and add nice buttons
        for i in range(0, len(self.program)):
            l = QHBoxLayout()
            # Run the correct stringify
            label = QLabel(getattr(programUI, "_programUI__{}String".format(self.program[i]["category"]))(**self.program[i]))
            l.addWidget(label)
            btn = addQBtn(l, "Up", lambda n=i: self.__up(n))
            if i == 0: btn.setEnabled(False)
            btn = addQBtn(l, "Down", lambda n=i: self.__down(n))
            if i == len(self.program)-1: btn.setEnabled(False)
            btn = addQBtn(l, "Delete", lambda n=i: self.__delete(n), 'quit')
            self.scrollbox.addLayout(l)
        self.scrollbox.addStretch()
    
    # Move this action up in the order
    def __up(self, i):
        self.program[i], self.program[i-1] = self.program[i-1], self.program[i]
        self.__updateProgram()
    
    # Move this action doen in the order
    def __down(self, i):
        self.program[i], self.program[i+1] = self.program[i+1], self.program[i]
        self.__updateProgram()
    
    # Delete this action
    def __delete(self, i):
        self.program.pop(i)
        self.__updateProgram()
    
    # Stringify scan variables
    def __scanString(category, lowervx, uppervx, lowervy, uppervy, xsteps, ysteps, settle, data_rate, refresh, log, make_heatmap, filename, groupname):
        string = ["Scan"]
        string.append("X: {}-{}V in {} steps".format(lowervx, uppervx, xsteps))
        string.append("Y: {}-{}V in {} steps".format(lowervy, uppervy, ysteps))
        string.append("Timings: settle {}s, data rate {}Hz, graph refresh {}Hz".format(settle, data_rate, refresh))
        if log: string.append("Data will be saved : filename \"{}\", groupname \"{}\"".format(filename, groupname))
        else: string.append("Data will not be logged")
        return "\n - ".join(string)
    
    # Stringify step variables
    def __stepString(category, axis, steps, volt, freq):
        string = ["Step"]
        string.append("Step direction: {}".format(axis))
        string.append("Take {} steps with {}V at {}Hz".format(steps, volt, freq))
        return "\n - ".join(string)
    
    # Stringify approach variables
    def __approachString(category, approach_stages, threshold, stepcounts, voltages, frequencies, rate, consec_req, log):
        string = ["Approach"]
        for i in range(0, approach_stages):
            string.append("Stage {} parameters: {}V, {}Hz, {}V threshold, {} steps backoff".format(i, voltages[i], frequencies[i], threshold[i], stepcounts[i]))
        string.append("Other parameters: rate {}Hz, {} consecutive exceedings, logging {}".format(rate, consec_req, log))
        return "\n - ".join(string)

    # Stop all active processes in a way where nothing breaks
    def stopAll(self):
        if self.i != -2:
            self.i = -2
            match self.type:
                case "line":
                    self.scan_module.stopAll()
                case "approach":
                    self.approach_module.stopAll()
                case "step":
                    self.step_module.stopAll()
        self.startButton.setEnabled(True)
        self.parent.setDoc("")
        self.doc.setText('Program aborted.')