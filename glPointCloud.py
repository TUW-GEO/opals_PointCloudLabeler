import OpenGL.GL as GL
import OpenGL.GL.shaders
import numpy as np
#from OpenGL.GLUT import *
import ctypes
import sys, random

classMapSize = 256

vertex_shader = """
#version 330
layout(location = 0) in vec3 position;
layout(location = 1) in float amp;
layout(location = 2) in int   classId;
layout(location = 3) in int   index;

uniform int attrMode;
uniform float minAmp; 
uniform float maxAmp;
uniform vec3 classMap[256];    

#define ATT_MODE_AMP    0
#define ATT_MODE_CLASS  1
#define ATT_MODE_INDEX  2

vec3 Class2Color(int c) {
    return vec3(classMap[c]);
}

vec3 Index2Color(int i) {
    return vec3( ((i >>   0) & 0xFF) / 255.0,
                 ((i >>   8) & 0xFF) / 255.0,
                 ((i >>  16) & 0xFF) / 255.0
               );
}

vec3 Amp2Color(float a) {
    float range = 1;
    if (maxAmp != minAmp)
        range = maxAmp-minAmp;
    float v = (clamp(a,minAmp,maxAmp)-minAmp)/range;
    return vec3(v, v, v);
}

out vec3  color;
void main()
{
   float z = 1.0f;
   if(attrMode == ATT_MODE_AMP) {
      color = Amp2Color(amp);
   } else if(attrMode == ATT_MODE_CLASS) {
      color = Class2Color(classId);	
   }  else if(attrMode == ATT_MODE_INDEX) {
      if (index == 0) {
         z = -1000f; // disables point
         color = vec3(0,0,0);
      } else {
        color = Index2Color(index);
      }	
   }   
   gl_Position = vec4(position, z);
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


ATT_MODE_AMP   = 0
ATT_MODE_CLASS = 1
ATT_MODE_INDEX = 2


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
    classMapSize = 256

    def __init__(self):
        self.vao = None     # vertex array object
        self.vbo = None
        self.shader = None
        self.idxDisplayMode = None
        self.idxMinAmp = None
        self.idxMaxAmp = None
        self.idxClassMap = None

        self.ptCount = None
        self.vertices = None
        self.amplitudes = None
        self.classIds = None
        self.ptIds = None   # one based vertex indices

    def _upload_data(self, vertices, amplitudes, classIds, ptIds):
        # Generate buffers to hold our vertices ----------------------------------------------------------------------------
        data = np.hstack((vertices, amplitudes.reshape(-1, 1), classIds.reshape(-1, 1).view('float32'),
                          ptIds.reshape(-1, 1).view('float32')))
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, data.nbytes, data, GL.GL_STATIC_DRAW)

    def set_data(self, vertices, amplitudes, classIds):
        assert isinstance(vertices, np.ndarray) and isinstance(amplitudes, np.ndarray) and isinstance(classIds, np.ndarray)
        assert vertices.shape[1] == 3
        self.ptCount = vertices.shape[0]
        assert amplitudes.shape[0] == self.ptCount and classIds.shape[0] == self.ptCount
        self.ptIds = np.arange(1, self.ptCount+1, 1, dtype=int)
        self.vertices = vertices
        self.amplitudes = amplitudes
        self.classIds = classIds
        pass

    @property
    def displayMode(self):
        mode = ctypes.c_int(0)
        GL.glGetUniformiv(self.shader, self.idxDisplayMode, mode)
        return mode.value

    @displayMode.setter
    def displayMode(self, mode):
        GL.glUseProgram(self.shader)
        GL.glUniform1i(self.idxDisplayMode, mode)

    @property
    def amplitudeRange(self):
        min = ctypes.c_float(0)
        max = ctypes.c_float(0)
        GL.glGetUniformiv(self.shader, self.idxMinAmp, min)
        GL.glGetUniformiv(self.shader, self.idxMaxAmp, max)
        return (min, max)

    @amplitudeRange.setter
    def amplitudeRange(self, range):
        GL.glUseProgram(self.shader)
        GL.glUniform1f(self.idxMinAmp, range[0])
        GL.glUniform1f(self.idxMaxAmp, range[1])

    @property
    def classColorMap(self):
        GL.glUseProgram(self.shader)
        map = np.empty(shape=(classMapSize, 3), dtype=np.float32)
        GL.glGetUniformfv(self.idxClassMap, classMapSize*3, map)

    @classColorMap.setter
    def classColorMap(self, map):
        GL.glUseProgram(self.shader)
        GL.glUniform3fv(self.idxClassMap, classMapSize, map)

    def initíalize(self, vs=vertex_shader, fs=fragment_shader):
        self.shader = OpenGL.GL.shaders.compileProgram(
            OpenGL.GL.shaders.compileShader(vs, GL.GL_VERTEX_SHADER),
            OpenGL.GL.shaders.compileShader(fs, GL.GL_FRAGMENT_SHADER)
        )

        # get index of uniform variables
        self.idxDisplayMode = GL.glGetUniformLocation(self.shader, "attrMode")
        self.idxMinAmp = GL.glGetUniformLocation(self.shader, "minAmp")
        self.idxMaxAmp = GL.glGetUniformLocation(self.shader, "maxAmp")
        self.idxClassMap = GL.glGetUniformLocation(self.shader, "classMap")

        # Create a new VAO (Vertex Array Object) and bind it
        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)

        # Generate buffers to hold our vertices
        self.vbo = GL.glGenBuffers(1)
        self._upload_data(self.vertices, self.amplitudes, self.classIds, self.ptIds)

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


    def draw(self, pointSize=3):
        GL.glUseProgram(self.shader)
        GL.glBindVertexArray(self.vao)
        GL.glPointSize(pointSize)
        GL.glDrawArrays(GL.GL_POINTS, 0, self.ptCount)
        GL.glBindVertexArray(0)
        GL.glUseProgram(0)

    def select(self, minx, miny, sizex, sizey):
        old_mode = self.displayMode
        self.displayMode = ATT_MODE_INDEX

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
            self._upload_data(self.vertices, self.amplitudes, self.classIds, ptIdsTemp)
            iter += 1

        #print(f"selected ids {selectedPts}")
        # restore old ptIds and display mode
        self._upload_data(self.vertices, self.amplitudes, self.classIds, self.ptIds)
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

