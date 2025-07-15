# -*- coding: utf-8 -*-
"""
SSMiSS module to perform scans.

Version 1.2.1 (2025/05/21)
Kylian van Dam - Master Student at ICE/QTM
University of Twente
"""

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt.QtCore import QThread, QTimer, Qt
from pyqtgraph.Qt.QtWidgets import QCheckBox, QVBoxLayout, QHBoxLayout, QLabel
import threading
from datetime import datetime

from Modules.TabLayout import TabLayout
from Instruments.NIpci6036E import NIpci6036E
from utils import addQLineEdit, addVdtQLineEdit, addQBtn, stepData


#%% Defaults and standards (most of which can be freely changed at runtime), packed in one neat class

class scanVars():
    # Set up default values for a scan
    def __init__(self, folder):
        self.lowervx = 0
        self.uppervx = 7
        self.lowervy = 0
        self.uppervy = 7
        self.xsteps = 21
        self.ysteps = 21
        self.settle = 0.5                                           # Time between consecutive steps (s)
        self.data_rate = 100                                        # Data acquisition rate (Hz)
        self.refresh = 1                                            # Refresh interval of plots and data reading (s)
        self.log = True                                             # Log data in a file
        self.make_heatmap = True                                    # Enable processing the data in a live heatmap
        self.filename = ''                                          # Particular filename
        self.groupname = ''                                         # Particular group name
        self.lowerV = 0                                             # Global scanner voltage limiter (V) (not changeable at runtime)
        self.upperV = 7                                             # Global scanner voltage limiter (V) (not changeable at runtime)
        self.filebase = datetime.now().strftime('%Y%m%d-%H%M%S_')   # Start of all filenames (not changeable at runtime)
        self.folder = folder                                        # Folder to put the files into (not changeable at runtime)
        self.archiveFile = "Data/scans.csv"                         # Location of the archive file

    # Construct how steps are taken
    def stepdata(self):
        [self.linx, self.liny] = stepData(self.lowervx, self.uppervx, self.xsteps, self.lowervy, self.uppervy, self.ysteps, self.settle, self.data_rate)
    
    # Put loads of specifications in the only metadata part of the TDMS file that I can actually directly control
    def createGroupName(self):
        return 'vx{}-{}-{}_vy{}-{}-{}_settle-{}_'.format(self.lowervx, self.uppervx, self.xsteps, self.lowervy, self.uppervy, self.ysteps, self.settle) + self.groupname

    # Makes a valid filename, mostly here for later extension
    def createFileName(self):
        return 'Data/' + self.folder + '/' + self.filebase + self.filename
    
    # Used to mass-set all variables from a dict
    def set_all(self, lowervx, uppervx, lowervy, uppervy, xsteps, ysteps, settle, data_rate, refresh, log, make_heatmap, filename, groupname):
        self.lowervx = lowervx
        self.uppervx = uppervx
        self.lowervy = lowervy
        self.uppervy = uppervy
        self.xsteps = xsteps
        self.ysteps = ysteps
        self.settle = settle
        self.data_rate = data_rate
        self.refresh = refresh
        self.log = log
        self.make_heatmap = make_heatmap
        self.filename = filename
        self.groupname = groupname
    
    # Write all used settings to a general archiving file
    def archive(self):
        v = [self.groupname, self.filebase[:-1], self.lowervx, self.uppervx, self.xsteps, self.lowervy, self.uppervy, self.ysteps, self.settle, self.createFileName()]
        string = ', '.join([str(x) for x in v]) + '\n'
        with open(self.archiveFile, 'a') as f: f.write(string)


#%% Classes

# Class that takes care of scans. Adds itself to a QStackedLayout, and creates accompanying PushButton tabs.
class scanUI(TabLayout, QVBoxLayout):
    def __init__(self, parent, daq, meas_list, write_list, folder, advance):
        # Ensure this is actually a QVBoxLayout
        super(scanUI, self).__init__(parent)
        self.makeTab('Line Scan')
        
        # Create a variable storage object
        self.sv = scanVars(folder)
        
        # Assigning variables
        self.daq = daq
        self.write_list = write_list
        self.meas_list = meas_list
        self.advance = advance
        self.data = np.empty((len(self.meas_list), 0))
        
        # Create a thread that handles a full line scan
        self.line_scan = ScanLineThread(self.sv, self.write_list, self, self.daq)
        self.line_scan.finished.connect(self.__lineScanClosing)
        
        # Set up a data refresh timer
        self.graph_timer = QTimer()
        self.graph_timer.timeout.connect(self.update_scan_plots)
        self.graph_timer.setInterval(int(self.sv.refresh * 1000))
        
        # Make a bar for info
        info = QHBoxLayout(); self.addLayout(info)
        # Add widget for starting line scans
        self.startButton = addQBtn(info, 'Start scan', self.__startProgram, 'confirm')
        self.startButton.setFixedSize(140, 23)
        # Add a panic button
        self.closeButton = addQBtn(info, 'Stop scan!', self.stopAll, 'quit')
        self.closeButton.setFixedSize(140, 23)
        # Add a label (textbox) for displaying *stuff*
        self.doc = QLabel('No active scan.')
        self.doc.setAlignment(Qt.AlignHCenter)
        info.addWidget(self.doc)
        
        #Make scanning menus
        scanUI.makeMenu(self, self.sv, 0)
        self.__makeGraphs(100)

    # Extension of __init__ that creates the menu for single scans in the QStackedLayout
    def makeMenu(parent, sv, stretchFactor):
        layout = QVBoxLayout()
        parent.addLayout(layout, stretchFactor)
        
        # Add a horizontal bar, for logging settings
        settings = QHBoxLayout()
        layout.addLayout(settings)
        # Add checkboxes
        parent.heatmapbox = QCheckBox('Live heatmap')
        settings.addWidget(parent.heatmapbox);
        if sv.make_heatmap: parent.heatmapbox.toggle()
        parent.logbox = QCheckBox('Log to file')
        settings.addWidget(parent.logbox); 
        if sv.log: parent.logbox.toggle()
        # Add logging names
        parent.filebox = addQLineEdit(settings, "File name:", sv.filename)
        parent.groupbox = addQLineEdit(settings, "Group name (notes):", sv.groupname)
        
        # Add another horizontal bar, for x-scanner related text boxes
        xparams = QHBoxLayout()
        layout.addLayout(xparams)
        # Add text boxes and labels
        parent.lowerxbox = addVdtQLineEdit(xparams, "Lower Vx", sv.lowerV, sv.upperV, sv.lowervx)
        parent.upperxbox = addVdtQLineEdit(xparams, "Upper Vx", sv.lowerV, sv.upperV, sv.uppervx)
        parent.xstepbox = addVdtQLineEdit(xparams, "x-steps", 2, None, sv.xsteps, False)
        
        # Add another horizontal bar, for y-scanner related text boxes
        yparams = QHBoxLayout()
        layout.addLayout(yparams)
        # Add text boxes and labels
        parent.lowerybox = addVdtQLineEdit(yparams, "Lower Vy", sv.lowerV, sv.upperV, sv.lowervx)
        parent.upperybox = addVdtQLineEdit(yparams, "Upper Vy", sv.lowerV, sv.upperV, sv.uppervx)
        parent.ystepbox = addVdtQLineEdit(yparams, "y-steps", 2, None, sv.xsteps, False)
        
        # Add another horizontal bar, for general text boxes
        params = QHBoxLayout()
        layout.addLayout(params)
        # Add text boxes and labels
        parent.settlebox = addVdtQLineEdit(params, "Settle time (s)", 0.001, None, 0.5)
        parent.ratebox = addVdtQLineEdit(params, "Data rate (Hz)", 1, 10000, 100)
        parent.refreshbox = addVdtQLineEdit(params, "Graph refresh rate (s)", 0.01, 5, 1)

    # Extension of __init__ for making the grahs
    def __makeGraphs(self, stretchFactor):
        # Set graphical window for putting graphs in
        graphs = pg.GraphicsLayoutWidget()
        self.addWidget(graphs, stretchFactor)
        
        # Enable antialiasing for prettier plots
        pg.setConfigOptions(antialias=True)
        
        # Prepare actual plots
        self.p1 = graphs.addPlot(title="Strain vs applied voltage", row = 0, col = 0)
        self.p1.setLabel('bottom', "Voltage (amplifier*V)"); self.p1.setLabel('left', "Strain (mV)")
        self.p2 = graphs.addPlot(title="Averaged strain vs applied voltage (mV)", row = 0, col = 1)
        
        # Give lines fancy colours
        self.curve1 = self.p1.plot(pen=None, symbol='o', symbolPen=pg.mkPen(color='y', width=1), symbolBrush=None)
        self.curve1.setSymbolSize(5)
        self.curve2 = self.p1.plot(pen=None, symbol='o', symbolPen=pg.mkPen(color='r', width=1), symbolBrush=None)
        self.curve2.setSymbolSize(5)
        
        # Prepare a placeholder for the heatmap and add it
        self.surface = np.zeros((1,1))
        self.image = pg.ImageItem(image=self.surface)
        self.p2.addItem(self.image, axisOrder='row-major')
        self.colorbar = self.p2.addColorBar(self.image, colorMap=pg.colormap.get('CET-D1'), interactive=False)

    # Handles the starting of a line scan
    def startLineScan(self, settings=None):
        print('Creating line scanning thread from {}'.format(threading.get_ident()))
        
        # Clear the current heatmap
        self.surface = np.zeros((1,1))
        self.image.setImage(self.surface)
        
        # If this is a single scan
        if settings is None:
            # Find settings from current snapshot
            settings = scanUI.snapshot(self)
        # Update variables and settings according to settings information
        self.sv.set_all(**settings)
        
        self.sv.archive()
        
        self.graph_timer.setInterval(int(self.sv.refresh * 1000))
        # Calculate what voltage steps to take
        self.sv.stepdata()
        
        # Set the plot to have a fixed x-range            
        self.p1.setXRange(self.sv.lowervx, self.sv.uppervx)
        
        # Set up a task for reading from the DAQ and configure logging settings. Don't start it yet.
        self.read_task = self.daq.make_read_task('read', self.meas_list)
        NIpci6036E.set_continuous_hardware_clock(self.read_task, self.sv.data_rate)
        NIpci6036E.commit(self.read_task)
        if self.sv.log:
            NIpci6036E.set_log(self.read_task, self.sv.createFileName(), self.sv.createGroupName())
        
        # Start a new line scan
        self.line_scan.start()
        # Start updating graphs
        self.graph_timer.start()
        # Keep track of what y-line we are on
        self.i = 1
        self.doc.setText('Scanning {}/{}...'.format(self.i, len(self.sv.liny)))
    
    # Fires when a line scan thread stops, and does closing things
    def __lineScanClosing(self):
        # If I need to do graceful termination things
        if self.line_scan.done:
            self.graph_timer.stop()
            self.update_scan_plots()                   # Note that this USES THE READ_TASK!
            NIpci6036E.close_task(self.read_task)      # So stop it only AFTER the last update
            self.line_scan.done = False
            self.advance.emit()
        # Update UI
        self.startButton.setEnabled(True)
        self.parent.enableTabs()
        self.doc.setText('No active scan.')
        self.curve1.clear()
        self.curve2.clear()
    
    def __startProgram(self):
        self.parent.disableTabs(self.tabs)
        self.startButton.setEnabled(False)
        self.startLineScan()
    
    # Data acquisition and concatenation
    def __acquire_data(self):
        self.data = np.append(self.data, np.vstack(NIpci6036E.read_available(self.read_task)), 1)
    
    # Handle updating the plots
    def update_scan_plots(self):
        self.__acquire_data()

        if np.shape(self.data)[1] > len(self.sv.linx):
            self.__updateHeatmap()
        
        # Update plots
        hlinxlen = int(len(self.sv.linx)/2)
        
        # Split the data over a forward curve and a backward curve, if we started the backward curve
        if np.shape(self.data)[1] < hlinxlen:
            self.curve1.setData(self.sv.linx[:len(self.data[0])], self.data[0])
            self.curve2.setData([], [])
        else:
            self.curve1.setData(self.sv.linx[:hlinxlen], self.data[0, :hlinxlen])
            self.curve2.setData(self.sv.linx[hlinxlen:len(self.data[0])], self.data[0, hlinxlen:])

    # Update the heatmap
    def __updateHeatmap(self):
        # Remove a chunk of data from the variable equal to a single back-and-forth
        chunk = self.dumpData(len(self.sv.linx))
        
        # Update UI
        self.i += 1
        self.doc.setText('Scanning {}/{}...'.format(self.i, len(self.sv.liny)))
        
        if self.sv.make_heatmap:
            # Get the averages per voltage value
            _, averages = self.__average(chunk)
            
            # If there is no existing surface
            if self.surface.size == 1:
                # Make a surface and put it on the screen
                self.surface = np.atleast_2d(averages).T
                self.image.setImage(self.surface)
                self.colorbar.setLevels(low = np.min(self.surface), high = np.max(self.surface))
            else:
                # Add to the existing surface and update it on screen
                self.surface = np.append(self.surface, np.atleast_2d(averages).T, 1)
                self.image.setImage(self.surface)
                self.colorbar.setLevels(low = np.min(self.surface), high = np.max(self.surface))

    # Average data per TARGET piezo x-voltage (NOT measured piezo x-voltage!)
    def __average(self, data):
        # Find unique targets
        voltages = np.unique(self.sv.linx)
        # Create space
        averages = np.zeros(voltages.size)
        
        # Do averaging
        for i in range(0, voltages.size):
            averages[i] = data[0][self.sv.linx == voltages[i]].mean()
        return voltages, averages

    # Empty data variable (or remove the first chunk entries)
    def dumpData(self, chunk=0):
        if chunk == 0:
            # Delete all data
            self.data = np.empty((len(self.meas_list), 0))
        else:
            # Extract data
            temp = self.data[:, 0:chunk]
            # Remove extracted data
            self.data = self.data[:, chunk:np.shape(self.data)[1]]
            return temp
    
    # Make a dictionary of variables by taking a snapshot of current values in widget
    def snapshot(layout):
        values = {}
        values["lowervx"] = float(layout.lowerxbox.text())
        values["uppervx"] = float(layout.upperxbox.text())
        values["xsteps"] = int(layout.xstepbox.text())
        values["lowervy"] = float(layout.lowerybox.text())
        values["uppervy"] = float(layout.upperybox.text())
        values["ysteps"] = int(layout.ystepbox.text())
        values["settle"] = float(layout.settlebox.text())
        values["data_rate"] = float(layout.ratebox.text())
        values["refresh"] = float(layout.refreshbox.text())
        values["make_heatmap"] = layout.heatmapbox.isChecked()
        values["log"] = layout.logbox.isChecked()
        values["filename"] = layout.filebox.text()
        values["groupname"] = layout.filebox.text()
        return values

    # Stop all active processes in a way where nothing breaks
    def stopAll(self):
        # Terminate the event loop handling scans (terminating the thread as a whole can cause Windows access violations, jolly!)
        self.line_scan.exit(-1)
        self.graph_timer.stop()
        # Do closing steps on measurement instruments
        self.daq.close()
        with self.daq.make_write_task('closing_write', self.write_list) as task:
            task.write(np.asarray([0, 0]))


# Definition of thread to perform a line scan
class ScanLineThread(QThread):
    # Use class variables to avoid overuse of globals
    def __init__(self, scan_vars, write_list, win, daq):
        super(ScanLineThread, self).__init__()
        self.sv = scan_vars
        self.write_list = write_list
        self.win = win
        self.done = False               # For figuring out whether I was terminated or gracefully ended
        self.daq = daq

    # Start a line scan
    def run(self):
        print('Line scanning thread {}'.format(threading.get_ident()))
        # Throw away whatever data is currently existing, as it does not belong to my measurement
        self.win.dumpData()
        
        # Make a write task
        with self.daq.make_write_task('write', self.write_list, self.sv.lowerV, self.sv.upperV) as self.write_task:
            NIpci6036E.set_finite_hardware_clock(self.write_task, self.sv.data_rate, samps_per_chan=(len(self.sv.linx) * len(self.sv.liny) + 1))
            # Sync start trigger to the read_task
            NIpci6036E.set_start_trigger(self.write_task, self.win.read_task)
            # Write the first set of data, VERY IMPORTANT to do this BEFORE starting the task!
            # Not doing it messes up data sending rate, and the amount of data points sent here equals buffer size.
            self.write_stream = NIpci6036E.make_multi_channel_writer(self.write_task)
            self.write_stream.write_many_sample(np.append(ScanLineThread.__generateInput(self.sv.linx, self.sv.liny, 0), ScanLineThread.__generateInput(self.sv.linx, self.sv.liny, 1), 1))
            # Start the write_task (which won't do anything but wait for the read_task start trigger)
            self.write_task.start()
            # Start the read task
            self.win.read_task.start()
            
            # Set up a timer for writing the other lines, (it's more accurate than sleep statements)
            self.write_timer = QTimer()
            self.write_timer.timeout.connect(self.__write)
            self.write_timer.setInterval(int(len(self.sv.linx) / self.sv.data_rate * 1000))
            
            # Wait until all values are written to the piezos, then kill the event loop
            self.wait_timer = QTimer()
            self.wait_timer.timeout.connect(self.__waitWriting)
            self.wait_timer.setInterval(100)
            self.wait_timer.start()
            
            # Start writing the other lines
            self.i = 2
            self.write_timer.start()
            
            # Enter the event loop
            if self.exec() == 0:
                # If event loop was terminated gracefully
                print('Scan complete')
                self.done = True            # State termination was graceful
    
    # Write a line
    def __write(self):
        # If this was the last line
        if self.i == len(self.sv.liny):
            self.write_timer.stop()                         # Stop the timer
            self.write_task.write(np.asarray([0.0, 0.0]))   # End with voltages on zero
        else:
            # Write a new line
            self.write_stream.write_many_sample(ScanLineThread.__generateInput(self.sv.linx, self.sv.liny, self.i))
            self.i += 1
    
    # Generate the ith array of input (mostly taking care of getting the correct y-data)
    def __generateInput(xdata, ydata, i):
        return np.vstack((np.ones((len(xdata))) * ydata[i], xdata))
    
    # Stops the event loop if the write_task is done writing
    def __waitWriting(self):
        if self.write_task.is_task_done():
            self.quit()