from PyQt5 import QtCore, QtWidgets, QtGui, uic
from PyQt5.QtSvg import QSvgWidget
import numpy as np
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import svgwrite
from osgeo import gdal
from opals import pyDM

class OverviewWidget(QSvgWidget):
    polylinePicked = QtCore.pyqtSignal(object)

    def __init__(self, *args):
        QSvgWidget.__init__(self, *args)
        self.setMouseTracking(True)
        self.shd_filename = None
        self.shd_geotrafo = None
        self.shd_rasterSize = None
        self.shd_bbox = None
        self.axis = []
        self.linestring = None
        self.lines = []
        self.pis = []
        self.selection = None
        self.width = None
        self.height = None
        self.Axis = False
        self.selected_line_idx_new = None
        self.selected_line_idx_old = 0
        self.AxisManagement = None


    def setAxisManagment(self, listWidget):
        self.AxisManagement = listWidget
        self.AxisManagement.itemChanged.connect(self.handleItemChanged)

    def changeAxisWidth(self):
        pass

    def pixel2coords(self,px,py):
        x = self.shd_geotrafo[0] + px * self.shd_geotrafo[1] + py * self.shd_geotrafo[2]
        y = self.shd_geotrafo[3] + px * self.shd_geotrafo[4] + py * self.shd_geotrafo[5]
        return x,y

    def setShading(self,filename):
        self.shd_filename = filename
        ds = gdal.Open(self.shd_filename, gdal.GA_ReadOnly)
        self.shd_geotrafo = ds.GetGeoTransform()
        self.shd_rasterSize = (600,400)#(ds.RasterXSize, ds.RasterYSize)
        #self.width, self.height = self.width(), self.height()
        self.shd_bbox = [self.pixel2coords(0,0), self.pixel2coords(ds.RasterXSize, ds.RasterYSize)]
        del ds

    def setAxis(self, linestring):
        self.axis = linestring

    # def removeAxis(self, line_idx):
    #      if 0 <= line_idx < len(self.lines):
    #          del self.lines[line_idx]
    #          self.AxisManagement.takeItem(line_idx)
    #          self.drawAxis()

    def setSelectionBox(self,p1,p2,p3,p4):
        self.selection = [(p1[0][0], p1[0][1]),
                          (p2[0][0], p2[0][1]),
                          (p3[0][0], p3[0][1]),
                          (p4[0][0], p4[0][1]),
                          (p1[0][0], p1[0][1]) ]

    def world2pixel(self, x, y):
        a0, a1, a2, a3, a4, a5 = self.shd_geotrafo

        # Transformation als Matrixoperation
        px = (x - a0)
        py = (a3 - y)

        return px, py

    def pixel2world(self, px, py):
        #a0, a1, a2, a3, a4, a5 = self.shd_geotrafo

        red_x = self.shd_bbox[0][0]
        red_y = self.shd_bbox[0][1]

        dx = self.shd_bbox[1][0] - self.shd_bbox[0][0]
        dy = self.shd_bbox[0][1] - self.shd_bbox[1][1]

        width, height = self.size().width(), self.size().height()

        norm_px = (px / width) * dx
        norm_py = (py / height) * dy

        transformation_matrix = np.array([[1, 0], [0, -1]])
        offset_vector = np.array([red_x, red_y])

        world_coords = np.dot(transformation_matrix, np.array([norm_px, norm_py])) + offset_vector
        return [world_coords[0], world_coords[1],0]

    def dataRefresh(self):
        self.svg = svgwrite.Drawing()

        # svg coordinate origin is upper left
        # use reduction point for vertical inverting coordinates:
        # svg_x = x - red_x
        # svg_Y = red_y - y
        self.red_x = self.shd_bbox[0][0]  # left coordinate of shading
        self.red_y = self.shd_bbox[0][1]  # upper coordinate of shading

        minx = self.shd_bbox[0][0] - self.red_x
        miny = self.red_y-self.shd_bbox[0][1]

        self.dx = self.shd_bbox[1][0] - self.shd_bbox[0][0]
        self.dy = self.shd_bbox[0][1] - self.shd_bbox[1][1]

        self.stroke_width = self.dx / 200.

        self.svg.viewbox(minx=minx, miny=miny, width=self.dx, height=self.dy)
        self.svg.add(self.svg.image(href=self.shd_filename, insert=(minx,miny), size=(self.dx,self.dy)))

        if self.axis:
            self.drawAxis()

        if self.selection:
            self.drawSection()

        self.update_svg()

    def drawAxis(self, activate=False):#, deactivate=False):
         if len(self.lines) < 1 or activate:
             color = 'blue'
         elif self.AxisManagement.count() > 0 or not activate:
             color = 'lightblue'

         for idx in range(len(self.axis) - 1):
             #pt1 = (self.axis[idx][0] - self.red_x, self.red_y - self.axis[idx][1])
             #pt2 = (self.axis[idx + 1][0] - self.red_x, self.red_y - self.axis[idx + 1][1])

             pt1 = self.world2pixel(self.axis[idx][0], self.axis[idx][1])
             pt2 = self.world2pixel(self.axis[idx + 1][0], self.axis[idx + 1][1])

             self.remove_line(pt1, pt2)
             self.svg.add(self.svg.line(start=pt1, end=pt2, stroke=color, stroke_width=self.stroke_width))

         self.update_svg()

    def drawSection(self):
        for idx in range(len(self.selection) - 1):
            #pt1 = (self.selection[idx][0] - self.red_x, self.red_y - self.selection[idx][1])
            #pt2 = (self.selection[idx + 1][0] - self.red_x, self.red_y - self.selection[idx + 1][1])

            pt1 = self.world2pixel(self.selection[idx][0], self.selection[idx][1])
            pt2 = self.world2pixel(self.selection[idx + 1][0], self.selection[idx + 1][1])

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

    def setAxisODM(self,odm):
        self.axis_odm = odm

    def changeAxisWidth(self,width):
        self.axis_width = width

        self.stroke_width = float(width)

        for line in self.lines:
            if line == self.currentaxis:
                self.output_polyline(line)
            else:
                self.output_polyline(line,False)

    def handleItemChanged(self, item):
        if self.selected_line_idx_new < 0:
            self.selected_line_idx_old = 0
        else:
            self.selected_line_idx_old = self.selected_line_idx_new

        if item.checkState() == QtCore.Qt.Checked:
            for i in range(self.AxisManagement.count()):
                list_item = self.AxisManagement.item(i)
                if list_item != item:
                    list_item.setCheckState(QtCore.Qt.Unchecked)

            self.selected_line_idx_new = self.AxisManagement.row(item)

        else:
            self.selected_line_idx = None

        self.changeAxis(self.lines[self.selected_line_idx_new], self.lines[self.selected_line_idx_old])

    def changeAxis(self,new, old):
        self.output_search(old, False)
        self.output_search(new)


    def output_polyline(self, line, active=True):
        for idx, part in enumerate(line.parts()):
            for p in part.points():
                self.axis.append([p.x,p.y])
        if active:
            self.drawAxis(True)
            self.currentaxis = [line]
            self.polylinePicked.emit([line])

        else:
            self.drawAxis(False)
        self.axis = []

    def output_search(self, lines, active=True):
        for idx, l in enumerate(lines):
            self.output_polyline(l,active)

    def mousePressEvent(self, mouseEvent):
        if mouseEvent.button() == QtCore.Qt.LeftButton and self.Axis:
            self.width = self.size().width()
            self.height = self.size().height()

            self.axis.append(self.pixel2world(mouseEvent.x(),mouseEvent.y()))

            if len(self.axis) > 1:
                self.drawAxis()

        if mouseEvent.button() == QtCore.Qt.RightButton and self.axis != []:
            f = pyDM.PolylineFactory()
            # create polylines and add them to the odm
            for pt in self.axis:
                f.addPoint(pt[0],pt[1])#,pt[2])

            self.axis_odm.addPolyline(f.getPolyline())
            self.axis_odm.save()

            #muss einfacher gehen
           # pt = (mouseEvent.x() / self.width * self.dx + self.red_x, self.red_y - mouseEvent.y() / self.height * self.dy)
            pt = self.pixel2world(mouseEvent.x(),mouseEvent.y())
            pi = self.axis_odm.getPolylineIndex()
            line = pi.searchGeometry(1,pyDM.Point(pt[0], pt[1], 0))
            self.lines.append(line)

            #self.lines.append([f.getPolyline()])
            self.currentaxis = self.lines[0]

            #if len(self.lines) == 1:
             #   self.polylinePicked.emit(line)

            self.axis = []

            item = QtWidgets.QListWidgetItem(f"Axis {len(self.lines)}")
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            if len(self.lines) == 1:
                item.setCheckState(QtCore.Qt.Checked)
                self.selected_line_idx_new = self.AxisManagement.row(item)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)

            self.AxisManagement.addItem(item)

        if mouseEvent.button() == QtCore.Qt.LeftButton and not self.Axis:
            pi = self.axis_odm.getPolylineIndex()
            pt = self.pixel2world(mouseEvent.x(), mouseEvent.y())
            self.searchLine = pi.searchGeometry(1, pyDM.Point(pt[0], pt[1], 0))

            #self.index = self.lines.index(self.searchLine)

            self.changeAxis(self.searchLine, self.currentaxis)
            #self.handleItemChanged(self.AxisManagement.item(self.index))

