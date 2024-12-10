import sys, os, json
from opals import Import, Grid, Shade, pyDM, Info
from osgeo import osr, gdal
import threading

from PyQt5.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
                             QFormLayout, QSpacerItem, QSizePolicy, QFileDialog, QSlider, QLayout)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5 import QtCore

import dash_leaflet as dl
from dash import Dash, html, Output, Input, State, dcc, Patch


# dash code handling
def set_dash_layout(filename, bounds, opacity):
    global DASH_APP
    image_path = DASH_APP.get_asset_url(filename)
    draw = { 'polyline': True,
             'rectangle': False,
             'polygon': False,
             'circle': False,
             'marker': False,
             'circlemarker': False }

    labelFlex = {'flexShrink': 0}
    slideFlex = {'width': '100%', 'margin-top' : '3px'}

    DASH_APP.layout = html.Div([ dl.Map([
            dl.ImageOverlay(opacity=opacity, url=image_path, bounds=bounds, id="shading-image"),
            dl.TileLayer(), dl.FeatureGroup([
                dl.EditControl(id="edit_control",
                               draw=draw) ]),
        ], bounds=bounds, style={'height': '90vh'}, id="map"),

        # we create a opacity slider
        html.Div([
            html.Label('Shading opacity',style=labelFlex),
            html.Div(dcc.Slider(0, 100, marks=None, value=int(opacity*100), id='slider-updatemode'), style=slideFlex)
            ], style={ 'display': 'flex'})
    ])

def run_dash(path, filename, bounds, opacity):
    global DASH_APP
    DASH_APP = Dash(assets_folder=path)

    set_dash_layout(filename, bounds, opacity)

    # Retrieve the geojson object from the edit control
    @DASH_APP.callback(Input("edit_control", "geojson"))
    def feature_defined(x):
        if 'features' not in x:
            return
        lineIdx = 0
        for entry in x['features']:
            if 'geometry' not in entry:
                continue
            geometry = entry['geometry']
            if geometry["type"] != "LineString":
                continue
            print(f"{lineIdx}. line: {geometry['coordinates']} ")
            lineIdx += 1

    @DASH_APP.callback( Output("map", "children"),
                    Input('slider-updatemode', 'value'),
                    State("map", "children"))
    def display_value(value, data):
        p = Patch()
        for idx, e in enumerate(data):
            if "props" in e:
                if "id" in e["props"]:
                    if e["props"]["id"] == "shading-image":
                        p[idx]["props"]["opacity"] = value / 100.
        return p


    # the map bounds callback is not working if the dl.Map is created with the bounds parameter
    # it only works if center and zoom is used (but we don't need it currently)
    #@DASH_APP.callback(Input("map", "bounds"))
    #def log_bounds(bounds):
    #    print(bounds)


    DASH_APP.run_server(debug=False)


class MapWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Set up the PyQt5 layout
        self.setGeometry(100, 100, 800, 600)

        # Create a QWebEngineView to display the map
        self.browser = QWebEngineView()
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.browser.setSizePolicy(size_policy)
        self.file = None
        self.dashTask = None
        self.opacity = None

        buttonlayout = QHBoxLayout()
        self.loadButton = QPushButton('load', self)
        self.loadButton.clicked.connect(self.load)
        self.resetButton = QPushButton('initialPtClasses', self)
        self.resetButton.clicked.connect(self.reset)
        self.closeButton = QPushButton('close', self)
        self.closeButton.clicked.connect(self.close)

        # set initial opacity
        self.inital_opacity = 0.8

        buttonlayout.addWidget(self.loadButton)
        buttonlayout.addWidget(self.resetButton)
        buttonlayout.addWidget(self.closeButton)

        layout = QFormLayout()
        layout.addRow(self.browser)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.addRow(buttonlayout)

        self.sourceCRS = None
        self.targetCRS = self.getWkt(4326)  # web mercato projection
        self.viewBounds = None

        self.setLayout(layout)
        self.refreshView()

    def getWkt(self, epsgCode):
        crs = osr.SpatialReference()
        crs.ImportFromEPSG(epsgCode)
        return crs.ExportToWkt()

    def reset(self):
        self.file = None
        self.refreshView()

    def refreshView(self):
        if not self.file:
            self.browser.setUrl(QtCore.QUrl.fromLocalFile(os.path.abspath("empty.html")))
        else:
            path, shading = os.path.split(os.path.abspath(self.file))
            if not self.dashTask:
                self.dashTask = threading.Thread(target=run_dash, args=(path, shading, self.viewBounds, self.inital_opacity), daemon=True)
                self.dashTask.start()
            else:
                set_dash_layout(shading, self.viewBounds, opacity=self.inital_opacity)
            self.browser.setUrl(QtCore.QUrl("http://127.0.0.1:8050/"))

    def load(self):
        shading, _ = QFileDialog.getOpenFileName(self, "Select shading", "",
                                                   "PNG (*.png);;All Files (*.*)")
        if shading == "":
            return

        self.file = shading
        inf = Info.Info(inFile=shading)
        inf.run()
        self.sourceCRS = inf.statistic[0].getCoordRefSys()
        self.boundingBox = inf.statistic[0].getBoundingBox()

        self.trafo = pyDM.Trafo(self.sourceCRS, self.targetCRS)
        minPt = self.trafo.transform(self.boundingBox[0], self.boundingBox[1], self.boundingBox[2])
        maxPt = self.trafo.transform(self.boundingBox[3], self.boundingBox[4], self.boundingBox[5])

        self.viewBounds = [[minPt[0], minPt[1]], [maxPt[0], maxPt[1]]]
        self.refreshView()


    def close(self):
        super().close()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MapWidget()
    window.show()
    sys.exit(app.exec_())