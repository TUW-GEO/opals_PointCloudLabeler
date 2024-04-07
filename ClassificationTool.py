import numpy
from opals import Import, Grid, Shade, pyDM, Info
from PyQt5 import QtWidgets,uic
from PyQt5.QtGui import *
import os
import opals
import numpy as np
import math
import copy
from sortedcontainers import SortedDict

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


class MovingPolygon():
    def __init__(self,linestring,pos):
        self.linestring = linestring
        self.pos = pos
        self.current_length = 0
        self.total_stationing = 0

    def segment_length(self, point1, point2):
        return ((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2) ** 0.5

    def get_stationing_at_point(self,point):
        self.total_stationing = 0
        for i in range(len(self.linestring) - 1):
            length = self.segment_length(self.linestring[i], self.linestring[i + 1])
            segment_vector = [self.linestring[i + 1][0] - self.linestring[i][0], self.linestring[i + 1][1] - self.linestring[i][1]]
            pos_vector = [point[0] - self.linestring[i][0], point[1] - self.linestring[i][1]]
            dot_product = pos_vector[0] * segment_vector[0] + pos_vector[1] * segment_vector[1]
            if dot_product <= 0:
                return self.total_stationing
            self.total_stationing += length
        return self.total_stationing

    def checkPosition(self):
        stationings = SortedDict()
        self.total_stationing = 0

        for i in range(len(self.linestring) - 1):
            length = self.segment_length(self.linestring[i], self.linestring[i + 1])
            self.total_stationing += length
            stationings[self.total_stationing] = (self.linestring[i], self.linestring[i + 1])

        index = stationings.bisect_left(self.get_stationing_at_point(self.pos))

        segment_start, segment_end = stationings.peekitem(index)[1]
        return(segment_start,segment_end)

class ClassificationTool(QtWidgets.QMainWindow):
    def __init__(self):
        super(ClassificationTool, self).__init__()
        uic.loadUi('ClassificationTool.ui', self)

        self.Section.setMouseTracking(True)
        self.linestring = None
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
        self.manuallyClassified = '_manuallyClassified'
        self.classificationData = CLASSIFICATION_DATA
        self.classHisto = {}  # class histogram of the current section


        #self.PathToFile.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21.laz" )
        #self.PathToAxisShp.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21_axis_transformed.shp")
        #self.PathToFile.setText(r"C:\swdvlp64_cmake\opals\distro\demo\strip21.laz")
        #self.PathToAxisShp.setText(r"C:\swdvlp64_cmake\opals\distro\demo\strip21_axis.shp")

        #Test data
        self.PathToFile.setText(r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\Test_Data\Fluss_110736_0_loos_528600_533980_Klassifiziert.las")
        self.PathToAxisShp.setText(r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\Test_Data\Fluss_110736_0_loos_528600_533980_Klassifiziert_axis.shp")

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

    def initUI(self):
        #Build ComboBox:
        self.refeshClassComboBox()

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

        self.Section.setClassifcationData(self.classificationData)

    def load_pointcloud(self):
        path = str(self.PathToFile.text()).strip()
        os.chdir(os.path.dirname(os.path.abspath(path)))

        # get the filname (jo, os.path funktionalität verwennden)
        #data = path.split('\\')
        #data = data[len(data) - 1]
        #filename = data.split('.')
        #name = filename[0]
        _, data = os.path.split(path)
        name, _ = os.path.splitext(data)

        odm_name = name + '.odm'
        grid_name = name + '_z.tif'
        shd_name = name + '_shd.tif'

        #import into odm if needed
        if os.path.isfile(odm_name) == False:
            Import.Import(inFile=data, outFile=odm_name).run()

        #Check if odm is in tiling modus (jo: spielt das eine rolle, ob der odm im tiling mode ist? sollte jedenfalls nicht sein)
        inf = Info.Info(inFile=odm_name)
        inf.run()
        #idx_stat = inf.statistic[0].getIndices()
        idx_stat = inf.statistic.getIndices()

        for i in idx_stat:
            node = i.getCountNode()

        #if node == 0:
        #    # jo: spielt das eine rolle, ob der odm im tiling mode ist? sollte nicht der fall sein
        #    Import.Import(inFile=data, tilePointCount=50000, outFile=odm_name).run()

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
        #data = axis.split('\\')
        #file = data[len(data)-1]
        # jo, warum nicht einfach absoluten pfad verwenden? gegebenfalls os.path funktionalität verwennden
        _, file = os.path.split(axis)
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

    def Direction(self, p1, p2):
        p1 = np.array(p1).reshape(1, 2)
        p2 = np.array(p2).reshape(1, 2)
        p = p2 - p1
        p = p / math.sqrt(p[0, 0] ** 2 + p[0, 1] ** 2)
        self.direction = p

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
        result = pyDM.NumpyConverter.searchPoint(self.odm, polygon, self.layout2, withCoordinates=True, noDataObj=np.nan)
        self.result = result

        self.checkClassification = result['Classification'].copy()
        self.result[self.manuallyClassified] = self.result['Classification'] != 0

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
        if not self.linestring:
            return

        self.along = float(self.along_section.text().strip())
        self.across = float(self.across_section.text().strip())
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
        type, inDM = lf2.addColumn(dm, 'Id', True);assert inDM == True
        type, inDM = lf2.addColumn(dm, 'Classification', True); assert inDM == True
        type, inDM = lf2.addColumn(dm, self.manuallyClassified, True, pyDM.ColumnType.bool_)  # add atribute for knn

        self.layout2 = lf2.getLayout()

        self.Direction(self.begin, self.end)
        self.polygon()

    def ptsInSection(self):
        self.Section.setData(self.result)
        coords1 = [self.result["x"][0], self.result["y"][0], self.result["z"][0]]
        coords2 = [coords1[0] + 10., coords1[1] + 10., coords1[2] + 10.]
        self.Section.setStretchAxis(coords1, coords2)

    def viewFirstSection(self):
        self.load_axis()
        checkPos = MovingPolygon(self.segment, self.linestring[0]).checkPosition()
        self.begin, self.end = checkPos[0], checkPos[1]
        self.createPolygon()
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

    def changeAttributes(self):
        if np.array_equal(self.result['Classification'],self.checkClassification) == False:
            self.setObj = {}
            self.setObj['Id'] = self.result['Id']
            self.setObj['Classification'] = self.result['Classification']
            self.setObj[self.manuallyClassified] = self.result[self.manuallyClassified]
            pyDM.NumpyConverter.setById(self.setObj, self.odm, self.layout2)
            self.odm.save()

    def knn(self):
        comp = copy.deepcopy(self.result)

        kdtree = pyDM.PointIndexLeaf(pyDM.IndexType.kdtree,2,True)

        for idx in range(len(self.knnSection['x'])):
            kdtree.addPoint(pyDM.Point(self.knnSection['x'][idx],self.knnSection['y'][idx],self.knnSection['z'][idx]))

        #for idx in range(len(self.setObj['x'])):
         #   kdtree.addPoint(pyDM.Point(self.setObj['x'][idx], self.setObj['y'][idx], self.setObj['z'][idx]))

        for idx in range(len(self.result['x'])):
            if not self.result[self.manuallyClassified][idx]:
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
        pos = [0,0]
        self.changeAttributes()
        self.knnSection = copy.deepcopy(self.result)

        for i in range(len(self.begin)):
            pos[i] = self.begin[i] + ((self.along * (1 - self.overlap)) * self.direction[0, i])

        checkPos = MovingPolygon(self.linestring,pos).checkPosition()

        #if self.counter == (len(self.linestring) - 1) or self.counter < 0:
         #   QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, "Error occured", "End of Polyline! No more points available.").exec_()
        #else:

        self.Direction(checkPos[0], checkPos[1])

        for i in range(len(self.begin)):
            self.begin[i] = self.begin[i] + ((self.along * (1 - self.overlap)) * self.direction[0, i])

        self.polygon()

        if self.knnTree.isChecked():
            self.knn()

        self.ptsInSection()
        self.Section.dataRefresh()
        self.showMessages()

    def previousSection(self):
        pos = [0, 0]
        self.changeAttributes()

        for i in range(len(self.begin)):
            pos[i] = self.begin[i] - ((self.along * (1 - self.overlap)) * self.direction[0, i])

        checkPos = MovingPolygon(self.linestring, pos).checkPosition()

        #if self.counter == (len(self.linestring) - 1) or self.counter < 0:
         #   QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, "Error occured", "Begin of Polyline! No more points available.").exec_()

        #else:
        self.Direction(checkPos[0], checkPos[1])

        for i in range(len(self.begin)):
            self.begin[i] = self.begin[i] - ((self.along * (1 - self.overlap)) * self.direction[0, i])

        self.polygon()
        self.ptsInSection()
        self.Section.dataRefresh()
        self.showMessages()

    def PointsClassification(self):
        for key, value in self.classificationData.items():
            if value[0] == str(self.ClassList.currentText()):
                self.Section.currentClass = key

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
        self.model.appendRow(QStandardItem(r'Class histogram: {}'.format(self.classHisto)))


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