from opals import pyDM
import sys
import math

class AnalyseDistance(pyDM.AnalyseDistance):

     def __init__(self, polyline = None):
         # initialize the base class (mandatory!)
         super().__init__()
         self.distance = None
         self.indices = None
         self.basePt = None
         self.polyline = polyline

     def reset(self):
         self.sumDistance = 0
         self.counter = 0
         self.exceedCounter = 0

     def closest(self, distance, idx, basePt, Idx1, Idx2, minDistPt):
         self.distance = distance
         self.basePt = pyDM.Point(minDistPt.x, minDistPt.y, 0)
         self.vertices = sorted((Idx1, Idx2))

         self.closestVertex = Idx1
         if self.polyline and Idx1 != Idx2:
            pt1 = self.polyline[Idx1]
            pt2 = self.polyline[Idx2]
            d1 = math.sqrt((pt1.x - minDistPt.x)**2 + (pt1.y - minDistPt.y)**2)
            d2 = math.sqrt((pt2.x - minDistPt.x)**2 + (pt2.y - minDistPt.y)**2)
            if d1 > d2:
                self.closestVertex = Idx2



     def exceeds(self,idx):
         pass
     
def get_closest_point(polyline, point, maxDist=-1):
    obj = AnalyseDistance(polyline)
    if not isinstance(point, pyDM.Point):
        point = pyDM.Point(point[0], point[1], 0)
    pyDM.GeometricAlgorithms.analyseDistance(line=polyline, pt=point, callback=obj, maxDist=maxDist, d3=False)
    return obj.closestVertex

def get_closest_point_on_line(polyline, point, maxDist=-1):
    obj = AnalyseDistance(polyline)
    if not isinstance(point, pyDM.Point):
        point = pyDM.Point(point[0], point[1], 0)
    pyDM.GeometricAlgorithms.analyseDistance(line=polyline, pt=point, callback=obj, maxDist=maxDist, d3=False)
    return obj.vertices[0], obj.basePt

def insert_point_in_polyline(polyline, ptlist, point, maxDist=-1):
    obj = AnalyseDistance(polyline)
    if not isinstance(point, pyDM.Point):
        point = pyDM.Point(point[0], point[1], 0)
    pyDM.GeometricAlgorithms.analyseDistance(line=polyline, pt=point, callback=obj, maxDist=maxDist, d3=False)

    #if point is inserted after the last vertex it gets appended, else it gets inserted before next vertex
    if obj.vertices[0] == len(ptlist)-1:
        ptlist.append([point.x, point.y])
    else:
        ptlist.insert(obj.vertices[-1], [point.x, point.y])
    return ptlist


