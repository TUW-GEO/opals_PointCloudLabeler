#! /usr/bin/env python
import numpy as np
from Geometry import Point3D, Vector3D, Matrix4x4
from OpenGL.GL import *
import math

class Camera:
    def __init__(self):
        self.FIELD_OF_VIEW_IN_DEGREES = 30.0
        self.ORBITING_SPEED_IN_DEGREES_PER_RADIUS_OF_VIEWPORT = 300.0
        self.OrthoProjection = True
        # These are in world-space units.
        self.nearPlane = 0.001
        self.farPlane = 100.0

        # During dollying (i.e. when the camera is translating into
        # the scene), if the camera gets too close to the target
        # point, we push the target point away.
        # The threshold distance at which such "pushing" of the
        # target point begins is this fraction of nearPlane.
        # To prevent the target point from ever being clipped,
        # this fraction should be chosen to be greater than 1.0.
        self.PUSH_THRESHOLD = self.nearPlane * 1.3

        # We give these some initial values just as a safeguard
        # against division by zero when computing their ratio.
        self.viewportWidthInPixels = 10
        self.viewportHeightInPixels = 10
        self.viewportRadiusInPixels = 5

        self.sceneRadius = 10

        # point of view, or center of camera; the ego-center; the eye-point
        self.position = Point3D()

        # point of interest; what the camera is looking at; the exo-center
        self.target = Point3D()

        # This is the up vector for the (local) camera space
        self.up = Vector3D()

        # This is the up vector for the (global) world space;
        # it is perpendicular to the horizontal (x,z)-plane
        self.ground = Vector3D(0,0,1)

        self.reset()

    def reset(self):
        tangent = math.tan( self.FIELD_OF_VIEW_IN_DEGREES/2.0 / 180.0 * math.pi )
        distanceFromTarget = self.sceneRadius / tangent
        self.position = Point3D(0,0,distanceFromTarget)
        self.target = Point3D(0,0,0)
        self.up = self.ground.returnCopy()

    def setOrthoView(self,x,y):
        dist = (self.target-self.position).length()
        vec = Vector3D(x, y, 0)

        self.position = self.target + vec*dist
        self.up = Vector3D(0,0,1)

    def setViewportDimensions( self, widthInPixels, heightInPixels ):
        self.viewportWidthInPixels = widthInPixels
        self.viewportHeightInPixels = heightInPixels
        self.viewportRadiusInPixels = 0.5*widthInPixels if (widthInPixels < heightInPixels) else 0.5*heightInPixels

    def getViewportWidth(self):
        return self.viewportWidthInPixels
    def getViewportHeight(self):
        return self.viewportHeightInPixels
    def setSceneRadius(self,radius):
        self.sceneRadius = radius

    def getAspectFactors(self):
        "https://gamedev.stackexchange.com/questions/49674/opengl-resizing-display-and-glortho-glviewport"
        aspect = self.viewportWidthInPixels / float(self.viewportHeightInPixels)
        if aspect >= 1.0:
            f1 = aspect
            f2 = 1.
        else:
            f1 = 1.
            f2 = 1./aspect
        return f1, f2

    def transform(self):
        if self.OrthoProjection == True:
          dist = (self.position-self.target).length()*0.3
          f1, f2 = self.getAspectFactors()
          glOrtho(-dist*f1, dist*f1, -dist*f2, dist*f2, -self.farPlane, self.farPlane);
        else:
          tangent = math.tan( self.FIELD_OF_VIEW_IN_DEGREES/2.0 / 180.0 * math.pi )
          viewportRadius = self.nearPlane * tangent
          if self.viewportWidthInPixels < self.viewportHeightInPixels:
              viewportWidth = 2.0*viewportRadius
              viewportHeight = viewportWidth * self.viewportHeightInPixels / float(self.viewportWidthInPixels)
          else:
              viewportHeight = 2.0*viewportRadius
              viewportWidth = viewportHeight * self.viewportWidthInPixels / float(self.viewportHeightInPixels)
          glFrustum(
              - 0.5 * viewportWidth,  0.5 * viewportWidth,    # left, right
              - 0.5 * viewportHeight, 0.5 * viewportHeight,   # bottom, top
              self.nearPlane, self.farPlane
              )

        M = Matrix4x4.lookAt(self.position, self.target, self.up, False)
        glMultMatrixf(M.get())

    def getProjectionMatrix(self):
        if self.OrthoProjection == True:
          dist = (self.position-self.target).length()*0.3
          f1, f2 = self.getAspectFactors()
          return np.array( [[1/(dist*f1), 0, 0, 0],
                           [0, 1/(dist*f2), 0, 0],
                           [0, 0, -1/self.farPlane, 0],
                           [0, 0, 0, 1]], dtype=np.float32)
        else:
            raise Exception("Building perspective projection matrix (glFrustum) not implemented yet")
            return None

    def getViewMatrix(self):
        mat = Matrix4x4.lookAt(self.position, self.target, self.up, False)
        return np.array(mat.get(), dtype=np.float32).reshape(4, 4)


    def getTransformationMatrix_4x4(self, rotation):
        x = rotation[0,0]
        y = rotation[0,1]
        dist = (self.target-self.position).length()
        vec = Vector3D(-y, x, 0)

        position = self.target + vec*dist
        up = Vector3D(0,0,1)

        mat = Matrix4x4.createTransformationMatrix(position, self.target, up, True)
        
        return mat

    def transformAxis(self):
        if self.OrthoProjection == True:
          dist = 1.5
          glOrtho(-dist, dist, -dist, dist, -self.farPlane, self.farPlane);

          vec = (self.position-self.target).normalized()*0.5
          source = (vec*10).asPoint3D()
          target = vec.asPoint3D()
        else:
          tangent = math.tan( self.FIELD_OF_VIEW_IN_DEGREES/2.0 / 180.0 * math.pi )
          viewportRadius = self.nearPlane * tangent
          if self.viewportWidthInPixels < self.viewportHeightInPixels:
              viewportWidth = 2.0*viewportRadius
              viewportHeight = viewportWidth * self.viewportHeightInPixels / float(self.viewportWidthInPixels)
          else:
              viewportHeight = 2.0*viewportRadius
              viewportWidth = viewportHeight * self.viewportWidthInPixels / float(self.viewportHeightInPixels)
          glFrustum(
              - 0.5 * viewportWidth,  0.5 * viewportWidth,    # left, right
              - 0.5 * viewportHeight, 0.5 * viewportHeight,   # bottom, top
              self.nearPlane, self.farPlane
              )

          target = Point3D()
          vec = (self.position-Point3D()).normalized()*0.5
          source = (vec*10).asPoint3D()
          target = vec.asPoint3D()
        M = Matrix4x4.lookAt(source, target, self.up, False)
        glMultMatrixf(M.get())

    # Causes the camera to "orbit" around the target point.
    # This is also called "tumbling" in some software packages.
    def orbit(self,old_x_pixels,old_y_pixels,new_x_pixels,new_y_pixels):
        pixelsPerDegree = self.viewportRadiusInPixels / float(self.ORBITING_SPEED_IN_DEGREES_PER_RADIUS_OF_VIEWPORT)
        radiansPerPixel = 1.0 / pixelsPerDegree * math.pi / 180.0

        t2p = self.position - self.target

        M = Matrix4x4.rotationAroundOrigin( (old_x_pixels - new_x_pixels) * radiansPerPixel, self.ground )
        t2p = M * t2p
        self.up = M * self.up
        right = (self.up ^ t2p).normalized()
        M = Matrix4x4.rotationAroundOrigin( (old_y_pixels - new_y_pixels) * radiansPerPixel, right )
        t2p = M * t2p
        self.up = M * self.up
        self.position = self.target + t2p

    # This causes the scene to appear to translate right and up
    # (i.e., what really happens is the camera is translated left and down).
    # This is also called "panning" in some software packages.
    # Passing in negative delta values causes the opposite motion.
    def translateSceneRightAndUp( self, delta_x_pixels, delta_y_pixels ):
        direction = self.target - self.position
        distanceFromTarget = direction.length()
        direction = direction.normalized()

        translationSpeedInUnitsPerRadius = distanceFromTarget * math.tan( self.FIELD_OF_VIEW_IN_DEGREES/2.0 / 180.0 * math.pi )
        pixelsPerUnit = self.viewportRadiusInPixels / translationSpeedInUnitsPerRadius

        right = direction ^ self.up

        translation = right*(- delta_x_pixels / pixelsPerUnit) + self.up*(- delta_y_pixels / pixelsPerUnit)

        self.position = self.position + translation
        self.target = self.target + translation

    # This causes the camera to translate forward into the scene.
    # This is also called "dollying" or "tracking" in some software packages.
    # Passing in a negative delta causes the opposite motion.
    # If ``pushTarget'' is True, the point of interest translates forward (or backward)
    # *with* the camera, i.e. it's "pushed" along with the camera; otherwise it remains stationary.
    def dollyCameraForward( self, delta_pixels, pushTarget ):
        direction = self.target - self.position
        distanceFromTarget = direction.length()
        direction = direction.normalized()

        translationSpeedInUnitsPerRadius = distanceFromTarget * math.tan( self.FIELD_OF_VIEW_IN_DEGREES/2.0 / 180.0 * math.pi )
        pixelsPerUnit = self.viewportRadiusInPixels / translationSpeedInUnitsPerRadius

        dollyDistance = delta_pixels / pixelsPerUnit

        if not pushTarget:
            distanceFromTarget -= dollyDistance
            if distanceFromTarget < self.PUSH_THRESHOLD * self.nearPlane:
                distanceFromTarget = self.PUSH_THRESHOLD * self.nearPlane

        self.position += direction * dollyDistance
        self.target = self.position + direction * distanceFromTarget


