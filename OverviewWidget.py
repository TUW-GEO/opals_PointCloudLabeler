from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import svgwrite
from osgeo import gdal
from opals import pyDM

class OverviewWidget(QSvgWidget):

    def __init__(self, *args):
        QSvgWidget.__init__(self, *args)
        self.setMouseTracking(True)
        self.shd_filename = None
        self.shd_geotrafo = None
        self.shd_rasterSize = None
        self.shd_bbox = None
        self.axis = []
        self.selection = None
        self.width = None
        self.height = None
        self.Axis = False
        #self.width, self.height = self.size(), self.height()
        self.lines = []
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

    def setSelectionBox(self,p1,p2,p3,p4):
        self.selection = [(p1[0][0], p1[0][1]),
                          (p2[0][0], p2[0][1]),
                          (p3[0][0], p3[0][1]),
                          (p4[0][0], p4[0][1]),
                          (p1[0][0], p1[0][1]) ]

    def world2pixel(self,x,y):
        pass
    def pixel2world(self):
        pass

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

        self.svg.viewbox(minx=minx, miny=miny, width=self.dx, height=self.dy)
        self.svg.add(self.svg.image(href=self.shd_filename, insert=(minx,miny), size=(self.dx,self.dy)))

        if self.axis:
            for idx in range(len(self.axis) - 1):
                pt1 = (self.axis[idx][0] - self.red_x, self.red_y - self.axis[idx][1])
                pt2 = (self.axis[idx + 1][0] - self.red_x, self.red_y - self.axis[idx + 1][1])
                self.svg.add(self.svg.line(start=pt1, end=pt2, stroke='blue', stroke_width=2))

        if self.selection:
            for idx in range(len(self.selection)-1):
                pt1 = (self.selection[idx][0]-self.red_x,self.red_y-self.selection[idx][1])
                pt2 = (self.selection[idx+1][0]-self.red_x,self.red_y-self.selection[idx+1][1])
                self.svg.add(self.svg.line(start=pt1, end=pt2, stroke='red', stroke_width=1))

        svg_xml = self.svg.tostring()
        svg_bytes = bytearray(svg_xml, encoding ='utf-8')
        self.renderer().load(svg_bytes)
        self.renderer().setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
        self.update()

    def drawAxis(self):
        if self.lines == []:
            color = 'blue'
        else:
            color = 'lightblue'

        pt1 = (self.axis[-2][0] - self.red_x, self.red_y - self.axis[-2][1])
        pt2 = (self.axis[-1][0] - self.red_x, self.red_y - self.axis[-1][1])

        self.svg.add(self.svg.line(start=pt1, end=pt2, stroke=color, stroke_width=self.dx/100.))

        svg_xml = self.svg.tostring()
        svg_bytes = bytearray(svg_xml, encoding='utf-8')
        self.renderer().load(svg_bytes)
        self.renderer().setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
        self.update()

    def setAxisODM(self,odm):
        self.axis_odm = odm

    def mousePressEvent(self, mouseEvent):
        if mouseEvent.button() == QtCore.Qt.LeftButton and self.Axis:
            self.width = self.size().width()
            self.height = self.size().height()

            self.axis.append([mouseEvent.x()/self.width*self.dx + self.red_x, self.red_y - mouseEvent.y()/self.height*self.dy])

            if len(self.axis) > 1:
                self.drawAxis()
        if mouseEvent.button() == QtCore.Qt.RightButton and self.axis != []:
            f = pyDM.PolylineFactory()

            # create polylines and add them to the odm
            for pt in self.axis:
                f.addPoint(pt[0],pt[1])

            self.axis_odm.addPolyline(f.getPolyline())
            pi = self.axis_odm.getPolylineIndex()
            self.axis_odm.save()
            self.lines.append(pi)
            self.axis = []

        if mouseEvent.button() == QtCore.Qt.LeftButton and not self.Axis:
            self.searchLine = pi.searchGeometry(1, pyDM.Point(mouseEvent.x()/self.width*self.dx,self.red_y - mouseEvent.y()/self.height*self.dy))