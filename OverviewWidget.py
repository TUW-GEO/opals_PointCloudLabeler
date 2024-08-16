from PyQt5 import QtCore, QtWidgets
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import svgwrite
from osgeo import gdal
from opals import pyDM
import os
from AxisGenerator import AxisGenerator

class OverviewWidget(QSvgWidget):
    polylinePicked = QtCore.pyqtSignal(object)

    def __init__(self, *args):
        QSvgWidget.__init__(self, *args)
        self.setMouseTracking(True)
        self.shd_filename = None
        self.shd_geotrafo = None
        self.scale_pixel2svg = None
        self.shd_bbox = None
        self.axis_pts = []
        self.linestring = None
        self.selection = None
        self.width = None
        self.height = None
        self.DrawAxis = False
        self.SelectAxis = None
        self.AxisList = None
        self.createCrossCursor()
        #self.createCircleCursor()
        self.AxisManager = None
        self.stroke_width = 0.5
        self.is_loading = False
        self.AxisODMPath = None
        self.insert = False
        self.delete = False
        self.move = False
        self.pickedVertex = None
        self.leftButtonPressed = False
        self.linestrings = None
        self.preview = False

    def setAxisList(self, listWidget):
        self.AxisList = listWidget
        self.AxisList.itemChanged.connect(self.handleItemChanged)
        self.AxisList.installEventFilter(self)

    def setAxisManagement(self,axis_manager):
        self.AxisManager = axis_manager
        self.odm2idx = self.AxisManager.odm2idx
        self.idx2odm = self.AxisManager.idx2odm
        self.activeLineIdx = 0
        if axis_manager.axis == []:
            return
        else:
            self.dataRefresh()
            self.addAxisItem()

    def raster2world(self, px, py):
        x = self.shd_geotrafo[0] + px * self.shd_geotrafo[1] + py * self.shd_geotrafo[2]
        y = self.shd_geotrafo[3] + px * self.shd_geotrafo[4] + py * self.shd_geotrafo[5]
        return x,y

    def setShading(self,filename):
        self.shd_filename = filename
        ds = gdal.Open(self.shd_filename, gdal.GA_ReadOnly)
        self.shd_geotrafo = ds.GetGeoTransform()
        self.shd_bbox = [self.raster2world(0, 0), self.raster2world(ds.RasterXSize, ds.RasterYSize)]
        del ds

    def setSelectionBox(self,p1,p2,p3,p4):
        self.selection = [(p1[0][0], p1[0][1]),
                          (p2[0][0], p2[0][1]),
                          (p3[0][0], p3[0][1]),
                          (p4[0][0], p4[0][1]),
                          (p1[0][0], p1[0][1]) ]

    def world2svg(self, wx, wy):
        sx = wx - self.red_x
        sy = self.red_y - wy
        return sx, sy

    def pixel2svg(self, px, py):
        width, height = self.size().width(), self.size().height()
        sx = (px - width/2)*self.scale_pixel2svg + self.dx/2
        sy = (py - height/2)*self.scale_pixel2svg + self.dy/2
        return sx, sy

    def pixel2world(self, px, py):
        sx, sy = self.pixel2svg(px, py)

        wx = self.red_x + sx
        wy = self.red_y - sy
        return wx, wy

    def dataRefresh(self):
        self.svg = svgwrite.Drawing()

        # svg coordinate origin is upper left of shading
        self.red_x = self.shd_bbox[0][0]  # left coordinate of shading
        self.red_y = self.shd_bbox[0][1]  # upper coordinate of shading

        minx = self.shd_bbox[0][0] - self.red_x
        miny = self.red_y-self.shd_bbox[0][1]

        self.dx = self.shd_bbox[1][0] - self.shd_bbox[0][0]
        self.dy = self.shd_bbox[0][1] - self.shd_bbox[1][1]

        self.svg.viewbox(minx=minx, miny=miny, width=self.dx, height=self.dy)
        self.svg.add(self.svg.image(href=self.shd_filename, insert=(minx,miny), size=(self.dx,self.dy)))

        width, height = self.size().width(), self.size().height()

        # we use Qt.KeepAspectRatio for drawing so the larger svg/pixel ratio defines scale
        rx = self.dx / width
        ry = self.dy / height
        self.scale_pixel2svg = max([rx, ry])

        try:
            for line in self.AxisManager.axis:
                self.lineidx = self.odm2idx[line[0].info().get(0)]
                if self.odm2idx[line[0].info().get(0)] == self.activeLineIdx:
                    self.color = 'green'
                    self.axis_pts = self.AxisManager.allAxisPts[self.odm2idx[line[0].info().get(0)]]
                    self.drawAxis()

                else:
                    self.color = 'lightblue'
                    self.axis_pts = self.AxisManager.allAxisPts[self.odm2idx[line[0].info().get(0)]]
                    self.drawAxis()

                if self.odm2idx[line[0].info().get(0)] == self.activeLineIdx:
                    self.color = 'blue'
                    self.axis_pts = self.AxisManager.splines[self.activeLineIdx]
                    self.drawAxis(nodes=False)

            if self.selection:
                self.drawSection()

            if self.preview:
                for line in self.linestrings:
                    self.color = 'lightblue'
                    self.axis_pts = line
                    self.drawAxis()


        except Exception as e:
            pass

        self.axis_pts = []
        self.update_svg()

    def drawAxis(self, nodes = True , firstPoint=False):
         if firstPoint and nodes:
             pt1 = self.world2svg(self.axis_pts[0][0], self.axis_pts[0][1])
             self.svg.add(self.svg.circle(center=pt1, r=self.stroke_width / 2, stroke='orange', fill='none'))

         for idx in range(len(self.axis_pts) - 1):
             if idx == self.pickedVertex and self.activeLineIdx == self.lineidx:
                 node_color = 'grey'
             else:
                 node_color = 'orange'


             pt1 = self.world2svg(self.axis_pts[idx][0], self.axis_pts[idx][1])
             pt2 = self.world2svg(self.axis_pts[idx + 1][0], self.axis_pts[idx + 1][1])

             self.svg.add(self.svg.line(start=pt1, end=pt2, stroke= self.color, stroke_width=self.stroke_width))
             if nodes: self.svg.add(self.svg.circle(center=pt1, r=self.stroke_width/2, stroke=node_color, fill='none'))

             if idx == (len(self.axis_pts) - 2):
                if nodes: self.svg.add(self.svg.circle(center=pt2, r=self.stroke_width / 2, stroke=node_color, fill='none'))

         self.update_svg()

    def drawSection(self):
        for idx in range(len(self.selection) - 1):
            pt1 = self.world2svg(self.selection[idx][0], self.selection[idx][1])
            pt2 = self.world2svg(self.selection[idx + 1][0], self.selection[idx + 1][1])

            self.svg.add(self.svg.line(start=pt1, end=pt2, stroke='red', stroke_width=self.stroke_width))

        self.update_svg()

    def update_svg(self):
        # Update the SVG in the widget
        svg_xml = self.svg.tostring()
        svg_bytes = bytearray(svg_xml, encoding='utf-8')
        self.renderer().load(svg_bytes)
        self.renderer().setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
        self.update()

    def changeLineWidth(self,value):
        self.stroke_width = value / 2.
        self.dataRefresh()

    def handleItemChanged(self, item):
        if self.is_loading:
            return

        if item.checkState() == QtCore.Qt.Checked:
            for i in range(self.AxisList.count()):
                list_item = self.AxisList.item(i)
                if list_item != item:
                    list_item.setCheckState(QtCore.Qt.Unchecked)

            self.activeLineIdx = self.AxisList.row(item)
            self.polylinePicked.emit(self.AxisManager.allAxisPts[self.activeLineIdx])
            self.dataRefresh()

        else:
            self.selected_line_idx = None

    def setItemChecked(self, index):
        for i in range(self.AxisList.count()):
            item = self.AxisList.item(i)
            if i == index:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)

    def addAxisItem(self):
        self.is_loading = True

        for i, line in enumerate(self.AxisManager.axis):
            item = QtWidgets.QListWidgetItem(f"Axis {i + 1}: {{Nodes : {self.AxisManager.axisInfo[i][0]}, Length : {round(self.AxisManager.axisInfo[i][1], 2)}}}")
            self.AxisList.addItem(item)

            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)

            if i == 0:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)

        self.is_loading = False

    def addItem(self):
        self.is_loading = True

        item = QtWidgets.QListWidgetItem(f"Axis {len(self.AxisManager.axis)}: {{Nodes : {self.AxisManager.axisInfo[len(self.AxisManager.axis) - 1][0]}, Length : {round(self.AxisManager.axisInfo[len(self.AxisManager.axis) - 1][1], 2)}}}")

        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        if len(self.AxisManager.axis) == 1:
            item.setCheckState(QtCore.Qt.Checked)
            self.selected_line_idx_new = self.AxisList.row(item)
        else:
            item.setCheckState(QtCore.Qt.Unchecked)

        self.AxisList.addItem(item)
        self.is_loading = False

    def linestring2polylineobj(self):
        f = pyDM.PolylineFactory()
        # create polylines and add them to the odm
        for pt in self.axis_pts:
            f.addPoint(pt[0], pt[1])
        if self.AxisManager.odm:
            self.addLineToODM(f.getPolyline(), draw=True)
        else:
            self.addLineToODM(f.getPolyline(), draw=False)

    def addLineToODM(self,line, draw=False):
        try:
            if not self.AxisManager.odm:
                odm_filename, _ = QFileDialog.getSaveFileName(self, 'Save ODM File', '', 'ODM Files (*.odm)')
                _, data = os.path.split(odm_filename)

                self.AxisODMPath = odm_filename

                if data:
                    self.AxisManager.set_filename(data)
                    self.AxisManager.addLine(line)
            if draw:
                self.AxisManager.addLine(line)

        except Exception as e:
            return

    def deleteSelectedItems(self):
        selectedIndices = [self.AxisList.row(item) for item in self.AxisList.selectedItems()]
        selectedIndices.sort(reverse=True)
        for idx in selectedIndices:
            if idx == self.activeLineIdx:

                message_box = QMessageBox(
                    QMessageBox.Warning,
                    'Confirm Deletion',
                    'The selected item is the active line. Do you want to delete it?'
                )
                message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                reply = message_box.exec_()

                if reply == QMessageBox.Yes:
                    if len(self.AxisManager.axis) == 1:
                        self.AxisManager.removeByIdx(idx)
                        self.AxisList.takeItem(idx)
                        del self.selection
                        self.polylinePicked.emit(self.AxisManager.allAxisPts)

                    else:
                        self.AxisManager.removeByIdx(idx)
                        self.AxisList.takeItem(idx)
                        self.activeLineIdx = self.AxisManager.odm2idx[self.AxisManager.axis[0][0].info().get(0)]
                        self.setItemChecked(self.activeLineIdx)
                        self.polylinePicked.emit(self.AxisManager.allAxisPts[self.activeLineIdx])

                elif reply == QMessageBox.No:
                    return
            else:
                self.AxisManager.removeByIdx(idx)
                self.AxisList.takeItem(idx)

        self.odm2idx = self.AxisManager.odm2idx
        self.idx2odm = self.AxisManager.idx2odm
        self.dataRefresh()
        self.updateItemLabels()

    def updateItemLabels(self):
        for i in range(self.AxisList.count()):
            item = self.AxisList.item(i)
            item.setText(f"Axis {i + 1}: {{Nodes : {self.AxisManager.axisInfo[i][0]}, Length : {round(self.AxisManager.axisInfo[i][1], 2)}}}")

    def ArialCoverage(self, distance, rotation, preview=False, export=False, filename=None):
        if preview:
            try:
                self.generator = AxisGenerator(self.shd_bbox, float(rotation), float(distance))
                self.linestrings = self.generator.getPolylineCoords()
                self.preview = True
                self.dataRefresh()
                self.preview = False
            except Exception as e:
                pass
        else:
            if not self.linestrings:
                self.generator = AxisGenerator(self.shd_bbox, float(rotation), float(distance))
                self.linestrings = self.generator.getPolylineCoords()
            self.AxisManager.set_filename(filename)

            for line in self.linestrings:
                self.axis_pts = line
                self.linestring2polylineobj()
                self.addItem()

            self.axis_pts = []
            self.dataRefresh()

            if export:
                name, _ = filename.split('.')
                self.generator.linestrings2shapefile(name+'.shp')

    def mousePressEvent(self, mouseEvent):
        if mouseEvent.button() == QtCore.Qt.LeftButton and self.DrawAxis:
            self.width = self.size().width()
            self.height = self.size().height()

            self.axis_pts.append(self.pixel2world(mouseEvent.x(),mouseEvent.y()))

            self.color = 'lightblue'

            # if self.AxisManager.axis == []:
            #     self.color = 'blue'
            # else:
            #     self.color = 'lightblue'

            if len(self.axis_pts) == 1:
                self.drawAxis(firstPoint=True)
            elif len(self.axis_pts) > 1:
                self.drawAxis()


        if mouseEvent.button() == QtCore.Qt.RightButton and self.axis_pts != [] and self.DrawAxis:
            try:
                self.linestring2polylineobj()

                self.currentaxis = self.AxisManager.axis[0]

                if len(self.AxisManager.axis) == 1:
                    self.polylinePicked.emit(self.AxisManager.allAxisPts[0])
                    self.dataRefresh()

                self.axis_pts = []
                self.addItem()

            except Exception as e:
                return

        if mouseEvent.button() == QtCore.Qt.LeftButton and not self.DrawAxis:
            try:
                pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
                line = self.AxisManager.getByCoords(pt[0],pt[1])
                self.activeLineIdx = self.odm2idx[line[0].info().get(0)]
                self.setItemChecked(self.activeLineIdx)
                self.polylinePicked.emit(self.AxisManager.allAxisPts[self.activeLineIdx])
                self.dataRefresh()

            except Exception as e:
                return

        if mouseEvent.button() == QtCore.Qt.LeftButton and self.insert:
            pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
            line = self.AxisManager.getByCoords(pt[0], pt[1])
            self.AxisManager.InsertVertices(line[0], pt)
            self.polylinePicked.emit(self.AxisManager.allAxisPts[self.activeLineIdx])
            self.dataRefresh()
            self.updateItemLabels()

        elif mouseEvent.button() == QtCore.Qt.LeftButton and self.delete:
            pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
            line = self.AxisManager.getByCoords(pt[0], pt[1])
            self.AxisManager.DeleteVertices(line[0], pt)
            self.polylinePicked.emit(self.AxisManager.allAxisPts[self.activeLineIdx])
            self.dataRefresh()
            self.updateItemLabels()

        elif mouseEvent.button() == QtCore.Qt.LeftButton and self.move:
            pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
            line = self.AxisManager.getByCoords(pt[0], pt[1])
            self.pickedVertex = self.AxisManager.PickVertices(line[0], pt)
            self.dataRefresh()
            self.updateItemLabels()

    def mouseMoveEvent(self, mouseEvent):
        if int(mouseEvent.buttons()) & QtCore.Qt.LeftButton and self.move:
            self.mouse = (mouseEvent.x(), mouseEvent.y())
            #self.createCircleCursor()

    def mouseReleaseEvent(self, mouseEvent):
        if mouseEvent.button() == QtCore.Qt.LeftButton and self.move:
            pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
            line = self.AxisManager.getByCoords(pt[0], pt[1])
            self.AxisManager.MoveVertices(line[0], self.pickedVertex, pt)
            self.polylinePicked.emit(self.AxisManager.allAxisPts[self.activeLineIdx])
            self.pickedVertex = None
            #self.leftButtonPressed = False
            self.dataRefresh()
            self.updateItemLabels()

    # def createCircleCursor(self):
    #     cursor_pixmap = QPixmap(32, 32)
    #     cursor_pixmap.fill(Qt.transparent)
    #     painter = QPainter(cursor_pixmap)
    #     painter.setPen(QPen(QColor(255, 165, 0), 2))
    #     painter.drawEllipse(0, 0, 8, 8)
    #     painter.end()
    #     self.circleCursor = QCursor(cursor_pixmap)

# Create custom cursor and change the cursor, depends on the mode in which the widget is set to:
    def createCrossCursor(self):
        # Create a white cross cursor
        cursor_pixmap = QPixmap(16, 16)
        cursor_pixmap.fill(Qt.transparent)
        painter = QPainter(cursor_pixmap)
        painter.setPen(QPen(QColor(255, 0, 255), 1))
        painter.drawLine(8, 0, 8, 16)
        painter.drawLine(0, 8, 16, 8)
        painter.end()
        self.crossCursor = QCursor(cursor_pixmap)

    def enterEvent(self, event):
        self.updateCursor()
        super().enterEvent(event)

    def updateCursor(self):
        if self.DrawAxis:
            self.setCursor(self.crossCursor)
        #elif self.move and self.leftButtonPressed:
         #   self.setCursor(self.circleCursor)
        else:
            self.unsetCursor()
    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.ContextMenu and source is self.AxisList:
            menu = QtWidgets.QMenu()
            menu.addAction('Delete')
            if menu.exec_(event.globalPos()):
                self.deleteSelectedItems()

            return True
        return super(OverviewWidget, self).eventFilter(source, event)