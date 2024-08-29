import fiona
from shapely.geometry import Polygon, LineString, box, mapping
from shapely.affinity import rotate, translate
import math

class AxisGenerator:
    def __init__(self, corners, angle, space):
        if len(corners) != 2:
            raise ValueError("Exactly 2 corner points must be specified for a rectangle.")

        self.corners = self.createPolygon(corners)
        self.polygon = Polygon(self.corners)
        self.angle = angle
        self.space = space / math.cos(math.radians(angle))
        self.center = self.polygon.centroid

    def createPolygon(self, corners):
        (x1, y1), (x2, y2) = corners
        pts = [(x1, y1), (x2, y2), (x1, y2), (x2, y1)]
        center_x = sum([p[0] for p in pts]) / 4
        center_y = sum([p[1] for p in pts]) / 4
        pts.sort(key=lambda p: math.atan2(p[1] - center_y, p[0] - center_x), reverse=True)
        return pts

    def createBoundingBox(self, scale=1.5):
        minx, miny, maxx, maxy = self.polygon.bounds
        width = maxx - minx
        height = maxy - miny

        enlarged_box = box(minx - width * scale, miny - height * scale,
                           maxx + width * scale, maxy + height * scale)
        return enlarged_box

    def addPolylines(self):
        lines = []
        enlarged_box = self.createBoundingBox()

        basis_line = LineString([(-enlarged_box.bounds[2], 0), (enlarged_box.bounds[2], 0)])

        rotate_line = rotate(basis_line, self.angle, origin=(0, 0), use_radians=False)

        rotate_line = translate(rotate_line, xoff=self.center.x, yoff=self.center.y)

        for direction in [1, -1]:
            shift = 0
            while True:
                shifted_line = translate(rotate_line, yoff=shift)
                intersect_pts = self.polygon.intersection(shifted_line)

                if not intersect_pts.is_empty:
                    if isinstance(intersect_pts, LineString):
                        lines.append(list(intersect_pts.coords))
                    elif hasattr(intersect_pts, "geoms"):
                        for intersection in intersect_pts.geoms:
                            lines.append(list(intersection.coords))

                shift += direction * self.space

                if not self.polygon.intersects(shifted_line):
                    break

        return lines

    def linestrings2shapefile(self, path):
        polylines = self.addPolylines()

        scheme = {
            'geometry': 'LineString',
            'properties': {'id': 'int'},
        }

        with fiona.open(path, 'w', driver='ESRI Shapefile', schema=scheme) as output:
            for idx, line in enumerate(polylines):
                line_geom = LineString(line)
                output.write({
                    'geometry': mapping(line_geom),
                    'properties': {'id': idx},
                })

    def getPolylineCoords(self):
        polylines = self.addPolylines()
        return polylines
