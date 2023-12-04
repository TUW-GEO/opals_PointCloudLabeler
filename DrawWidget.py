from PyQt5 import QtCore, QtGui
from PyQt5.QtOpenGL import *
from OpenGL.GL import *
from OpenGL.GLUT import *
import sys
import math
#from sets import Set as set

from Camera import Camera
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
        self.geoList = None
        self.axisList = None
        self.Data = None
        self.Center = None
        self.Scale = None
        self.WireFrame = False
        self.PointFont = QtGui.QFont("Arial", 8)
        self.FaceFont = QtGui.QFont("Arial", 8)
        self.AxisFont = self.PointFont
        self.FaceFont.setUnderline(True)
        self.PointLabels = []
        self.FaceLabels = []
        self.FontColor = QtGui.QColor(QtCore.Qt.white)
        self.ShowPointLabels = True
        self.ShowFaceLabels = True
        self.widthInPixels = None
        self.heightInPixels = None
        self.FaceTansparency = 0
        self.resetStretchData()

    def setOrthoView(self):
        if self.camera.OrthoProjection != True:
            self.camera.OrthoProjection = True
            self.update()

    def setPerspectiveView(self):
        if self.camera.OrthoProjection != False:
            self.camera.OrthoProjection = False
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
        self.dataRefesh()

    def setStretch(self,value):
        # set stretch factor -> self.StrechFactor
        self.StrechFactor = math.pow(10, value/5.)
        self.dataRefesh()

    def setData(self, data):
        self.Data = data

    def _minmax(self, min, max, coords):
        for i, v in enumerate(coords):
            if v < min[i]:
                min[i] = v
            if v > max[i]:
                max[i] = v

    def getDataExtends(self):
        min = [sys.float_info.max, sys.float_info.max, sys.float_info.max]
        max = [-sys.float_info.max, -sys.float_info.max, -sys.float_info.max]
        for obj in self.Data:
            if obj.type == GeometryType.point:
                self._minmax(min, max, obj.coords)
            elif obj.type == GeometryType.segment:
                self._minmax(min, max, obj.coords[0])
                self._minmax(min, max, obj.coords[1])
            elif obj.type == GeometryType.triangle:
                self._minmax(min, max, obj.coords[0])
                self._minmax(min, max, obj.coords[1])
                self._minmax(min, max, obj.coords[2])
        return min, max

    def _normalize(self, coor):
        #transform coordinates based on strech axis
        vec = [ coor[i]-self.StrechRefPt[i] for i in range(3) ]
        dz = [0, 0, vec[2]]
        a =  sum([vec[i] * self.StrechVecA[i] for i in range(3)])
        n =  sum([vec[i] * self.StrechVecN[i] for i in range(3)]) * self.StrechFactor
        vec = [ self.StrechRefPt[i] + a*self.StrechVecA[i] + n*self.StrechVecN[i] + dz[i] for i in range(3) ]

        #normalize coordinates for better viewing
        #return [ (coor[i]-self.Center[i])*self.Scale for i in range(3) ]
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
        self.dataRefesh()

    def dataRefesh(self):
        ##print "dataRefesh"

        if len(self.Data) == 0:
            self.geoList = None
            self.PointLabels = []
            self.FaceLabels = []
            return

        ##        if self.geoList == None:
        ##          self.geoList = glGenLists( 1 )
        ##        else:
        ##          glDeleteLists(self.geoList,1)
        ##          self.geoList = glGenLists( 1 )

        self.geoList = glGenLists(1)
        glNewList(self.geoList, GL_COMPILE)

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

        ##        if self.WireFrame == True:
        ##          glPolygonMode( GL_FRONT_AND_BACK, GL_LINE )
        ##        else:
        ##          glPolygonMode( GL_FRONT_AND_BACK, GL_FILL )

        for obj in self.Data:
            if obj.enabled == False:
                continue
            if obj.type == GeometryType.point:
                glColor(obj.color.redF(), obj.color.greenF(), obj.color.blueF())
                glBegin(GL_POINTS)
                glVertex(self._normalize(obj.coords))
                glEnd()
                pass
            elif obj.type == GeometryType.segment:
                glColor(obj.color.redF(), obj.color.greenF(), obj.color.blueF())
                glBegin(GL_LINE_STRIP)
                for c in obj.coords:
                    glVertex(self._normalize(c))
                glEnd()
            elif obj.type == GeometryType.triangle:
                alpha = 1 - self.FaceTansparency / 100.
                glColor(obj.color.redF(), obj.color.greenF(), obj.color.blueF(), alpha)
                if self.WireFrame == True:
                    glLineStipple(2, 0xAAAA);
                    pts = [self._normalize(obj.coords[idx]) for idx in range(3)]
                    for idx in range(3):
                        if obj.constr[idx] != None:
                            glDisable(GL_LINE_STIPPLE)
                        else:
                            glEnable(GL_LINE_STIPPLE)
                        glBegin(GL_LINE_STRIP)
                        glVertex(pts[(idx - 1) % 3])
                        glVertex(pts[(idx + 1) % 3])
                        glEnd()
                    glDisable(GL_LINE_STIPPLE);
                else:
                    glBegin(GL_TRIANGLES)
                    for c in obj.coords:
                        x, y, z = self._normalize(c)
                        glVertex(x, y, z)
                    glEnd()

        glEndList()

        ps = set()
        self.PointLabels = []
        self.FaceLabels = []
        for obj in self.Data:
            if obj.enabled == False:
                continue
            if obj.type == GeometryType.point:
                if not obj.id in ps:
                    ps.add(obj.id)
                    label = str(obj.id)
                    pt = Point3D(self._normalize(obj.coords))
                    self.PointLabels.append([pt, label])
            elif obj.type == GeometryType.segment:
                for idx, id in enumerate(obj.subids):
                    if not id in ps:
                        ps.add(id)
                        label = str(id)
                        pt = Point3D(self._normalize(obj.coords[idx]))
                        self.PointLabels.append([pt, label])
            elif obj.type == GeometryType.triangle:
                label = str(obj.id)
                x = (obj.coords[0][0] + obj.coords[1][0] + obj.coords[2][0]) / 3.
                y = (obj.coords[0][1] + obj.coords[1][1] + obj.coords[2][1]) / 3.
                z = (obj.coords[0][2] + obj.coords[1][2] + obj.coords[2][2]) / 3.
                pt = Point3D(self._normalize([x, y, z]))
                self.FaceLabels.append([pt, label])
                for idx, id in enumerate(obj.subids):
                    if not id in ps:
                        ps.add(id)
                        label = str(id)
                        pt = Point3D(self._normalize(obj.coords[idx]))
                        self.PointLabels.append([pt, label])

        self.update()

    def paintGL(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        self.camera.transform()
        glMatrixMode(GL_MODELVIEW);
        glLoadIdentity();

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glDepthFunc(GL_LEQUAL)
        glEnable(GL_DEPTH_TEST)
        # glEnable( GL_CULL_FACE );
        glFrontFace(GL_CCW);
        # glDisable( GL_LIGHTING );
        # glShadeModel( GL_FLAT );

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        if self.geoList:
            glCallList(self.geoList)

        if self.ShowPointLabels and len(self.PointLabels):
            glDisable(GL_LIGHTING)
            glDisable(GL_DEPTH_TEST)
            glColor(self.FontColor.redF(), self.FontColor.greenF(), self.FontColor.blueF())
            for pt, label in self.PointLabels:
                self.renderText(pt.x(), pt.y(), pt.z(), label, self.PointFont)

        if self.ShowFaceLabels and len(self.FaceLabels):
            glDisable(GL_LIGHTING)
            glDisable(GL_DEPTH_TEST)
            glColor(self.FontColor.redF(), self.FontColor.greenF(), self.FontColor.blueF())
            for pt, label in self.FaceLabels:
                self.renderText(pt.x(), pt.y(), pt.z(), label, self.FaceFont)

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

    def mouseMoveEvent(self, mouseEvent):
        if int(mouseEvent.buttons()) != QtCore.Qt.NoButton:
            # user is dragging
            delta_x = mouseEvent.x() - self.oldx
            delta_y = self.oldy - mouseEvent.y()
            if int(mouseEvent.buttons()) & QtCore.Qt.LeftButton:
                self.camera.orbit(self.oldx, self.oldy, mouseEvent.x(), mouseEvent.y())
            elif int(mouseEvent.buttons()) & QtCore.Qt.RightButton:
                self.camera.translateSceneRightAndUp(delta_x, delta_y)
            elif int(mouseEvent.buttons()) & QtCore.Qt.MidButton:
                self.camera.dollyCameraForward(3 * (delta_x + delta_y), False)
            self.update()
        self.oldx = mouseEvent.x()
        self.oldy = mouseEvent.y()

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
##    def mousePressEvent(self, e):
##        print "mouse press"
##        self.isPressed = True
##
##    def mouseReleaseEvent(self, e):
##        print "mouse release"
##        self.isPressed = False
