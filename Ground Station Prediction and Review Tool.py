#################################################################################################################################
#       Ground Station Prediction and Review Tool 																				#
#    																															#
#       Author:	Austin Langford, AEM, MnSGC																						#
#       Based on work from the Montana Space Grant Consortium																	#
#       Software created for use by the Minnesota Space Grant Consortium								   						#
#       Purpose: To use a ground location, and a flight path to analyze the quality of the ground location 						#
#       Handles predictions from predict.habhub.com 																 			#
#       Creation Date: June 2016																								#
#       Last Edit Date: August 19, 2016																							#
#################################################################################################################################

from ui_mainwindow import Ui_MainWindow
import PyQt4
from PyQt4 import *
from PyQt4 import QtCore
from PyQt4.QtCore import QThread
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtWebKit import *
from PyQt4 import QtGui
import sys
import numpy as np
from datetime import *
import csv
import threading

from googleMaps import *
from PointingMath import *

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)

googleMapsApiKey = ''			# https://developers.google.com/maps/documentation/javascript/get-api-key

class MyThread(QThread):
    def run(self):
        self.exec_()

class GPSLocation:

	def __init__(self, lat, lon):
		self.lat = lat
		self.lon = lon
		self.alt = 900

		self.selected = False

	def getLat(self):
		return self.lat

	def getLon(self):
		return self.lon

	def getAlt(self):
		return self.alt

	def setSelected(self):
		self.selected = True

	def isSelected(self):
		return self.selected


class Analyzer(QtCore.QObject):
	""" A class that holds the signals and function for running the location analysis """

	updateLatLst = pyqtSignal(np.ndarray)
	updateLonLst = pyqtSignal(np.ndarray)
	updateAltLst = pyqtSignal(np.ndarray)
	updateResolution = pyqtSignal(float)
	startAnalysis = pyqtSignal()
	interruptSignal = pyqtSignal()

	def __init__(self, MainWindow, latLst, lonLst, altLst, resolution):
		super(Analyzer, self).__init__()
		self.mainWindow = MainWindow
		self.latLst = latLst
		self.lonLst = lonLst
		self.altLst = altLst
		self.resolution = resolution
		self.interrupt = False

		# Slots
		self.mainWindow.locations.connect(self.mainWindow.analysisFinished)
		self.mainWindow.progress.connect(self.mainWindow.updateAnalysisProgress)

	def runAnalysis(self):
		# Prediction
		self.interrupt = False
		testLocations = []
		tempLat = self.latLst[len(self.latLst) / 2] - 1
		while tempLat <= self.latLst[len(self.latLst) / 2] + 1:
			tempLon = self.lonLst[len(self.lonLst) / 2] - 1
			while tempLon <= self.lonLst[len(self.lonLst) / 2] + 1:
				try:
					testLoc = GPSLocation(tempLat, tempLon)
					testLocations.append(testLoc)
					tempLon = round(tempLon + self.resolution, 4)
				except:
					print('Failed, skipping')
			tempLat = round(tempLat + self.resolution, 4)

		accum = 0
		progress = 0
		for each in testLocations:
			QtGui.QApplication.processEvents()
			if self.interrupt:
				break
			i = 0
			# eleLst = []
			losLst = []
			while i < len(self.latLst) and not self.interrupt:
				QtGui.QApplication.processEvents()
				lat = self.latLst[i]
				lon = self.lonLst[i]
				alt = self.altLst[i]
				distance = haversine(each.getLat(), each.getLon(), lat, lon)
				# ele = elevationAngle(alt, each.getAlt(), distance)
				los = losDistance(alt, each.getAlt(), distance)
				# eleLst.append(ele)
				losLst.append(los)
				i += 1
			if sum(losLst) / len(losLst) < 40:
				each.setSelected()
			progress += 1
			self.mainWindow.progress.emit(int(progress), int(len(testLocations)))

		goodSpotCoords = []
		for each in testLocations:
			if each.isSelected():
				accum += 1
				goodSpotCoords.append(each)

		self.mainWindow.locations.emit(goodSpotCoords)

	def setResolution(self, resolution):
		self.resolution = resolution

	def setLatLst(self, latLst):
		self.latLst = latLst

	def setLonLst(self, lonLst):
		self.lonLst = lonLst

	def setAltLst(self, altLst):
		self.altLst = altLst

	def setInterrupt(self):
		self.interrupt = True


class WebView(PyQt4.QtWebKit.QWebPage):
	""" A class that allows messages from JavaScript being run in a QWebView to be retrieved """

	def javaScriptConsoleMessage(self, message, line, source):
		if source:
			print('line(%s) source(%s): %s' % (line, source, message))
		else:
			print(message)


class Proxy(PyQt4.QtCore.QObject):
	""" Helps get the info from the JavaScript to the main window """

	@PyQt4.QtCore.pyqtSlot(float, float)
	def showLocation(self, latitude, longitude):
		self.parent().edit.setText('%s, %s' % (latitude, longitude))


class MainWindow(QMainWindow,Ui_MainWindow):
	""" The main GUI window """

	progress = pyqtSignal(int, int)
	locations = pyqtSignal(list)

	def __init__(self, parent=None):
		super(MainWindow, self).__init__(parent)
		self.ui = Ui_MainWindow()			# Set up the GUI window from the file ui_mainwindow.py
		self.setupUi(self)

		self.dataFile = ''

		# Ground Station information
		self.groundLat = 0
		self.groundLon = 0
		self.groundAlt = 0

		# Checkbox booleans
		self.checkBlocked = False

		# Create and start a side thread to run the predictions in
		self.analysisThread = MyThread()
		self.analysisThread.start()

		# Create the analyzer and connect the signals
		self.spotAnalyzer = Analyzer(self, [], [], [], 0.001)
		self.spotAnalyzer.moveToThread(self.analysisThread)
		self.spotAnalyzer.updateLatLst.connect(self.spotAnalyzer.setLatLst)
		self.spotAnalyzer.updateLonLst.connect(self.spotAnalyzer.setLonLst)
		self.spotAnalyzer.updateAltLst.connect(self.spotAnalyzer.setAltLst)
		self.spotAnalyzer.updateResolution.connect(self.spotAnalyzer.setResolution)
		self.spotAnalyzer.startAnalysis.connect(self.spotAnalyzer.runAnalysis)
		self.spotAnalyzer.interruptSignal.connect(self.spotAnalyzer.setInterrupt)

		# Lists of Locations
		self.points = []
		self.goodSpotCoords = []

		# Graphing Arrays
		self.receivedTime = np.array([])
		self.receivedLat = np.array([])
		self.receivedLon = np.array([])
		self.receivedAlt = np.array([])
		self.losLog = np.array([])
		self.elevationLog = np.array([])
		self.bearingLog = np.array([])

		# Button Function Link Setup
		self.getFile.clicked.connect(self.selectFile)
		self.reviewCheckbox.stateChanged.connect(lambda: self.checkboxInteractions('review'))
		self.predictionCheckbox.stateChanged.connect(lambda: self.checkboxInteractions('predict'))
		self.findSpotsButton.clicked.connect(self.analysisButtonPress)
		self.analysisRunning = False

		# Map Setup
		self.mapView = PyQt4.QtWebKit.QWebView(self)
		self.mapView.setPage(WebView(self))
		self.mapLayout = QtGui.QVBoxLayout()
		self.mapLayout.addWidget(self.mapView)
		self.webWidget.setLayout(self.mapLayout)
		self.map = self.mapView.page().mainFrame()
		self.map.loadFinished.connect(self.handleLoadFinished)		# Connect the function to the signal
		self._proxy = Proxy(self)
		self.dragged = False			# Helps set the initial ground station location so that it's not far from the path

		# Map Helper
		self.edit = QLineEdit()										# An object that can hold the information return from the javascript
		self.edit.textChanged.connect(self.updateGroundLocation)	# Connect a change in line edit to update the information
		
		# Graphing Setup
		self.figure = Figure()
		self.canvas = FigureCanvas(self.figure)
		self.canvas.setParent(self.graphWidget)
		self.canvas.setFocusPolicy(Qt.StrongFocus)
		self.canvas.setFocus()
		self.mpl_toolbar = NavigationToolbar(self.canvas, self.graphWidget)
		vbox = QVBoxLayout()
		vbox.addWidget(self.canvas)  			# the matplotlib canvas
		vbox.addWidget(self.mpl_toolbar)
		self.graphWidget.setLayout(vbox)

		self.tabWidget.setCurrentIndex(0)		# Set the tab to the graph tab when you open

	def handleLoadFinished(self, ok):
		""" Connects things from JavaScript to the proxy class """

		self.map.addToJavaScriptWindowObject('qt', self._proxy)		# Connect the load finished to the proxy

	def updateGroundLocation(self):
		""" Updates the instance variables, and determines the altitude """

		# Set the class variables for latitude and longitude, and set the display text
		self.groundLat = float(str(self.edit.text()).split(',')[0])
		self.trackerLat.setText(str(self.groundLat))
		self.groundLon = float(str(self.edit.text()).split(',')[1][1:])
		self.trackerLon.setText(str(self.groundLon))

		# Use Google Maps Api to get the altitude of the latitude and longitude
		elevation = getAltitude(self.groundLat,self.groundLon, googleMapsApiKey)
		self.groundAlt = elevation
		self.trackerAlt.setText(str(self.groundAlt))		# Set the display text
		self.dragged = True 				# The ground location has been set at least once

		self.makePlots()					# Make the plots when you have all the ground station information

	def updateGroundLocationDisplay(self):
		self.trackerLat.setText(str(self.groundLat))
		self.trackerLon.setText(str(self.groundLon))
		elevation = getAltitude(self.groundLat, self.groundLon, googleMapsApiKey)
		self.groundAlt = elevation
		self.trackerAlt.setText(str(self.groundAlt))

	def analysisFinished(self, goodSpots):
		self.findSpotsButton.setText('Look for Good Locations')
		self.analysisRunning = False
		self.goodSpotCoords = goodSpots
		self.makePlots()

	def updateAnalysisProgress(self, progress, total):
		percentage = float(progress)/float(total) * 100
		self.goodSpotProgress.setValue(percentage)

	def analysisButtonPress(self):
		if not self.analysisRunning:
			self.analysisRunning = True
			if not self.resolutionEntryBox.text() == '':
				resolution = self.resolutionEntryBox.text()
			else:
				resolution = self.resolutionEntryBox.placeholderText()

			self.goodSpotProgress.setValue(0)
			self.spotAnalyzer.updateLatLst.emit(self.receivedLat)
			self.spotAnalyzer.updateLonLst.emit(self.receivedLon)
			self.spotAnalyzer.updateAltLst.emit(self.receivedAlt)
			self.spotAnalyzer.updateResolution.emit(float(resolution))
			self.spotAnalyzer.startAnalysis.emit()

			self.findSpotsButton.setText('Stop Looking')

		else:
			self.spotAnalyzer.interruptSignal.emit()
			self.findSpotsButton.setText('Look for Good Locations')
			self.analysisRunning = False
			self.goodSpotProgress.setValue(0)
			return

	def checkboxInteractions(self,arg):
		""" Makes sure only one checkbox is checked """

		if arg == 'review':
			if not self.checkBlocked:
				self.checkBlocked = True
				self.predictionCheckbox.setChecked(False)
			self.checkBlocked = False
		if arg == 'predict':
			if not self.checkBlocked:
				self.checkBlocked = True
				self.reviewCheckbox.setChecked(False)
			self.checkBlocked = False
	
	def selectFile(self):
		""" Lets you use a file browser to select the file you want to open """

		self.dataFile = QFileDialog.getOpenFileName()			# Opens the file browser, the selected file is saved in self.dataFile
		print(self.dataFile)
		# Try to determine if this is a prediction or review based on file type
		if self.dataFile.split('.')[-1] == 'kml':
			self.predictionCheckbox.setChecked(True)
		if self.dataFile.split('.')[-1] == 'csv' or self.dataFile.split('.')[-1] == 'txt':
			self.reviewCheckbox.setChecked(True)

		self.fileLabel.setText(self.dataFile)					# Display the file path

		# Handle the file
		self.makePlots()
		
	def parseFile(self):
		""" Checks if you want to do a review or a prediction, and then parses the file and fills the graphing arrays appropriately """

		### Review ###
		if self.reviewCheckbox.isChecked():
			self.points = []		# Reset the coordinates list
			try:
				firstLine = True
				if self.dataFile[-3:] == "csv":		# If the file is a .csv file, do the following steps
					with open(self.dataFile,'r') as csvfile:
						f = csv.reader(csvfile,delimiter=',')		# Make a csv reader object
						for line in f:		# Step through each line and run the csvParse function
							self.csvParse(line,firstLine)
							firstLine = False		# Handles the header line
				elif self.dataFile[-3:] == 'txt':		# If the file is a .txt file, do the following
					f = open(self.dataFile,'r')
					for line in f.readlines():		# Step through each line and run the txtParse function
						self.txtParse(line,firstLine)
						firstLine = False		# Handles the header line
				self.mapView.setHtml(getHTML(self.points, self.groundLat, self.groundLon, self.groundAlt, self.dragged, googleMapsApiKey, self.goodSpotCoords))
			except Exception, e:
				print(str(e))

		### Prediction ###
		elif self.predictionCheckbox.isChecked():		# Path for the prediction
			self.points = []		# Reset the coordinates list
			# try:
			self.kmlParse()		# Handle the KML file
			self.mapView.setHtml(getHTML(self.points, self.groundLat, self.groundLon, self.groundAlt, self.dragged, googleMapsApiKey, self.goodSpotCoords))	# Setup the map with the new webcode
			# except Exception, e:
			# 	print(str(e))
	
	def makePlots(self):
		""" Generates the plots based on the file selected and the ground station location """
		
		# Reset the arrays
		self.receivedTime = np.array([])
		self.receivedLat = np.array([])
		self.receivedLon = np.array([])
		self.receivedAlt = np.array([])
		self.losLog = np.array([])
		self.elevationLog = np.array([])
		self.bearingLog = np.array([])
		
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
			
			# plot data for predictions
			if self.predictionCheckbox.isChecked():
				ALTPLOT.plot(self.receivedTime-self.receivedTime[0],self.receivedAlt, 'r-')
				ALTPLOT.set_ylabel('Altitude (ft)')
				for tick in ALTPLOT.get_xticklabels():			# Rotate the xlabels 45 degrees so they don't overlap
					tick.set_rotation(45)
				LOSPLOT.plot(self.receivedTime-self.receivedTime[0],self.losLog,'g-')
				LOSPLOT.set_ylabel('Line-of-Sight (km)')
				for tick in LOSPLOT.get_xticklabels():
					tick.set_rotation(45)
				ELEPLOT.plot(self.receivedTime-self.receivedTime[0],self.elevationLog, 'b-')
				ELEPLOT.set_ylabel('Elevation Angle')
				for tick in ELEPLOT.get_xticklabels():
					tick.set_rotation(45)
				BEARPLOT.plot(self.receivedTime-self.receivedTime[0],self.bearingLog,'y-')
				BEARPLOT.set_ylabel('Bearing Angle')
				for tick in BEARPLOT.get_xticklabels():
					tick.set_rotation(45)

			# Plot data for reviews, Review files may start at the end of the flight, or they may be in the correct order
			elif self.reviewCheckbox.isChecked():
				if self.receivedTime[0] - self.receivedTime[-1] > 0:
					ALTPLOT.plot(self.receivedTime-self.receivedTime[-1],self.receivedAlt, 'r-')
					ALTPLOT.set_ylabel('Altitude (ft)')
					for tick in ALTPLOT.get_xticklabels():
						tick.set_rotation(45)
					LOSPLOT.plot(self.receivedTime-self.receivedTime[-1],self.losLog,'g-')
					LOSPLOT.set_ylabel('Line-of-Sight (km)')
					for tick in LOSPLOT.get_xticklabels():
						tick.set_rotation(45)
					ELEPLOT.plot(self.receivedTime-self.receivedTime[-1],self.elevationLog, 'b-')
					ELEPLOT.set_ylabel('Elevation Angle')
					for tick in ELEPLOT.get_xticklabels():
						tick.set_rotation(45)
					BEARPLOT.plot(self.receivedTime-self.receivedTime[-1],self.bearingLog,'y-')
					BEARPLOT.set_ylabel('Bearing Angle')
					for tick in BEARPLOT.get_xticklabels():
						tick.set_rotation(45)
				else:
					ALTPLOT.plot(self.receivedTime-self.receivedTime[0],self.receivedAlt, 'r-')
					ALTPLOT.set_ylabel('Altitude (ft)')
					for tick in ALTPLOT.get_xticklabels():			# Rotate the xlabels 45 degrees so they don't overlap
						tick.set_rotation(45)
					LOSPLOT.plot(self.receivedTime-self.receivedTime[0],self.losLog,'g-')
					LOSPLOT.set_ylabel('Line-of-Sight (km)')
					for tick in LOSPLOT.get_xticklabels():
						tick.set_rotation(45)
					ELEPLOT.plot(self.receivedTime-self.receivedTime[0],self.elevationLog, 'b-')
					ELEPLOT.set_ylabel('Elevation Angle')
					for tick in ELEPLOT.get_xticklabels():
						tick.set_rotation(45)
					BEARPLOT.plot(self.receivedTime-self.receivedTime[0],self.bearingLog,'y-')
					BEARPLOT.set_ylabel('Bearing Angle')
					for tick in BEARPLOT.get_xticklabels():
						tick.set_rotation(45)

			# refresh canvas
			self.canvas.draw()

		except Exception, e:
			print(str(e))
		
	def txtParse(self,line,firstLine):
		""" 
		Parses .txt files given, 
		format IMEI,Time-UTC,Date,Latitude,Longitude,Altitude-meters,Altitude-feet,Vertical Velocity-m/s,Vertical Velocity-ft/s if taken from MSU Website
		format "Date StartTime",TrackingMethod,Time-UTC,Latitude,Longitude,Altitude-feet,bearing,elevationAngle,line-of-sightDistance if from log file
		"""

		### Log File ###
		try:
			if (len(line.split(',')[0].split(' '))) == 2:		# The first item is date and time with a space, not IMEI, so this will work to determine which method this is from
				# Get the time in seconds
				line = line.split(',')
				tempTime = line[2].split(':')
				gpsTime = float(tempTime[0])*3600 + float(tempTime[1])*60 + float(tempTime[2])

				# Get the lat, lon and alt
				lat = float(line[3])
				lon = float(line[4])
				alt = float(line[5])

				# Calculate the necessary values
				distance = haversine(self.groundLat, self.groundLon,lat ,lon)
				bear = bearing(self.groundLat, self.groundLon,lat ,lon)
				ele = elevationAngle(alt,self.groundAlt, distance)
				los = losDistance(alt,self.groundAlt,distance)
				
				# Fill the arrays
				self.receivedTime = np.append(self.receivedTime, gpsTime)
				self.receivedLon = np.append(self.receivedLon, lon)
				self.receivedLat = np.append(self.receivedLat, lat)
				self.receivedAlt = np.append(self.receivedAlt, alt)
				self.bearingLog = np.append(self.bearingLog, bear)
				self.elevationLog = np.append(self.elevationLog, ele)
				self.losLog = np.append(self.losLog, los)

				self.points.append((lat,lon))		# Add the point to the list of coordinates

				return
		except:
			pass

		### From MSGC Website ###
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
			if(len(line)) == 9:
				alt = float(line[6].replace('"',''))
			if(len(line)) == 10:
				alt = float((line[6] + line[7]).replace('"',''))
			if(len(line)) == 11:
				alt = float((line[7] + line[8]).replace('"',''))
				
			# Calculate the necessary values
			distance = haversine(self.groundLat, self.groundLon,lat ,lon)
			bear = bearing(self.groundLat, self.groundLon,lat ,lon)
			ele = elevationAngle(alt,self.groundAlt, distance)
			los = math.sqrt(math.pow(distance/3.2808,2) + math.pow((alt-self.groundAlt)/3.2808,2))/1000		# Calculate the line of sight distance
			
			# Fill the arrays
			self.receivedTime = np.append(self.receivedTime, gpsTime)
			self.receivedLon = np.append(self.receivedLon, lon)
			self.receivedLat = np.append(self.receivedLat, lat)
			self.receivedAlt = np.append(self.receivedAlt, alt)
			self.bearingLog = np.append(self.bearingLog, bear)
			self.elevationLog = np.append(self.elevationLog, ele)
			self.losLog = np.append(self.losLog, los)

			self.points.append((lat,lon))		# Add the point to the list of coordinates
	
	def csvParse(self,line,firstLine):
		""" 
		Parses .csv files given, 
		format IMEI,Time-UTC,Date,Latitude,Longitude,Altitude-meters,Altitude-feet,Vertical Velocity-m/s,Vertical Velocity-ft/s
		"""

		if not firstLine:		# Ignore the header line
			for each in line:
				each = each.replace("'",'')		# Get rid of the '' surrounding every piece
			
			# Get the time in seconds
			tempTime = line[1].split(':')
			gpsTime = float(tempTime[0])*3600 + float(tempTime[1])*60 + float(tempTime[2])
			
			# Get the coordinates
			lat = float(line[3])
			lon = float(line[4])
			alt = float(line[6].replace(',',''))
			
			# Calculate the necessary quantities
			distance = haversine(self.groundLat, self.groundLon,lat ,lon)
			bear = bearing(self.groundLat, self.groundLon,lat ,lon)
			ele = elevationAngle(alt,self.groundAlt,distance)
			los = math.sqrt(math.pow(distance/3.2808,2) + math.pow((alt-self.groundAlt)/3.2808,2))/1000		# Calculate the line of sight distance
			
			# Fill the graphing arrays
			self.receivedTime = np.append(self.receivedTime,gpsTime)
			self.receivedLon = np.append(self.receivedLon,lon)
			self.receivedLat = np.append(self.receivedLat,lat)
			self.receivedAlt = np.append(self.receivedAlt,alt)
			self.bearingLog = np.append(self.bearingLog,bear)
			self.elevationLog = np.append(self.elevationLog,ele)
			self.losLog = np.append(self.losLog,los)

			self.points.append((lat,lon))		# Add the coordinate to the list

	def kmlParse(self):
		""" Parses .kml files from predict.habhub.com """

		f = open(self.dataFile,'r')
		gpsTime = 0
		descending = False
		prev = 0
		firstLine = True
		for line in f:
			if line.find('<description>')!=-1:
				if line.find('Ascent rate')!=-1:
					self.ascentRate = float(line[line.find('Ascent rate:')+len('Ascent rate:')+1:line.find('m/s')])
					line = line[line.find('m/s')+len('m/s'):]
					self.descentRate = float(line[line.find('descent rate:')+len('descent rate:')+1:line.find('m/s')])
					self.maxAlt = float(line[line.find('burst at')+len('burst at')+1:line.find('m.')])
			if (len(line.split(',')) == 3) and (line.find('<') == -1):
				lineLst = line.split(',')		# Coordinates are delimited by ,
				lat = float(lineLst[1])
				lon = float(lineLst[0])		# Make it negative because they come in degrees west
				if lineLst[2] != '':		# Sometimes an altitude of 0 is given as a null string
					alt = float(lineLst[2]) * 3.2808		# Convert to feet
				else:
					alt = 0
				if alt<prev:
					descending = True

				if not self.dragged and firstLine:
					self.groundLat = lat
					self.groundLon = lon
					self.updateGroundLocationDisplay()

				firstLine = False

				distance = haversine(self.groundLat, self.groundLon,lat ,lon)
				bear = bearing(self.groundLat, self.groundLon,lat ,lon)
				ele = elevationAngle(alt,self.groundAlt,distance)
				los = math.sqrt(math.pow(distance/3.2808,2) + math.pow((alt-self.groundAlt)/3.2808,2))/1000		# Calculate the line of sight distance
				if not descending:
					gpsTime += abs((alt-prev)/3.2808)/self.ascentRate
				if descending:
					gpsTime += abs((alt-prev)/3.2808)/self.descentRate
				prev = alt

				# Fill in the graphing arrays
				self.receivedTime = np.append(self.receivedTime, gpsTime)
				self.receivedLon = np.append(self.receivedLon, lon)
				self.receivedLat = np.append(self.receivedLat, lat)
				self.receivedAlt = np.append(self.receivedAlt, alt)
				self.bearingLog = np.append(self.bearingLog,bear)
				self.elevationLog = np.append(self.elevationLog, ele)
				self.losLog = np.append(self.losLog, los)

				self.points.append((lat, lon))


def runPrediction(latLst, lonLst, altLst):
	# Prediction
	testLocations = []
	tempLat = latLst[len(latLst)/2] - abs(latLst[-1] - latLst[0])
	while tempLat <= latLst[len(latLst)/2] + abs(latLst[-1] - latLst[0]):
		tempLon = lonLst[len(lonLst)/2] - abs(lonLst[-1] - lonLst[0])
		while tempLon <= lonLst[len(lonLst)/2] + abs(lonLst[-1] - lonLst[0]):
			try:
				testLoc = GPSLocation(tempLat, tempLon)
				testLocations.append(testLoc)
				tempLon = round(tempLon + 0.001,4)
			except:
				print('Failed, skipping')
		tempLat = round(tempLat + 0.001,4)

	accum = 0
	for each in testLocations:
		i = 0
		eleLst = []
		losLst = []
		while i < len(latLst):
			lat = latLst[i]
			lon = lonLst[i]
			alt = altLst[i]
			distance = haversine(each.getLat(), each.getLon(), lat, lon)
			# ele = elevationAngle(alt, each.getAlt(), distance)
			los = losDistance(alt, each.getAlt(), distance)
			# eleLst.append(ele)
			losLst.append(los)
			i += 1
		if sum(losLst) / len(losLst) < 40:
			each.setSelected()

	goodSpotCoords = []
	for each in testLocations:
		if each.isSelected():
			print("Good Locations: ", each.getLat(), each.getLon())
			accum += 1
			goodSpotCoords.append(each)
	print(accum ,' good locations')

	return goodSpotCoords

if __name__ == "__main__":

	app = QtGui.QApplication.instance()		# checks if QApplication already exists
	if not app:		# create QApplication if it doesnt exist 
		app = QtGui.QApplication(sys.argv)

	with open('api_key') as f:
		googleMapsApiKey = f.readline().strip()

	mGui = MainWindow()		# Create the main GUI window
	mGui.showMaximized()	# Show the GUI maximized (full screen)
	app.exec_()				# Run the GUI