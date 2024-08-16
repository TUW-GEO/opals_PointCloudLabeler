import os.path
from StationUtilities import StationCubicSpline2D
from opals import pyDM
from CallBackObject import AnalyseDistance

class AxisManagement:
    def __init__(self, odm_filename, overwrite=False):
        self.odm = None
        if odm_filename:
            if os.path.exists(odm_filename) and not overwrite:
                self.odm = pyDM.Datamanager.load(odm_filename, readOnly=False, threadSafety=False)
            else:
                self.odm = pyDM.Datamanager.create(odm_filename, threadSafety=False)
        self._createlayout()
        # self.odm2idx = {}
        # self.idx2odm = {}
        # self.axis = []
        # self.allAxisPts = []
        # self.axisInfo = {}
        # self.splines = {}
        self._dataRefresh()

    def _createlayout(self):
        lf = pyDM.AddInfoLayoutFactory()
        lf.addColumn(pyDM.ColumnSemantic.Id)
        self.layout = lf.getLayout()

    def _dataRefresh(self):
        self.odm2idx = {}
        self.idx2odm = {}
        self.axisInfo = {}
        self.axis = []
        self.allAxisPts = []
        self.splines = {}
        if not self.odm or not self.odm.sizeGeometry():
            return
        for obj in self.odm.geometries(self.layout):
            id = obj.info().get(0)
            idx = len(self.axis)
            self.odm2idx[id] = idx
            self.idx2odm[idx] = id
            self.axis.append([obj])
            notes, length = self.information(obj)
            self.axisInfo[idx] = [notes, length]

            pts = self.polyline2linestring(obj)
            self.allAxisPts.append(pts)

    def _updatePolyline(self, pts, id):
        f = pyDM.PolylineFactory()
        for pt in pts:
            f.addPoint(pt[0], pt[1])

        new_polyline = f.getPolyline()

        new_polyline.setAddInfoView(self.layout, False)
        new_polyline.info().set(0, int(id))

        self.odm.replacePolyline(new_polyline, attributeOnly=False)
        self._dataRefresh()

    def set_filename(self, odm_filename):
        if self.odm:
            self.odm.save()
        self.odm = pyDM.Datamanager.create(odm_filename, threadSafety=False)

    def readShpFile(self, shp):
        imp = pyDM.Import.create(shp, pyDM.DataFormat.auto)

        for obj in imp:
            self.odm.addPolyline(obj)

        self._dataRefresh()

    def empty(self):
        return len(self.axis) == 0

    def addLine(self, line):
        id = self.odm.addPolyline(line)
        idx = len(self.axis)
        self.odm2idx[id] = idx
        self.idx2odm[idx] = id
        self.axis.append([self.odm.getGeometry(id)])
        notes, length = self.information(line)
        self.axisInfo[idx] = [notes, length]
        pts = self.polyline2linestring(line)
        self.allAxisPts.append(pts)
        self.save()

    def information(self, obj, new=True):
        length = 0
        if new:
            pts = self.polyline2linestring(obj)
            self.createSplines(pts)
        else:
            pts = obj

        notes = len(pts)
        for idx in range(1, len(pts)):
            pt1 = pts[idx - 1]
            pt2 = pts[idx]
            dx = pt2[0]-pt1[0]
            dy = pt2[1]-pt1[1]
            length += (dx ** 2 + dy ** 2) ** 0.5
        return notes, length

    def createSplines(self,pts, replace=False):
        if replace:
            axis_spline = StationCubicSpline2D(pts)
            self.splines[self.idx] = axis_spline.vertices
        else:
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

    def reindex_dict(self, d):
        return {i: value for i, (key, value) in enumerate(d.items())}

    def removeByIdx(self,idx):
        id = self.idx2odm[idx]
        self.odm.deletePolyline(id)
        del self.axis[idx]
        del self.idx2odm[idx]
        del self.odm2idx[id]
        del self.axisInfo[idx]
        del self.splines[idx]
        del self.allAxisPts[idx]

        self.idx2odm = self.reindex_dict(self.idx2odm)
        self.odm2idx = {value: key for key, value in self.idx2odm.items()}
        self.axisInfo = self.reindex_dict(self.axisInfo)
        self.splines = self.reindex_dict(self.splines)

        self.save()

    def InsertVertices(self, polyline,pt):
        id = polyline.info().get(0)
        self.idx = self.odm2idx[id]

        obj = AnalyseDistance()
        point = pyDM.Point(pt[0], pt[1],0)

        pyDM.GeometricAlgorithms.analyseDistance(line=polyline, pt=point, callback=obj, d3=False)

        pts = self.polyline2linestring(polyline)
        vertices = sorted(obj.insertVertex)
        pts.insert(vertices[-1],[pt[0], pt[1]])

        self._updatePolyline(pts, id)

        self.save()

    def DeleteVertices(self,polyline,pt):
        id = polyline.info().get(0)
        self.idx = self.odm2idx[id]

        obj = AnalyseDistance()
        point = pyDM.Point(pt[0], pt[1], 0)

        pyDM.GeometricAlgorithms.analyseDistance(line=polyline, pt=point, callback=obj, maxDist=2, d3=False)

        pts = self.polyline2linestring(polyline)
        vertex = obj.pickedVertex
        pts.pop(vertex)

        self._updatePolyline(pts, id)

        self.save()

    def PickVertices(self,line,pt):
        id = line.info().get(0)
        self.idx = self.odm2idx[id]

        obj = AnalyseDistance()
        point = pyDM.Point(pt[0], pt[1], 0)

        pyDM.GeometricAlgorithms.analyseDistance(line=line, pt=point, callback=obj, maxDist=2, d3=False)

        return obj.pickedVertex

    def MoveVertices(self, polyline, vertexId, pt):
        id = polyline.info().get(0)
        self.idx = self.odm2idx[id]

        pts = self.polyline2linestring(polyline)
        pts[vertexId] = [pt[0], pt[1]]

        self._updatePolyline(pts, id)

        self.save()

    def save(self):
        if self.odm:
            self.odm.save()