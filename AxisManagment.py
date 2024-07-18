from opals import pyDM

class AxisManagement:
    def __init__(self,odm):
        self.odm = odm
        #self.result = None
       # self._createlayout()
        self.odm2idx = {}
        self.idx2odm = {}
        self.axis = []
        self._read_odm()

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

    def addLine(self, line):
        id = self.odm.addPolyline(line)
        idx = len(self.axis)
        self.odm2idx[id] = idx
        self.idx2odm[idx] = id
        self.axis.append(line)

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
        searchLine[0].cloneView(self.layout)
        id = searchLine[0].info().get(0)
        assert(id in self.odm2idx)
        idx = self.odm2idx[id]
        return self.axis[idx]

    def removeByIdx(self,idx):
        id = self.idx2odm[idx]
        self.odm.deletePolyline(id)
        del self.idx2odm[idx]
        del self.odm2idx[id]