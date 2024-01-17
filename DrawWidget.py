#import PyQt5.QtCore.QByteArray
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication
from PyQt5.QtOpenGL import *
from OpenGL.GL import *
from OpenGL.GLUT import *
import sys
import math
import numpy as np
from sortedcontainers import SortedDict
from Camera import Camera
import glm

from Geometry import GeometryType, Point3D


class DrawWidget(QGLWidget):
    def __init__(self, parent=None):
        super(DrawWidget, self).__init__(parent)
        self.setMouseTracking(True)
        # self.setMinimumSize(500, 500)
        self.camera = Camera()
        self.camera.setSceneRadius(2)
        self.camera.reset()
        self.isPressed = False
        self.oldx = self.oldy = 0
        self.ptList = None
        self.axisList = None
        self.Data = None
        self.PointIds = None
        self.Center = None
        self.Scale = None
        self.ChangeColoring = False
        self.SelectPoint = False
        self.SelectRectangle = False
        self.LeftCtrlPressed = False
        self.RightCtrlPressed = False
        self.PointFont = QtGui.QFont("Arial", 8)
        self.FaceFont = QtGui.QFont("Arial", 8)
        self.AxisFont = self.PointFont
        self.FaceFont.setUnderline(True)
        self.FontColor = QtGui.QColor(QtCore.Qt.white)
        self.resetStretchData()

        self.cmap = {0:[210,210,210],1:[180,180,180],
        2:[135,70,10],3:[210,210,210],
        4:[145,200,0],5:[72,128,0],
        6:[180,20,20],7:[255,255,200],
        8:[220,105,20],9:[0,95,255],
        10:[100,80,60],11:[70,70,70],
        12:[35,35,35],13:[255,250,90],
        14:[255,220,0],15:[235,200,60],
        16:[190,160,50]}

        #mouse click:
        self.cicked = QtCore.pyqtSignal() #pyqtSignal()


    def setOrthoView(self,rotation):
        x = rotation[0,0]
        y = rotation[0,1]
        self.camera.setOrthoView(-y,x)
        self.update()

    def setGroundView(self):
        self.camera.setGroundView()
        self.update()

    def resetStretchData(self):
        self.StrechRefPt = [0, 0 ,0]
        self.StrechVecA  = [1, 0, 0]
        self.StrechVecN  = [0, 1, 0]
        self.StrechFactor = 1

    def setStretchAxis(self,coor1,coor2):
        self.StrechRefPt = [coor1[0],coor1[1],0]
        self.StrechVecA  = [coor2[0]-coor1[0],   coor2[1]-coor1[1],  0]
        len = math.sqrt(sum([math.pow(self.StrechVecA[i],2) for i in range(3)]))
        for i in range(3):
            self.StrechVecA[i] /= len
        self.StrechVecN  = [-self.StrechVecA[1], self.StrechVecA[0], 0]
        self.dataRefresh()

    def setStretch(self,value):
        # set stretch factor -> self.StrechFactor
        self.StrechFactor = math.pow(10, value/5.)
        self.dataRefresh()

    def setData(self, data):
        self.Data = data
        self.PointIds = data['Id']

    def _minmax(self, min, max, coords):
        for i, v in enumerate(coords):
            if v < min[i]:
                min[i] = v
            if v > max[i]:
                max[i] = v

    def getDataExtends(self):
        min = [self.Data["x"].min(), self.Data["y"].min(), self.Data["z"].min()]
        max = [self.Data["x"].max(), self.Data["y"].max(), self.Data["z"].max()]
        return min, max

    def _normalize(self, coor):
        #transform coordinates based on strech axis
        vec = [ coor[i]-self.StrechRefPt[i] for i in range(3) ]
        dz = [0, 0, vec[2]]
        a =  sum([vec[i] * self.StrechVecA[i] for i in range(3)])
        n =  sum([vec[i] * self.StrechVecN[i] for i in range(3)]) * self.StrechFactor
        vec = [ self.StrechRefPt[i] + a*self.StrechVecA[i] + n*self.StrechVecN[i] + dz[i] for i in range(3) ]

        #normalize coordinates for better viewing
        return [(vec[i] - self.Center[i]) * self.Scale for i in range(3)]

    def initAxis(self):
        self.axisList = glGenLists(2)
        glNewList(self.axisList, GL_COMPILE)
        glBegin(GL_LINES)
        glColor3f(1, 0, 0)
        glVertex(0, 0, 0)
        glVertex(1, 0, 0)

        glColor3f(0, 1, 0)
        glVertex(0, 0, 0)
        glVertex(0, 1, 0)

        glColor3f(0, 0, 1)
        glVertex(0, 0, 0)
        glVertex(0, 0, 1)
        glEnd()
        glEndList()

    def setTansparency(self, value):
        self.FaceTansparency = value
        self.dataRefresh()

    def dataRefresh(self):
        if len(self.Data) == 0:
            self.ptList = None
            self.PointLabels = []
            self.FaceLabels = []
            return

        self.ptList = glGenLists(1)
        glNewList(self.ptList, GL_COMPILE)

        min, max = self.getDataExtends()

        self.Center = [(min[i] + max[i]) / 2. for i in range(3)]

        maxdist = 0
        for i in range(3):
            v = max[i] - self.Center[i]
            if v > maxdist:
                maxdist = v
        if maxdist == 0:
            self.Scale = 1.
        else:
            self.Scale = 1. / maxdist
        #Färbung der Punkte
        glColor(1, 1, 1) #obj.color.redF(), obj.color.greenF(), obj.color.blueF())
        glBegin(GL_POINTS)
        for idx in range(self.Data["x"].shape[0]):
            coords = [self.Data["x"][idx], self.Data["y"][idx], self.Data["z"][idx]]
            glVertex(self._normalize(coords))

        glEnd()

        glEndList()

        self.update()

    def changeColoring(self):
        #Color by hight:
        if self.ChangeColoring == True:
            colormap = SortedDict([(0, (0, 153, 51)), (33, (153, 230, 0)), (66, (222, 222, 31)), (100, (135, 87, 18))])

            glNewList(self.ptList, GL_COMPILE)
            min, max = self.getDataExtends()

            steps = 256
            dz = (max[2] - min[2])/(steps - 1)
            lut = []

            for i in range(steps):
                percentage = (i / steps) * 100
                idx1 = colormap.bisect_right(percentage) - 1
                if idx1 == len(colormap) - 1:
                    idx1 -= 1
                idx2 = idx1 + 1

                val1 = colormap.peekitem(idx1)
                val2 = colormap.peekitem(idx2)

                f = (percentage - val1[0]) / (val2[0] - val1[0])
                c = [(val1[1][i] + f * (val2[1][i] - val1[1][i])) / 255 for i in range(3)]
                lut.append(c)

            glBegin(GL_POINTS)
            for i in range(len(self.Data['z'])):
                idx = int((self.Data['z'][i] - min[2]) / (max[2] - min[2]) * 255)
                coords = [self.Data["x"][i], self.Data["y"][i], self.Data["z"][i]]
                glColor(lut[idx])
                glVertex(self._normalize(coords))
            glEnd()

            glEndList()
            self.update()

        #color by classes:
        elif self.ChangeColoring == False:
            glNewList(self.ptList, GL_COMPILE)

            glColor(1, 1, 1)  # obj.color.redF(), obj.color.greenF(), obj.color.blueF())
            glBegin(GL_POINTS)
            for idx in range(self.Data["x"].shape[0]):
                coords = [self.Data["x"][idx], self.Data["y"][idx], self.Data["z"][idx]]
                glVertex(self._normalize(coords))
            glEnd()

            glEndList()

            self.update()

    def ClassifySinglePoint(self):
        glNewList(self.ptList, GL_COMPILE)
        id = []
        for i in range(len(self.Data['z'])):
            glStencilFunc(GL_ALWAYS,i+1,-1)
            self.Data['Id'][i]
            id.append(self.Data['Id'][i])

        #print(id[0])

        glEndList()
        self.update()

    def paintGL(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        self.camera.transform()
        glMatrixMode(GL_MODELVIEW);
        glLoadIdentity();

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT | GL_STENCIL_BUFFER_BIT)

        glEnable(GL_STENCIL_TEST)
        #glStencilMask(255)
        #glStencilFunc(GL_ALWAYS,1,255)
        glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE)

        glDepthFunc(GL_LEQUAL)
        glEnable(GL_DEPTH_TEST)

        glFrontFace(GL_CCW);

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        if self.ptList:
            glCallList(self.ptList)

        # draw axsis in corner
        glViewport(0, 0, 100, 100)
        glMatrixMode(GL_PROJECTION)

        glLoadIdentity()
        self.camera.transformAxis()
        glMatrixMode(GL_MODELVIEW);
        glLoadIdentity();

        # glEnable( GL_DEPTH_TEST );
        glDisable(GL_DEPTH_TEST);
        if self.axisList == None:
            self.initAxis()
        glCallList(self.axisList)
        glColor(self.FontColor.redF(), self.FontColor.greenF(), self.FontColor.blueF())
        self.renderText(1, 0, 0, "x", self.AxisFont)
        self.renderText(0, 1, 0, "y", self.AxisFont)
        self.renderText(0, 0, 1, "z", self.AxisFont)

        # restore old view port
        glViewport(0, 0, self.widthInPixels, self.heightInPixels)

        glFlush()

    def resizeGL(self, widthInPixels, heightInPixels):
        self.widthInPixels = widthInPixels
        self.heightInPixels = heightInPixels
        self.camera.setViewportDimensions(widthInPixels, heightInPixels)
        glViewport(0, 0, widthInPixels, heightInPixels)

    def initializeGL(self):
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClearDepth(1.0)
        glClearStencil(1)

    def mouseMoveEvent(self, mouseEvent):
        if int(mouseEvent.buttons()) != QtCore.Qt.NoButton:
            # user is dragging
            delta_x = mouseEvent.x() - self.oldx
            delta_y = self.oldy - mouseEvent.y()
            if int(mouseEvent.buttons()) & QtCore.Qt.LeftButton and QApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
                self.camera.orbit(self.oldx, self.oldy, mouseEvent.x(), mouseEvent.y())
            elif int(mouseEvent.buttons()) & QtCore.Qt.RightButton:
                self.camera.translateSceneRightAndUp(delta_x, delta_y)
            elif int(mouseEvent.buttons()) & QtCore.Qt.MidButton:
                self.camera.dollyCameraForward(3 * (delta_x + delta_y), False)
            self.update()
        self.oldx = mouseEvent.x()
        self.oldy = mouseEvent.y()

    def mousePressEvent(self, mouseEvent):
        if mouseEvent.button() == QtCore.Qt.LeftButton:
            if self.SelectPoint == True:
                self.color = bytearray(4)
                self.depth = GLfloat()
                self.index = GLuint()

                glFlush()
                glFinish()
                glPixelStorei(GL_UNPACK_ALIGNMENT,1)

                glReadPixels(mouseEvent.x(), self.heightInPixels - mouseEvent.y() - 1, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, self.color)
                glReadPixels(mouseEvent.x(), self.heightInPixels - mouseEvent.y() - 1, 1, 1, GL_DEPTH_COMPONENT, GL_FLOAT, self.depth)
                glReadPixels(mouseEvent.x(), self.heightInPixels - mouseEvent.y() - 1, 1, 1, GL_STENCIL_INDEX, GL_UNSIGNED_INT, self.index)

                self.ClassifySinglePoint()

    def mouseReleaseEvent(self, e):
        self.LeftPressed = False

    def wheelEvent(self, event):
        #pt = event.delta()
        numPixels = event.pixelDelta();
        numDegrees = event.angleDelta();
        if numPixels.isNull() is False:
            if abs(numPixels.x()) > abs(numPixels.y()):
                steps = numPixels.x()
            else:
                steps = numPixels.y()
        else:
            if abs(numDegrees.x()) > abs(numDegrees.y()):
                steps = numDegrees.x()
            else:
                steps = numDegrees.y()
        self.camera.dollyCameraForward(steps, False)
        self.update()

##    def mouseDoubleClickEvent(self, mouseEvent):
##        print "double click"
##
   # def mousePressEvent(self, e):
        #if e.button() == QtCore.LeftButton:
    #    ptcoords = (e.x()/self.Scale,e.y()/self.Scale)
        #print("mouse coords:", (e.x()/self.Scale,e.y(),e.z()))
        #print(self.Scale)
     #   self.isPressed = True
      #  return ptcoords

   # def mouseReleaseEvent(self, e):
    #    print("mouse release")
     #   self.isPressed = False
#