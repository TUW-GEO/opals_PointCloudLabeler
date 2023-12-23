#from osgeo import ogr
from PyQt5 import QtCore,QtWidgets,QtGui,uic
from PyQt5.QtGui import *
#from OpenGL.GLUT import *
import os
import opals
from opals import Import, Grid, Shade, pyDM
import numpy as np
import math

#color for unclassified points
DEFAULT_COLOR = QtGui.QColor(QtCore.Qt.white)

#cmap = {0:[210,210,210],1:[180,180,180],2:[135,70,10],3:[185]}

class ClassificationTool(QtWidgets.QMainWindow):
    def __init__(self):
        super(ClassificationTool, self).__init__()
        uic.loadUi('ClassificationTool.ui', self)
        self.initUI()
        self.linestring = None
        self.odm = None
        self.result = None
        self.direction = None
        self.layout = None
        self.dir_camera = None
        self.rot_camera = None
        self.width = None
        self.length = None
        self.linestart = None
        self.linestop = None
        self.pos = None
        self.PathToFile.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21.laz" )
        self.PathToAxisShp.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21_axis_transformed.shp")
        #self.PathToFile.setText(r"C:\swdvlp64_cmake\opals\distro\demo\strip21.laz")
        #self.PathToAxisShp.setText(r"C:\swdvlp64_cmake\opals\distro\demo\strip21_axis.shp")

    def initUI(self):
        self.LoadButton.pressed.connect(self.load_pointcloud)
        self.LoadAxis.pressed.connect(self.viewFirstSection)

        self.QPushButtonWidth.pressed.connect(self.viewFirstSection)
        self.QPushButtonLength.pressed.connect(self.viewFirstSection)
        self.Next.pressed.connect(self.nextSection)
        self.Previous.pressed.connect(self.previousSection)

        self.OrthoView.clicked.connect(self.setOrthoView)

        self.Save.pressed.connect(self.save_file)

    def load_pointcloud(self):
        self.Elevator.clear()

        path = str(self.PathToFile.text()).strip()
        os.chdir(os.path.dirname(os.path.abspath(path)))

        # get the filname
        data = path.split('\\')
        data = data[len(data) - 1]
        filename = data.split('.')
        name = filename[0]

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
        self.PathToAxisShp.clear()

    def get_points_in_polygon(self):
        if not self.odm:
            return
        if not self.linestring:
            return

        self.width = float(self.width_section.text().strip())
        self.length = float(self.lenght_section.text().strip())

        dm = self.odm
        #linestring = self.linestring
        self.linestart = self.linestring[0]
        self.linestop = self.linestring[1]

        lf = pyDM.AddInfoLayoutFactory()
        type, inDM = lf.addColumn(dm, 'Id', True); assert  inDM == True
        type, inDM = lf.addColumn(dm, 'GPSTime', True); assert inDM == True
        type, inDM = lf.addColumn(dm, 'Amplitude', True); assert inDM == True
        type, inDM = lf.addColumn(dm, 'Classification', True); assert inDM == True
        self.layout = lf.getLayout()

        def direction(p1, p2):
            p1 = np.array(p1).reshape(1, 2)
            p2 = np.array(p2).reshape(1, 2)
            p = p2 - p1
            p = p / math.sqrt(p[0, 0]**2 + p[0, 1]**2)
            self.direction = p
            return p

        def poly_points(start, vector, length, width):
            start_point = np.array(start).reshape(1, 2)
            rot_vector = np.array([-vector[0, 1], vector[0, 0]]).reshape(1, 2)
            p1 = start_point + (rot_vector * length / 2)
            p2 = start_point + (-rot_vector * length / 2)
            p3 = p2 + (width * vector)
            p4 = p1 + (width * vector)

            self.rot_camera = rot_vector

            return p1, p2, p3, p4

        p1, p2, p3, p4 = poly_points(self.linestart, direction(self.linestart, self.linestop), self.length, self.width)
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
        result = pyDM.NumpyConverter.searchPoint(dm, polygon, self.layout, withCoordinates = True)
        self.result = result
#
    def direction(self,p1,p2):
        p1 = np.array(p1).reshape(1, 2)
        p2 = np.array(p2).reshape(1, 2)
        p = p2 - p1
        p = p / math.sqrt(p[0, 0]**2 + p[0, 1]**2)
        self.direction = p
        return p

    def polygon(self):
        def poly_points(start, vector, length, width):
            start_point = np.array(start).reshape(1, 2)
            rot_vector = np.array([-vector[0, 1], vector[0, 0]]).reshape(1, 2)
            p1 = start_point + (rot_vector * length / 2)
            p2 = start_point + (-rot_vector * length / 2)
            p3 = p2 + (width * vector)
            p4 = p1 + (width * vector)
            self.rot_camera = rot_vector
            return p1, p2, p3, p4

        p1, p2, p3, p4 = poly_points(self.linestart, self.direction, self.length, self.width)
        pf = pyDM.PolygonFactory()

        def create_polygon(p1, p2, p3, p4):
            pf.addPoint(p1[0, 0], p1[0, 1])
            pf.addPoint(p2[0, 0], p2[0, 1])
            pf.addPoint(p3[0, 0], p3[0, 1])
            pf.addPoint(p4[0, 0], p4[0, 1])
            pf.closePart()
            return pf.getPolygon()

        # create the polygon
        polygon = create_polygon(p1, p2, p3, p4)

        # extract the points inside of the polygon
        result = pyDM.NumpyConverter.searchPoint(self.odm, polygon, self.layout, withCoordinates=True)
        self.result = result

    def viewFirstSection(self):
        self.load_axis()
        self.get_points_in_polygon()
        self.Section.setData(self.result)
        coords1 = [ self.result["x"][0], self.result["y"][0], self.result["z"][0]]
        coords2 = [ coords1[0]+10., coords1[1]+10., coords1[2]+10.]
        self.Section.setStretchAxis(coords1, coords2)

        self.Section.setOrthoView(self.rot_camera)

        self.Section.dataRefesh()

    def setOrthoView(self):
        if self.OrthoView.isChecked() == True:
            self.Section.setOrthoView(self.rot_camera)

    def nextSection(self): #ToDO: anfrage wann nächster eintrag in linestring und neuausrichtung des polygons notwendig ist
        for i in range(len(self.linestart)):
            self.linestart[i] = self.linestart[i] + (self.width*self.direction[0,i])
        self.polygon()

        self.Section.setData(self.result)
        coords1 = [self.result["x"][0], self.result["y"][0], self.result["z"][0]]
        coords2 = [coords1[0] + 10., coords1[1] + 10., coords1[2] + 10.]
        self.Section.setStretchAxis(coords1, coords2)

        self.Section.dataRefesh()

    def previousSection(self):
        self.Section.dataRefesh()

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
