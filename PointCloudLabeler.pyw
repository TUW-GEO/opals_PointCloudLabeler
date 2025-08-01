try:
    import os
    import numpy
    from opals import Import, Grid, Shade, pyDM
    from PyQt5 import QtWidgets,uic, QtCore
    from PyQt5.QtGui import *
    from PyQt5.QtCore import QThreadPool, QMutex, QRunnable, Qt
    from PyQt5.QtWidgets import QFileDialog, QDialog, QLineEdit, QPushButton, QFormLayout, QCheckBox, QHBoxLayout, QShortcut, QTableWidget, QTableWidgetItem
    from sklearn.neighbors import KDTree
except ModuleNotFoundError as e:    
    print(f"Unable to import necessary libraries (Details: {e})")
    print(f"Make sure that necessary requirements have been installed by calling\n")
    print(f"pip install -r requirements.txt")
    print(f"\nin directory '{os.path.abspath(os.path.split(__file__)[0])}'")
    exit(-1)
import opals
import numpy as np
import copy
from StationUtilities import StationCubicSpline2D
from AxisManagment import AxisManagement
from glPointCloud import COLOR_MODE_ATTR, COLOR_MODE_CLASS
from Geometry import Point3D, Matrix4x4
from ProgressControl import Control, ProgressEmitter
import argparse
import time

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

PREDICTION_MODEL = {0: '2d', 1:'3d'}


class GenerateDialog(QDialog):
    preview_clicked = QtCore.pyqtSignal()

    def __init__(self, parent=None, defaultDistance='0'):
        super().__init__(parent)
        self.defaultDistance = defaultDistance
        self.initUI()
        QtCore.QTimer.singleShot(0, self.handle_preview)
        self.finished.connect(self._close)

    def initUI(self):
        self.setWindowTitle('Axis Generation - Parameter Setting')

        self.rotation = QLineEdit(self)
        self.rotation.setText('0')
        self.rotation.setFixedSize(50, 25)

        self.rotation_plus_button = QPushButton('+', self)
        self.rotation_plus_button.setFixedSize(30, 25)
        self.rotation_plus_button.clicked.connect(self.increase_rotation)
        self.rotation_plus_button.setFocusPolicy(QtCore.Qt.NoFocus)

        self.rotation_minus_button = QPushButton('-', self)
        self.rotation_minus_button.setFixedSize(30, 25)
        self.rotation_minus_button.clicked.connect(self.decrease_rotation)
        self.rotation_minus_button.setFocusPolicy(QtCore.Qt.NoFocus)

        rotation_layout = QHBoxLayout()
        rotation_layout.addWidget(self.rotation)
        rotation_layout.addWidget(self.rotation_plus_button)
        rotation_layout.addWidget(self.rotation_minus_button)

        self.distance = QLineEdit(self)
        self.distance.setText(self.defaultDistance)
        self.distance.setFixedSize(50, 25)

        self.shpFileExport = QCheckBox("Export to shp-File", self)
        self.shpFileExport.setChecked(False)

        self.rotation_plus_button.clicked.connect(self.handle_preview)
        self.rotation_minus_button.clicked.connect(self.handle_preview)

        self.ok_button = QPushButton('OK', self)
        self.ok_button.clicked.connect(self.accept)
        #self.ok_button.setDefault(True)
        self.ok_button.setFocusPolicy(QtCore.Qt.NoFocus)

        form_layout = QFormLayout()
        form_layout.addRow('Rotation Angle [deg]:', rotation_layout)
        form_layout.addRow('Distance between the Axis:', self.distance)
        form_layout.addRow(self.shpFileExport)
        form_layout.addRow(self.ok_button)

        self.setLayout(form_layout)

    def rotationButtons(self):
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.rotation_minus_button)
        button_layout.addWidget(self.rotation_plus_button)
        return button_layout

    def handle_preview(self):
        self.preview_clicked.emit()

    def _close(self):
        self.parent().closeDialog(self)

    def increase_rotation(self):
        current_value = float(self.rotation.text() or 0)
        self.rotation.setText(str(current_value + 1))

    def decrease_rotation(self):
        current_value = float(self.rotation.text() or 0)
        self.rotation.setText(str(current_value - 1))
    def _close(self):
        self.parent().closeDialog(self)
    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Return:
            self.handle_preview()

class Thread(QtCore.QThread):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def run(self):
        self.parent.checkProgress()
        self.parent.Overview.dataRefresh(show_progress=True)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.fn(*self.args, **self.kwargs)
        except e:
            print(e)

class BatchWorker(QRunnable):
    def __init__(self, fn, stations):
        super().__init__()

        self.fn = fn
        self.stations = stations

    def run(self):
        for st in self.stations:
            try:
                self.fn(st)
            except e:
                print(e)

class ClassificationTool(QtWidgets.QMainWindow):
    def __init__(self):
        super(ClassificationTool, self).__init__()
        root_dir = os.path.split(__file__)[0]
        uic.loadUi(os.path.join(root_dir, 'PointCloudLabeler.ui'), self)

        self.setWindowTitle('OPALS PointCloudLabeler')

        #"D:\users\fmeixner\PointCloudLabeler\Data\Fluss_110736_0_loos_528600_533980_Klassifiziert.odm"
        self.Overview.setStyleSheet("border: 1px solid black; background-color: rgb(255, 255, 255);")

        self.Section.setMouseTracking(True)
        self.Overview.setMouseTracking(True)
        self.station_axis = None
        self.current_station = None
        self.min_station = None
        self.max_station = None
        self.odm = None
        self.result = None
        self.direction = None
        self.layout2 = None
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
        self.meanPtDistance = None
        self.ptsLoad = 0
        self.ptsClass = 0
        self.ptsNoClass = 0
        self.knnPts = 0
        self.manuallyClassified = '_manuallyClassified'
        self.classificationData = CLASSIFICATION_DATA
        self.prediction = PREDICTION
        self.prediction_model = PREDICTION_MODEL
        self.classHisto = {}  # class histogram of the current section
        self.axis_manager = None
        self.axis_pts = None
        self.currrentaxisID = None
        self.shortcuts_set = []
        self.shortcuts = []
        self.shortcutBindings = {}
        self.queuelist = []
        self.bufferdict = {}
        self.threadpool = QThreadPool()
        self.mutex = QMutex()
        self.mutexQL = QMutex()
        self.knnSection = None
        self.classesToPredict = {0, 1, 7}

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

    def PredictModelComboBox(self):
        currentSelection = self.predictionModel.currentText()

        for key, val in self.prediction_model.items():
            self.predictionModel.addItem(val)

        if currentSelection != "":
            self.predictionModel.setCurrentText(currentSelection)

    def setShortcutBinding(self, key, currentText):
        self.shortcutBindings[key] = currentText
        self.showShortcutBindings()

    def execShortcutBinding(self, key):
        if key in self.shortcutBindings.keys():
            self.ClassList.setCurrentText(self.shortcutBindings[key])

    def handleItemChangedClassCheckboxes(self):
        for i, key in enumerate(self.classificationData.keys()):
            item = self.tableWidgetClassesCheckboxes.item(i, 0)
            state = item.checkState()
            if state == 2:
                self.classesToPredict.add(key)
            else:
                self.classesToPredict.discard(key)
        print(self.classesToPredict)

    def initUI(self):
        #Build ComboBox:
        self.refeshClassComboBox()
        self.PredictComboBox()
        self.PredictModelComboBox()
        self.showProgress.clicked.connect(self.showClassificationProgress)

        self.progressBar.setVisible(False)
        self.progressemitter = ProgressEmitter()
        self.control = Control(self.progressemitter)

        self.progressemitter.progressChanged.connect(self.progressBar.setValue)
        self.progressemitter.stageChanged.connect(lambda text: print(f"Stage: {text}"))

        # create Shortcuts for setting the bindings and the Shortcuts for setting the Class
        for i in range(10):
            key = f'Ctrl+{i}'
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda i=i: self.setShortcutBinding(i, self.ClassList.currentText()) )
            self.shortcuts_set.append(shortcut)

        for i in range(10):
            key = f'Alt+{i}'
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda i=i: self.execShortcutBinding(i) )
            self.shortcuts.append(shortcut)


        ##########
        self.tableWidgetClassesCheckboxes.setRowCount(len(self.classificationData.keys())) 
        self.tableWidgetClassesCheckboxes.setColumnCount(1)
        self.tableWidgetClassesCheckboxes.verticalHeader().setVisible(False)
        self.tableWidgetClassesCheckboxes.horizontalHeader().setVisible(False)
        idx = 0
        for key, value in self.classificationData.items():

            item = QTableWidgetItem('{}'.format(value[0]))
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            if key in self.classesToPredict:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            pixmap = QPixmap(100,100)
            pixmap.fill((QColor(value[1][0],value[1][1],value[1][2])))
            icon = QIcon(pixmap)
            item.setIcon(icon)
            self.tableWidgetClassesCheckboxes.setItem(idx, 0, item)

            idx += 1
        self.tableWidgetClassesCheckboxes.resizeColumnsToContents()

        self.tableWidgetClassesCheckboxes.itemChanged.connect(self.handleItemChangedClassCheckboxes)
        ##########

        self.PathToAxisShp.setEnabled(False)

        self.LoadButton.pressed.connect(self.loadPointcloud)
        self.LoadAxis.pressed.connect(self.clearAxisView)
        self.LoadAxis.pressed.connect(self.viewFirstSection)

        self.Next.pressed.connect(self.nextSection)
        self.Previous.pressed.connect(self.previousSection)

        self.HightColor.clicked.connect(self.HightColoring)
        self.ClassColor.clicked.connect(self.ClassColoring)

        self.OrthoView.clicked.connect(self.setOrthoView)

        self.PointSelection.clicked.connect(self.SelectPoint)
        self.RectangleSelection.clicked.connect(self.SelectRectangle)

        self.ClassList.currentTextChanged.connect(self.WritePointsToglSectionWidget)
        self.ResetPointClasses.clicked.connect(self.resetSection)

        self.PointSize.valueChanged.connect(self.Section.setPointSize)
        self.LineSize.valueChanged.connect(self.Overview.changeLineWidth)

        self.StatusMessageModel = QStandardItemModel()
        self.StatusMessages.setModel(self.StatusMessageModel)

        self.ViewShortcutBindings.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        self.Overview.setAxisList(self.AxisView)
        self.Overview.polylinePicked.connect(self.handlePickedPolyline)
        self.Overview.selectSection.connect(self.selectSection)

        self.Save.pressed.connect(self.saveFile)

        self.Section.setClassifcationData(self.classificationData)

        self.DrawMode.clicked.connect(self.EdditingAxis)
        self.SelectionMode.clicked.connect(self.EdditingAxis)
        self.EditMode.toggled.connect(self.activateEditing)
        
        self.Insert.toggled.connect(self.EditButtonsToggled)
        self.Delete.toggled.connect(self.EditButtonsToggled)
        self.Move.toggled.connect(self.EditButtonsToggled)

        self.Generate.clicked.connect(self.GenerateAxis)

        self.ZoomIn.pressed.connect(self.Overview.zoomIn)
        self.ZoomOut.pressed.connect(self.Overview.zoomOut)
        self.ZoomAll.pressed.connect(self.Overview.zoomOnLayer)

    def showClassificationProgress(self):
        self.thread = Thread(self)
        self.thread.started.connect(self.showProgressProcessing)
        self.thread.finished.connect(self.showProgressDone)
        self.thread.start()

    def showProgressProcessing(self):
        self.showProgress.setText('please wait')
        self.showProgress.setEnabled(False)

    def showProgressDone(self):
        self.showProgress.setText('show progress')
        self.showProgress.setEnabled(True)

    def loadPointcloud(self, path=None):
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
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

            self.file_name = name
            odm_name = name + '.odm'
            grid_name = name + '_z.tif'
            shd_name = name + '_shd.tif'
            axis_odm_name = name + '_axis.odm'

            if os.path.isfile(odm_name) == False:
                self.progressBar.setVisible(True)
                imp = Import.Import(inFile=data, outFile=odm_name)
                imp.set_controlObject(self.control)
                imp.run()
                del imp
                self.progressBar.setVisible(False)


                #Extract the header of the odm to get the point density
            self.ptsDensity = pyDM.Datamanager.getHeaderODM(odm_name).estimatedPointDensity()

                        #create shadin
            if os.path.isfile(shd_name) == False:
                if os.path.isfile(grid_name) == False:
                    self.progressBar.setVisible(True)
                    grd = Grid.Grid(inFile=odm_name, outFile=grid_name, filter='echo[last]',
                    interpolation=opals.Types.GridInterpolator.movingPlanes, gridSize=0.5)
                    grd.set_controlObject(self.control)
                    grd.run()
                    del grd
                    

                self.progressBar.setVisible(True)
                shd = Shade.Shade(inFile=grid_name, outFile=shd_name)
                shd.set_controlObject(self.control)
                shd.run()
                del shd
                self.progressBar.setVisible(False)

                        # load the opals datamanager in read and write
            self.odm = pyDM.Datamanager.load(odm_name, readOnly=False, threadSafety=False)

        except Exception as e:
            QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "Warning",
                                 "Wrong file type! \nPlease choose a file with the right type. ").exec_()

        try:
            if os.path.isfile(axis_odm_name) == False:
                self.axis_manager = AxisManagement(axis_odm_name)
                self.Overview.setAxisManagement(self.axis_manager)
                self.Overview.AxisODMPath = os.path.abspath(axis_odm_name)
            else:
                self.axis_manager = AxisManagement(None)
                self.Overview.setAxisManagement(self.axis_manager)

            self.Overview.setShading(shd_name)
            self.Overview.dataRefresh()
            self.Overview.SelectAxis = True

            self.PathToFile.setEnabled(False)
            self.PathToAxisShp.setEnabled(True)

        except Exception as e:
            return

        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        
        self.clearSectionPreloads()

    def load_axis(self, inFile = '', File=True):
        if self.PathToAxisShp.text() == '':
            self.PathToAxisShp.setText(self.Overview.AxisODMPath)

        pts = None
        if File:
            axis = str(self.PathToAxisShp.text()).strip()

            if not inFile:
                axis_file, _ = QFileDialog.getOpenFileName(self, "Select axis file", "",
                                                         "OPALS Datamanager (*.odm);;Shape File (*.shp);;All Files (*.*)")
            else:
                axis_file = inFile
            if axis_file == "":
                return
            self.PathToAxisShp.setText(os.path.abspath(axis_file))

            _, data = os.path.split(axis_file)
            name, _ = os.path.splitext(data)

            if _ != '.shp' and _ != '.odm':
                QtWidgets.QMessageBox(QtWidgets.QMessageBox.Warning, "Warning!",
                                      "Wrong file type! \nFile has to be a shape-file or a odm-file.").exec_()

            elif _ == '.shp':
                axis_odm_name = name + ".odm"
                self.axis_manager = AxisManagement(axis_odm_name, overwrite=True)
                self.axis_manager.readShpFile(axis_file)
                self.Overview.setAxisManagement(self.axis_manager)

                if not self.axis_manager.empty():
                    pts = self.axis_manager.polyline2linestring(self.axis_manager.axis[0][0])

            elif _ == '.odm':
                self.axis_manager = AxisManagement(axis_file)
                self.Overview.setAxisManagement(self.axis_manager)

                if not self.axis_manager.empty():
                    pts = self.axis_manager.polyline2linestring(self.axis_manager.axis[0][0])

        else:
            pts = self.axis_pts

        if not pts:
            self.FalseAxis = True
            return

        self.FalseAxis = False
        self.polygonSize()

        # maximal extrapolation distance at start and end of axis
        extrapolation_distance = float(self.along_section.text().strip())*5

        self.station_axis = StationCubicSpline2D(pts)

        self.current_station = 0
        self.min_station = self.station_axis.min_station()-extrapolation_distance   # min allowed station value
        self.max_station = self.station_axis.max_station()+extrapolation_distance   # max allowed station value

        self.PathToAxisShp.setEnabled(False)

        self.clearSectionPreloads()

    def getSectionPolygon(self, start, dirvector, length, width):
        start_point = np.array([start]).reshape(1, 2)
        across_vector = np.array([-dirvector[1], dirvector[0]]).reshape(1, 2) # normal vector of direction vector
        dirvector = np.array([dirvector[0], dirvector[1]]).reshape(1, 2)
        p1 = start_point + (across_vector * length / 2)
        p2 = start_point + (-across_vector * length / 2)
        p3 = p2 + (width * dirvector)
        p4 = p1 + (width * dirvector)

        pf = pyDM.PolygonFactory()
        pointlist = []

        for p in (p1, p2, p3, p4):
            x, y = p[0, 0], p[0, 1]
            pf.addPoint(x, y)
            pointlist.append((x, y))

        pf.closePart()
        polygon = pf.getPolygon()
        return polygon, pointlist
    
    def retrievePointArray(self, polygon):
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
        return result
    
    def retrievePointArrayFromStation(self, station):
        print(f'retrievePointArrayFromStation: station: {station}')
        across, along, overlap = self.across, self.along, self.overlap
        begin, direction = self.station_axis.get_point_and_direction(station)
        polygon, pointlist = self.getSectionPolygon(begin, direction, across, along)
        result = self.retrievePointArray(polygon)

        self.mutex.lock()
        print('mutex locked by retrievePAFSation')
        try:
            self.bufferdict[(station, across, along, overlap)] = result
            print(f'points retrieved and saved for {(station, across, along, overlap)}')
        finally:
            self.mutex.unlock()
            print('mutex unlocked by retrievePAFSation')

    def refreshQueue(self):
        self.mutexQL.lock()
        currentQueueList = []
        oldQueueList = self.queuelist
        ds = round(self.along * (1 - self.overlap), 2)
        currst = self.current_station
        minst, maxst = self.min_station, self. max_station
        toCalculate = []

        for i in range(-5, 6):
            if i == 0:
                continue
            st = round(currst + i * ds, 2)
            st = min(max(st, minst), maxst)
            if st == currst:
                continue
            currentQueueList.append(st)
            if st not in oldQueueList:
                toCalculate.append(st)
        
        if toCalculate:
            self.threadpool.start(BatchWorker(fn=self.retrievePointArrayFromStation, stations=toCalculate))

        print(f'old Quelist: {oldQueueList}')
        print(f'new quelist: {currentQueueList}')
        self.queuelist = currentQueueList
        self.mutexQL.unlock()
        self.threadpool.start(Worker(fn=self.delSectionNotInQueuelist))

    def delSectionNotInQueuelist(self):
        self.mutexQL.lock()
        queuelist = self.queuelist
        self.mutexQL.unlock()

        self.mutex.lock()
        print('mutex locked by delsectionnotinqueue')
        ks = list(self.bufferdict.keys())
        print(f'keylist: {ks}')
        for k in ks:
            if k[0] not in queuelist:
                deleted = self.bufferdict.pop(k)
                print(f'bufferdict item deleted for key: {k}')
        self.mutex.unlock()
        print('mutex unlocked by delsectionnotinqueue')

    def clearSectionPreloads(self):
        self.threadpool.clear()
        self.mutex.lock()
        self.bufferdict = {}
        self.mutex.unlock()
        print('bufferdict emptied')
        self.queuelist = []

        

    def initialiseSection(self):
        polygon, pointlist = self.getSectionPolygon(self.begin, self.direction, self.across, self.along)

        self.Overview.setSelectionBox(pointlist)
        self.Overview.section_color = 'red'
        self.Overview.overlap = self.overlap

        self.mutex.lock()
        if (self.current_station, self.across, self.along, self.overlap) in list(self.bufferdict.keys()):
            self.result = self.bufferdict[(self.current_station, self.across, self.along, self.overlap)]
            print(f'\n points loaded from bufferdict for key {(self.current_station, self.across, self.along, self.overlap)}..................... \n')
        else:
            self.result = self.retrievePointArray(polygon)
            print(f'\n points were not in bufferdict for key {(self.current_station, self.across, self.along, self.overlap)} \n')
        self.mutex.unlock()

        self.checkClassification = self.result['Classification'].copy()

        self.ptsLoad = len(self.result['x'])
        # build histogram of class ids
        classes, counts = numpy.unique(self.result['Classification'], return_counts=True)
        self.classHisto = {cl:cn for cl, cn in zip(classes, counts)}
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


    def selectSection(self, x, y):
        self.knnSection = None
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        f = pyDM.PolylineFactory()
        for pt in self.station_axis.vertices:
            f.addPoint(pt[0], pt[1])
        polyline = f.getPolyline()

        basePt, dir, station = self.station_axis.get_point_and_direction_from_point(x, y, polyline)
        self.begin = [basePt.x, basePt.y]
        self.direction = dir
        self.current_station = round(station, 2) 
        self.initialiseSection()
        self.ptsInSection()
        self.Section.dataRefresh()
        self.Overview.dataRefresh()
        self.showMessages()
        QtWidgets.QApplication.restoreOverrideCursor()
        self.refreshQueue()

    def polygonSize(self):
        if not self.meanPtDistance:
            self.meanPtDistance = 1 / np.sqrt(self.ptsDensity)

            self.across = 1000 * self.meanPtDistance

            if self.across > 30:
                self.across = 30.0
            else:
                self.across = round(1000 * self.meanPtDistance,2)

            self.along = round(5 * self.meanPtDistance,2)

            self.along_section.setText(str(self.along))
            self.across_section.setText(str(self.across))
        else:
            return

    def ptsInSection(self):
        self.Section.setData(self.result)

    def handlePickedPolyline(self, polyline):
        if polyline != []:
            self.axis_pts = polyline
            self.viewFirstSection(False)
            self.axis_pts = []
        else:
            self.Section._clearWidget()
        self.clearSectionPreloads()

    def clearAxisView(self):
        self.AxisView.clear()

    def viewFirstSection(self,File=True, inFile=''):
        try:
            if not self.odm:
                return
            if self.Overview.AxisView:
                self.clearAxisView()
                del self.Overview.selection

            if not File:
                self.load_axis(File=File)
            else:
                self.load_axis(inFile=inFile)

            if self.FalseAxis:
                return
            
            if not self.station_axis:
                return

            self.overlap = (float(self.overlap_section.text().strip()))/100

            dm = self.odm

            lf = pyDM.AddInfoLayoutFactory()
            type, inDM = lf.addColumn(dm, 'Id', True); assert inDM == True
            type, inDM = lf.addColumn(dm, 'Classification', True); assert inDM == True
            type, inDM = lf.addColumn(dm, self.manuallyClassified, True, pyDM.ColumnType.uint8)
            self.layout2 = lf.getLayout()

            self.begin, self.direction = self.station_axis.get_point_and_direction(self.current_station)
            
            self.initialiseSection()

            self.ptsInSection()
            self.Section.setOrthoView(self.direction)
            self.Section.dataRefresh()
            self.Overview.dataRefresh()
            self.firstSection = True
            self.showMessages()
            self.refreshQueue()
        except Exception as e:
            print(f"Exception occured: {e}")
            return

    def overlapPolygons(self):
        # self.disableButtonFunctions()
        if not self.station_axis:
            return
        self.overlap = float(self.overlap_section.text().strip())/100

    def activateEditing(self):
        self.Insert.setChecked(False)
        self.Delete.setChecked(False)
        self.Move.setChecked(False)
        isChecked = self.EditMode.isChecked()
        self.Insert.setEnabled(isChecked)
        self.Delete.setEnabled(isChecked)
        self.Move.setEnabled(isChecked)
        if isChecked:
            self.Overview.Draw = False

    def EditButtonsToggled(self):
        sender = self.sender()
        if sender.isChecked():
            if sender == self.Insert:
                self.Overview.insert = True
                self.Overview.delete = False
                self.Overview.move = False
                self.Delete.setChecked(False)
                self.Move.setChecked(False)
            elif sender == self.Delete:
                self.Overview.delete = True
                self.Overview.insert = False
                self.Overview.move = False
                self.Insert.setChecked(False)
                self.Move.setChecked(False)
            elif sender == self.Move:
                self.Overview.move = True
                self.Overview.insert = False
                self.Overview.delete = False
                self.Insert.setChecked(False)
                self.Delete.setChecked(False)

    def GenerateAxis(self):
        try:
            self.polygonSize()
            defaultDistance = str(self.across)
            defaultWidth = str(self.along)
            dialog = GenerateDialog(self,defaultDistance=defaultDistance)

            dialog.preview_clicked.connect(lambda: self.handlePreview(dialog))
            dialog.finished.connect(lambda: self.closeDialog(dialog))

            if dialog.exec_() == QDialog.Accepted:
                arial_axis_odm_name = self.file_name + '_arial_axis.odm'

                rotation = dialog.rotation.text()
                distance = dialog.distance.text()
                self.Overview.ArialCoverage(distance=distance, width=self.along, rotation=rotation, preview=False, export=dialog.shpFileExport.isChecked(), filename=arial_axis_odm_name)

                if not self.axis_manager.empty():
                    self.axis_pts = self.axis_manager.polyline2linestring(self.axis_manager.axis[0][0])

                self.across = float(dialog.distance.text())

                self.viewFirstSection(File=False)
                self.across_section.setText(str(self.across))
                self.PathToAxisShp.setText(os.path.abspath(arial_axis_odm_name))
                self.PathToAxisShp.setEnabled(False)
        except Exception as e:
            return

    def handlePreview(self, dialog):
        rotation = dialog.rotation.text()
        distance = dialog.distance.text()
        self.Overview.clear()
        self.Overview.ArialCoverage(distance=distance, width=self.along, rotation=rotation, preview=True)

    def closeDialog(self, dialog):
        self.Overview.clear()

    def changePolygonSize(self):
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        if not self.station_axis:
            return

        along = float(self.along_section.text().strip())
        across = float(self.across_section.text().strip())
        overlap = float(self.overlap_section.text().strip())

        if not (along == self.along and across == self.across and overlap == self.overlap):
            self.along = along
            self.across = across
            self.overlap = overlap
            
            self.clearSectionPreloads()
            self.initialiseSection()
            self.ptsInSection()
            self.Section.dataRefresh()
            self.Overview.dataRefresh()
            self.showMessages()
            self.refreshQueue()
        QtWidgets.QApplication.restoreOverrideCursor()

    def setOrthoView(self):
        try:
            self.Section.setOrthoView(self.direction)
        except Exception as e:
            return

    def EdditingAxis(self):
        self.Overview.insert = False
        self.Overview.delete = False
        self.Overview.move = False

        if self.DrawMode.isChecked():
            self.Overview.Draw = True
            self.Overview.SelectAxis = False
            self.SelectionMode.setChecked(False)
        elif self.SelectionMode.isChecked():
            self.Overview.Draw = False
            self.Overview.SelectAxis = True
            self.DrawMode.setChecked(False)

    def changeAttributes(self):
        if np.array_equal(self.result['Classification'],self.checkClassification) == False:
            self.setObj = {}
            self.setObj['Id'] = self.result['Id']
            self.setObj['Classification'] = self.result['Classification']
            self.setObj[self.manuallyClassified] = self.result[self.manuallyClassified]
            pyDM.NumpyConverter.setById(self.setObj, self.odm, self.layout2)
            self.odm.save()

    def knn(self, knnMode = '2d'):
        assigned_pts = 0
        if not self.knnSection:
            return

        ######################## 2D NEAREST NEIGHBOR SEARCH ##########################
        if knnMode == '2d':
            center = Point3D(self.Section.Center)
            transMat = self.Section.camera.getTransformationMatrix(self.direction) # 4x4 transformation matrix (homogenous coordinates)
            cx, cy, cz = center.x(), center.y(), center.z()
            kx, ky, kz = self.knnSection['x'], self.knnSection['y'], self.knnSection['z']

            coords = np.vstack([kx - cx, ky - cy, kz - cz, np.ones(len(kx))])

            transformed = transMat.dot(coords)
            transPoints = np.column_stack((transformed[0], transformed[2])) # only X and Z, Y (projected axis in orthoview = direction along axis) is discarded

            tree = KDTree(transPoints)

            classes = np.array(self.knnSection['Classification'])

            mask = np.isin(self.result['Classification'], list(self.classesToPredict))
            coords2 = np.vstack([
                self.result['x'][mask] - cx,
                self.result['y'][mask] - cy,
                self.result['z'][mask] - cz,
                np.ones(mask.sum())
            ])
            transformed2 = transMat.dot(coords2)

            queries = np.column_stack((transformed2[0], transformed2[2]))

            # find nearest neighbor
            idxs = tree.query(queries, return_distance=False)

            real_indices = np.nonzero(mask)[0] # to get original indices before masking

            for real_idx, idx_nearest in zip(real_indices, idxs):
                self.result['Classification'][real_idx] = classes[idx_nearest]
                self.result[self.manuallyClassified][real_idx] = 2
                assigned_pts += 1
 
        ######################## 3D NEAREST NEIGHBOR SEARCH ##########################
        elif knnMode == '3d':
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

    def checkProgress(self):
        start = time.time()

        bbox = self.odm.getLimit()

        ysteps=100
        xsteps=100

        Y = np.linspace(bbox.ymin, bbox.ymax, ysteps, endpoint=False)
        X = np.linspace(bbox.xmin, bbox.xmax, xsteps, endpoint=False)

        dy = (bbox.ymax - bbox.ymin) / ysteps
        dx = (bbox.xmax - bbox.xmin) / xsteps

        def checkProgressByCell(x, y, dx, dy, odm, layout):
            try:
                window = pyDM.Window(x, y, x+dx, y+dy)
                pts = pyDM.NumpyConverter.searchPoint(odm, window, layout, withCoordinates=True, noDataObj=0)
                return 1 if any(c == 0 for c in pts['Classification']) else 0
            except Exception:
                return 2
            
        grid_x, grid_y = np.meshgrid(X, Y)
        result = [checkProgressByCell(x, y, dx, dy, self.odm, self.layout2) for x, y in zip(grid_x.ravel(), grid_y.ravel())]
        progress = np.array(result).reshape(ysteps, xsteps)
        
        
        self.Overview.setProgress(progress, X, Y, dx, dy)
        end = time.time()
        #print(f'Progress set, it took {end-start}s')

    def nextSection(self):
        self.switchSection('next')

    def previousSection(self):
        self.switchSection('previous')

    def switchSection(self, direction):
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        start=time.time()
        if not self.station_axis:
            return

        # calculate new station
        ds = round(self.along * (1 - self.overlap), 2)

        if direction == 'next':
            new_station = self.current_station + ds
            if new_station + ds > self.max_station:
                new_station = self.max_station-ds
        elif direction == 'previous':
            new_station = self.current_station - ds
            if new_station < self.min_station:
                new_station = self.min_station
        if new_station == self.current_station:
            return
        self.current_station = round(new_station, 2)

        endst=time.time()
        print(f'calculating new station took {endst-start}s')

        self.changeAttributes()
        #self.knnSection = copy.deepcopy(self.result) # copy of previous section for knn prediction
        self.knnSection = {k: np.copy(v) for k, v in self.result.items()}
        endcop = time.time()
        print(f'copying to knnsection took {endcop-endst}s')

        self.begin, self.direction = self.station_axis.get_point_and_direction(self.current_station)
        starti = time.time()
        print(f'going further in nextsection until initialisesection took {starti-endcop}')
        self.initialiseSection()
        endi = time.time()
        print(f'self.initialiseSection took {endi-starti}s')
        
        
        # knn prediction
        if self.knnPrediction.currentText() == 'always predict' or self.knnPrediction.currentText() == f'predict {direction}':
            self.knn(self.predictionModel.currentText())

        self.ptsInSection()
        self.Section.dataRefresh()
        self.Overview.dataRefresh()
        self.showMessages()

        end = time.time()
        print(f'going to next section took {end-start}s')
        self.refreshQueue()
        endr = time.time()
        print(f'self.refreshQueue took {endr-end}s')
        QtWidgets.QApplication.restoreOverrideCursor()

    def WritePointsToglSectionWidget(self):
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
            self.WritePointsToglSectionWidget()
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
        try:
            if self.firstSection:
                if self.HightColor.isChecked():
                    self.HightColor.setChecked(False)

                if self.ClassColor.isChecked():
                    self.Section.currentColor = COLOR_MODE_CLASS
                    self.Section.dataRefresh()
        except Exception as e:
            return

    def HightColoring(self):
        try:
            if self.ClassColor.isChecked():
                self.ClassColor.setChecked(False)

            if self.HightColor.isChecked():
                self.Section.currentColor = COLOR_MODE_ATTR
                self.Section.dataRefresh()
        except Exception as e:
            return

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
    
    def showShortcutBindings(self):
        self.ViewShortcutBindings.setRowCount(2) 
        self.ViewShortcutBindings.setColumnCount(len(self.shortcutBindings.keys()))
        self.ViewShortcutBindings.verticalHeader().setVisible(False)
        self.ViewShortcutBindings.horizontalHeader().setVisible(False)
        idx = 0
        sortedshortcutBindings = dict(sorted(self.shortcutBindings.items()))
        for key, value in sortedshortcutBindings.items():
            self.ViewShortcutBindings.setItem(0, idx, QTableWidgetItem('Alt+{}'.format(key)))

            item = QTableWidgetItem('{}'.format(value))
            for key, val in self.classificationData.items():
                if val[0] == value:
                    pixmap = QPixmap(100,100)
                    pixmap.fill((QColor(val[1][0],val[1][1],val[1][2])))
                    icon = QIcon(pixmap)
                    item.setIcon(icon)
            self.ViewShortcutBindings.setItem(1, idx, item)

            idx += 1
        self.ViewShortcutBindings.resizeColumnsToContents()

    def resetSection(self):
        if not self.station_axis:
            return
        self.Section.ResetPointClasses()

    def saveFile(self):
        if not self.station_axis:
            return

        self.changeAttributes()
        self.Section.savePointClasses()
        self.PathToFile.setEnabled(True)
        self.PathToAxisShp.setEnabled(True)

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Return or event.key() == QtCore.Qt.Key_Tab:
            self.changePolygonSize()

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = ClassificationTool()

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inFile", help="filename of the odm-file containing the pointcloud")
    parser.add_argument("-a", "--axisFile", help="filename of the file containing the axis")
    parser.add_argument("-p", "--predMode", help="'no prediction' or 'predict previous' or 'always predict' or 'predict next'")
    args = parser.parse_args()
    if args.inFile:
        win.loadPointcloud(args.inFile)

    
    if args.predMode:
        win.knnPrediction.setCurrentText(args.predMode)
    win.show()
    if args.axisFile:
        win.viewFirstSection(inFile=args.axisFile)
    sys.exit(app.exec_())