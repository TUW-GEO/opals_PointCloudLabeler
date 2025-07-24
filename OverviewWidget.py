from PyQt5 import QtCore, QtWidgets
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QApplication
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import svgwrite
from osgeo import gdal
from opals import pyDM
import os
from AxisGenerator import AxisGenerator
import numpy as np

class OverviewWidget(QSvgWidget):
    polylinePicked = QtCore.pyqtSignal(object)
    selectSection = pyqtSignal(float, float)
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
        self.sections = None
        self.section_color = 'red'
        self.classificationProgress = None
        self.progressLinspaceX = None
        self.progressLinspaceY = None
        self.progressDX = None
        self.progressDY = None
        self.axis_color = 'blue'
        self.node_color = 'orange'
        self.width = None
        self.height = None
        self.Draw = False
        self.SelectAxis = None
        self.AxisList = None
        self.createCrossCursor()
        self.AxisManager = None
        self.stroke_width = 0.5
        self.is_loading = False
        self.AxisODMPath = None
        self.AxisView = False
        self.insert = False
        self.delete = False
        self.move = False
        self.pickedVertex = None
        self.leftButtonPressed = False
        self.linestrings = None
        self.preview = False
        self.aspect_ratio = None
        self.svg_vb_minx = None
        self.svg_vb_miny = None
        self.svg_vb_dx = None
        self.svg_vb_dy = None
        self.svg_zoom = 1
        self.svg_zoom_factor = 1.1
        self.red_x = None
        self.red_y = None
        self.overlap = None
        self.distance = None

    def zoom(self,px, py, factor):
        try:
            widget_width = self.size().width()
            widget_height = self.size().height()

            self.svg_vb_minx = px * self.svg_vb_dx * (factor-1) / (self.svg_zoom*factor*widget_width)  + self.svg_vb_minx
            self.svg_vb_miny = py * self.svg_vb_dy * (factor-1) / (self.svg_zoom*factor*widget_height) + self.svg_vb_miny

            self.svg_zoom *= factor
            self.dataRefresh()
        except Exception as e:
            return


    def zoomIn(self):
        self.zoom(self.size().width()/2., self.size().height()/2., self.svg_zoom_factor)

    def zoomOut(self):
        self.zoom(self.size().width()/2., self.size().height()/2., 1/self.svg_zoom_factor)

    def zoomOnLayer(self):
        try:
            self.zoom(self.size().width()/2., self.size().height()/2., 1 / self.svg_zoom)
            self.svg_vb_minx = 0
            self.svg_vb_miny = 0
            self.svg_vb_dx = self.svg_vb_dx_init
            self.svg_vb_dy = self.svg_vb_dy_init

            self.dataRefresh()
        except Exception as e:
            return

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
        self.aspect_ratio = self.size().width() / self.size().height()
        self.shd_filename = filename
        ds = gdal.Open(self.shd_filename, gdal.GA_ReadOnly)
        self.shd_geotrafo = ds.GetGeoTransform()
        self.shd_bbox = [self.raster2world(0, 0), self.raster2world(ds.RasterXSize, ds.RasterYSize)]
        self.svg_vb_minx = 0
        self.svg_vb_miny = 0
        dx = self.shd_bbox[1][0]-self.shd_bbox[0][0]
        dy = self.shd_bbox[0][1]-self.shd_bbox[1][1]
        if dx > dy*self.aspect_ratio:
            size = dx
        else:
            size = dy*self.aspect_ratio
        self.svg_zoom = 1
        self.svg_vb_dx = size
        self.svg_vb_dy = size/self.aspect_ratio

        self.svg_vb_dx_init = size
        self.svg_vb_dy_init = size/self.aspect_ratio
        self.svg_vb_minx_init = 0
        self.svg_vb_miny_init = 0

        self.red_x = self.shd_bbox[0][0]
        self.red_y = self.shd_bbox[0][1]
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
        widget_width = self.size().width()
        widget_height = self.size().height()

        scale_x = self.svg_vb_dx / (self.svg_zoom * widget_width)
        scale_y = self.svg_vb_dy / (self.svg_zoom * widget_height)

        sx = px * scale_x + self.svg_vb_minx
        sy = py * scale_y + self.svg_vb_miny

        return sx, sy

    def pixel2world(self, px, py):
        sx, sy = self.pixel2svg(px, py)

        wx = self.red_x + sx
        wy = self.red_y - sy
        return wx, wy

    def dataRefresh(self, show_progress=False):
        self.svg = svgwrite.Drawing()

        self.svg.viewbox(minx=self.svg_vb_minx, miny=self.svg_vb_miny, width=self.svg_vb_dx/self.svg_zoom, height=self.svg_vb_dy/self.svg_zoom)
        dx = self.shd_bbox[1][0] - self.shd_bbox[0][0]
        dy = self.shd_bbox[0][1] - self.shd_bbox[1][1]
        self.svg.add(self.svg.image(href=self.shd_filename, insert=(0, 0), size=(dx, dy)))

        # Draw Classification Progress
        if show_progress:
            self.drawProgress()

        try:
            for line in self.AxisManager.axis:
                self.lineidx = self.odm2idx[line[0].info().get(0)]
                if self.odm2idx[line[0].info().get(0)] == self.activeLineIdx:
                    self.axis_color = 'green'
                    self.axis_pts = self.AxisManager.allAxisPts[self.odm2idx[line[0].info().get(0)]]
                    self.drawAxis()

                else:
                    self.axis_color = 'lightblue'
                    self.axis_pts = self.AxisManager.allAxisPts[self.odm2idx[line[0].info().get(0)]]
                    self.drawAxis()

                if self.odm2idx[line[0].info().get(0)] == self.activeLineIdx:
                    self.axis_color = 'blue'
                    self.axis_pts = self.AxisManager.splines[self.activeLineIdx]
                    self.drawAxis(nodes=False)

            if self.selection:
                self.section_color = 'red'
                self.drawSection()

            if self.preview:
                for i in range(len(self.linestrings)):
                    self.axis_color = 'lightblue'
                    self.section_color = 'lightcoral'
                    self.axis_pts = self.linestrings[i]
                    p1 = self.sections[i][0]
                    p2 = self.sections[i][1]
                    p3 = self.sections[i][2]
                    p4 = self.sections[i][3]
                    self.setSelectionBox(p1, p2, p3, p4)
                    self.drawAxis()
                    self.drawSection()

        except Exception as e:
            pass

        self.axis_pts = []
        self.update_svg()

    def drawAxis(self, nodes = True , firstPoint=False):
         if firstPoint and nodes:
             pt1 = self.world2svg(self.axis_pts[0][0], self.axis_pts[0][1])
             self.svg.add(self.svg.circle(center=pt1, r=self.stroke_width / 2, stroke=self.node_color, fill='none'))

         for idx in range(len(self.axis_pts) - 1):
             if idx == self.pickedVertex and self.activeLineIdx == self.lineidx:
                 self.node_color = 'grey'
             else:
                 self.node_color = 'orange'


             pt1 = self.world2svg(self.axis_pts[idx][0], self.axis_pts[idx][1])
             pt2 = self.world2svg(self.axis_pts[idx + 1][0], self.axis_pts[idx + 1][1])

             self.svg.add(self.svg.line(start=pt1, end=pt2, stroke=self.axis_color, stroke_width=self.stroke_width))
             if nodes: self.svg.add(self.svg.circle(center=pt1, r=self.stroke_width/2, stroke=self.node_color, fill='none'))

             if idx == (len(self.axis_pts) - 2):
                if nodes: self.svg.add(self.svg.circle(center=pt2, r=self.stroke_width / 2, stroke=self.node_color, fill='none'))

         self.update_svg()

    def drawSection(self):
        for idx in range(len(self.selection) - 1):
            pt1 = self.world2svg(self.selection[idx][0], self.selection[idx][1])
            pt2 = self.world2svg(self.selection[idx + 1][0], self.selection[idx + 1][1])

            self.svg.add(self.svg.line(start=pt1, end=pt2, stroke=self.section_color, stroke_width=self.stroke_width))

        self.update_svg()

    def drawProgress(self):
        if self.classificationProgress is not None and self.classificationProgress.size > 0:
            dx = self.progressDX
            dy = self.progressDY
                        
            for i, y in enumerate(self.progressLinspaceY):
                for j, x in enumerate(self.progressLinspaceX):
                    classified = self.classificationProgress[i, j]
                    pts = [self.world2svg(x, y),
                        self.world2svg(x, y+dy),
                        self.world2svg(x+dx, y+dy),
                        self.world2svg(x+dx, y),
                        self.world2svg(x, y)]
                    
                    if classified == 0:
                        color = 'lightgreen'
                    elif classified == 1:
                        color = 'red'
                    elif classified == 2:
                        color = 'orange'

                    self.svg.add(self.svg.polygon(points=pts, fill=color, fill_opacity=0.4))
           
            self.update_svg()

    def setProgress(self, progress, X, Y, dx, dy):
        self.classificationProgress = progress
        self.progressLinspaceX = X
        self.progressLinspaceY = Y
        self.progressDX = dx
        self.progressDY = dy

    def update_svg(self):
        # Update the SVG in the widget
        svg_xml = self.svg.tostring()
        svg_bytes = bytearray(svg_xml, encoding='utf-8')
        self.renderer().load(svg_bytes)
        self.update()

    def changeLineWidth(self,value):
        try:
            self.stroke_width = value / 2.
            self.dataRefresh()
        except Exception as e:
            return

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

                self.AxisView = True

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

    def ArialCoverage(self, distance, width, rotation, preview=False, export=False, filename=None):
        if preview:
            try:
                self.generator = AxisGenerator(self.shd_bbox, float(rotation), float(distance))
                self.linestrings = self.generator.getPolylineCoords()
                #for line in self.linestrings:
                self.sections = self.previewSections(self.linestrings, width, distance)
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
    def previewSections(self,linestrings, width, length):
        length = float(length)
        sections = []
        for line in linestrings:
            start_point = np.array([line[0]]).reshape(1, 2)

            dx = line[1][0] - line[0][0]
            dy = line[1][1] - line[0][1]
            slen = (dx ** 2 + dy ** 2) ** 0.5
            if slen == 0:
                raise Exception("Identical subsequent 2d points are not allowed")
            dir = [dx / slen, dy / slen]

            rot_vector = np.array([-dir[1], dir[0]]).reshape(1, 2)
            vector = np.array([dir[0], dir[1]]).reshape(1, 2)
            p1 = start_point + (rot_vector * length / 2)
            p2 = start_point + (-rot_vector * length / 2)
            p3 = p2 + (width * vector)
            p4 = p1 + (width * vector)

            sections.append([p1,p2,p3,p4])
        return sections

    def clear(self):
        self.linestrings = None
        self.sections = None
        self.selection = None
        self.dataRefresh()

    def mousePressEvent(self, mouseEvent):
        if mouseEvent.button() == QtCore.Qt.LeftButton and self.Draw and self.shd_filename:
            self.width = self.size().width()
            self.height = self.size().height()

            self.axis_pts.append(self.pixel2world(mouseEvent.x(),mouseEvent.y()))

            self.axis_color = 'lightblue'

            if len(self.axis_pts) == 1:
                self.drawAxis(firstPoint=True)
            elif len(self.axis_pts) > 1:
                self.drawAxis()

        if mouseEvent.button() == QtCore.Qt.RightButton and self.axis_pts != [] and self.Draw:
            try:
                self.linestring2polylineobj()

                self.currentaxis = self.AxisManager.axis[0]

                if len(self.AxisManager.axis) == 1:
                    self.polylinePicked.emit(self.AxisManager.allAxisPts[0])
                    self.dataRefresh()

                self.axis_pts = []
                self.addItem()
                self.AxisView = False

            except Exception as e:
                return

        if mouseEvent.button() == QtCore.Qt.LeftButton and self.SelectAxis:
            try:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

                pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
                line = self.AxisManager.getByCoords(pt[0],pt[1])
                self.activeLineIdx = self.odm2idx[line[0].info().get(0)]
                self.setItemChecked(self.activeLineIdx)
                self.polylinePicked.emit(self.AxisManager.allAxisPts[self.activeLineIdx])
                self.dataRefresh()

            except Exception as e:
                return

            finally:
                QtWidgets.QApplication.restoreOverrideCursor()

        if mouseEvent.button() == QtCore.Qt.LeftButton and self.insert:
            try:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

                pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
                line = self.AxisManager.getByCoords(pt[0], pt[1])
                self.AxisManager.InsertVertices(line[0], pt)



                self.polylinePicked.emit(self.AxisManager.allAxisPts[self.activeLineIdx])
                self.dataRefresh()
                self.updateItemLabels()

            except Exception as e:
                return

            finally:
                QtWidgets.QApplication.restoreOverrideCursor()

        elif mouseEvent.button() == QtCore.Qt.LeftButton and self.delete:
            try:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

                pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
                line = self.AxisManager.getByCoords(pt[0], pt[1])
                self.AxisManager.DeleteVertices(line[0], pt)
                self.polylinePicked.emit(self.AxisManager.allAxisPts[self.activeLineIdx])
                self.dataRefresh()
                self.updateItemLabels()
            except Exception as e:
                return

            finally:
                QtWidgets.QApplication.restoreOverrideCursor()

        elif mouseEvent.button() == QtCore.Qt.LeftButton and self.move:
            try:
                pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
                line = self.AxisManager.getByCoords(pt[0], pt[1])
                self.pickedVertex = self.AxisManager.PickVertices(line[0], pt)
                self.dataRefresh()
                self.updateItemLabels()
            except Exception as e:
                return

        elif mouseEvent.button() == QtCore.Qt.RightButton and self.SelectAxis:
            self.last_pos = (mouseEvent.x(), mouseEvent.y())
        



    def mouseMoveEvent(self, mouseEvent):
        self.pos = (mouseEvent.x(), mouseEvent.y())

        if int(mouseEvent.buttons()) & QtCore.Qt.LeftButton and self.move:
            self.mouse = (mouseEvent.x(), mouseEvent.y())

        elif int(mouseEvent.buttons()) & QtCore.Qt.RightButton and self.SelectAxis:
            dx = self.last_pos[0]-mouseEvent.x()
            dy = self.last_pos[1]-mouseEvent.y()
            svg_dx, svg_dy = self.pixel2svg(dx, dy)
            self.svg_vb_minx = svg_dx
            self.svg_vb_miny = svg_dy
            self.dataRefresh()
            self.last_pos = (mouseEvent.x(), mouseEvent.y())

    def mouseReleaseEvent(self, mouseEvent):
        if mouseEvent.button() == QtCore.Qt.LeftButton and self.move:
            try:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

                pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
                line = self.AxisManager.getByCoords(pt[0], pt[1])
                self.AxisManager.MoveVertices(line[0], self.pickedVertex, pt)
                self.polylinePicked.emit(self.AxisManager.allAxisPts[self.activeLineIdx])
                self.pickedVertex = None
                self.dataRefresh()
                self.updateItemLabels()
            except Exception as e:
                return

            finally:
                QtWidgets.QApplication.restoreOverrideCursor()

        if mouseEvent.button() == QtCore.Qt.RightButton and self.SelectAxis and QApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
            x, y = self.pixel2world(mouseEvent.x(), mouseEvent.y())
            self.selectSection.emit(x, y)
            
    def wheelEvent(self, event):
        if event.angleDelta().y() > 0 and self.SelectAxis:
            self.zoom(self.pos[0], self.pos[1], self.svg_zoom_factor)
        elif event.angleDelta().y() < 0 and self.SelectAxis:
            self.zoom(self.pos[0], self.pos[1], (1/self.svg_zoom_factor))

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
        if self.Draw:
            self.setCursor(self.crossCursor)

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