import urllib2
from convex_hull import *

def getHTML(points, groundLat, groundLon, groundAlt, dragged, apiKey, goodSpots):
	""" Creates an HTML and JavaScript file with the flight path plotted,
		as well as a draggable marker representing the ground station location
	"""

	### For every point in the list, format it into a string that can be inserted in to the JavaScript function
	allPoints = ''
	for each in points:
		temp = '{lat: ' + str(each[0]) + ', lng: ' + str(each[1]) + '},'
		allPoints += temp
	allPoints = allPoints[:-1]

	# Get the boundary points of the determined good locations
	goodSpotLst = []
	for each in goodSpots:
		goodSpotLst.append([each.getLat(),each.getLon()])		# Make a list that ConvexHull will accept
	goodSpots = ConvexHull(goodSpotLst).convex_hull()		# Create the convex hull

	# Format the boundary points into the string
	goodSpotCoords = ''
	if len(goodSpots) != 0:
		for each in goodSpots:
			temp = '{lat: ' + str(each[0]) + ', lng: ' + str(each[1]) + '},'
			goodSpotCoords += temp
		goodSpotCoords = goodSpotCoords[:-1]
	if goodSpotCoords == '':
		goodSpotCoords = 0

	if (not dragged):  # If the marker hasn't been set yet, you need to get a default point, so just use the first coordinate in the list
		groundLat = points[0][0]
		groundLon = points[0][1]


	### The HTML and JavaScript is a formatted string, this allows for a Google Maps widget ###
	html = '''
	<html><head>
	<meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
	<style type="text/css">
	    html { height: 100% }
	    body { height: 100%; margin: 0; padding: 0 }
	    #map { width: 100%; height: 100% }
	</style>
	        <script async defer
	        src="https://maps.googleapis.com/maps/api/js?key=''' + str(apiKey) + '''&callback=initialize">
	        google.maps.event.addDomListener(window, "load", initialize)
	</script>
	<script type="text/javascript">
	    var map, marker
	    function initialize() {
	        map = new google.maps.Map(document.getElementById("map"), {
	            center: {lat: ''' + str(groundLat) + ''', lng: ''' + str(groundLon) + '''},
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
			if (''' + str(goodSpotCoords) + ''' != 0){
				goodSpotCoordinates = [''' + str(goodSpotCoords) + '''];
				goodSpotPath = new google.maps.Polygon({
					map: map,
					paths: goodSpotCoordinates,
					strokeColor: '#00FF00',
					strokeOpacity: 0.8,
					strokeWeight: 1,
					fillColor: '#00FF00',
					fillOpacity: 0.1
				});
            }
            flightPlanCoordinates = [''' + str(allPoints) + '''];
			flightPath = new google.maps.Polyline({
                map: map,
                path: flightPlanCoordinates,
                geodesic: true,
                strokeColor: '#FF0000',
                strokeOpacity: 1.0,
                strokeWeight: 2
            });
	    }

	</script>
	</head>
	<body><div id="map"/></body>
	</html>
	'''
	return html


def getAltitude(lat,lon, apiKey):
	""" Uses the google api to determine the altitude (in feet) of the location by latitude and longitude """

	url = 'https://maps.googleapis.com/maps/api/elevation/json?locations='+str(lat)+','+str(lon)+'&key='+apiKey		# Site that returns the elevation of latitude and longitude
	response = urllib2.urlopen(url)
	pageTxt = str(response.read())		# Get the text of the page from the URL
	elevation = pageTxt[pageTxt.find('elevation')+len('elevation')+4:pageTxt.find(',')]		# Parse the text on the page
	alt = float(elevation)

	return alt*3.2808		# Convert to ft