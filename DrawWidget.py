from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication
from PyQt5.QtOpenGL import *
from OpenGL.GL import *
from OpenGL.GL.framebufferobjects import *
import math
import numpy as np
from sortedcontainers import SortedDict
from Camera import Camera
import struct
import copy


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
        self.ptListids = None
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
        self.FontColor = QtGui.QColor(QtCore.Qt.white)
        self.resetStretchData()
        self.currentClass = 0
        self.currentColor = 1
        self.PointSize = 1
        self.classificationData = None

        #mouse click:
        self.cicked = QtCore.pyqtSignal() #pyqtSignal()

        #paint
        self.start = None
        self.stop = None
        self.mouse = None
        self.wheel = 0

    def setClassifcationData(self, classificationData):
        self.classificationData = classificationData

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
        self.reset = copy.deepcopy(data['Classification'])

    def _minmax(self, min, max, coords):
        for i, v in enumerate(coords):
            if v < min[i]:
                min[i] = v
            if v > max[i]:
                max[i] = v

    def getDataExtends(self):
        if len(self.Data["x"]) == 0:
            return [0.,0.,0.], [0.,0.,0.]
        else:
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

    def setPointSize(self, value):
        try:
            self.PointSize = value
            self.dataRefresh()
        except Exception as e:
         return

    def createColorlist(self):
        glNewList(self.ptList, GL_COMPILE)
        if self.currentColor == 1:
            glPointSize(self.PointSize)
            glBegin(GL_POINTS)
            for idx in range(self.Data['x'].shape[0]):
                classId = self.Data['Classification'][idx]
                assert( classId in self.classificationData )   # must be always the case
                c = [self.classificationData[classId][1][i] / 255 for i in range(3)]

                coords = [self.Data["x"][idx], self.Data["y"][idx], self.Data["z"][idx]]
                glColor(c)
                glVertex(self._normalize(coords))
            glEnd()

        elif self.currentColor == 2:
            glPointSize(self.PointSize)
            colormap = SortedDict([(0, (0, 153, 51)), (33, (153, 230, 0)), (66, (222, 222, 31)), (100, (135, 87, 18))])

            min, max = self.getDataExtends()

            steps = 256
            dz = (max[2] - min[2]) / (steps - 1)
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

    def createIdList(self):
        glNewList(self.ptListids,GL_COMPILE)

        glPointSize(self.PointSize)
        glBegin(GL_POINTS)
        for i in range(self.Data["x"].shape[0]):
            coords = [self.Data["x"][i], self.Data["y"][i], self.Data["z"][i]]
            r, g, b = self.Index2Color(i)
            glColor3ub(r, g, b)
            glVertex(self._normalize(coords))
        glEnd()

        glEndList()

    def dataRefresh(self):
        if len(self.Data) == 0:
            self.ptList = None
            return

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

        self.ptList = glGenLists(1)
        self.ptListids = glGenLists(3)

        self.createColorlist()
        self.createIdList()

        self.update()

    def Reset(self):
        self.Data['Classification'] = self.reset
        self.reset = copy.deepcopy(self.Data['Classification'])
        self.dataRefresh()

    def deleteReset(self):
        self.reset = self.Data['Classification']

    def Index2Color(self,i):
        r, g, b, _ = struct.Struct('<I').pack(i + 1 & 0xFFFFFFFF)
        return r, g, b

    def Color2Index(self,byteArray):
        return byteArray[0] + byteArray[1]*256 + byteArray[2]*256*256 -1

    def multiPtPicking(self,widht,height,posX,posY):
        #posX and posY are the coordinates of the top left corner
        #of the rectangle; width and hight are the dimensions of the
        #rectangle

        Width = abs(widht)
        Height = abs(height)

        idxPt = []

        posBuffer = glReadPixels(posX, self.heightInPixels - posY - Height, Width, Height, GL_RGBA, GL_UNSIGNED_BYTE)
        posColArr = np.frombuffer(posBuffer, dtype=np.uint8)
        posColArr_idx0 = posColArr[0::4]    # take every 4 byte starting from 0 index
        posColArr_idx1 = posColArr[1::4]    # take every 4 byte starting from 1 index
        posColArr_idx2 = posColArr[2::4]    # take every 4 byte starting from 2 index
        # convert split col array into single id array
        posIds = posColArr_idx0.astype(int) + posColArr_idx1*256 + posColArr_idx2*256*256 - 1
        # ignore empty ids (-1), make ids unique and convert it to a list
        idxPt = np.unique(posIds[posIds>=0]).tolist()

        for pt in idxPt:
            self.Data['Classification'][pt] = self.currentClass
            self.Data['_manuallyClassified'][pt] = 1

    def Picking(self, singlePoint = True):
        self.makeCurrent()
        self.paintGL(False)
        glReadBuffer(GL_BACK)

        if singlePoint:
            if self.wheel == 0:
                self.multiPtPicking(1, 1, self.mouse[0], self.mouse[1])

            else:
                width = int(abs(self.wheel*2))
                height = int(abs(self.wheel*2))
                minx = self.mouse[0] - abs(self.wheel)
                miny = self.mouse[1] - abs(self.wheel)
                self.multiPtPicking(width, height, minx, miny)


        else:
            minx = min(self.start[0], self.stop[0])
            miny = min(self.start[1], self.stop[1])
            width = int(abs(self.start[0] - self.stop[0]))
            height = int(abs(self.start[1] - self.stop[1]))

            self.multiPtPicking(width,height,minx,miny)

        self.dataRefresh()

    def paintGL(self,renderScreen = True):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        self.camera.transform()

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glDepthFunc(GL_LEQUAL)
        glEnable(GL_DEPTH_TEST)

        glFrontFace(GL_CCW)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        if renderScreen and self.ptList:
            glCallList(self.ptList)

            glMatrixMode(GL_MODELVIEW);
            glLoadIdentity();

            # draw axsis in corner
            glViewport(0, 0, 100, 100)
            glMatrixMode(GL_PROJECTION)

            glLoadIdentity()
            self.camera.transformAxis()
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity();

            glDisable(GL_DEPTH_TEST)
            if self.axisList == None:
                self.initAxis()
            glCallList(self.axisList)
            glColor(self.FontColor.redF(), self.FontColor.greenF(), self.FontColor.blueF())
            self.renderText(1, 0, 0, "x", self.AxisFont)
            self.renderText(0, 1, 0, "y", self.AxisFont)
            self.renderText(0, 0, 1, "z", self.AxisFont)

            # restore old view port
            glViewport(0, 0, self.widthInPixels, self.heightInPixels)

            rect_selection = False
            pt_selection = False
            if self.start and self.stop and self.SelectRectangle:
                rect_selection = True
            elif self.mouse and self.SelectPoint:
                pt_selection = True

            if rect_selection or pt_selection:
                # draw selection box
                # we switch to orthogonal view with 'windows coordinates'. therefore, we can directly use
                # the mouse coordinates for drawing
                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                glOrtho(0, self.widthInPixels, self.heightInPixels, 0, -self.camera.farPlane, self.camera.farPlane)

                if rect_selection:
                    glBegin(GL_LINE_LOOP)
                    glColor3f(0.7, 0.7, 0.7)  # color for selection rectangle
                    glVertex(self.start[0], self.start[1], 0)
                    glVertex(self.stop[0],  self.start[1], 0)
                    glVertex(self.stop[0],  self.stop[1],  0)
                    glVertex(self.start[0], self.stop[1],  0)
                    glEnd()
                elif pt_selection:
                    glBegin(GL_LINE_LOOP)
                    glColor3f(0.7, 0.7, 0.7) # color for selection rectangle
                    glVertex(self.mouse[0] - self.wheel, self.mouse[1] + self.wheel, 0)
                    glVertex(self.mouse[0] + self.wheel, self.mouse[1] + self.wheel, 0)
                    glVertex(self.mouse[0] + self.wheel, self.mouse[1] - self.wheel, 0)
                    glVertex(self.mouse[0] - self.wheel, self.mouse[1] - self.wheel, 0)
                    glEnd()

        elif self.ptListids:
            glCallList(self.ptListids)

        glFlush()

    def resizeGL(self, widthInPixels, heightInPixels):
        self.widthInPixels = widthInPixels
        self.heightInPixels = heightInPixels
        self.camera.setViewportDimensions(widthInPixels, heightInPixels)
        glViewport(0, 0, widthInPixels, heightInPixels)

    def initializeGL(self):
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClearDepth(1.0)

    def mousePressEvent(self, mouseEvent):
        self.oldx = mouseEvent.x()
        self.oldy = mouseEvent.y()
        if mouseEvent.button() == QtCore.Qt.LeftButton:
            if self.SelectPoint:
                self.mouse = (mouseEvent.x(), mouseEvent.y())
                self.Picking(True)
            elif self.SelectRectangle:
                self.start = (mouseEvent.x(), mouseEvent.y())

    def mouseMoveEvent(self, mouseEvent):
        if int(mouseEvent.buttons()) != QtCore.Qt.NoButton:
            # user is dragging
            delta_x = mouseEvent.x() - self.oldx
            delta_y = self.oldy - mouseEvent.y()

            if int(mouseEvent.buttons()) & QtCore.Qt.LeftButton:
                if QApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
                    self.camera.orbit(self.oldx, self.oldy, mouseEvent.x(), mouseEvent.y())
                elif self.SelectRectangle:
                    self.stop = (mouseEvent.x(), mouseEvent.y())
                elif self.SelectPoint:
                    self.mouse = (mouseEvent.x(), mouseEvent.y())
                    self.Picking(True)

            elif int(mouseEvent.buttons()) & QtCore.Qt.RightButton:
                self.camera.translateSceneRightAndUp(delta_x, delta_y)

            elif int(mouseEvent.buttons()) & QtCore.Qt.MidButton:
                self.camera.dollyCameraForward(3 * (delta_x + delta_y), False)
            self.update()

        #detect mouse position without pressing any mouse button
        elif int(mouseEvent.button()) == QtCore.Qt.NoButton:
            if self.SelectPoint:
                self.mouse = (mouseEvent.x(), mouseEvent.y())
            else:
                self.wheel = 0
            self.update()

        self.oldx = mouseEvent.x()
        self.oldy = mouseEvent.y()

    def mouseReleaseEvent(self, mouseEvent):
        if mouseEvent.button() == QtCore.Qt.LeftButton:
            if self.SelectRectangle:
                self.stop = (mouseEvent.x(), mouseEvent.y())
                self.Picking(False)

                # reset selection points
                self.start = self.stop = None
                self.update()

            elif self.SelectPoint:
                self.mouse = None

    def wheelEvent(self, event):
        #if not self.SelectPoint:
        if QApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
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

        else:
            self.wheel += event.angleDelta().y()/120   #can be positive or negative
            self.update()