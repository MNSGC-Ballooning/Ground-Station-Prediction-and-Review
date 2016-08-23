#################################################################################################################################
#	   Ground Station Prediction and Review Tool 																				#
#																																#
#	   Author:	Austin Langford, AEM, MnSGC																						#
#	   Based on work from the Montana Space Grant Consortium																	#
#	   Software created for use by the Minnesota Space Grant Consortium								   							#
#	   Purpose: To use a ground location, and a flight path to analyze the quality of the ground location 						#
#	   Handles predictions from predict.habhub.com 																 				#
#	   Creation Date: June 2016																									#
#	   Last Edit Date: August 19, 2016																							#
#################################################################################################################################

from ui_mainwindow import Ui_MainWindow
import PyQt4
from PyQt4 import *
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtWebKit import *
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
import urllib2

from matplotlib.figure import Figure
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_qt4agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.backends import qt4_compat

googleMapsApiKey = 'AIzaSyDxwliW8hKUg072nJcVn3TtWlSEmY9rEvA'			# https://developers.google.com/maps/documentation/javascript/get-api-key

class WebView(PyQt4.QtWebKit.QWebPage):
	""" A class that allows messages from JavaScript being run in a QWebView to be retrieved """

	def javaScriptConsoleMessage(self, message, line, source):
		if source:
			print('line(%s) source(%s): %s' % (line, source, message))
		else:
			print(message)

class Proxy(QtCore.QObject):
	""" Helps get the info from the JavaScript to the main window """

	@QtCore.pyqtSlot(float, float)
	def showLocation(self, latitude, longitude):
		self.parent().edit.setText('%s, %s' % (latitude, longitude))
		
class MainWindow(QMainWindow,Ui_MainWindow):
	""" The main GUI window """

	def __init__(self, parent=None):
		super(MainWindow, self).__init__(parent)
		self.ui = Ui_MainWindow()			# Set up the GUI window from the file ui_mainwindow.py
		self.setupUi(self)

		# Ground Station information
		self.groundLat = 0
		self.groundLon = 0
		self.groundAlt = 0

		# Checkbox booleans
		self.checkBlocked = False

		# List of Locations
		self.points = []

		#Graphing Arrays
		self.receivedTime = np.array([])
		self.receivedLat = np.array([])
		self.receivedLon = np.array([])
		self.receivedAlt = np.array([])
		self.losLog = np.array([])
		self.elevationLog = np.array([])
		self.bearingLog = np.array([])

		#Button Function Link Setup
		self.getFile.clicked.connect(self.selectFile)
		self.reviewCheckbox.stateChanged.connect(lambda: self.checkboxInteractions('review'))
		self.predictionCheckbox.stateChanged.connect(lambda: self.checkboxInteractions('predict'))

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
		elevation = getAltitude(self.groundLat,self.groundLon)
		self.groundAlt = elevation
		self.trackerAlt.setText(str(self.groundAlt))		# Set the display text
		self.dragged = True 				# The ground location has been set at least once

		self.makePlots()					# Make the plots when you have all the ground station information

	def checkboxInteractions(self,arg):
		""" Makes sure only one checkbox is checked """

		if(arg == 'review'):
			if(not self.checkBlocked):
				self.checkBlocked = True
				self.predictionCheckbox.setChecked(False)
			self.checkBlocked = False
		if(arg == 'predict'):
			if(not self.checkBlocked):
				self.checkBlocked = True
				self.reviewCheckbox.setChecked(False)
			self.checkBlocked = False
	
	def selectFile(self):
		""" Lets you use a file browser to select the file you want to open """

		self.dataFile = QFileDialog.getOpenFileName()			# Opens the file browser, the selected file is saved in self.dataFile
		print(self.dataFile)
		try:													# Try to determine if this is a prediction or review based on file type
			if(self.dataFile.split('.')[1] == 'kml'):
				self.predictionCheckbox.setChecked(True)
			if(self.dataFile.split('.')[1] == 'csv'):
				self.reviewCheckbox.setChecked(True)
		except:
			pass

		self.fileLabel.setText(self.dataFile)					# Display the file path

		# Handle the file
		self.parseFile()
		self.makePlots()
		
	def parseFile(self):
		""" Checks if you want to do a review or a prediction, and then parses the file and fills the graphing arrays appropriately """

		### Review ###
		if self.reviewCheckbox.isChecked():
			self.points = []		# Reset the coordinates list
			try:
				firstLine = True		
				gpsTime = []		# Make this temporary list
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
				self.mapView.setHtml(self.html(self.points))
			except:
				print("Wrong file format")

		### Prediction ###
		elif self.predictionCheckbox.isChecked():		# Path for the prediction
			self.points = []		# Reset the coordinates list
			try:
				self.kmlParse()		# Handle the KML file
				self.mapView.setHtml(self.html(self.points))	# Setup the map with the new webcode
			except:
				print("Wrong file format")
	
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
			if(self.predictionCheckbox.isChecked()):
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

			# Plot data for reviews, Review files start at the end of the flight
			elif(self.reviewCheckbox.isChecked()):
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

			# refresh canvas
			self.canvas.draw()

		except:
			print("Error making plots")
		
	def txtParse(self,line,firstLine):
		""" 
		Parses .txt files given, 
		format IMEI,Time-UTC,Date,Latitude,Longitude,Altitude-meters,Altitude-feet,Vertical Velocity-m/s,Vertical Velocity-ft/s
		"""

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
				
			# Calculate the necessary values
			distance = haversine(self.groundLat, self.groundLon,lat ,lon)
			bear = bearing(self.groundLat, self.groundLon,lat ,lon)
			ele = elevationAngle(alt,self.groundAlt, distance)
			los = math.sqrt(math.pow(distance/3.2808,2) + math.pow((alt-self.groundAlt)/3.2808,2))/1000		# Calculate the line of sight distance
			
			# Fill the arrays
			self.receivedTime = np.append(self.receivedTime,gpsTime)
			self.receivedLon = np.append(self.receivedLon,lon)
			self.receivedLat = np.append(self.receivedLat,lat)
			self.receivedAlt = np.append(self.receivedAlt,alt)
			self.bearingLog = np.append(self.bearingLog,bear)
			self.elevationLog = np.append(self.elevationLog,ele)
			self.losLog = np.append(self.losLog,los)

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
		for line in f:
			if(line.find('<description>')!=-1):
				if(line.find('Ascent rate')!=-1):
					self.ascentRate = float(line[line.find('Ascent rate:')+len('Ascent rate:')+1:line.find('m/s')])
					line = line[line.find('m/s')+len('m/s'):]
					self.descentRate = float(line[line.find('descent rate:')+len('descent rate:')+1:line.find('m/s')])
					self.maxAlt = float(line[line.find('burst at')+len('burst at')+1:line.find('m.')])
			if((len(line.split(',')) == 3) and (line.find('<') == -1)):
				lineLst = line.split(',')		# Coordinates are delimited by ,
				lat = float(lineLst[1])
				lon = float(lineLst[0])		# Make it negative because they come in degrees west
				if lineLst[2] != '':		# Sometimes an altitude of 0 is given as a null string
					alt = float(lineLst[2]) * 3.2808		# Convert to feet
				else:
					alt = 0
				if(alt<prev):
					descending = True

				distance = haversine(self.groundLat, self.groundLon,lat ,lon)
				bear = bearing(self.groundLat, self.groundLon,lat ,lon)
				ele = elevationAngle(alt,self.groundAlt,distance)
				los = math.sqrt(math.pow(distance/3.2808,2) + math.pow((alt-self.groundAlt)/3.2808,2))/1000		# Calculate the line of sight distance
				if(not descending):
					gpsTime += abs((alt-prev)/3.2808)/self.ascentRate
				if(descending):
					gpsTime += abs((alt-prev)/3.2808)/self.descentRate
				prev = alt

				# Fill in the graphing arrays
				self.receivedTime = np.append(self.receivedTime,gpsTime)
				self.receivedLon = np.append(self.receivedLon,lon)
				self.receivedLat = np.append(self.receivedLat,lat)
				self.receivedAlt = np.append(self.receivedAlt,alt)
				self.bearingLog = np.append(self.bearingLog,bear)
				self.elevationLog = np.append(self.elevationLog,ele)
				self.losLog = np.append(self.losLog,los)

				self.points.append((lat,lon))

	def html(self,points):
		""" Creates an HTML and JavaScript file with the flight path plotted, as well as a draggable marker representing the ground station location """

		### For every point in the list, format it into a string that can be inserted in to the JavaScript function
		allPoints = ''
		for each in points:
			allPoints += '{lat: '+str(each[0])+', lng: '+str(each[1])+'},'
		allPoints = allPoints[:-1]

		if(not self.dragged):		# If the marker hasn't been set yet, you need to get a default point, so just use the first coordinate in the list
			self.groundLat = points[0][0]
			self.groundLon = points[0][1]
			# Get the altitude
			elevation = getAltitude(self.groundLat,self.groundLon)
			self.groundAlt = float(elevation)

		### The HTML and JavaScript is a formatted string, this allows for a Google Maps widget ###
		html = '''
		<html><head>
		<meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
		<style type="text/css">
		    html { height: 100% }
		    body { height: 100%; margin: 0; padding: 0 }
		    #map { width: 100%; height: 100% }
		</style>
		</script>
		        <script async defer
		        src="https://maps.googleapis.com/maps/api/js?key='''+str(googleMapsApiKey)+'''&callback=initialize">
		</script>
		<script type="text/javascript">
		    var map, marker
		    function initialize() {
		        map = new google.maps.Map(document.getElementById("map"), {
		            center: {lat: '''+str(self.groundLat)+''', lng: '''+str(self.groundLon)+'''},
		            zoom: 10,
		            mapTypeId: 'terrain'
		        })
		        marker = new google.maps.Marker({
		            map: map,
		            position: map.getCenter(),
		            draggable: true
		        })
		        marker.addListener("dragend", function () {
		            var pos = marker.getPosition()
		            qt.showLocation(pos.lat(), pos.lng())
		            console.log("dragend: " + pos.toString())
		        })
	            
	            flightPlanCoordinates = ['''+str(allPoints)+'''];
				flightPath = new google.maps.Polyline({
	                map: map,
	                path: flightPlanCoordinates,
	                geodesic: true,
	                strokeColor: '#FF0000',
	                strokeOpacity: 1.0,
	                strokeWeight: 2
	            });
		    }
		    google.maps.event.addDomListener(window, "load", initialize)
		</script>
		</head>
		<body><div id="map"/></body>
		</html>
		'''
		return html
		
def bearing(groundLat, groundLon, balloonLat, balloonLon):
	""" Calculates a bearing angle based on GPS coordinates """

	dLat = math.radians(balloonLat-groundLat)	   # delta latitude in radians
	dLon = math.radians(balloonLon-groundLon)	   # delta longitude in radians
			
	y = math.sin(dLon)*math.cos(math.radians(balloonLat))
	x = math.cos(math.radians(groundLat))*math.sin(math.radians(balloonLat))-math.sin(math.radians(groundLat))*math.cos(math.radians(balloonLat))*math.cos(dLat)
	tempBearing = math.degrees(math.atan2(y,x))	 # returns the bearing from true north
	# Get the bearing between 0 and 360
	if (tempBearing < 0):
		tempBearing = tempBearing + 360
	if (tempBearing > 360):
		tempBearing = tempBearing - 360
	return tempBearing

def getAltitude(lat,lon):
	""" Uses the google api to determine the altitude (in feet) of the location by latitude and longitude """

	url = 'https://maps.googleapis.com/maps/api/elevation/json?locations='+str(lat)+','+str(lon)+'&key='+googleMapsApiKey		# Site that returns the elevation of latitude and longitude
	response = urllib2.urlopen(url)
	pageTxt = str(response.read())		# Get the text of the page from the URL
	elevation = pageTxt[pageTxt.find('elevation')+len('elevation')+4:pageTxt.find(',')]		# Parse the text on the page
	alt = float(elevation)

	return alt*3.2808		# Convert to ft

def elevationAngle(skyAlt, groundAlt, distance):
	""" Calculates an Elevation Angle based on altitudes and ground (great circle) distance """

	return math.degrees(math.atan2(skyAlt-groundAlt,distance))

def haversine(groundLat, groundLon, balloonLat, balloonLon):
	""" haversine formula, see: http://www.movable-type.co.uk/scripts/latlong.html, determines ground distance """

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

	mGui = MainWindow()		# Create the main GUI window
	mGui.showMaximized()	# Show the GUI maximized (full screen)
	app.exec_()				# Run the GUI

else:
	print "Error Booting Gui"
	while(1):
		pass