import sys

import threading

from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5 import QtCore

import dash
import dash_core_components as dcc
import dash_html_components as html


def run_dash(data, layout):
    app = dash.Dash()

    app.layout = html.Div(children=[
        html.H1(children='Hello Dash'),

        html.Div(children='''
            Dash: A web application framework for Python.
        '''),

        dcc.Graph(
            id='example-graph',
            figure={
                'data': data,
                'layout': layout
            })
        ])
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
    data = [
        {'x': [1, 2, 3], 'y': [4, 1, 2], 'type': 'bar', 'name': 'SF'},
        {'x': [1, 2, 3], 'y': [2, 4, 5], 'type': 'bar', 'name': u'Montréal'},
    ]

    layout = {
        'title': 'Dash Data Visualization'
    }

    threading.Thread(target=run_dash, args=(data, layout), daemon=True).start()
    app = QApplication(sys.argv)
    window = MapWidget()
    window.show()
    sys.exit(app.exec_())