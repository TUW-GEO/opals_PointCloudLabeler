import sys

import threading

from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5 import QtCore

import dash_leaflet as dl
from dash import Dash, html, Output, Input


def run_dash(path, filename, bounds):
    app = Dash(prevent_initial_callbacks=True, assets_folder=path)

    image_path = app.get_asset_url(filename)
    app.layout = dl.Map([
            dl.ImageOverlay(opacity=0.5, url=image_path, bounds=bounds),
            dl.TileLayer(), dl.FeatureGroup([
                dl.EditControl(id="edit_control",
                               draw={'polyline': True,
                'rectangle': False,
                'polygon': False,
                'circle': False,
                'marker': False,
                'circlemarker': False}) ]),
        ], bounds=bounds, style={'height': '97vh'})

    # Copy data from the edit control to the geojson component.
    @app.callback(Input("edit_control", "geojson"))
    def feature_defined(x):
        if 'features' not in x:
            return
        lineIdx = 0
        for entry in  x['features']:
            if 'geometry' not in entry:
                continue
            geometry = entry['geometry']
            if geometry["type"] != "LineString":
                continue
            print(f"{lineIdx}. line: {geometry['coordinates']} ")
            lineIdx += 1

    app.run_server(debug=False)


class MapWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Set up the PyQt5 layout
        self.setGeometry(100, 100, 800, 600)
        layout = QVBoxLayout()

        # Create a QWebEngineView to display the map
        self.browser = QWebEngineView()
        #self.browser.setUrl(QtCore.QUrl.fromLocalFile(os.path.abspath(self.map_filename)))
        self.browser.setUrl(QtCore.QUrl("http://127.0.0.1:8050/"))

        layout.addWidget(self.browser)
        self.setLayout(layout)


if __name__ == '__main__':

    path = "E:/opals/nightly/win64/demo"
    shading = 'strip11.png'
    bounds = [[48.19985304047831, 15.397944359419803], [48.201458853379336, 15.401859646979037]]

    threading.Thread(target=run_dash, args=(path, shading, bounds), daemon=True).start()
    app = QApplication(sys.argv)
    window = MapWidget()
    window.show()
    sys.exit(app.exec_())