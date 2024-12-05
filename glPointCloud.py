import OpenGL.GL as GL
import OpenGL.GL.shaders
import numpy as np
#from OpenGL.GLUT import *
import ctypes
import sys, random

vertex_shader = """
#version 330
layout(location = 0) in vec3  position;
layout(location = 1) in float attr;
layout(location = 2) in int   classId;
layout(location = 3) in int   index;

uniform int attrMode;
uniform float minAttr;
uniform float maxAttr;
uniform vec3 classMap[256];
uniform mat4 viewMat;
uniform mat4 projMat;

#define COLOR_MODE_ATTR    0
#define COLOR_MODE_CLASS  1
#define COLOR_MODE_INDEX  2

vec3 Class2Color(int c) {
    return vec3(classMap[c]);
    //return vec3(1.f,0,0);
}

vec3 Index2Color(int i) {
    return vec3( ((i >>   0) & 0xFF) / 255.0,
                 ((i >>   8) & 0xFF) / 255.0,
                 ((i >>  16) & 0xFF) / 255.0
               );
}

vec3 Attr2Color(float a) {
    float range = 1;
    if (maxAttr != minAttr)
        range = maxAttr-minAttr;
    float v = (clamp(a,minAttr,maxAttr)-minAttr)/range;
    return vec3(v, v, v);
}

out vec3  color;
void main()
{
   float z = 1.0f;
   if(attrMode == COLOR_MODE_ATTR) {
      color = Attr2Color(attr);
   } else if(attrMode == COLOR_MODE_CLASS) {
      color = Class2Color(classId);	
   }  else if(attrMode == COLOR_MODE_INDEX) {
      if (index == 0) {
         z = -1000; // disables point
         color = vec3(0,0,0);
      } else {
        color = Index2Color(index);
      }	
   }   
   gl_Position = projMat*viewMat*vec4(position, z);
}
"""

fragment_shader = """
#version 330
in vec3 color;
void main()
{
   gl_FragColor = vec4(color, 1.0);
}
"""


COLOR_MODE_ATTR  = 0
COLOR_MODE_CLASS = 1
COLOR_MODE_INDEX = 2


vertices = [[0.6, 0.6, 0.0],
            [-0.6, 0.6, 0.0],
            [0.0, -0.6, 0.0],
            [0.0, 0.0, 0.0],
            [-0.2, 0.0, 0.0],
            [0.0, 0.0001, -1.0]
            ]

vertices = np.array(vertices, dtype=np.float32)
amp = np.array([30, 56, 14, 80, 43, 16], dtype=np.float32)
classIds = np.array([2, 2, 0, 4, 0, 2], dtype=np.int32)


class glPointCloud:

    classMapSize = 256  # number of supported class ids

    def __init__(self):
        self.vao = None     # vertex array object
        self.vbo = None
        self.shader = None
        self.idxDisplayMode = None
        self.idxMinAttr = None
        self.idxMaxAttr = None
        self.idxClassMap = None
        self.idxViewMat = None
        self.idxProjMat = None

        self.ptCount = None
        self.vertices = None
        self.attrValues = None
        self.classIds = None
        self.ptIds = None   # one based vertex indices
        self._initialized = False

    def _upload_data(self, vertices, attrValues, classIds, ptIds):
        if vertices is None:
            # in case vertices is none we still need to bind an empty array, otherwise
            # subsequent glVertexAttribPointer calls will fail
            empty = np.empty( shape=(0,0), dtype=np.float32)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, empty.nbytes, empty, GL.GL_STATIC_DRAW)
            return

        # Generate buffers to hold our vertices ----------------------------------------------------------------------------
        classIds_int32 = classIds
        if classIds_int32.itemsize != 4:               # we need classIds as 4 byte integer (to allow float32 cast)
            classIds_int32 = classIds.astype(np.int32)
        data = np.hstack((vertices, attrValues.reshape(-1, 1), classIds_int32.reshape(-1, 1).view('float32'),
                          ptIds.reshape(-1, 1).view('float32')))
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, data.nbytes, data, GL.GL_STATIC_DRAW)

    def set_data(self, vertices, attrValues, classIds, upload=True):
        assert isinstance(vertices, np.ndarray) and isinstance(attrValues, np.ndarray) and isinstance(classIds, np.ndarray)
        assert vertices.shape[1] == 3
        self.ptCount = vertices.shape[0]
        assert attrValues.shape[0] == self.ptCount and classIds.shape[0] == self.ptCount
        self.ptIds = np.arange(1, self.ptCount+1, 1, dtype=int)
        self.vertices = vertices
        self.attrValues = attrValues
        self.classIds = classIds
        if upload:
            self._upload_data(self.vertices, self.attrValues, self.classIds, self.ptIds)
        pass

    @staticmethod
    def generate_color_map():
        colorMap = np.empty(shape=(glPointCloud.classMapSize, 3), dtype=np.float32)
        for r in range(glPointCloud.classMapSize):
            colorMap[r, 0] = random.random()
            colorMap[r, 1] = random.random()
            colorMap[r, 2] = random.random()
        return colorMap

    @property
    def displayMode(self):
        mode = ctypes.c_int(0)
        GL.glGetUniformiv(self.shader, self.idxDisplayMode, mode)
        return mode.value

    @displayMode.setter
    def displayMode(self, mode):
        GL.glUseProgram(self.shader)
        GL.glUniform1i(self.idxDisplayMode, mode)
        GL.glUseProgram(0)

    @property
    def attributeRange(self):
        min = ctypes.c_float(0)
        max = ctypes.c_float(0)
        GL.glGetUniformiv(self.shader, self.idxMinAttr, min)
        GL.glGetUniformiv(self.shader, self.idxMaxAttr, max)
        GL.glUseProgram(0)
        return (min, max)

    @attributeRange.setter
    def attributeRange(self, range):
        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.idxMinAttr, range[0])
        GL.glUniform1f(self.idxMaxAttr, range[1])
        GL.glUseProgram(0)

    @property
    def classColorMap(self):
        GL.glUseProgram(self.shader)
        map = np.empty(shape=(glPointCloud.classMapSize, 3), dtype=np.float32)
        GL.glGetUniformfv(self.idxClassMap, glPointCloud.classMapSize*3, map)
        GL.glUseProgram(0)
        return map

    @classColorMap.setter
    def classColorMap(self, map):
        GL.glUseProgram(self.shader)
        GL.glUniform3fv(self.idxClassMap, glPointCloud.classMapSize, map)
        GL.glUseProgram(0)

    @property
    def viewMatrix(self):
        GL.glUseProgram(self.shader)
        mat = np.empty(shape=(4, 4), dtype=np.float32)
        GL.glGetUniformfv(self.idxViewMat, 4*4, mat)
        GL.glUseProgram(0)
        return mat

    @viewMatrix.setter
    def viewMatrix(self, mat):
        GL.glUseProgram(self.shader)
        GL.glUniformMatrix4fv(self.idxViewMat, 1, 0, mat)
        GL.glUseProgram(0)


    @property
    def initialized(self):
        return self._initialized

    def initíalize(self, vs=vertex_shader, fs=fragment_shader):
        self.shader = OpenGL.GL.shaders.compileProgram(
            OpenGL.GL.shaders.compileShader(vs, GL.GL_VERTEX_SHADER),
            OpenGL.GL.shaders.compileShader(fs, GL.GL_FRAGMENT_SHADER)
        )

        # get index of uniform variables
        self.idxDisplayMode = GL.glGetUniformLocation(self.shader, "attrMode")
        self.idxMinAttr  = GL.glGetUniformLocation(self.shader, "minAttr")
        self.idxMaxAttr  = GL.glGetUniformLocation(self.shader, "maxAttr")
        self.idxClassMap = GL.glGetUniformLocation(self.shader, "classMap")
        self.idxViewMat  = GL.glGetUniformLocation(self.shader, "viewMat")
        self.idxProjMat  = GL.glGetUniformLocation(self.shader, "projMat")

        # Create a new VAO (Vertex Array Object) and bind it
        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)

        # Generate buffers to hold our vertices
        self.vbo = GL.glGenBuffers(1)
        self._upload_data(self.vertices, self.attrValues, self.classIds, self.ptIds)

        # Set attribute pointers
        stride = 6 * vertices.itemsize
        position_offset = ctypes.c_void_p(0)
        amp_offset = ctypes.c_void_p(3 * vertices.itemsize)
        class_offset = ctypes.c_void_p(4 * vertices.itemsize)
        index_offset = ctypes.c_void_p(5 * vertices.itemsize)
        GL.glVertexAttribPointer(0, 3, GL.GL_FLOAT, GL.GL_FALSE, stride, position_offset)
        GL.glVertexAttribPointer(1, 1, GL.GL_FLOAT, GL.GL_FALSE, stride, amp_offset)
        GL.glVertexAttribPointer(2, 1, GL.GL_FLOAT, GL.GL_FALSE, stride, class_offset)
        GL.glVertexAttribPointer(3, 1, GL.GL_FLOAT, GL.GL_FALSE, stride, index_offset)
        GL.glEnableVertexAttribArray(0)
        GL.glEnableVertexAttribArray(1)
        GL.glEnableVertexAttribArray(2)
        GL.glEnableVertexAttribArray(3)

        self._initialized = True



    def draw(self, pointSize=3, projMat = None, viewMat = None):
        GL.glUseProgram(self.shader)
        if projMat is not None:
            GL.glUniformMatrix4fv(self.idxProjMat, 1, 0, projMat)
        if viewMat is not None:
            GL.glUniformMatrix4fv(self.idxViewMat, 1, 0, viewMat)
        GL.glBindVertexArray(self.vao)
        GL.glPointSize(pointSize)
        GL.glDrawArrays(GL.GL_POINTS, 0, self.ptCount)
        GL.glBindVertexArray(0)
        GL.glUseProgram(0)

    def select(self, minx, miny, sizex, sizey):
        old_mode = self.displayMode
        self.displayMode = COLOR_MODE_INDEX

        ptIdsTemp = self.ptIds.copy()

        selectedPts = []
        maxIter = 3
        iter = 0
        while True:
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
            self.draw()
            GL.glFlush()
            GL.glReadBuffer(GL.GL_BACK)
            posBuffer = GL.glReadPixels(minx, miny, sizex, sizey, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
            posColArr = np.frombuffer(posBuffer, dtype=np.uint8)
            posColArr_idx0 = posColArr[0::4]  # take every 4 byte starting from 0 index
            posColArr_idx1 = posColArr[1::4]  # take every 4 byte starting from 1 index
            posColArr_idx2 = posColArr[2::4]  # take every 4 byte starting from 2 index
            # convert split col array into single id array
            posIds = posColArr_idx0.astype(int) + posColArr_idx1 * 256 + posColArr_idx2 * 256 * 256
            # ignore empty ids (-1), make ids unique and convert it to a list
            idxPtArray = np.unique(posIds[posIds > 0])
            idxPtList = idxPtArray.tolist()
            if len(idxPtList) == 0 or iter == maxIter:
                break
            selectedPts.extend(idxPtList)
            ptIdsTemp[idxPtArray - 1] = 0
            self._upload_data(self.vertices, self.attrValues, self.classIds, ptIdsTemp)
            iter += 1

        #print(f"selected ids {selectedPts}")
        # restore old ptIds and display mode
        self._upload_data(self.vertices, self.attrValues, self.classIds, self.ptIds)
        self.displayMode = old_mode
        return selectedPts

# winWidth = None
# winHeight = None
# def main():
#     random.seed()
#     glutInit(sys.argv)
#     glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE | GLUT_DEPTH)
#     # glutInitContextVersion(3, 3) # this call cause an error when glVertexAttribPointer
#     glutInitContextFlags(GLUT_CORE_PROFILE | GLUT_DEBUG)
#     winWidth = 256
#     winHeight = 256
#     glutInitWindowSize(winWidth, winHeight)
#     glutCreateWindow(b"vbo")
#
#     print(GL.glGetString(GL.GL_VERSION))
#     print(
#         f'VERSION: {GL.glGetInteger(GL.GL_MAJOR_VERSION)}.{GL.glGetInteger(GL.GL_MINOR_VERSION)}'
#     )
#
#     pc = GLPointCloud()
#     pc.set_data(vertices, amp, classIds)
#     pc.initíalize(vertex_shader, fragment_shader)
#
#     # init uniform shader values
#     pc.displayMode = 0
#     pc.amplitudeRange = (0, amp.max())
#
#     # fill color map with random values
#     classColorMap = np.empty(shape=(classMapSize, 3), dtype=np.float32)
#     for r in range(classMapSize):
#         classColorMap[r, 0] = random.random()
#         classColorMap[r, 1] = random.random()
#         classColorMap[r, 2] = random.random()
#     pc.classColorMap = classColorMap
#
#     def disp_func():
#         GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
#         pc.draw()
#         GL.glFlush()
#         glutSwapBuffers()
#
#     glutDisplayFunc(disp_func)
#
#     def key_func(key, x, y):
#         global winWidth, winHeight
#         key = key.decode("utf-8")
#         if key == "s":
#             selectedPts = pc.select(0, 0, winWidth, winHeight)
#             print(f"selected ids {selectedPts}")
#         elif key == "m":
#             mode = pc.displayMode
#             print(f"switch mode (current={mode})")
#             mode = 1 - mode
#             pc.displayMode = mode
#             disp_func()
#
#     glutKeyboardFunc(key_func)
#
#     def reshape_func(w, h):
#         global winWidth, winHeight
#         GL.glViewport(0, 0, w, h)
#         #print(f"reshape w={w}, h={h}")
#         winWidth = w
#         winHeight = h
#
#     glutReshapeFunc(reshape_func)
#
#     GL.glClearColor(0.0, 0.0, 0.0, 0.0)
#     GL.glDepthFunc(GL.GL_LESS)
#     GL.glEnable(GL.GL_DEPTH_TEST)
#
#     glutMainLoop()
#
#
# if __name__ == '__main__':
#     main()

