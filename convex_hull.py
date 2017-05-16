# Graham Scan - Tom Switzer <thomas.switzer@gmail.com>
class ConvexHull:
	def __init__(self,points):
		self.TURN_LEFT = 1
		self.TURN_RIGHT = -1
		self.TURN_NONE = 0
		self.points = points


	def turn(self, p, q, r):
		return cmp((q[0] - p[0])*(r[1] - p[1]) - (r[0] - p[0])*(q[1] - p[1]), 0)

	def _keep_left(self, hull, r):
		while len(hull) > 1 and self.turn(hull[-2], hull[-1], r) != self.TURN_LEFT:
			hull.pop()
		if not len(hull) or hull[-1] != r:
			hull.append(r)
		return hull

	def convex_hull(self):
		"""Returns points on convex hull of an array of points in CCW order."""
		points = sorted(self.points)
		l = reduce(self._keep_left, points, [])
		u = reduce(self._keep_left, reversed(points), [])
		return l.extend(u[i] for i in xrange(1, len(u) - 1)) or l