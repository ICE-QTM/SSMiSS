# -*- coding: utf-8 -*-
"""
SSMiSS mixin class serving as a base for all modules.

Version 1.0 (2025/04/03)
Kylian van Dam - PMaster Student at ICE/QTM
University of Twente
"""

from numpy import array as nparray
from pyqtgraph.Qt.QtWidgets import QWidget, QPushButton


# Effectively a mixin for layouts slotted into a QStackedLayout with custom tabs
class TabLayout():
    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # make a TabWidget
        self.parent = parent
        self.widget = TabWidget(self.parent.getStack(), self)
    
    # Create tabs. For creating multiple at once, pass lists to name and fun
    def makeTab(self, name=None, fun=None):
        # Ensure name and fun are one-dimensional lists
        fun = nparray([fun]).flatten().tolist()
        name = nparray([name]).flatten().tolist()
        # Loop through them and create tabs for every entry
        self.tabs = []
        for i in range(0, len(fun)):
            self.tabs.append(self.widget.addTab(self.parent.getTabs(), name[i], fun[i]))
        
    # Ensure everything can be stoped with the same syntax
    def stopAll(self):
        print("{} claims it never has anything to stop".format(type(self).__name__))


# Widget for implementing custom tabs, intended for slotting into a parent's QStackedLayout
class TabWidget(QWidget):
    # Set own layout and add self to parent's layout
    def __init__(self, parent_stack, layout):
        super(TabWidget, self).__init__()
        
        self.layout = layout; self.setLayout(self.layout)
        self.parent_stack = parent_stack; self.parent_stack.addWidget(self)
    
    # Add a tab in tab_layout to switch the QStackedLayout to me
    def addTab(self, tab_layout, name='TabWidget', fun=None):
        tabbtn = QPushButton(name)
        tab_layout.addWidget(tabbtn)
        if fun:
            tabbtn.released.connect(fun)
        else:
            tabbtn.released.connect(self.switchTab)
        return tabbtn

    # Switch the QStackedLayout to me
    def switchTab(self):
        self.parent_stack.setCurrentWidget(self)