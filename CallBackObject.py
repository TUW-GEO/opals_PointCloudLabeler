from opals import pyDM
import sys

class AnalyseDistance(pyDM.AnalyseDistance):

     def __init__(self):
         # initialize the base class (mandatory!)
         if sys.version_info >= (3, 0):
             super().__init__()
         else:
             super(AnalyseDistance, self).__init__()
         self.sumDistance = 0
         self.counter = 0
         self.exceedCounter = 0
         self.distance = None
         self.indices = None
         self.footpoint = None

     def reset(self):
         self.sumDistance = 0
         self.counter = 0
         self.exceedCounter = 0

     def closest(self, distance, idx, basePt, Idx1, Idx2, minDistPt):
         self.counter += 1
         self.sumDistance += distance
         self.insertVertex = (Idx1, Idx2)
         self.pickedVertex = Idx1

     def exceeds(self,idx):
         self.exceedCounter += 1

     def meanDistance(self):
         return self.sumDistance / self.counter