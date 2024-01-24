from opals import Import, Grid, Shade, pyDM
from PyQt5 import QtCore,QtWidgets,QtGui,uic
from PyQt5.QtGui import *
import os
import opals
import numpy as np
import math
import copy


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
        self.rot_camera = None
        self.width = None
        self.length = None
        self.begin = None
        self.end = None
        self.counter = 0
        self.lineend = None
        self.forwards = False
        self.backwards = False
        self.hightcolor = False
        self.Point = False
        self.Rectangle = False
        self.PathToFile.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21.laz" )
        self.PathToAxisShp.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21_axis_transformed.shp")
        #self.PathToFile.setText(r"C:\swdvlp64_cmake\opals\distro\demo\strip21.laz")
        #self.PathToAxisShp.setText(r"C:\swdvlp64_cmake\opals\distro\demo\strip21_axis.shp")

    def initUI(self):
        self.LoadButton.pressed.connect(self.load_pointcloud)
        self.LoadAxis.pressed.connect(self.viewFirstSection)

        self.QPushButtonWidth.pressed.connect(self.changePolygonSize)
        self.QPushButtonLength.pressed.connect(self.changePolygonSize)
        self.Next.pressed.connect(self.nextSection)
        self.Previous.pressed.connect(self.previousSection)

        self.HightColor.clicked.connect(self.changecoloring)

        self.OrthoView.clicked.connect(self.setOrthoView)

        self.PointSelection.clicked.connect(self.SelectPoint)
        self.RectangleSelection.clicked.connect(self.SelectRectangle)

        self.ClassList.currentTextChanged.connect(self.PointsClassification)

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
        self.odm = pyDM.Datamanager.load(odm, readOnly=False, threadSafety=False)

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
        self.segment = copy.deepcopy(pts)
        self.PathToAxisShp.clear()

    def get_points_in_polygon(self):
        if not self.odm:
            return
        if not self.linestring:
            return

        self.width = float(self.width_section.text().strip())
        self.length = float(self.lenght_section.text().strip())

        dm = self.odm

        if self.forwards:
            self.begin = self.segment[self.counter]
            self.end = self.segment[self.counter + 1]
            self.forwards = False
        elif self.backwards:
            self.begin = self.segment[self.counter+1]
            self.end = self.segment[self.counter]
            self.backwards = False

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

        p1, p2, p3, p4 = poly_points(self.begin, direction(self.begin, self.end), self.length, self.width)
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
        result = pyDM.NumpyConverter.searchPoint(dm, polygon, self.layout, withCoordinates = True, noDataObj='min')
        self.result = result

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

        p1, p2, p3, p4 = poly_points(self.begin, self.direction, self.length, self.width)
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
        result = pyDM.NumpyConverter.searchPoint(self.odm, polygon, self.layout, withCoordinates=True, noDataObj='min')
        self.result = result

    def viewFirstSection(self):
        self.forwards = True
        self.load_axis()
        self.get_points_in_polygon()
        self.Section.setData(self.result)
        coords1 = [ self.result["x"][0], self.result["y"][0], self.result["z"][0]]
        coords2 = [ coords1[0]+10., coords1[1]+10., coords1[2]+10.]
        self.Section.setStretchAxis(coords1, coords2)

        self.Section.setOrthoView(self.rot_camera)

        self.Section.dataRefresh()

    def changePolygonSize(self):
        self.width = float(self.width_section.text().strip())
        self.length = float(self.lenght_section.text().strip())

        self.polygon()

        self.Section.setData(self.result)
        coords1 = [self.result["x"][0], self.result["y"][0], self.result["z"][0]]
        coords2 = [coords1[0] + 10., coords1[1] + 10., coords1[2] + 10.]
        self.Section.setStretchAxis(coords1, coords2)

        self.Section.dataRefresh()

    def setOrthoView(self):
        if self.OrthoView.isChecked() == True:
            self.Section.setOrthoView(self.rot_camera)

    def checkLineEnd(self):
        self.lineend = False
        currentDirection = self.direction * self.factor
        #print('curr Dir:', currentDirection)

        if currentDirection[0,0] > 0:
            self.lineend = ((self.begin[0] + self.width) > self.end[0])

        elif currentDirection[0,0] < 0:
            self.lineend = ((self.begin[0] + self.width) < self.end[0])

        elif currentDirection[0,0] == 0:
            if currentDirection[0,1] > 0:
                self.lineend = ((self.begin[1] + self.width) > self.end[1])
            elif currentDirection[0,1] < 0:
                self.lineend = ((self.begin[1] + self.width) < self.end[1])


    def nextSection(self):
        self.factor = 1
        self.end = self.linestring[self.counter+1]
        self.checkLineEnd()

        #print('--------------------------')
        #print('Vor')
        #print(self.counter)
        #print('old pos:',self.begin)
        #print('end:',self.end)
        #print('--------------------------')

        if self.lineend == True:
            self.forwards = True
            self.counter += 1

            if (self.begin[0] < self.linestring[self.counter + 1][0] and ((self.counter + 1) == (len(self.linestring) - 1))) or self.counter < 0:
                QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, "Error occured", "End of Polyline! No more points available.").exec_();
            else:
                self.get_points_in_polygon()
                self.Section.setData(self.result)
                coords1 = [self.result["x"][0], self.result["y"][0], self.result["z"][0]]
                coords2 = [coords1[0] + 10., coords1[1] + 10., coords1[2] + 10.]
                self.Section.setStretchAxis(coords1, coords2)

                self.Section.setOrthoView(self.rot_camera)

                self.Section.dataRefresh()

        else:
            for i in range(len(self.begin)):
                self.begin[i] = self.begin[i] + (self.width*self.direction[0,i])
            #print('new pos:', self.begin)
            self.polygon()

            self.Section.setData(self.result)
            coords1 = [self.result["x"][0], self.result["y"][0], self.result["z"][0]]
            coords2 = [coords1[0] + 10., coords1[1] + 10., coords1[2] + 10.]
            self.Section.setStretchAxis(coords1, coords2)

            self.Section.dataRefresh()

    def previousSection(self):
        self.factor = -1
        self.end = self.linestring[self.counter]
        self.checkLineEnd()

        #print('--------------------------')
        #print('zurück')
        #print(self.counter)
        #print('old pos:', self.begin)
        #print('end:', self.end)
        #print('--------------------------')

        if self.lineend == True:
            self.backwards = True
            self.counter -= 1
            #print('counter -= 1')

            if self.counter < 0:
                QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, "Error occured", "Begin of Polyline! No more points available.").exec_();
            else:
                self.get_points_in_polygon()
                self.Section.setData(self.result)
                coords1 = [self.result["x"][0], self.result["y"][0], self.result["z"][0]]
                coords2 = [coords1[0] + 10., coords1[1] + 10., coords1[2] + 10.]
                self.Section.setStretchAxis(coords1, coords2)

                self.Section.setOrthoView(self.rot_camera)

                self.Section.dataRefresh()

        else:
            for i in range(len(self.begin)):
                self.begin[i] = self.begin[i] - (self.width*self.direction[0,i])
            #print('new pos:', self.begin)
            self.polygon()

            self.Section.setData(self.result)
            coords1 = [self.result["x"][0], self.result["y"][0], self.result["z"][0]]
            coords2 = [coords1[0] + 10., coords1[1] + 10., coords1[2] + 10.]
            self.Section.setStretchAxis(coords1, coords2)

            self.Section.dataRefresh()

    def PointsClassification(self):
        classes = {'0 unclassified' : 0, '1 undefined' : 1, '2 ground' : 2,
                   '3 low vegetation' : 3, '4 medium vegetation' : 4, '5 high vegetation' : 5,
                   '6 building' : 6, '7 noise' : 7, '8 model key point' : 8,
                   '9 water' : 9, '10 rail' : 10, '11 road surface' : 11,
                   '12 bridge deck' : 12, '13 wire guard' : 13, '14 wire conductor': 14,
                   '15 transmission tower' : 15, '16 wire connector' : 16}

        self.Section.currentClass = classes[str(self.ClassList.currentText())]

    def SelectPoint(self):
        if self.RectangleSelection.isChecked():
            self.RectangleSelection.setChecked(False)
            self.Section.SelectRectangle = False

        if self.PointSelection.isChecked():
            self.PointsClassification()
            self.Section.SelectPoint = True
        elif self.PointSelection.isChecked() == False:
            self.Section.SelectPoint = False

    def SelectRectangle(self):
        if self.PointSelection.isChecked():
            self.PointSelection.setChecked(False)
            self.Section.SelectPoint = False

        if self.RectangleSelection.isChecked():
            self.Section.SelectRectangle = True
        elif self.RectangleSelection.isChecked() == False:
            self.Section.SelectRectangle = False

    def changecoloring(self):
        if self.HightColor.isChecked():
            self.Section.currentColor = 2
            self.Section.dataRefresh()
        elif self.HightColor.isChecked() == False:
            self.Section.currentColor = 1
            self.Section.dataRefresh()

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
