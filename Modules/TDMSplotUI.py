# -*- coding: utf-8 -*-
"""
SSMiSS module for post-processing of .tdms files.

Version 1.0.1 (2025/04/25)
Kylian van Dam - Master Student at ICE/QTM
University of Twente
"""

from pyqtgraph.Qt.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFileDialog
from pyqtgraph.Qt.QtCore import QSize, QThread
from pyqtgraph.Qt.QtGui import QIcon
import nptdms as npt
import numpy as np
from numpy.polynomial import Polynomial as P
import pyqtgraph as pg
from os import path

from Modules.TabLayout import TabLayout
from utils import addQLineEdit, addVdtQLineEdit, addQBtn, stepData


#%% Defaults and standards (most of which can be freely changed at runtime), packed in one neat class

class tdmsVars():
    # Set up default values for a scan
    def __init__(self):
        # Path to file, relative or full
        self.file = None
        self.suffix = None
        self.use_old_naming_schame = False       # Old naming scheme had info in file name rather than group name
        self.group = 0                           # Index of group to use
        self.channel = 0                         # Index of channel to use
        self.skip = 0                            # Skip the first [fraction] values of every settle period
        self.ystart = 0                          # Crop data to start at value
        self.yend = 0                            # Crop data to end at value (0 corrects to no cropping)


#%% Classes

# Class that takes care of analysing .tdms files. Adds itself to a QStackedLayout, and creates accompanying PushButton tabs.
class TDMSplotUI(TabLayout, QVBoxLayout):
    def __init__(self, parent):
        # Ensure this is actually a QVBoxLayout
        super(TDMSplotUI, self).__init__(parent)
        self.makeTab('TDMS plotting')
        self.parent.addExclusion(self.tabs)
        
        # Create variables
        self.tv = tdmsVars()
        
        # Make a thread to offload work onto
        self.thread = HeatmappifyThread(self, self.tv)
        self.thread.finished.connect(self.updateGraphs)
        self.conversion = MakeCSVThread(self, self.tv)
        
        # Make a bar for the file selection
        file = QHBoxLayout(); self.addLayout(file)
        # Add button and text box to the bar
        self.tdmsbox = addQLineEdit(file, "TDMS:")
        self.tdmsbox.setReadOnly(True)
        fileButton = addQBtn(file, '', self.__openTDMSFileDialog)
        fileButton.setIcon(QIcon('Icons/folder-horizontal-open.png'))
        fileButton.setIconSize(QSize(16, 16))
        
        self.win = QHBoxLayout()
        self.addLayout(self.win)
        
        self.__makeUI()
        self.__makeGraphs()
    
    # Extension of __init__
    def __makeUI(self):
        control = QVBoxLayout(); self.win.addLayout(control)
        
        # Add a button to covert groups to csv
        self.groupnamebox = addQLineEdit(control, "Conversion file suffix: ")
        self.convertButton = addQBtn(control, 'Convert group to csv', self.__convert)
        self.convertButton.setFixedSize(180, 23)
        
        # Add a combobox to select the group
        control.addWidget(QLabel('Group:'))
        self.groupbox = QComboBox(); control.addWidget(self.groupbox)
        # When the selected group changes, fire a function to update the channel combobox
        self.groupbox.activated.connect(self.__groupChange)
        
        # Add a combobox to select the channel
        control.addWidget(QLabel('Channel:'))
        self.chanbox = QComboBox(); control.addWidget(self.chanbox)
        
        # Add more fields to enter values
        self.skipbox = addVdtQLineEdit(control, 'Skip fraction:', 0, 1, 0)
        self.lybox = addVdtQLineEdit(control, 'Starting y:', 0, None, 0, False)
        self.uybox = addVdtQLineEdit(control, 'Ending y:', 0, None, 0, False)
        
        # Add a button to start the analysis
        self.startButton = addQBtn(control, 'Start analysis', self.__calculate)
        self.startButton.setFixedSize(140, 23)
    
    # Extension of __init__
    def __makeGraphs(self):
        # Make actual plots
        plot = pg.GraphicsLayoutWidget()
        self.win.addWidget(plot)
        
        pg.setConfigOptions(antialias=True)
        
        # Create the plots
        p1 = plot.addPlot(title="Forwards (µV)", row = 0, col = 0)
        p2 = plot.addPlot(title="Backwards  (µV)", row = 0, col = 1)
        p3 = plot.addPlot(title="Difference  (µV)", row = 1, col = 0)
        p4 = plot.addPlot(title="Range per row (µV)", row = 1, col = 1);
        
        # Put in a placeholder image
        self.image1 = pg.ImageItem(np.zeros((1, 1)))
        p1.addItem(self.image1, axisOrder='row-major')
        self.colorbar1 = p1.addColorBar(self.image1, colorMap=pg.colormap.get('CET-D1'), interactive=False)
        
        # Put in a placeholder image
        self.image2 = pg.ImageItem(np.zeros((1, 1)))
        p2.addItem(self.image2, axisOrder='row-major')
        self.colorbar2 = p2.addColorBar(self.image2, colorMap=pg.colormap.get('CET-D1'), interactive=False)
        
        # Put in a placeholder image
        self.image3 = pg.ImageItem(np.zeros((1, 1)))
        p3.addItem(self.image3, axisOrder='row-major')
        self.colorbar3 = p3.addColorBar(self.image3, colorMap=pg.colormap.get('CET-D1'), interactive=False)
        
        # Make two different-coloured curves
        self.curve4a = p4.plot(pen='y'); self.curve4b = p4.plot(pen='r')
        p4.setLabel('bottom', "Row"); p4.setLabel('left', "Strain (µV)")

    # Takes the values set with TDMSplotUI.setData() and displays them in the graphs
    def updateGraphs(self):
        self.image1.setImage(image=self.imagef)
        self.colorbar1.setLevels(low = min(np.min(self.imagef), np.min(self.imageb)), high = max(np.max(self.imagef), np.max(self.imageb)))
        self.image2.setImage(image=self.imageb)
        self.colorbar2.setLevels(low = min(np.min(self.imagef), np.min(self.imageb)), high = max(np.max(self.imagef), np.max(self.imageb)))
        self.image3.setImage(image=self.difference)
        self.colorbar3.setLevels(low = np.min(self.difference), high = np.max(self.difference))
        self.curve4a.setData(self.rangesf); self.curve4b.setData(self.rangesb)
        self.startButton.setEnabled(True)
        self.convertButton.setEnabled(True)
    
    # Store data in variables
    def setData(self, imagef, imageb, rangesf, rangesb):
        self.imagef = imagef
        self.imageb = imageb
        self.rangesf = rangesf
        self.rangesb = rangesb
        self.difference = self.imagef - self.imageb
    
    # Opens a dialog for selecting a JSON file
    def __openTDMSFileDialog(self):
        file, _ = QFileDialog.getOpenFileName(self.widget, "Open a TDMS file", "", "TDMS files (*.tdms);;All files (*)")
        if file:
            self.tdmsbox.setText(file)
            # Read metadata
            with npt.TdmsFile.read_metadata(file) as tdms:
                # Get all groups
                self.groups = tdms.groups()
                # Make a dictionary where every group leads to its channels
                self.channels = {group.name: group.channels() for group in self.groups}
                # (Re)populate the groupbox
                self.groupbox.clear()
                self.groupbox.addItems([group.name for group in self.groups])
                # (Re)populate the channelbox
                self.__groupChange(self.groupbox.currentText())
    
    # (Re)populate the channelbox to contain the group names' associated channels
    def __groupChange(self, text):
        self.chanbox.clear()
        self.chanbox.addItems([channel.name for channel in self.channels[text]])
    
    def __convert(self):
        self.startButton.setEnabled(False)
        self.convertButton.setEnabled(False)
        self.__snapshot()
        self.conversion.start()
    
    # Read data from the screen and set it, then start the analysis thread
    def __calculate(self):
        self.startButton.setEnabled(False)
        self.convertButton.setEnabled(False)
        self.__snapshot()
        self.thread.start()
        
    def __snapshot(self):
        # Path to file, relative or full
        self.tv.file = self.tdmsbox.text()
        self.tv.suffix = self.groupnamebox.text()
        self.tv.use_old_naming_schame = False           # Old naming scheme had info in file name rather than group name
        self.tv.group = self.groupbox.currentIndex()    # Index of group to use
        self.tv.channel = self.chanbox.currentIndex()   # Index of channel to use
        self.tv.skip = float(self.skipbox.text())       # Skip the first [fraction] values of every settle period
        self.tv.ystart = int(self.lybox.text())         # Crop data to start at value
        self.tv.yend = int(self.uybox.text())           # Crop data to end at value (0 corrects to no cropping)
        
    # Stops everything this module is doing
    def stopAll(self):
        self.thread.terminate()
        self.conversion.terminate()


# Thread to easily convert tdms groups to csv files (in a format readable by QTMplot!)
class MakeCSVThread(QThread):
    def __init__(self, plotUI, tdmsVars):
        super(MakeCSVThread, self).__init__()
        self.plotUI = plotUI
        self.tv = tdmsVars
    
    def run(self):
        # Make the file name
        csv = self.tv.file[:-5] + self.tv.suffix + ".csv"
        # Only do anything if the requested filename does not exist
        if path.exists(csv):
            print("File already exists. Conversion aborted.")
        else:    
            # Open the tdms
            with npt.TdmsFile.open(self.tv.file) as tdms:
                # Get the correct group
                group = tdms.groups()[self.tv.group]
                # Turn it into a pandas dataframe, also turn the index column into an actual column since it is our time column and we want it printed
                df = group.as_dataframe(True).reset_index(names="time")
                
                # Read the specifics of this measurement
                splitted = group.name.split('_')
                lowervx = float(splitted[0].split('-')[0][2:])
                uppervx = float(splitted[0].split('-')[1])
                xsteps = int(splitted[0].split('-')[2])
                lowervy = float(splitted[1].split('-')[0][2:])
                uppervy = float(splitted[1].split('-')[1])
                ysteps = int(splitted[1].split('-')[2])
                settle = float(splitted[2].split('-')[1])
                data_rate = int(1 / group.channels()[0].properties["wf_increment"])
                
                # Reproduce the input voltages using aforementioned specifics
                [linx, liny] = stepData(lowervx, uppervx, xsteps, lowervy, uppervy, ysteps, settle, data_rate)
                liny = np.repeat(liny, len(linx))
                linx = np.tile(linx, ysteps)
                
                # Add the input voltages to the dataframe
                df.drop(range(len(linx), df.shape[0]), inplace=True)
                df.insert(1, 'xvolt', linx)
                df.insert(2, 'yvolt', liny)
                
                # Create a header compatible with QTMplot/qtmimport
                head = np.datetime_as_string(group.channels()[0].properties["wf_start_time"]) + '|sssgg\n' + group.name + '\n' + ', '.join(df.columns)
            # Write everything to the file
            np.savetxt(csv, df, delimiter=', ', newline='\n', header = head, comments = '', fmt='%g')

        self.plotUI.startButton.setEnabled(True)
        self.plotUI.convertButton.setEnabled(True)


# Thread that handles the actual analysis.
class HeatmappifyThread(QThread):
    def __init__(self, plotUI, tdmsVars):
        super(HeatmappifyThread, self).__init__()
        self.plotUI = plotUI
        self.tv = tdmsVars
    
    def run(self):
        print("Opening file...")
        with npt.TdmsFile.open(self.tv.file) as tdms:
            # Find the desired group and channel
            group = tdms.groups()[self.tv.group]
            channel = group.channels()[self.tv.channel]
            
            # Read properties for recreation of input
            if self.tv.use_old_naming_schame:
                splitted = self.tv.file.split('_')[-4:]
            else:
                splitted = group.name.split('_')
            lowervx = float(splitted[0].split('-')[0][2:])
            uppervx = float(splitted[0].split('-')[1])
            xsteps = int(splitted[0].split('-')[2])
            lowervy = float(splitted[1].split('-')[0][2:])
            uppervy = float(splitted[1].split('-')[1])
            ysteps = int(splitted[1].split('-')[2])
            settle = float(splitted[2].split('-')[1])
            
            # Recreate input
            data_rate = int(1 / channel.properties["wf_increment"])
            [linx, liny] = stepData(lowervx, uppervx, xsteps, lowervy, uppervy, ysteps, settle, data_rate)
            repeats = int(settle * data_rate)
            skip = int(self.tv.skip * repeats)
            
            print("Making heatmaps...")
            linef = np.zeros((0))
            lineb = np.zeros((0))
            # Calculate the first line
            for j in range(0, 2*xsteps):
                # Average data per settle time
                if j >= xsteps:
                    lineb = np.append(lineb, channel[j * repeats + skip:(j+1) * repeats].mean())
                else:
                    linef = np.append(linef, channel[j * repeats + skip:(j+1) * repeats].mean())
            imagef = np.atleast_2d(linef).T
            imageb = np.atleast_2d(np.flip(lineb)).T
            
            # Calculate all other lines
            for i in range(1, ysteps):
                linef = np.zeros((0))
                lineb = np.zeros((0))
                for j in range(0, 2*xsteps):
                    if j >= xsteps:
                        lineb = np.append(lineb, channel[i * len(linx) + j * repeats + skip:i * len(linx) + (j+1) * repeats].mean())
                    else:
                        linef = np.append(linef, channel[i * len(linx) + j * repeats + skip:i * len(linx) + (j+1) * repeats].mean())
                imagef = np.append(imagef, np.atleast_2d(linef).T, 1)
                imageb = np.append(imageb, np.atleast_2d(np.flip(lineb)).T, 1)
            # Convert from units of 100 µV to units of µV
            imagef = imagef * 100
            imageb = imageb * 100

            print("Gathering more data insights...")
            # Do some additional processing
            start = channel.properties["wf_start_time"]
            end = start + np.timedelta64(int(len(linx) * len(liny) / data_rate), 's')
            span = HeatmappifyThread.__timedelta64_to_str(end - start)
            print("Start time: {}\nEnd time: {}\nExecution time: {}".format(start, end, span))

        # Crop
        if self.tv.yend == 0: yend = np.shape(imagef)[1]
        imagef = imagef[:, self.tv.ystart:yend]
        imageb = imageb[:, self.tv.ystart:yend]
        difference = imagef - imageb
        # Calculate average x-ranges of one-dimensional fits of individual lines
        rangesf = np.asarray([x(xsteps-1)-x(0) for x in [P.fit(range(0, xsteps), x, 1, []) for x in imagef.T]])
        driftf = np.asarray([np.min(x) - np.max(x) for x in imagef])
        rangesb = np.asarray([x(xsteps-1)-x(0) for x in [P.fit(range(0, xsteps), x, 1, []) for x in imageb.T]])
        driftb = np.asarray([np.min(x) - np.max(x) for x in imageb])
        print("Average horizontal range: {} and {}".format(np.mean(rangesf), np.mean(rangesb)))
        print("Average maximal drift: {} and {}".format(np.mean(driftf), np.mean(driftb)))
        print("Maximal difference: {}".format(np.max(np.abs(difference))))
        
        # Hand the data to the main class
        self.plotUI.setData(imagef, imageb, rangesf, rangesb)
        
    # Make a str representation for timedelta64 as if datatime64
    def __timedelta64_to_str(t):
        d = t.astype('timedelta64[D]').astype(int)
        h = t.astype('timedelta64[h]').astype(int) - 24 * d
        m = t.astype('timedelta64[m]').astype(int) - 60 * (24 * d + h)
        s = t.astype('timedelta64[s]').astype(int) - 60 * (60 * (24 * d + h) + m)
        return "{}T{}:{}:{}".format(d, h, m, s)


