import numpy
from opals import Import, Grid, Shade, pyDM, Info
from PyQt5 import QtWidgets,uic, QtCore
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QFileDialog, QApplication
import os
import opals
import numpy as np
import math
import copy
from sortedcontainers import SortedDict
from StationUtilities import StationPolyline2D, StationCubicSpline2D

# predefined classication dictionary, mapping class ids to class lables and colors
CLASSIFICATION_DATA = {0: ['0 unclassified', [210, 210, 210]],
                       1: ['1 undefined', [180, 180, 180]],
                       2: ['2 ground', [135, 70, 10]],
                       3: ['3 low vegetation', [185, 230, 120]],
                       4: ['4 medium vegetation', [145, 200, 0]],
                       5: ['5 high vegetation', [72, 128, 0]],
                       6: ['6 building', [180, 20, 20]],
                       7: ['7 noise', [255, 255, 200]],
                       8: ['8 model key point', [220, 105, 20]],
                       9: ['9 water', [0, 95, 255]],
                       10: ['10 rail', [100, 80, 60]],
                       11: ['11 road surface', [70, 70, 70]],
                       12: ['12 bridge deck', [35, 35, 35]],
                       13: ['13 wire guard', [255, 250, 90]],
                       14: ['14 wire conductor', [255, 220, 0]],
                       15: ['15 transmission tower', [235, 200, 60]],
                       16: ['16 wire connector', [190, 160, 50]],
                       40: ['40 bathymetric point (e.g. seafloor or riverbed)', [180, 180, 95]],
                       41: ['41 water surface', [35, 0, 250]],
                       42: ['42 derived water surface', [40, 220, 240]],
                       43: ['43 underwater object', [140, 80, 160]],
                       44: ['44 IHO S-57 object', [90, 75, 170]],
                       45: ['45 volume backscatter', [60, 130, 130]]}

PREDICTION = {0:'no prediction', 1:'predict next', 2:'predict previous', 3:'always predict'}

class ClassificationTool(QtWidgets.QMainWindow):
    def __init__(self):
        super(ClassificationTool, self).__init__()
        uic.loadUi('PointCloudLabeler.ui', self)

        self.Overview.setStyleSheet("border: 1px solid black;")

        self.Section.setMouseTracking(True)
        self.Overview.setMouseTracking(True)
        self.station_axis = None
        self.current_station = None
        self.min_station = None
        self.max_station = None
        self.odm = None
        self.result = None
        self.direction = None
        self.layout = None
        self.layout2 = None
        self.rot_camera = None
        self.along = None
        self.across = None
        self.overlap = None
        self.begin = None
        self.counter = 0
        self.lineend = None
        self.forwards = False
        self.backwards = False
        self.hightcolor = False
        self.Point = False
        self.FalseAxis = False
        self.Rectangle = False
        self.firstSection = None
        self.ptsLoad = 0
        self.ptsClass = 0
        self.ptsNoClass = 0
        self.knnPts = 0
        self.manuallyClassified = '_manuallyClassified'
        self.classificationData = CLASSIFICATION_DATA
        self.prediction = PREDICTION
        self.classHisto = {}  # class histogram of the current section
        self.axis = []
        self.currrentaxisID = None


        #Test data
        #self.PathToFile.setText(r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\Test_Data\Fluss_110736_0_loos_528600_533980_Klassifiziert.las")
        #self.PathToAxisShp.setText(r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\Test_Data\Fluss_110736_0_loos_528600_533980_Klassifiziert_axis.shp")

        #self.PathToFile.setText(r"X:\students\fmeixner\PointCloudLabeler\Data\Fluss_110736_0_loos_528600_533980_Klassifiziert.las")
        #self.PathToAxisShp.setText(r"X:\students\fmeixner\PointCloudLabeler\Data\Fluss_110736_0_loos_528600_533980_Klassifiziert_axis.shp")

        # Test data jo
        #self.PathToFile.setText(r"C:\projects\bugs\felix_pydm_290224\Fluss_110736_0_loos_528600_533980_Klassifiziert.las")
        #self.PathToFile.setText(r"C:\projects\bugs\felix_pydm_290224\test.odm")
        #self.PathToAxisShp.setText(r"C:\projects\bugs\felix_pydm_290224\Fluss_110736_0_loos_528600_533980_Klassifiziert_axis.shp")

        #self.PathToFile.setText(r"C:\Users\felix\Documents\Test_Data\Fluss_110736_0_loos_528600_533980_Klassifiziert.las")
        #self.PathToAxisShp.setText(r"C:\Users\felix\Documents\Test_Data\Fluss_110736_0_loos_528600_533980_Klassifiziert_axis.shp")

        self.initUI()


    def refeshClassComboBox(self):
        #first remove all entries from combo box
        currSelection = self.ClassList.currentText()

        self.ClassList.clear()

        #now fill combo box
        for key, val in self.classificationData.items():
            pixmap = QPixmap(100,100)
            pixmap.fill((QColor(val[1][0],val[1][1],val[1][2])))
            icon = QIcon(pixmap)
            self.ClassList.addItem(icon,val[0],QColor(val[1][0],val[1][1],val[1][2]))

        # restore current selection if necessary
        if currSelection != "":
            self.ClassList.setCurrentText(currSelection)

    def PredictComboBox(self):
        currentSelection = self.knnPrediction.currentText()

        for key, val in self.prediction.items():
            self.knnPrediction.addItem(val)

        if currentSelection != "":
            self.knnPrediction.setCurrentText(currentSelection)

    def initUI(self):
        #Build ComboBox:
        self.refeshClassComboBox()
        self.PredictComboBox()

        self.PathToAxisShp.setEnabled(False)

        self.LoadButton.pressed.connect(self.load_pointcloud)
        self.LoadAxis.pressed.connect(self.viewFirstSection)

        self.Next.pressed.connect(self.nextSection)
        self.Previous.pressed.connect(self.previousSection)

        self.HightColor.clicked.connect(self.HightColoring)
        self.ClassColor.clicked.connect(self.ClassColoring)

        self.OrthoView.clicked.connect(self.setOrthoView)

        self.PointSelection.clicked.connect(self.SelectPoint)
        self.RectangleSelection.clicked.connect(self.SelectRectangle)

        self.ClassList.currentTextChanged.connect(self.PointsClassification)
        self.Reset.clicked.connect(self.resetSection)

        self.PointSize.valueChanged.connect(self.Section.setPointSize)
        self.LineSize.valueChanged.connect(self.Overview.changeAxisWidth)

        self.StatusMessageModel = QStandardItemModel()
        self.StatusMessages.setModel(self.StatusMessageModel)

        self.Overview.setAxisManagment(self.AxisView)

        self.Save.pressed.connect(self.save_file)

        self.Section.setClassifcationData(self.classificationData)

        self.DrawAxis.stateChanged.connect(self.DigitalAxis)

        self.Overview.polylinePicked.connect(self.handlePickedPolyline)


    def load_pointcloud(self, path=None):
       #path = str(self.PathToFile.text()).strip()

        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Select point cloud file", "",
                                                  "OPALS Datamanager (*.odm);;LAS Files (*.las *laz);;All Files (*.*)")
        if path == "":
            return
        self.PathToFile.setText(os.path.abspath(path))
        os.chdir(os.path.dirname(os.path.abspath(path)))

        # get the filename
        _, data = os.path.split(path)
        name, _ = os.path.splitext(data)

        try:
            odm_name = name + '.odm'
            grid_name = name + '_z.tif'
            shd_name = name + '_shd.tif'

             #import into odm if needed
            if os.path.isfile(odm_name) == False:
                Import.Import(inFile=data, outFile=odm_name).run()

            #Extract the header of the odm to get the point density
            self.ptsDensity = pyDM.Datamanager.getHeaderODM(odm_name).estimatedPointDensity()

            #create shading
            if os.path.isfile(grid_name) == False:
                Grid.Grid(inFile=odm_name, outFile=grid_name, filter='echo[last]',
                      interpolation=opals.Types.GridInterpolator.movingPlanes, gridSize=0.5).run()

            if os.path.isfile(shd_name) == False:
                Shade.Shade(inFile=grid_name, outFile=shd_name).run()

            # load the opals datamanager in read and write
            self.odm = pyDM.Datamanager.load(odm_name, readOnly=False, threadSafety=False)

            #if not pyDM.Datamanager.existsODM(name + '_axis.odm'):
            axis_odm = pyDM.Datamanager.create(name + "_axis.odm", False)
            self.Overview.setAxisODM(axis_odm)

            self.Overview.setShading(shd_name)
            self.Overview.dataRefresh()

            self.PathToFile.setEnabled(False)
            self.PathToAxisShp.setEnabled(True)

        except Exception as e:
            QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "Warning",
                                  "Wrong file type! \nPlease choose a file with the right type. ").exec_()

    def load_axis(self,File=True):
        if File:
            axis = str(self.PathToAxisShp.text()).strip()
            #if axis == "":
            axis, _ = QFileDialog.getOpenFileName(self, "Select axis file", "",
                                                      "OPALS Datamanager (*.odm);;Shape File (*.shp);;All Files (*.*)")
            if axis == "":
                return
            self.PathToAxisShp.setText(os.path.abspath(axis))

            _, data = os.path.split(axis)
            name, _ = os.path.splitext(data)

            if _ != '.shp' and _ != '.odm':
                QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "Warning!",
                                      "Wrong file type! \nFile has to be a shape-file.").exec_()
                self.FalseAxis = True
            elif _ == '.shp':
                self.FalseAxis = False
                imp = pyDM.Import.create(axis, pyDM.DataFormat.auto)

                pts = []
                self.lines = []

                for obj in imp:
                    self.lines.append([obj])
                    # loop over points
                    if len(self.lines) == 1:
                        for i in range(obj.sizePoint()):
                            pt = obj[i]
                            pts.append([pt.x, pt.y])
                self.Overview.setAxis(self.lines)

            # elif _ == '.odm':
            #     imp = pyDM.Import.create(axis, pyDM.DataFormat.auto)
            #
            #     lf = pyDM.AddInfoLayoutFactory()
            #     lf.addColumn(pyDM.ColumnSemantic.Id)
            #     layout = lf.getLayout()
            #
            #     ids = []
            #
            #     for obj in axis.geometries(layout):
            #         ids.append(obj.info().get(0))
            #     i=0

        else:
            pts = self.axis

        self.polygonSize()

        # maximal extrapolation distance at start and end of axis
        extrapolation_distance = float(self.along_section.text().strip())*5

        if len(pts) == 1:
            self.station_axis = StationPolyline2D(pts)
        else:
           # self.station_axis = StationCubicSpline2D(pts)
            self.station_axis = StationPolyline2D(pts)
        #
        self.current_station = 0
        self.min_station = self.station_axis.min_station()-extrapolation_distance   # min allowed station value
        self.max_station = self.station_axis.max_station()+extrapolation_distance   # max allowed station value
        #
        self.PathToAxisShp.setEnabled(False)
        #
        # self.Overview.setAxis(self.station_axis.vertices)
        self.Overview.drawAxis(True)

    def polygon(self):
        def poly_points(start, vector, length, width):
            start_point = np.array([start]).reshape(1, 2)
            rot_vector = np.array([-vector[1], vector[0]]).reshape(1, 2)
            vector = np.array([vector[0], vector[1]]).reshape(1, 2)
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
        #self.Overview.dataRefresh()
        self.Overview.drawSection()

        # extract the points inside of the polygon
        try:
            result = pyDM.NumpyConverter.searchPoint(self.odm, polygon, self.layout2, withCoordinates=True, noDataObj=0)
        except Exception as e:
            # this occurs if no points where found
            result = {}
            result['Classification'] = np.empty(shape=(0, 0))
            result['x'] = np.empty(shape=(0, 0))
            result['y'] = np.empty(shape=(0, 0))
            result['z'] = np.empty(shape=(0, 0))
        self.result = result

        self.checkClassification = result['Classification'].copy()

        self.ptsLoad = len(self.result['x'])
        # build histogram of class ids
        classes, counts = numpy.unique(self.result['Classification'], return_counts=True)
        self.classHisto = {}
        for cl, cn in zip(classes, counts):
            self.classHisto[cl] = cn
        self.ptsNoClass = 0 if 0 not in self.classHisto else self.classHisto[0]
        self.ptsClass = self.ptsLoad - self.ptsNoClass

        # add new classes to self.classificationData if needed
        classesAdded = False
        for classId in self.classHisto:
            if classId in self.classificationData:
                continue
            c = [np.random.random() for i in range(3)]
            self.classificationData[classId] = [f'{classId} undefined class_{classId}',[int(c[i]*255) for i in range(3)]]
            classesAdded = True

        # update class selection combo box if needed
        if classesAdded:
            self.refeshClassComboBox()

    def createPolygon(self):
        if not self.odm:
            return
        if not self.station_axis:
            return

        self.overlap = (float(self.overlap_section.text().strip()))/100

        dm = self.odm

        lf = pyDM.AddInfoLayoutFactory()
        type, inDM = lf.addColumn(dm, 'Id', True); assert  inDM == True
        type, inDM = lf.addColumn(dm, 'GPSTime', True); assert inDM == True
        type, inDM = lf.addColumn(dm, 'Amplitude', True); assert inDM == True
        type, inDM = lf.addColumn(dm, 'Classification', True); assert inDM == True
        type, inDM = lf.addColumn(dm,self.manuallyClassified,True,pyDM.ColumnType.bool_) #add atribute for knn

        self.layout = lf.getLayout()

        lf2 = pyDM.AddInfoLayoutFactory()
        type, inDM = lf2.addColumn(dm, 'Id', True); assert inDM == True
        type, inDM = lf2.addColumn(dm, 'Classification', True); assert inDM == True
        type, inDM = lf2.addColumn(dm, self.manuallyClassified, True, pyDM.ColumnType.uint8)
        self.layout2 = lf2.getLayout()

        self.begin, self.direction = self.station_axis.get_point_and_direction(self.current_station)
        self.polygon()

    def polygonSize(self):
        meanPtDistance = 1 / np.sqrt(self.ptsDensity)

        self.across = 1000 * meanPtDistance

        if self.across > 30:
            self.across = 30.0
        else:
            self.across = round(1000 * meanPtDistance,2)

        self.along = round(5 * meanPtDistance,2)

        self.along_section.setText(str(self.along))
        self.across_section.setText(str(self.across))

    def ptsInSection(self):
        self.Section.setData(self.result)
        if len(self.result["x"]) > 2:
            coords1 = [self.result["x"][0], self.result["y"][0], self.result["z"][0]]
            coords2 = [coords1[0] + 10., coords1[1] + 10., coords1[2] + 10.]
            self.Section.setStretchAxis(coords1, coords2)

    def handlePickedPolyline(self, polyline):
        # Process the received polyline
        self.axis = []
        print("Received polyline:", polyline)
        for idx, l in enumerate(polyline):
            for idx, part in enumerate(l.parts()):
                for p in part.points():
                    self.axis.append([p.x,p.y])
        self.Overview.axis = self.axis
        self.viewFirstSection(False)

    def viewFirstSection(self,File=True):
        if not self.odm:
            return

        if not File:
            self.load_axis(File=File)
        else:
            self.load_axis()

        if self.FalseAxis:
            return

        self.createPolygon()
        self.ptsInSection()
        self.Section.setOrthoView(self.rot_camera)
        self.Section.dataRefresh()
        self.firstSection = True
        self.showMessages()

    def overlapPolygons(self):
        # self.disableButtonFunctions()
        if not self.station_axis:
            return

        self.overlap = float(self.overlap_section.text().strip())/100

    def changePolygonSize(self):
        if not self.station_axis:
            return

        self.along = float(self.along_section.text().strip())
        self.across = float(self.across_section.text().strip())

        self.polygon()
        self.ptsInSection()
        self.Section.dataRefresh()
        self.showMessages()

    def setOrthoView(self):
        self.Section.setOrthoView(self.rot_camera)

    def DigitalAxis(self):
        if self.DrawAxis.isChecked():
            self.Overview.Axis = True
        else:
            self.Overview.Axis = False

    def changeAttributes(self):
        if np.array_equal(self.result['Classification'],self.checkClassification) == False:
            self.setObj = {}
            self.setObj['Id'] = self.result['Id']
            self.setObj['Classification'] = self.result['Classification']
            self.setObj[self.manuallyClassified] = self.result[self.manuallyClassified]
            pyDM.NumpyConverter.setById(self.setObj, self.odm, self.layout2)
            self.odm.save()

    def knn(self):
        # create 3d kdtree for nearest neighbour selection
        kdtree = pyDM.PointIndexLeaf(pyDM.IndexType.kdtree, 3, True)
        # settings for nn selection
        nnCount = 1
        searchMode = pyDM.SelectionMode.nearest
        maxSearchDist = -1

        for idx in range(len(self.knnSection['x'])):
            classid = self.knnSection['Classification'][idx]
            pt = pyDM.Point(self.knnSection['x'][idx],self.knnSection['y'][idx],self.knnSection['z'][idx])
            pt.setAddInfoView(self.layout2, False)
            pt.info().set(1,int(classid))
            kdtree.addPoint(pt)

        assigned_pts = 0
        for idx in range(len(self.result['x'])):
            if self.result['Classification'][idx] == 0:
                searchPt = pyDM.Point(self.result['x'][idx],self.result['y'][idx],self.result['z'][idx])
                pts = kdtree.searchPoint(nnCount,searchPt,maxSearchDist,searchMode)

                if pts != []:
                    classid = pts[0].info().get(1)
                    self.result['Classification'][idx] = classid
                    self.result[self.manuallyClassified][idx] = 2
                    assigned_pts += 1

        self.knnPts = assigned_pts
        self.ptsNoClass = sum(self.result['Classification'] > 0)
        self.ptsNoClass = sum(self.result['Classification'] == 0)
        # update histogram
        classes, counts = numpy.unique(self.result['Classification'], return_counts=True)
        self.classHisto = {}
        for cl, cn in zip(classes, counts):
            self.classHisto[cl] = cn

    def nextSection(self):
        if not self.station_axis:
            return

        ds = self.along * (1 - self.overlap)
        new_station = self.current_station + ds
        if new_station + ds > self.max_station:
            new_station = self.max_station-ds
        if new_station == self.current_station:
            return

        self.changeAttributes()
        self.knnSection = copy.deepcopy(self.result)

        self.current_station = new_station
        self.begin, self.direction = self.station_axis.get_point_and_direction(self.current_station)
        self.polygon()

        if self.knnPrediction.currentText() == 'predict next' or self.knnPrediction.currentText() == 'always predict':
            self.knn()


        self.ptsInSection()
        self.Section.dataRefresh()
        self.showMessages()

    def previousSection(self):
        if not self.station_axis:
            return

        ds = self.along * (1 - self.overlap)
        new_station = self.current_station - ds
        if new_station < self.min_station:
            new_station = self.min_station
        if new_station == self.current_station:
            return

        self.changeAttributes()
        self.knnSection = copy.deepcopy(self.result)

        self.current_station = new_station
        self.begin, self.direction = self.station_axis.get_point_and_direction(self.current_station)
        self.polygon()

        if self.knnPrediction.currentText() == 'predict previous' or self.knnPrediction.currentText() == 'always predict':
            self.knn()

        self.ptsInSection()
        self.Section.dataRefresh()
        self.showMessages()

    def PointsClassification(self):
        for key, value in self.classificationData.items():
            if value[0] == str(self.ClassList.currentText()):
                self.Section.currentClass = key

    def SelectPoint(self):
        if not self.station_axis:
            return

        if self.RectangleSelection.isChecked():
            self.RectangleSelection.setChecked(False)
            self.Section.SelectRectangle = False

        if self.PointSelection.isChecked():
            self.PointsClassification()
            self.Section.SelectPoint = True

        elif self.PointSelection.isChecked() == False:
            self.Section.SelectPoint = False

    def SelectRectangle(self):
        if not self.station_axis:
            return

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
        self.StatusMessageModel.clear()
        self.StatusMessageModel.appendRow(QStandardItem(r'Current station: {:.2f} - {:.2f}'.format(self.current_station,
                                                                                                   self.current_station + self.along)))
        self.StatusMessageModel.appendRow(QStandardItem(r'Loaded: {} Points'.format(self.ptsLoad)))
        self.StatusMessageModel.appendRow(QStandardItem(r'Classified: {} Points'.format(self.ptsClass)))
        self.StatusMessageModel.appendRow(QStandardItem(r'Unclassified: {} Points'.format(self.ptsNoClass)))
        self.StatusMessageModel.appendRow(QStandardItem(r'Class histogram: {}'.format(self.classHisto)))


        if self.knnPrediction.currentText() == ('predict previous' or 'always predict' or 'predict next'):
            self.StatusMessageModel.appendRow(QStandardItem(r'Class predicted: {} Points'.format(self.knnPts)))

    def resetSection(self):
        if not self.station_axis:
            return
        self.Section.Reset()

    def save_file(self):
        if not self.station_axis:
            return

        self.changeAttributes()
        self.Section.deleteReset()
        self.PathToFile.setEnabled(True)
        self.PathToAxisShp.setEnabled(True)

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Return or event.key() == QtCore.Qt.Key_Tab:
            self.changePolygonSize()

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = ClassificationTool()
    if len(sys.argv) > 1:
        win.load_pointcloud(sys.argv[1])
    win.show()
    sys.exit(app.exec_())