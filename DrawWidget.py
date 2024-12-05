from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication
from PyQt5.QtOpenGL import *
from OpenGL.GL import *
from OpenGL.GL.framebufferobjects import *
import math
import numpy as np
from sortedcontainers import SortedDict
from Camera import Camera
from glPointCloud import glPointCloud, COLOR_MODE_ATTR, COLOR_MODE_CLASS, COLOR_MODE_INDEX
import struct
import copy


class DrawWidget(QGLWidget):

    def __init__(self, parent=None):
        super(DrawWidget, self).__init__(parent)
        self.setMouseTracking(True)
        self.camera = Camera()
        self.camera.setSceneRadius(2)
        self.camera.reset()
        self.PointFont = QtGui.QFont("Arial", 8)
        self.FaceFont = QtGui.QFont("Arial", 8)
        self.AxisFont = self.PointFont
        self.FontColor = QtGui.QColor(QtCore.Qt.white)

        self.glPointCloud = glPointCloud()
        self.ClassColorPal = glPointCloud.generate_color_map()

        # Mouse click signal
        self.clicked = QtCore.pyqtSignal()  # pyqtSignal()

        self._reset()  # Call the reset method to initialize/reset attributes

    def _reset(self):
        """Resets the widget attributes to their initial state."""
        self.isPressed = False
        self.oldx = self.oldy = 0
        self.axisList = None
        self.Data = None
        self.glVertices = None    # for drawing in opengl
        self.glAttrValues = None  # for drawing in opengl
        self.PointIds = None
        self.Center = None
        self.Scale = None
        self.ChangeColoring = False
        self.SelectPoint = False
        self.SelectRectangle = False
        self.LeftCtrlPressed = False
        self.RightCtrlPressed = False
        self.currentClass = 0
        self._currentColor = 1
        self.PointSize = 1
        self.classificationData = None
        self.start = None
        self.stop = None
        self.mouse = None
        self.wheel = 0
        self.update()

    def _clear(self):
        self.update()

    def setClassifcationData(self, classificationData):
        self.classificationData = classificationData
        for id, value in classificationData.items():
            color = value[1]
            if id >= self.ClassColorPal.shape[0]:
                raise Exception(f"class id {id} exceeds number of currently supported color map entries ({self.ClassColorPal.shape[0]})")
            self.ClassColorPal[id][0] = color[0]/255.
            self.ClassColorPal[id][1] = color[1]/255.
            self.ClassColorPal[id][2] = color[2]/255.

    def setOrthoView(self,rotation):
        x = rotation[0,0]
        y = rotation[0,1]
        self.camera.setOrthoView(-y,x)
        self.update()

    def setGroundView(self):
        self.camera.setGroundView()
        self.update()

    def setData(self, data):
        try:
            self.Data = data
            self.reset = copy.deepcopy(data['Classification'])
        except Exception as e:
            return

    @property
    def currentColor(self):
        return self.glPointCloud.displayMode

    @currentColor.setter
    def currentColor(self, mode):
        self.glPointCloud.displayMode = mode

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

        # reduce rendering coordinates for better precision of large coordinate values
        coord_x = ((self.Data["x"]-self.Center[0])*self.Scale).astype(np.float32)
        coord_y = ((self.Data["y"]-self.Center[1])*self.Scale).astype(np.float32)
        coord_z = ((self.Data["z"]-self.Center[2])*self.Scale).astype(np.float32)
        self.glVertices = np.hstack((coord_x.reshape(-1, 1), coord_y.reshape(-1, 1), coord_z.reshape(-1, 1)))
        self.glAttrValues = self.Data["z"].astype(np.float32)  # we could use a different attribute as well
        self.glPointCloud.set_data(self.glVertices, self.glAttrValues, self.Data['Classification'] )

        # upload class color map
        self.glPointCloud.classColorPal = self.ClassColorPal
        self.glPointCloud.attributeRange = (min[2], max[2])

        self.update()

    def Reset(self):
        self.Data['Classification'] = self.reset
        self.reset = copy.deepcopy(self.Data['Classification'])
        self.dataRefresh()

    def deleteReset(self):
        self.reset = self.Data['Classification']

    def WindowPicking(self, width, height, posX, posY):
        self.makeCurrent()

        Width = abs(width)
        Height = abs(height)

        idxPt = self.glPointCloud.select(posX, self.heightInPixels - posY - Height, Width, Height)

        for pt in idxPt:
            self.Data['Classification'][pt] = self.currentClass
            self.Data['_manuallyClassified'][pt] = 1

    def Picking(self, singlePoint = True):

        if singlePoint:
            if self.wheel == 0:
                self.WindowPicking(1, 1, self.mouse[0], self.mouse[1])

            else:
                width = int(abs(self.wheel*2))
                height = int(abs(self.wheel*2))
                minx = self.mouse[0] - abs(self.wheel)
                miny = self.mouse[1] - abs(self.wheel)
                self.WindowPicking(width, height, minx, miny)


        else:
            minx = min(self.start[0], self.stop[0])
            miny = min(self.start[1], self.stop[1])
            width = int(abs(self.start[0] - self.stop[0]))
            height = int(abs(self.start[1] - self.stop[1]))

            self.WindowPicking(width,height,minx,miny)

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

        if renderScreen and self.Data:
            #glCallList(self.ptList)
            viewMat = self.camera.getViewMatrix()
            projMat = self.camera.getProjectionMatrix()
            self.glPointCloud.draw(pointSize=self.PointSize, projMat=projMat, viewMat=viewMat)

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()

            # draw axsis in corner
            glViewport(0, 0, 100, 100)
            glMatrixMode(GL_PROJECTION)

            glLoadIdentity()
            self.camera.transformAxis()
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()

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

        glFlush()

    def resizeGL(self, widthInPixels, heightInPixels):
        self.widthInPixels = widthInPixels
        self.heightInPixels = heightInPixels
        self.camera.setViewportDimensions(widthInPixels, heightInPixels)
        glViewport(0, 0, widthInPixels, heightInPixels)

    def initializeGL(self):
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClearDepth(1.0)
        self.glPointCloud.initíalize()


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