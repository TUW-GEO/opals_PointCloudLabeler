from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import svgwrite
from osgeo import gdal

class OverviewWidget(QSvgWidget):

    def __init__(self, *args):
        QSvgWidget.__init__(self, *args)
        self.setMouseTracking(True)
        self.shd_filename = None
        self.shd_geotrafo = None
        self.shd_rasterSize = None
        self.shd_bbox = None
        self.axis = None
        self.selection = None
        self.width = None
        self.height = None
    def pixel2coords(self,px,py):
        x = self.shd_geotrafo[0] + px * self.shd_geotrafo[1] + py * self.shd_geotrafo[2]
        y = self.shd_geotrafo[3] + px * self.shd_geotrafo[4] + py * self.shd_geotrafo[5]
        return x,y

    def setShading(self,filename):
        self.shd_filename = filename
        ds = gdal.Open(self.shd_filename, gdal.GA_ReadOnly)
        self.shd_geotrafo = ds.GetGeoTransform()
        self.shd_rasterSize = (600,400)#(ds.RasterXSize, ds.RasterYSize)
        self.width, self.height = ds.RasterXSize, ds.RasterYSize
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

    def dataRefresh(self):
        svg = svgwrite.Drawing()

        # svg coordinate origin is upper left
        # use reduction point for vertical inverting coordinates:
        # svg_x = x - red_x
        # svg_Y = red_y - y
        red_x = self.shd_bbox[0][0]  # left coordinate of shading
        red_y = self.shd_bbox[0][1]  # upper coordinate of shading

        minx = self.shd_bbox[0][0] - red_x
        miny = red_y-self.shd_bbox[0][1]

        dx = self.shd_bbox[1][0] - self.shd_bbox[0][0]
        dy = self.shd_bbox[0][1] - self.shd_bbox[1][1]
        svg.viewbox(minx=minx, miny=miny, width=dx, height=dy)
        svg.add(svg.image(href=self.shd_filename, insert=(minx,miny), size=(dx,dy)))
        #self.OverviewWidget.resize(self.width, self.height)
        if self.axis:
            for idx in range(len(self.axis)-1):
                pt1 = (self.axis[idx][0]-red_x, red_y-self.axis[idx][1])
                pt2 = (self.axis[idx+1][0]-red_x, red_y-self.axis[idx+1][1])
                svg.add(svg.line(start=pt1, end=pt2, stroke='blue', stroke_width=2))

        if self.selection:
            for idx in range(len(self.selection)-1):
                pt1 = (self.selection[idx][0]-red_x,red_y-self.selection[idx][1])
                pt2 = (self.selection[idx+1][0]-red_x,red_y-self.selection[idx+1][1])
                svg.add(svg.line(start=pt1, end=pt2, stroke='red', stroke_width=1))

        svg_xml = svg.tostring()
        svg_bytes = bytearray(svg_xml, encoding ='utf-8')
        self.renderer().load(svg_bytes)
        self.renderer().setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
        self.update()

    def mousePressEvent(self, mouseEvent):
        print(mouseEvent.x(),mouseEvent.y())

    def mouseMoveEvent(self, mouseEvent):
        pass

    def mouseReleaseEvent(self, mouseEvent):
        pass