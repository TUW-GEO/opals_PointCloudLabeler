import folium
from folium.raster_layers import ImageOverlay
import opals
from osgeo import osr, gdal
from opals import Import, Grid, Shade, pyDM, Info
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5 import QtCore
import os
import sys


class MapWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.targetCRS = self.getWkt(4326) #Gauss-krueger East
        self.readdata()
        self.createMap()

        # Set up the PyQt5 layout
        self.setGeometry(100, 100, 800, 600)
        layout = QVBoxLayout()

        # Create a QWebEngineView to display the map
        self.browser = QWebEngineView()
        self.browser.setUrl(QtCore.QUrl.fromLocalFile(os.path.abspath(self.map_filename)))

        layout.addWidget(self.browser)
        self.setLayout(layout)

    def getWkt(self, epsgCode):
        crs = osr.SpatialReference()
        crs.ImportFromEPSG(epsgCode)
        return crs.ExportToWkt()

    def trafoObj(self):
        self.trafo = pyDM.Trafo(self.sourceCRS, self.targetCRS)

    def readdata(self):
        self.path = 'D:/users/fmeixner/Folium/Data'
        os.chdir(self.path)

        name = 'strip11'
        odm_name = name + '.odm'
        data = name + '.laz'
        shd_name = name + '_shd.tif'
        grid_name = name + '_z.tif'
        png_name = name + '.png'

        self.tif2png(shd_name, png_name)

        inf = Info.Info(inFile=data)
        inf.run()
        self.sourceCRS = inf.statistic[0].getCoordRefSys()

        self.trafoObj()

        if os.path.isfile(odm_name) == False:
            # Import data:
            Import.Import(inFile=data, outFile=odm_name).run()

            # create shading:
            Grid.Grid(inFile=odm_name, outFile=grid_name, filter='echo[last]',
                      interpolation=opals.Types.GridInterpolator.movingPlanes, gridSize=0.5).run()
            Shade.Shade(inFile=grid_name, outFile=shd_name).run()

        # get the limit of the area
        dm = pyDM.Datamanager.load(odm_name, False, False)
        limit = dm.getLimit()
        self.xmin, self.ymin, self.zmin = limit.xmin, limit.ymin, limit.zmin
        self.xmax, self.ymax, self.zmax = limit.xmax, limit.ymax, limit.zmax

        self.targetCoords_max = self.trafo.transform(self.xmax, self.ymax, self.zmax)
        self.targetCoords_min = self.trafo.transform(self.xmin, self.ymin, self.zmin)

    def tif2png(self, shd_name, png_name):
        input_tiff = self.path + '/' + shd_name
        self.output_png = self.path + '/' + png_name

        gdal.Translate(self.output_png, input_tiff, format='png')
    def createMap(self):
        m = folium.Map(
            location=[(self.targetCoords_min[0] + self.targetCoords_max[0]) / 2, (self.targetCoords_min[1] + self.targetCoords_max[1]) / 2],
        )
        m.fit_bounds([[self.targetCoords_min[0], self.targetCoords_min[1]], [self.targetCoords_max[0], self.targetCoords_max[1]]])
        self.map_filename = os.path.join(self.path, "map_output.html")

        bounds = [[self.targetCoords_min[0], self.targetCoords_min[1]], [self.targetCoords_max[0], self.targetCoords_max[1]]]
        overlay = ImageOverlay(image=self.output_png, bounds=bounds, opacity=0.6)
        overlay.add_to(m)

        m.save(self.map_filename)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MapWidget()
    window.show()
    sys.exit(app.exec_())
