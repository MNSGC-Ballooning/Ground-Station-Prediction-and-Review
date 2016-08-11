from ui_mainwindow import Ui_MainWindow
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import QtGui
import sys
import os
import math
import time
import numpy as np
from datetime import *
import time
import matplotlib
import csv

from matplotlib.figure import Figure
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.backends import qt4_compat

# matplotlib.use('Qt4Agg')
# matplotlib.rcParams['backend.qt4']='PySide'

# from matplotlib.figure import Figure
# from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas

# Antenna Tracker Locatioin
groundLat = 0
groundLon = 0
groundAlt = 0

#Graphing Arrays
receivedTime = np.array([])
receivedLat = np.array([])
receivedLon = np.array([])
receivedAlt = np.array([])
losLog = np.array([])
elevationLog = np.array([])
bearingLog = np.array([])

#Which mode you're in
reviewMode = False
predictionMode = False
checkBlocked = False

DPI = 100
		
class MainWindow(QMainWindow,Ui_MainWindow):
	def __init__(self, parent=None):
		global dpi
		super(MainWindow, self).__init__(parent)
		self.ui = Ui_MainWindow()
		self.setupUi(self)
		
		#Button Function Link Setup
		self.getFile.clicked.connect(self.selectFile)
		self.plotStuff.clicked.connect(self.makePlots)
		self.reviewCheckbox.stateChanged.connect(self.reviewChecked)
		self.predictionCheckbox.stateChanged.connect(self.predictChecked)
		
		# Graphing Setup
		self.figure = Figure(dpi = DPI)
		self.canvas = FigureCanvas(self.figure)
		self.canvas.setParent(self.graphWidget)
		self.canvas.setFocusPolicy(Qt.StrongFocus)
		self.canvas.setFocus()
		self.mpl_toolbar = NavigationToolbar(self.canvas, self.graphWidget)
		
		vbox = QVBoxLayout()
		vbox.addWidget(self.canvas)  # the matplotlib canvas
		vbox.addWidget(self.mpl_toolbar)
		self.graphWidget.setLayout(vbox)

	def reviewChecked(self):
		global checkBlocked
		if(not checkBlocked):
			checkBlocked = True
			self.predictionCheckbox.setChecked(False)
		checkBlocked = False

	def predictChecked(self):
		global checkBlocked
		if(not checkBlocked):
			checkBlocked = True
			self.reviewCheckbox.setChecked(False)
		checkBlocked = False

	# Lets you use a file browser to select the file you want to open	
	def selectFile(self):
		global dataFile
		dataFile = QFileDialog.getOpenFileName()
		print(dataFile)
		self.fileLabel.setText(dataFile)
		
	# Checks if you want to do a review or a prediction, and then parses the file and fills the graphing arrays appropriately
	def parseFile(self):
		global dataFile, groundLat, groundLon, groundAlt,receivedTime, receivedAlt, receivedLat, receivedLon,bearingLog, elevationLog,losLog
		if self.reviewCheckbox.isChecked():		# Path for the review
			try:
				firstLine = True		
				gpsTime = []		# Make this temporary list
				if dataFile[-3:] == "csv":		# If the file is a .csv file, do the following steps
					with open(dataFile,'r') as csvfile:
						f = csv.reader(csvfile,delimiter=',')		# Make a csv reader object
						for line in f:		# Step through each line and run the csvParse function
							self.csvParse(line,firstLine)
							firstLine = False		# Handles the header line
				elif dataFile[-3:] == 'txt':		# If the file is a .txt file, do the following
					f = open(dataFile,'r')
					for line in f.readlines():		# Step through each line and run the txtParse function
						self.txtParse(line,firstLine)
						firstLine = False		# Handles the header line
			except:
				print("Wrong file format")
		elif self.predictionCheckbox.isChecked():		# Path for the prediction
			try:
				f = open(dataFile,'r')
				gpsTime = []
				lines = f.read()		# Get the whole file at once
				lines = lines.split('-')		# Each set of lat, lon, and alt is delimited by -
				lines = lines[2:-7]		# Get rid of the first and last couple of lines that don't contain data
				temp = 0
				for line in lines:		# Get each set of coordinates
					line = line.split(',')		# Coordinates are delimited by ,
					lat = float(line[1])
					lon = -float(line[0])		# Make it negative because they come in degrees west
					if line[2] != '':		# Sometimes an altitude of 0 is given as a null string
						alt = float(line[2]) * 3.2808		# Convert to feet
					else:
						alt = 0
					distance = haversine(groundLat, groundLon,lat ,lon)
					bear = bearing(groundLat, groundLon,lat ,lon)
					ele = elevationAngle(alt,distance)
					los = math.sqrt(math.pow(distance/3.2808,2) + math.pow((alt-groundAlt)/3.2808,2))/1000		# Calculate the line of sight distance
					gpsTime = temp		# A dummy for the time, no time is given so I just step through by one so that you can plot this
					
					# Fill in the graphing arrays
					receivedTime = np.append(receivedTime,gpsTime)
					receivedLon = np.append(receivedLon,lon)
					receivedLat = np.append(receivedLat,lat)
					receivedAlt = np.append(receivedAlt,alt)
					bearingLog = np.append(bearingLog,bear)
					elevationLog = np.append(elevationLog,ele)
					losLog = np.append(losLog,los)
					
					temp += 1
			except:
				print("Wrong file format")

	# Generates the plots based on the file selected and the ground station location	
	def makePlots(self):
		global receivedTime, receivedLat, receivedLon, receivedAlt, losLog, elevationLog, bearingLog, groundLat, groundLon, groundAlt
		
		# Get the ground station location, autofill Minneapolis if none is given
		if self.trackerLat.text() == '':
			groundLat = float(self.trackerLat.placeholderText())
		else:
			groundLat = float(self.trackerLat.text())
		if self.trackerLon.text() == '':
			groundLon = float(self.trackerLon.placeholderText())
		else:
			groundLon = float(self.trackerLon.text())
		if self.trackerAlt.text() == '':
			groundAlt = float(self.trackerAlt.placeholderText())
		else:
			groundAlt = float(self.trackerAlt.text())
			
		# Reset the arrays
		receivedTime = np.array([])
		receivedLat = np.array([])
		receivedLon = np.array([])
		receivedAlt = np.array([])
		losLog = np.array([])
		elevationLog = np.array([])
		bearingLog = np.array([])
		
		self.parseFile()		# Go through the file and fill the arrays
		try:
			# create an axis
			ALTPLOT = self.figure.add_subplot(221)
			LOSPLOT = self.figure.add_subplot(222)
			ELEPLOT = self.figure.add_subplot(223)
			BEARPLOT = self.figure.add_subplot(224)
			self.figure.tight_layout()

			# discards the old graph
			ALTPLOT.hold(False)
			LOSPLOT.hold(False)
			ELEPLOT.hold(False)
			BEARPLOT.hold(False)
			
			# plot data
			ALTPLOT.plot(receivedTime-receivedTime[-1],receivedAlt, 'r-')
			ALTPLOT.set_ylabel('Altitude (ft)')
			LOSPLOT.plot(receivedTime-receivedTime[-1],losLog,'g-')
			LOSPLOT.set_ylabel('Line-of-Sight (km)')
			ELEPLOT.plot(receivedTime-receivedTime[-1],elevationLog, 'b-')
			ELEPLOT.set_ylabel('Elevation Angle')
			BEARPLOT.plot(receivedTime-receivedTime[-1],bearingLog,'y-')
			BEARPLOT.set_ylabel('Bearing Angle')

			# refresh canvas
			self.canvas.draw()
		except:
			print("Error making plots")
		
	# Parses .txt files given
	def txtParse(self,line,firstLine):
		global dataFile, groundLat, groundLon, groundAlt,receivedTime, receivedAlt, receivedLat, receivedLon,bearingLog, elevationLog,losLog
		if not firstLine:		# Skip the header line
			# Replace commas with spaces, get rid of single quotes, and split on the spaces
			line = line.replace(',',' ')		# This is because the altitude is given this the format XX,XXX
			line = line.replace("'",'')
			line = line.split(' ')
			
			# Get the time in seconds
			tempTime = line[1].split(':')
			gpsTime = float(tempTime[0])*3600 + float(tempTime[1])*60 + float(tempTime[2])
			
			lat = float(line[3])
			lon = float(line[4])
			
			# Depending on how high the balloon is, the meters column may also be in the format XX,XXX, so you need to check for this
			if len(line) == 10:
				alt = float((line[6] + line[7]).replace('"',''))
			else:
				alt = float((line[7] + line[8]).replace('"',''))
				
				
			distance = haversine(groundLat, groundLon,lat ,lon)
			bear = bearing(groundLat, groundLon,lat ,lon)
			ele = elevationAngle(alt,distance)
			los = math.sqrt(math.pow(distance/3.2808,2) + math.pow((alt-groundAlt)/3.2808,2))/1000		# Calculate the line of sight distance
			
			# Fill the arrays
			receivedTime = np.append(receivedTime,gpsTime)
			receivedLon = np.append(receivedLon,lon)
			receivedLat = np.append(receivedLat,lat)
			receivedAlt = np.append(receivedAlt,alt)
			bearingLog = np.append(bearingLog,bear)
			elevationLog = np.append(elevationLog,ele)
			losLog = np.append(losLog,los)
	
	# Parses .csv files given
	def csvParse(self,line,firstLine):
		global dataFile, groundLat, groundLon, groundAlt,receivedTime, receivedAlt, receivedLat, receivedLon,bearingLog, elevationLog,losLog
		if not firstLine:		# Ignore the header line
			for each in line:
				each = each.replace("'",'')		# Get rid of the '' surrounding every piece
			
			# Get the time in seconds
			tempTime = line[1].split(':')
			gpsTime = float(tempTime[0])*3600 + float(tempTime[1])*60 + float(tempTime[2])
			
			lat = float(line[3])
			lon = float(line[4])
			alt = float(line[6].replace(',',''))
			
			distance = haversine(groundLat, groundLon,lat ,lon)
			bear = bearing(groundLat, groundLon,lat ,lon)
			ele = elevationAngle(alt,distance)
			los = math.sqrt(math.pow(distance/3.2808,2) + math.pow((alt-groundAlt)/3.2808,2))/1000		# Calculate the line of sight distance
			
			# Fill the graphing arrays
			receivedTime = np.append(receivedTime,gpsTime)
			receivedLon = np.append(receivedLon,lon)
			receivedLat = np.append(receivedLat,lat)
			receivedAlt = np.append(receivedAlt,alt)
			bearingLog = np.append(bearingLog,bear)
			elevationLog = np.append(elevationLog,ele)
			losLog = np.append(losLog,los)
		
		
# Calculates a bearing angle based on GPS coordinates
def bearing(groundLat, groundLon, balloonLat, balloonLon):
	dLat = math.radians(balloonLat-groundLat)	   # delta latitude in radians
	dLon = math.radians(balloonLon-groundLon)	   # delta longitude in radians
			
	y = math.sin(dLon)*math.cos(math.radians(balloonLat))
	x = math.cos(math.radians(groundLat))*math.sin(math.radians(balloonLat))-math.sin(math.radians(groundLat))*math.cos(math.radians(balloonLat))*math.cos(dLat)
	tempBearing = math.degrees(math.atan2(y,x))	 # returns the bearing from true north
	if (tempBearing < 0):
		tempBearing = tempBearing + 360
	if (tempBearing > 360):
		tempBearing = tempBearing - 360
	return tempBearing

# Calculates an Elevation Angle based on altitudes and ground (great circle) distance
def elevationAngle(skyAlt, distance):
	return math.degrees(math.atan2(skyAlt-groundAlt,distance))

# haversine formula, see: http://www.movable-type.co.uk/scripts/latlong.html, determines ground distance
def haversine(groundLat, groundLon, balloonLat, balloonLon):
	R = 6371		# radius of earth in Km

	dLat = math.radians(balloonLat-groundLat)	   # delta latitude in radians
	dLon = math.radians(balloonLon-groundLon)	   # delta longitude in radians
	####################################
	a = math.sin(dLat/2)*math.sin(dLat/2)+math.cos(math.radians(groundLat))*math.cos(math.radians(balloonLat))*math.sin(dLon/2)*math.sin(dLon/2)
	#############################
	c = 2*math.atan2(math.sqrt(a),math.sqrt(1-a))
	
	d = R*c
	
	return d*3280.839895 # multiply distance in Km by 3280 for feet

	
if __name__ == "__main__":
	#re.sub("[^\d\.]", "", "1,000")
	app=QtGui.QApplication.instance()		# checks if QApplication already exists 
	if not app:		# create QApplication if it doesnt exist 
		app = QtGui.QApplication(sys.argv)
	screen_resolution = app.desktop().screenGeometry()
	width, height = screen_resolution.width(), screen_resolution.height()
	DPI = int((height)/7.95)
	print(DPI)
	mGui = MainWindow()
	mGui.show()
	app.exec_()

else:
	print "Error Booting Gui"
	while(1):
		pass