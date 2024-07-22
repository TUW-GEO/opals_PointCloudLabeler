from PyQt5 import QtCore, QtWidgets, QtGui, uic
from PyQt5.QtSvg import QSvgWidget
import numpy as np
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import svgwrite
from osgeo import gdal
from opals import pyDM, Info
from AxisManagment import AxisManagement

class OverviewWidget(QSvgWidget):
    polylinePicked = QtCore.pyqtSignal(object)

    def __init__(self, *args):
        QSvgWidget.__init__(self, *args)
        self.setMouseTracking(True)
        self.shd_filename = None
        self.shd_geotrafo = None
        #self.shd_rasterSize = None
        self.scale_pixel2svg = None
        self.shd_bbox = None
        self.axis = []
        self.linestring = None
        self.lines = []
        self.pis = []
        self.selection = None
        self.width = None
        self.height = None
        self.DrawAxis = False
        self.SelectAxis = None
        self.selected_line_idx_new = 0
        self.selected_line_idx_old = 0
        self.AxisList = None
        self.oldSelection = None
        self.createCrossCursor()
        self.AxisManager = None


    def setAxisList(self, listWidget):
        self.AxisList = listWidget
        self.AxisList.itemChanged.connect(self.handleItemChanged)

    def setAxisODM(self,odm):
        self.axis_odm = odm

    def setAxisManagement(self,axis_manager):
        self.AxisManager = axis_manager
        self.odm2idx = axis_manager.odm2idx
        self.idx2odm = axis_manager.idx2odm
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

        self.stroke_width = self.dx / 200.

        self.svg.viewbox(minx=minx, miny=miny, width=self.dx, height=self.dy)
        self.svg.add(self.svg.image(href=self.shd_filename, insert=(minx,miny), size=(self.dx,self.dy)))

        width, height = self.size().width(), self.size().height()

        # we use Qt.KeepAspectRatio for drawing so the larger svg/pixel ratio defines scale
        rx = self.dx / width
        ry = self.dy / height
        self.scale_pixel2svg = max([rx, ry])

        try:
            for line in self.AxisManager.axis:
                if self.odm2idx[line[0].info().get(0)] == self.activeLineIdx:
                    self.color = 'blue'
                else:
                    self.color = 'lightblue'

                self.output_search(line)

                if self.axis:
                    self.drawAxis()

                self.axis=[]

            if self.selection:
                self.drawSection()

        except Exception as e:
            pass

        self.update_svg()

    def drawAxis(self, firstPoint=False):
         if firstPoint:
             pt1 = self.world2svg(self.axis[0][0], self.axis[0][1])
             self.svg.add(self.svg.circle(center=pt1, r=self.stroke_width / 2, stroke='orange', fill='none'))

         for idx in range(len(self.axis) - 1):
             pt1 = self.world2svg(self.axis[idx][0], self.axis[idx][1])
             pt2 = self.world2svg(self.axis[idx + 1][0], self.axis[idx + 1][1])

             #self.remove_line(pt1, pt2)
             self.svg.add(self.svg.line(start=pt1, end=pt2, stroke= self.color, stroke_width=self.stroke_width))
             self.svg.add(self.svg.circle(center=pt1, r=self.stroke_width/2, stroke='orange', fill='none'))

             if idx == (len(self.axis) - 2):
                self.svg.add(self.svg.circle(center=pt2, r=self.stroke_width / 2, stroke='orange', fill='none'))


         self.update_svg()

    def drawSection(self):
        for idx in range(len(self.selection) - 1):
            #try:
               # pt1_old = self.world2svg(self.oldSelection[idx][0], self.oldSelection[idx][1])
               # pt2_old = self.world2svg(self.oldSelection[idx + 1][0], self.oldSelection[idx + 1][1])

                #self.remove_line(pt1_old, pt2_old)
            #except Exception as e:
             #   pass

            pt1 = self.world2svg(self.selection[idx][0], self.selection[idx][1])
            pt2 = self.world2svg(self.selection[idx + 1][0], self.selection[idx + 1][1])

            self.svg.add(self.svg.line(start=pt1, end=pt2, stroke='red', stroke_width=1))

        self.update_svg()


    def remove_line(self, pt1, pt2):
        # Remove the line from SVG structure
        svg_lines = self.svg.elements
        for element in svg_lines:
            if isinstance(element, svgwrite.shapes.Line):
                x1, y1 = element.attribs['x1'], element.attribs['y1']
                x2, y2 = element.attribs['x2'], element.attribs['y2']
                if (x1, y1) == pt1 and (x2, y2) == pt2:
                    svg_lines.remove(element)
                    break

        self.update_svg()

    def update_svg(self):
        # Update the SVG in the widget
        svg_xml = self.svg.tostring()
        svg_bytes = bytearray(svg_xml, encoding='utf-8')
        self.renderer().load(svg_bytes)
        self.renderer().setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
        self.update()


    def changeAxisWidth(self,width):
        self.axis_width = width

        self.stroke_width = float(width)

        for line in self.AxisManager.axis:
            if line == self.currentaxis:
                self.output_polyline(line)
            else:
                self.output_polyline(line,False)

    def handleItemChanged(self, item):
        if item.checkState() == QtCore.Qt.Checked:
            for i in range(self.AxisList.count()):
                list_item = self.AxisList.item(i)
                if list_item != item:
                    list_item.setCheckState(QtCore.Qt.Unchecked)

            self.activeLineIdx = self.AxisList.row(item)

        else:
            self.selected_line_idx = None
        self.dataRefresh()

    def setItemChecked(self, index):
        for i in range(self.AxisList.count()):
            item = self.AxisList.item(i)
            if i == index:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)

    def changeAxis(self,new, old):
        #self.activeLineIdx
        self.dataRefresh()

        self.output_search(old, False)
        self.output_search(new)

    def output_polyline(self, line, odm=False):
        for idx, part in enumerate(line.parts()):
            for p in part.points():
                self.axis.append([p.x,p.y])

        if self.odm2idx[line.info().get(0)] == self.activeLineIdx:
            self.polylinePicked.emit([line])

        if odm:
            self.linestring2polylineobj()

    def output_search(self,lines):
        for idx, l in enumerate(lines):
            self.output_polyline(l)

    def addAxisItem(self):
        for i, line in enumerate(self.AxisManager.axis):
            item = QtWidgets.QListWidgetItem(f"Axis {i + 1}") #ToDo: mehr Information über Achse (länge und anzahl der stützpunkte)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            self.AxisList.addItem(item)

            if i == 0:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)

            self.AxisList.addItem(item)

    def addItem(self):
        item = QtWidgets.QListWidgetItem(f"Axis {len(self.AxisManager.axis)}")
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        if len(self.AxisManager.axis) == 1:
            item.setCheckState(QtCore.Qt.Checked)
            self.selected_line_idx_new = self.AxisList.row(item)
        else:
            item.setCheckState(QtCore.Qt.Unchecked)

        self.AxisList.addItem(item)

    def linestring2polylineobj(self):
        f = pyDM.PolylineFactory()
        # create polylines and add them to the odm
        for pt in self.axis:
            f.addPoint(pt[0], pt[1])  # ,pt[2])

        self.addLineToODM(f.getPolyline())

    def addLineToODM(self,line):
        self.AxisManager.addLine(line)

    def mousePressEvent(self, mouseEvent):
        if mouseEvent.button() == QtCore.Qt.LeftButton and self.DrawAxis:
            self.width = self.size().width()
            self.height = self.size().height()

            self.axis.append(self.pixel2world(mouseEvent.x(),mouseEvent.y()))

            if len(self.axis) == 1:
                self.drawAxis(firstPoint=True)
                #self.dataRefresh()
            elif len(self.axis) > 1:
                self.drawAxis()
                #self.dataRefresh()


        if mouseEvent.button() == QtCore.Qt.RightButton and self.axis != [] and self.DrawAxis:
            self.linestring2polylineobj()

            self.currentaxis = self.AxisManager.axis[0]

            if len(self.AxisManager.axis) == 1:
                self.polylinePicked.emit(self.AxisManager.axis[0])

            self.axis = []
            self.addItem()

        if mouseEvent.button() == QtCore.Qt.LeftButton and not self.DrawAxis:
            try:
                pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
                line = self.AxisManager.getByCoords(pt[0],pt[1])
                self.activeLineIdx = self.odm2idx[line[0].info().get(0)]
                self.setItemChecked(self.activeLineIdx)
                self.dataRefresh()

            except Exception as e:
                return

# Create custom cursor and change the cursor, depends on the mode in which the widget is setto:
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
            #self.setCursor(Qt.CrossCursor)
            self.setCursor(self.crossCursor)
        else:
            self.unsetCursor()