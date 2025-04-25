# -*- coding: utf-8 -*-
"""
A collection of utility functions, mostly for adding PyQt objects

Version 1.0 (2025/04/03)
Kylian van Dam - Master Student at ICE/QTM
University of Twente
"""

from pyqtgraph.Qt.QtWidgets import QLabel, QLineEdit, QPushButton, QFrame
from pyqtgraph.Qt.QtGui import QDoubleValidator, QIntValidator
import numpy as np


#%% Functions

def addQLineEdit(parent, label, default = None):
    parent.addWidget(QLabel(label))
    if default is not None:
        default = str(default)
    line = QLineEdit(default)
    parent.addWidget(line)
    return line

# Add a QLabel and a QValidated QLineEdit object to parent, with specifications as given
def addVdtQLineEdit(parent, label, lowerbound, upperbound, default = None, double = True, scientific = False):
    # Make Validator
    if double: val = QDoubleValidator();
    else: val = QIntValidator();
    if lowerbound is not None: val.setBottom(lowerbound)
    if upperbound is not None: val.setTop(upperbound)
    if scientific: val.setNotation(QDoubleValidator.ScientificNotation)
    # Make QLineEdit
    line = addQLineEdit(parent, label, default)
    line.setValidator(val)
    return line

def addQBtn(parent, label, fun):
    btn = QPushButton(label)
    parent.addWidget(btn)
    btn.released.connect(fun)
    return btn

def addHLine(parent):
    line = QFrame();
    line.setFrameShape(QFrame.HLine);
    line.setFrameShadow(QFrame.Sunken);
    parent.addWidget(line);
    return line

def stepData(lowervx, uppervx, xsteps, lowervy, uppervy, ysteps, settle, data_rate):
    linx = np.repeat(np.linspace(lowervx, uppervx, xsteps), settle * data_rate)
    linx = np.concatenate((linx, np.flip(linx)))
    liny = np.linspace(lowervy, uppervy, ysteps)
    return [linx, liny]