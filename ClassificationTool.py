from opals import Import, Grid, Shade, pyDM
from PyQt5 import QtWidgets,uic
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
        self.Section.setMouseTracking(True)
        self.linestring = None
        self.odm = None
        self.result = None
        self.direction = None
        self.layout = None
        self.rot_camera = None
        self.along = None
        self.across = None
        self.overlap = None
        self.begin = None
        self.end = None
        self.counter = 0
        self.lineend = None
        self.forwards = False
        self.backwards = False
        self.hightcolor = False
        self.Point = False
        self.Rectangle = False
        self.firstSection = None
        self.ptsLoad = 0
        self.ptsClass = 0
        self.ptsNoClass = 0
        self.knnPts = 0
        #self.PathToFile.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21.laz" )
        #self.PathToAxisShp.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21_axis_transformed.shp")
        #self.PathToFile.setText(r"C:\swdvlp64_cmake\opals\distro\demo\strip21.laz")
        #self.PathToAxisShp.setText(r"C:\swdvlp64_cmake\opals\distro\demo\strip21_axis.shp")

        #Test data
        self.PathToFile.setText(r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\Test_Data\Fluss_110736_0_loos_528600_533980_Klassifiziert.las")
        self.PathToAxisShp.setText(r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\Test_Data\Fluss_110736_0_loos_528600_533980_Klassifiziert_axis.shp")

    def initUI(self):
        self.LoadButton.pressed.connect(self.load_pointcloud)
        self.LoadAxis.pressed.connect(self.viewFirstSection)

        self.QPushButtonAlong.pressed.connect(self.changePolygonSize)
        self.QPushButtonAcross.pressed.connect(self.changePolygonSize)
        self.QPushButtonOverlap.pressed.connect(self.overlapPolygons)
        self.Next.pressed.connect(self.nextSection)
        self.Previous.pressed.connect(self.previousSection)

        self.HightColor.clicked.connect(self.HightColoring)
        self.ClassColor.clicked.connect(self.ClassColoring)

        self.OrthoView.clicked.connect(self.setOrthoView)

        self.PointSelection.clicked.connect(self.SelectPoint)
        self.RectangleSelection.clicked.connect(self.SelectRectangle)

        self.ClassList.currentTextChanged.connect(self.PointsClassification)
        self.Reset.clicked.connect(self.Section.Reset)

        self.PointSize.valueChanged.connect(self.Section.setPointSize)

        self.knnTree.setChecked(False)

        self.model = QStandardItemModel()
        self.StatusMessages.setModel(self.model)

        self.Save.pressed.connect(self.save_file)

    def load_pointcloud(self):
        path = str(self.PathToFile.text()).strip()
        os.chdir(os.path.dirname(os.path.abspath(path)))

        # get the filname
        data = path.split('\\')
        data = data[len(data) - 1]
        filename = data.split('.')
        name = filename[0]

        odm_name = name + '.odm'
        grid_name = name + '_z.tif'
        shd_name = name + '_shd.tif'

        #import into odm if needed
        if os.path.isfile(odm_name) == False:
            Import.Import(inFile=data, outFile=odm_name).run()

        #create shading
        if os.path.isfile(grid_name) == False:
            Grid.Grid(inFile=odm_name, outFile=grid_name, filter='echo[last]',
                  interpolation=opals.Types.GridInterpolator.movingPlanes, gridSize=0.5).run()

        if os.path.isfile(shd_name) == False:
            Shade.Shade(inFile=grid_name, outFile=shd_name).run()

        # load the opals datamanager in read and write
        self.odm = pyDM.Datamanager.load(odm_name, readOnly=False, threadSafety=False)

        self.Overview.setShading(shd_name)
        self.Overview.dataRefresh()

        self.PathToFile.setEnabled(False)

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

        self.linestring = pts.copy()
        self.segment = copy.deepcopy(pts)

        self.PathToAxisShp.setEnabled(False)

        self.Overview.setAxis(pts)
        self.Overview.dataRefresh()


    def get_points_in_polygon(self):
        if not self.odm:
            return
        if not self.linestring:
            return

        self.along = float(self.along_section.text().strip())
        self.across = float(self.across_section.text().strip())
        self.overlap = (float(self.overlap_section.text().strip()))/100

        dm = self.odm

        if self.forwards:
            self.begin = self.segment[self.counter].copy()
            self.end = self.segment[self.counter + 1].copy()
            self.forwards = False
        elif self.backwards:
            self.begin = self.segment[self.counter+1].copy()
            self.end = self.segment[self.counter].copy()
            self.backwards = False

        lf = pyDM.AddInfoLayoutFactory()
        type, inDM = lf.addColumn(dm, 'Id', True); assert  inDM == True
        type, inDM = lf.addColumn(dm, 'GPSTime', True); assert inDM == True
        type, inDM = lf.addColumn(dm, 'Amplitude', True); assert inDM == True
        type, inDM = lf.addColumn(dm, 'Classification', True); assert inDM == True
        #add atribute for knn
        #type, inDM = lf.addColumn(dm,'_manuallyClassified',True,pyDM.ColumnType.bool_); assert  inDM == True
        lf.addColumn(pyDM.ColumnType.bool_, '_manuallyClassified')
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

        p1, p2, p3, p4 = poly_points(self.begin, direction(self.begin, self.end), self.across, self.along)
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
        self.Overview.setSelectionBox(p1,p2,p3,p4)
        self.Overview.dataRefresh()

        #extract the points inside of the polygon
        result = pyDM.NumpyConverter.searchPoint(dm, polygon, self.layout, withCoordinates = True, noDataObj=np.nan)
        self.result = result

        self.result['_manuallyClassified'] = self.result['Classification'] != 0

        self.ptsLoad = len(self.result['x'])
        self.ptsClass = sum(self.result['Classification'] > 0)
        self.ptsNoClass = sum(self.result['Classification'] == 0)


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

        p1, p2, p3, p4 = poly_points(self.begin, self.direction, self.across, self.along)
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
        self.Overview.setSelectionBox(p1, p2, p3, p4)
        self.Overview.dataRefresh()

        # extract the points inside of the polygon
        result = pyDM.NumpyConverter.searchPoint(self.odm, polygon, self.layout, withCoordinates=True, noDataObj=np.nan)
        self.result = result

        self.result['_manuallyClassified'] = self.result['Classification'] != 0

        self.ptsLoad = len(self.result['x'])
        self.ptsClass = sum(self.result['Classification'] > 0)
        self.ptsNoClass = sum(self.result['Classification'] == 0)

    def ptsInSection(self):
        self.Section.setData(self.result)
        coords1 = [self.result["x"][0], self.result["y"][0], self.result["z"][0]]
        coords2 = [coords1[0] + 10., coords1[1] + 10., coords1[2] + 10.]
        self.Section.setStretchAxis(coords1, coords2)

    def viewFirstSection(self):
        self.forwards = True
        self.load_axis()
        self.get_points_in_polygon()
        self.ptsInSection()
        self.Section.setOrthoView(self.rot_camera)
        self.Section.dataRefresh()
        self.firstSection = True
        self.showMessages()

    def overlapPolygons(self):
        self.overlap = float(self.overlap_section.text().strip())/100

    def changePolygonSize(self):
        self.along = float(self.along_section.text().strip())
        self.across = float(self.across_section.text().strip())
        self.polygon()
        self.ptsInSection()
        self.Section.dataRefresh()
        self.showMessages()

    def setOrthoView(self):
        self.Section.setOrthoView(self.rot_camera)

    def checkLineEnd(self):
        self.lineend = False
        #print('curr Dir:', self.currentDirection)

        if self.currentDirection[0,0] > 0:
            self.lineend = ((self.begin[0] + self.along) > self.end[0])

        elif self.currentDirection[0,0] < 0:
            self.lineend = ((self.begin[0] - self.along) < self.end[0])

        elif self.currentDirection[0,0] == 0:
            if self.currentDirection[0,1] > 0:
                self.lineend = ((self.begin[1] + self.along) > self.end[1])
            elif self.currentDirection[0,1] < 0:
                self.lineend = ((self.begin[1] - self.along) < self.end[1])

    def changeAttributes(self):
        self.setObj = {}
        self.setObj['Id'] = self.result['Id']
        self.setObj['GPSTime'] = self.result['GPSTime']
        self.setObj['Amplitude'] = self.result['Amplitude']
        self.setObj['Classification'] = self.result['Classification']
        self.setObj['_manuallyClassified'] = self.result['_manuallyClassified']
        pyDM.NumpyConverter.setById(self.setObj, self.odm, self.layout)
        self.odm.save()

    def knn(self):
        comp = copy.deepcopy(self.result)

        kdtree = pyDM.PointIndexLeaf(pyDM.IndexType.kdtree,2,True)

        for idx in range(len(self.knnSection['x'])):
            kdtree.addPoint(pyDM.Point(self.knnSection['x'][idx],self.knnSection['y'][idx],self.knnSection['z'][idx]))

        for idx in range(len(self.result['x'])):
            if not self.result['_manuallyClassified'][idx]:
                nnCount = 1
                searchPt = pyDM.Point(self.result['x'][idx],self.result['y'][idx],0.)
                searchMode = pyDM.SelectionMode.nearest
                maxSearchDist = 2

                pts = kdtree.searchPoint(nnCount,searchPt,maxSearchDist,searchMode)

                if pts != []:
                    pt = np.where(self.knnSection['x'] == (pts[0].x))
                    k = self.knnSection['Classification'][pt[0][0]]
                    self.result['Classification'][idx] = k

        self.knnPts = sum(comp['Classification'] != self.result['Classification'])
        self.model.removeRow(1)
        self.model.removeRow(2)
        self.ptsNoClass = sum(self.result['Classification'] > 0)
        self.ptsNoClass = sum(self.result['Classification'] == 0)
        self.result = self.result

    def nextSection(self):
        if self.backwards:
            self.currentDirection = self.direction * -1
            self.direction = self.currentDirection
        else:
            self.currentDirection = self.direction

        self.backwards = False
        self.forwards = True

        if self.PathToFile.isEnabled() and self.PathToAxisShp.isEnabled():
            self.PathToFile.setEnabled(False)
            self.PathToAxisShp.setEnabled(False)

        if self.knnTree.isChecked():
            self.knnSection = copy.deepcopy(self.result)

        self.changeAttributes()
        self.end = self.segment[self.counter+1].copy()
        self.checkLineEnd()

        # print('--------------------------')
        # print(self.linestring)
        # print(self.segment)
        # print('Vor')
        # print(self.counter)
        # print('old mousePos:',self.begin)
        # print('end:',self.end)
        # print('--------------------------')

        if self.lineend == True:
            self.forwards = True
            self.counter += 1

            if self.counter == (len(self.linestring)-1) or self.counter < 0:
                QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, "Error occured", "End of Polyline! No more points available.").exec_()
            else:
                self.get_points_in_polygon()
                self.ptsInSection()

                if self.knnTree.isChecked():
                    self.knn()

                self.Section.setOrthoView(self.rot_camera)
                self.Section.dataRefresh()

        else:
            for i in range(len(self.begin)):
                self.begin[i] = self.begin[i] + ((self.along*(1-self.overlap))*self.currentDirection[0,i])
            #print('new mousePos:', self.begin)
            self.polygon()
            self.ptsInSection()

            if self.knnTree.isChecked():
                self.knn()

            self.Section.dataRefresh()

        self.showMessages()

    def previousSection(self):
        if self.forwards:
            self.currentDirection = self.direction * -1

        self.forwards = False
        self.backwards = True
        self.changeAttributes()
        self.end = self.linestring[self.counter]
        self.checkLineEnd()

        # print('--------------------------')
        # print(self.linestring)
        # print('zurück')
        # print(self.counter)
        # print('old mousePos:', self.begin)
        # print('end:', self.end)
        # print('--------------------------')

        if self.lineend == True:
            self.backwards = True
            self.counter -= 1

            if self.counter < 0:
                QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, "Error occured", "Begin of Polyline! No more points available.").exec_()
            else:
                self.get_points_in_polygon()
                self.ptsInSection()
                self.Section.setOrthoView(self.rot_camera)
                self.Section.dataRefresh()

        else:
            for i in range(len(self.begin)):
                self.begin[i] = self.begin[i] + ((self.along * (1 - self.overlap)) * self.currentDirection[0, i])
            #print('new mousePos:', self.begin)
            self.polygon()
            self.ptsInSection()
            self.Section.dataRefresh()

        self.showMessages()

    def PointsClassification(self):
        classes = {'0 unclassified' : 0, '1 undefined' : 1, '2 ground' : 2,
                   '3 low vegetation' : 3, '4 medium vegetation' : 4, '5 high vegetation' : 5,
                   '6 building' : 6, '7 noise' : 7, '8 model key point' : 8,
                   '9 water' : 9, '10 rail' : 10, '11 road surface' : 11,
                   '12 bridge deck' : 12, '13 wire guard' : 13, '14 wire conductor': 14,
                   '15 transmission tower' : 15, '16 wire connector' : 16, '40 bathymetric point (e.g. seafloor or riverbed)' : 40,
                   '41 water surface' : 41, '42 derived water surface' : 42, '43 underwater object' : 43,
                   '44 IHO S-57 object' : 44, '45 volume backscatter' : 45 }

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

    def ClassColoring(self):
        if self.firstSection:
            if self.HightColor.isChecked():
                self.HightColor.setChecked(False)

            if self.ClassColor.isChecked():
                self.Section.currentColor = 1
                self.Section.dataRefresh()

    def HightColoring(self):
        if self.ClassColor.isChecked():
            self.ClassColor.setChecked(False)

        if self.HightColor.isChecked():
            self.Section.currentColor = 2
            self.Section.dataRefresh()

    def showMessages(self):
        self.model.clear()

        self.model.appendRow(QStandardItem(r'Loaded: {} Points'.format(self.ptsLoad)))
        self.model.appendRow(QStandardItem(r'Classified: {} Points'.format(self.ptsClass)))
        self.model.appendRow(QStandardItem(r'Unclassified: {} Points'.format(self.ptsNoClass)))

        if self.knnTree.isChecked():
            self.model.appendRow(QStandardItem(r'Class predicted: {} Points'.format(self.knnPts)))

    def save_file(self):
        self.changeAttributes()
        self.Section.deleteReset()
        self.PathToFile.setEnabled(True)
        self.PathToAxisShp.setEnabled(True)

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = ClassificationTool()
    win.show()
    sys.exit(app.exec_())