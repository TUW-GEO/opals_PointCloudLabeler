#from osgeo import ogr
from PyQt5 import QtCore,QtWidgets,QtGui,uic
from PyQt5.QtGui import *
#from OpenGL.GLUT import *
import os
import opals
from opals import Import, Grid, Shade, pyDM
import numpy as np
import math
from Geometry import GeometryType

#color for unclassified points
DEFAULT_COLOR = QtGui.QColor(QtCore.Qt.white)


class GeometryObject(object):
    '''
    a trivial custom data object
    '''
    def __init__(self, type, coords, id = None, subids = None):
        self.type = type
        self.id = id
        self.subids = subids
        self.coords = coords
        self.neigs = None
        self.color = DEFAULT_COLOR
        self.constr = None
        self.enabled = True

    def has_subid(self,idx):
        if self.subids and idx < len(self.subids):
            return True;
        else:
            return False;

class TreeItem(object):
    '''
    a python object used to return row/column data, and keep note of
    it's parents and/or children
    '''
    def __init__(self, geo, parentItem, subidx = -1):
        self.geo = geo
        self.subidx = subidx
        self.parentItem = parentItem
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return 12

    def setChecked(self, checked ):
        self.geo.enabled = checked

    def isChecked(self ):
        return self.geo.enabled

    def data(self):
        if self.geo.type == GeometryType.point:
            return QtCore.QVariant("Point")
        else:
            return QtCore.QVariant("unkown")

        #if column >= 2 and column <= 4:
           # if self.geo.type == GeometryType.point:
                #return QtCore.QVariant(format_coords(self.geo.coords,column-2))

    def parent(self):
        return self.parentItem


class Pointsmodel(QtCore.QAbstractItemModel):
    def __init__(self, parent = None):
        QtCore.QAbstractItemModel.__init__(self,parent)
        self.data = []
        self.rootItems = []
        self.pointIdMap = {}
        self.updateCallback = None
        self.nextPointId = 1
        self.setupModelData()

    def setUpdateCallback(self, callback):
        self.updateCallback = callback

    def getdata(self):
        return self.data

    def data(self, index, role):
        if not index.isValid():
            return QtCore.QVariant()

        item = index.internalPointer()
        if role == QtCore.Qt.DisplayRole:
            return item.data(index.column())
        elif role == QtCore.Qt.BackgroundRole:
            ##return QtCore.Qt.red
            return QtGui.QColor(item.geo.color)

            #if index.column() == 11:
             #   return QtGui.QColor(item.geo.color)
            #else:
             #   return QtCore.QVariant()

##        if role == QtCore.Qt.UserRole:
##            if item:
##                return item.person
        elif role == QtCore.Qt.CheckStateRole:
            #if index.column() == 0:
            return int(QtCore.Qt.Checked if item.isChecked() else QtCore.Qt.Unchecked)
            #else:
             #   return QtCore.QVariant()  # super(treeModel, self).data(index, role)

        return QtCore.QVariant()

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if index.isValid():# and index.column() == 0:
            if role == QtCore.Qt.EditRole:
                return False
            if role == QtCore.Qt.CheckStateRole:
                item = index.internalPointer()
                if item.parent() == None:
                    checked = (value == QtCore.Qt.Checked)
                    item.setChecked(checked)
                    for i in range(item.childCount()):
                        item.child(i).setChecked(checked)
                    #index2 = self.createIndex(index.row(), index.column())
                    #self.dataChanged.emit(index, index2)
                    self.updateCallback()
                    return True
                else:
                    return False

        return super(Pointsmodel, self).setData(index, value, role)

    def setupModelData(self):
        for geo in self.data:
            newItem = TreeItem(geo, None)
            self.rootItems.append(newItem)

    def hasPointId(self,coords):
        pt = tuple([coords[0],coords[1],coords[2]])
        return (pt in self.pointIdMap)

    def getPointId(self, coords, preId=None):
        pt = tuple([coords[0], coords[1], coords[2]])

        if pt in self.pointIdMap:
            return self.pointIdMap[pt]
        else:
            if preId != None:
                return preId
            while self.nextPointId in self.pointIdMap.values():
                self.nextPointId += 1
            id = self.nextPointId
            self.pointIdMap[pt] = id
            self.nextPointId += 1
            return id

    def storePointId(self,id,coords):
        pt = tuple([coords[0],coords[1],coords[2]])
        for pt2, id2 in list(self.pointIdMap.items()):
          if (id == id2 and pt != pt2) or (id != id2 and pt == pt2):
            del self.pointIdMap[pt2]
        self.pointIdMap[pt] = id

    def getPoint(self,find_id):
        for pt, id in self.pointIdMap.items():
          if find_id == id:
            geo = GeometryObject(GeometryType.point,pt,id)
            return geo
        return None


class ClassificationTool(QtWidgets.QMainWindow):
    def __init__(self):
        super(ClassificationTool, self).__init__()
        uic.loadUi('ClassificationTool.ui', self)
        self.initUI()
        self.linestring = None
        self.odm = None
        self.result = None
        #self.data = None
        self.PathToFile.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21.laz" )
        self.PathToAxisShp.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21_axis_transformed.shp")
        #self.PathToFile.setText(r"C:\swdvlp64_cmake\opals\distro\demo\strip21.laz")
        #self.PathToAxisShp.setText(r"C:\swdvlp64_cmake\opals\distro\demo\strip21_axis.shp")

    def initUI(self):
        self.LoadButton.pressed.connect(self.load_pointcloud)
        self.LoadAxis.pressed.connect(self.viewSection)

        self.Next.pressed.connect(self.nextSection)
        self.Previous.pressed.connect(self.previousSection)

        self.Pointsmodel = Pointsmodel() #ToDo: class für übergabe der Daten
        self.Section.setData(self.Pointsmodel.getdata())
        #self.Section.setData(self.data)

        self.Save.pressed.connect(self.save_file)

    def load_pointcloud(self):
        self.Elevator.clear()

        path = str(self.PathToFile.text()).strip()
        os.chdir(os.path.dirname(os.path.abspath(path)))

        # get the filname
        data = path.split('\\')  # ['...','...','...','strip21.laz']
        data = data[len(data) - 1]  # strip21.laz
        filename = data.split('.')  # ['strip21','laz']
        name = filename[0]  # 'strip21'

        #load the opals datamanager in read and write
        odm = name + '.odm'
        self.odm = pyDM.Datamanager.load(odm, readOnly=True, threadSafety=False)  #TODO change readonly!!!

        #create shading
        if os.path.isfile(name + '.odm') == False:
            Import.Import(inFile=data, outFile=name + '.odm').run()

        elif os.path.isfile(name + '.tif') == False:
            Grid.Grid(inFile=name + '.odm', outFile=name + '.tif', filter='echo[last]',
                  interpolation=opals.Types.GridInterpolator.movingPlanes, gridSize=0.5).run()

        shd = Shade.Shade(inFile=name + '.tif')
        shd.run()

        image = QPixmap(str(shd.outFile))
        self.Elevator.setPixmap(image)
        self.PathToFile.clear()

    #def load_axis(self):
        #axis = str(self.PathToAxisShp.text()).strip()
        #os.chdir(os.path.dirname(os.path.abspath(axis)))

        #data = axis.split('\\')
        #file = data[len(data)-1]
        #file = ogr.Open(data[len(data) - 1])
        #print(file)
        #shape = file.GetLayer(0)
        #print(shape)
        #feature = shape.GetFeature(0)
        #first = feature.ExportToJson(as_object=True)
        #linestring = first['geometry']['coordinates'] #List of all coordinates of the axis file
        #self.axis = linestring
        #print(linestring)

        #self.PathToAxisShp.clear()

    def load_axis(self):
        axis = str(self.PathToAxisShp.text()).strip()
        data = axis.split('\\')
        file = data[len(data)-1]
        imp = pyDM.Import.create(file, pyDM.DataFormat.auto)

        pts = []
        for obj in imp:
            # loop over points
            for i in range(obj.sizePoint()):
                pt = obj[i]
                pts.append([pt.x, pt.y])
        self.linestring = pts

    def get_points_in_polygon(self):
        self.load_axis()
        if not self.odm:
            return
        if not self.linestring:
            return

        width = float(self.width_section.text().strip())
        length = float(self.lenght_section.text().strip())
        dm = self.odm
        linestring = self.linestring

        lf = pyDM.AddInfoLayoutFactory()
        type, inDM = lf.addColumn(dm, 'Id', True); assert  inDM == True
        type, inDM = lf.addColumn(dm, 'GPSTime', True); assert inDM == True
        type, inDM = lf.addColumn(dm, 'Amplitude', True); assert inDM == True
        type, inDM = lf.addColumn(dm, 'Classification', True); assert inDM == True
        layout = lf.getLayout()

        def direction(p1, p2):
            p1 = np.array(p1).reshape(1, 2)
            p2 = np.array(p2).reshape(1, 2)
            p = p2 - p1
            p = p / math.sqrt(p[0, 0]**2 + p[0, 1]**2)
            return p

        def poly_points(start, vector, length, width):
            start_point = np.array(start).reshape(1, 2)
            rot_vector = np.array([-vector[0, 1], vector[0, 0]]).reshape(1, 2)
            p1 = start_point + (rot_vector * length / 2)
            p2 = start_point + (-rot_vector * length / 2)
            p3 = p2 + (width * vector)
            p4 = p1 + (width * vector)
            return p1, p2, p3, p4

        p1, p2, p3, p4 = poly_points(linestring[0], direction(linestring[0], linestring[1]), length, width)
        pf = pyDM.PolygonFactory()

        def create_polygon(p1, p2, p3, p4):
            pf.addPoint(p1[0, 0], p1[0, 1])
            pf.addPoint(p2[0, 0], p2[0, 1])
            pf.addPoint(p3[0, 0], p3[0, 1])
            pf.addPoint(p4[0, 0], p4[0, 1])
            pf.closePart()
            return pf.getPolygon()

        #create the polygon
        polygon = create_polygon(p1, p2, p3, p4)

        #extract the points inside of the polygon
        result = pyDM.NumpyConverter.searchPoint(dm, polygon, layout, withCoordinates = True)
        self.result = result

    def viewSection(self):
        self.get_points_in_polygon()
        self.Section.setData(self.result)
        coords1 = [ self.result["x"][0], self.result["y"][0], self.result["z"][0]]
        coords2 = [ coords1[0]+10., coords1[1]+10., coords1[2]+10.]
        self.Section.setStretchAxis(coords1, coords2)
        self.Section.dataRefesh()

    def nextSection(self):
        pass

    def previousSection(self):
        pass

    def save_file(self):
        pass


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = ClassificationTool()
    win.show()
    sys.exit(app.exec_())


#C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21.laz
#C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21_axis.shp
#axisFile = name + '_axis.shp'
