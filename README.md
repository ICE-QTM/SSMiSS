# SSMiSS
This repository contains the code that soon will be able to be used to do SQUID measurements at the QTM/ICE research group.

## Repository Structure
The files and folders are organised as follows:
* **SSMiSS.py** is the main file of the project. Running this will start the suite.
* **utils.py** is a file holding some utility functions.
* **Modules** has the files for the different modules of the suite.
* **Instruments** contains files with classes for isntrument communication.

## Requirements
To run the file, a Python installation 3.x is required (this was made in 3.11.7 with an Anaconda distribution). In addition, the following packages need to be installed:
* pyqtgraph
* pyvisa
* nidaqmx
* nptdms
* numpy
* pandas

## Manual
A user manual also detailing the different modules will soon be provided as **manual.pdf**.