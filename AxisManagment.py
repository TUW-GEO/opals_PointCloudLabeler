from StationUtilities import StationCubicSpline2D
from opals import pyDM

class AxisManagement:
    def __init__(self,odm):
        self.odm = odm
        #self.result = None
       # self._createlayout()
        self.odm2idx = {}
        self.idx2odm = {}
        self.axis = []
        self.axisInfo = {}
        self.splines = {}
        #self._read_odm()

    def _createlayout(self):
        lf = pyDM.AddInfoLayoutFactory()
        type, inDM = lf.addColumn(self.odm, 'Id', True);assert inDM == True
        self.layout = lf.getLayout()

    def _read_odm(self):
        self._createlayout()
        for obj in self.odm.geometries(self.layout):
            id = obj.info().get(0)
            idx = len(self.axis)
            self.odm2idx[id] = idx
            self.idx2odm[idx] = id
            self.axis.append([obj])
            notes, lenght = self.information(obj)
            self.axisInfo[idx] = [notes, lenght]
        i=0

    def readShpFile(self, shp):
        imp = pyDM.Import.create(shp, pyDM.DataFormat.auto)

        for obj in imp:
            self.addLine(obj)

        # return self.odm

    def addLine(self, line):
        id = self.odm.addPolyline(line)
        idx = len(self.axis)
        self.odm2idx[id] = idx
        self.idx2odm[idx] = id
        self.axis.append([line])
        notes, lenght = self.information(line)
        self.axisInfo[idx] = [notes, lenght]
        self.save()

    def information(self, obj):
        lenght = 0
        pts =  self.polyline2linestring(obj)
        self.createSplines(pts)
        notes = len(pts)
        for idx in range(1, len(pts)):
            pt1 = pts[idx - 1]
            pt2 = pts[idx]
            dx = pt2[0]-pt1[0]
            dy = pt2[1]-pt1[1]
            lenght =+ (dx ** 2 + dy ** 2) ** 0.5
        return notes, lenght

    def createSplines(self,pts):
        axis_spline = StationCubicSpline2D(pts)
        self.splines[len(self.axis)-1] = axis_spline.vertices

    def getByIdx(self, idx):
        return self.axis[idx]

    def getById(self, id):
        assert(id in self.odm2idx)
        idx = self.odm2idx[id]
        return self.axis[idx]

    def getByCoords(self, x, y):
        pi = self.odm.getPolylineIndex()
        searchLine = pi.searchGeometry(1, pyDM.Point(x, y, 0))
        assert( len(searchLine) == 1)
        #searchLine[0].cloneView(self.layout)
        id = searchLine[0].info().get(0)
        assert(id in self.odm2idx)
        idx = self.odm2idx[id]
        return self.axis[idx]


    def polyline2linestring(self,odm_line):
        pts = []
        for idx, part in enumerate(odm_line.parts()):
            for p in part.points():
                pts.append([p.x, p.y])
        return pts

    def removeByIdx(self,idx):
        id = self.idx2odm[idx]
        self.odm.deletePolyline(id)
        del self.idx2odm[idx]
        del self.odm2idx[id]

    def save(self):
        self.odm.save()