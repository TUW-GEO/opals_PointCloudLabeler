#from osgeo import ogr
from PyQt5 import QtCore,QtWidgets,uic
from PyQt5.QtGui import *
#from OpenGL.GLUT import *
import os
import opals
from opals import Import, Grid, Shade, pyDM
import numpy as np
import math
from Geometry import GeometryType


class ClassificationTool(QtWidgets.QMainWindow):
    def __init__(self):
        super(ClassificationTool, self).__init__()
        uic.loadUi('ClassificationTool_1.ui', self) #https://github.com/FelixMeix/classificationtool.git
        self.initUI()
        self.linestring = None
        self.odm = None
        self.result = None
        self.PathToFile.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21.laz" )
        self.PathToAxisShp.setText( r"C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21_axis_transformed.shp")

    def initUI(self):
        self.LoadButton.pressed.connect(self.load_pointcloud)
        self.LoadAxis.pressed.connect(self.get_points_in_polygon)

        self.Next.pressed.connect(self.next_section)
        self.Previous.pressed.connect(self.previous_section)
        self._sumit_counter = 0

        self.Save.pressed.connect(self.save_file)

    def load_pointcloud(self):
        self.Elevator.clear()

        path = str(self.PathToFile.text()).strip()
        os.chdir(os.path.dirname(os.path.abspath(path)))

        # get the filname
        data = path.split('\\')  # ['...','...','...','strip21.laz']
        data = data[len(data) - 1]  # strip21.laz
        filename = data.split('.')  # ['strip21','laz']
        name = filename[0]  # 'strip21'

        #load the opals datamanager in read and write
        odm = name + '.odm'
        self.odm = pyDM.Datamanager.load(odm, readOnly=True, threadSafety=False)  #TODO change readonly!!!

        #create shading
        if os.path.isfile(name + '.odm') == False:
            Import.Import(inFile=data, outFile=name + '.odm').run()

        elif os.path.isfile(name + '.tif') == False:
            Grid.Grid(inFile=name + '.odm', outFile=name + '.tif', filter='echo[last]',
                  interpolation=opals.Types.GridInterpolator.movingPlanes, gridSize=0.5).run()

        shd = Shade.Shade(inFile=name + '.tif')
        shd.run()

        image = QPixmap(str(shd.outFile))
        self.Elevator.setPixmap(image)
        self.PathToFile.clear()

    #def load_axis(self):
        #axis = str(self.PathToAxisShp.text()).strip()
        #os.chdir(os.path.dirname(os.path.abspath(axis)))

        #data = axis.split('\\')
        #file = data[len(data)-1]
        #file = ogr.Open(data[len(data) - 1])
        #print(file)
        #shape = file.GetLayer(0)
        #print(shape)
        #feature = shape.GetFeature(0)
        #first = feature.ExportToJson(as_object=True)
        #linestring = first['geometry']['coordinates'] #List of all coordinates of the axis file
        #self.axis = linestring
        #print(linestring)

        #self.PathToAxisShp.clear()

    def load_axis(self):
        axis = str(self.PathToAxisShp.text()).strip()
        data = axis.split('\\')
        file = data[len(data)-1]
        imp = pyDM.Import.create(file, pyDM.DataFormat.auto)

        pts = []
        for obj in imp:
            # loop over points
            for i in range(obj.sizePoint()):
                pt = obj[i]
                pts.append( [pt.x, pt.y] )
        self.linestring = pts

    def get_points_in_polygon(self):
        if not self.odm:
            return
        self.load_axis()
        if not self.linestring:
            return
        width = float(self.width_section.text().strip())
        length = float(self.lenght_section.text().strip())
        dm = self.odm
        linestring = self.linestring

        lf = pyDM.AddInfoLayoutFactory()
        type, inDM = lf.addColumn(dm, 'Id', True); assert  inDM == True
        type, inDM = lf.addColumn(dm, 'GPSTime', True); assert inDM == True
        type, inDM = lf.addColumn(dm, 'Amplitude', True); assert inDM == True
        type, inDM = lf.addColumn(dm, 'Classification', True); assert inDM == True
        layout = lf.getLayout()

        def direction(p1, p2):
            p1 = np.array(p1).reshape(1, 2)
            p2 = np.array(p2).reshape(1, 2)
            p = p2 - p1
            p = p / math.sqrt(p[0, 0]**2 + p[0, 1]**2)
            return p

        def poly_points(start, vector, length, width):
            start_point = np.array(start).reshape(1, 2)
            rot_vector = np.array([-vector[0, 1], vector[0, 0]]).reshape(1, 2)
            p1 = start_point + (rot_vector * length / 2)
            p2 = start_point + (-rot_vector * length / 2)
            p3 = p2 + (width * vector)
            p4 = p1 + (width * vector)
            return p1, p2, p3, p4

        p1, p2, p3, p4 = poly_points(linestring[0], direction(linestring[0], linestring[1]), length, width)
        pf = pyDM.PolygonFactory()

        def create_polygon(p1, p2, p3, p4):
            pf.addPoint(p1[0, 0], p1[0, 1])
            pf.addPoint(p2[0, 0], p2[0, 1])
            pf.addPoint(p3[0, 0], p3[0, 1])
            pf.addPoint(p4[0, 0], p4[0, 1])
            pf.closePart()
            return pf.getPolygon()

        #create the polygon
        polygon = create_polygon(p1, p2, p3, p4)

        #extract the points inside of the polygon
        result = pyDM.NumpyConverter.searchPoint(dm, polygon, layout, withCoordinates = True, noDataObj=[0, np.nan])
        self.result = result

    def next_section(self):
        self._sumit_counter += 1
        #self.plot_section(outGeo)

    def previous_section(self):
        self._sumit_counter -= 1
        #self.plot_section(outGeo)

    def save_file(self):
        pass


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    win = ClassificationTool()
    win.show()
    sys.exit(app.exec_())


#C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21.laz
#C:\Users\felix\OneDrive\Dokumente\TU Wien\Bachelorarbeit\Classificationtool\strip21_axis.shp
#axisFile = name + '_axis.shp'
