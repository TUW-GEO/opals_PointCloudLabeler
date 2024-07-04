import bisect

class StationPolyline2D:
    """2d polyline class with station support

    The class is initialized with a list of 2d point vertices. It then computes the corresponding station value
    (accumulated segment length) for each vertex. The class supports linear interpolation function to retrieve a point
    and direction based on a given station value.
    """
    def __init__(self, vertices):
        assert(isinstance(vertices, list))
        self.vertices = vertices
        self.stations = None
        self.directions = None
        self._update_values()

    def _update_values(self):
        self.stations = [0]
        self.directions = []
        currStat = 0
        for idx in range(1, len(self.vertices)):
            pt1 = self.vertices[idx - 1]
            pt2 = self.vertices[idx]
            dx = pt2[0]-pt1[0]
            dy = pt2[1]-pt1[1]
            slen = (dx ** 2 + dy ** 2) ** 0.5
            if slen == 0:
                raise Exception("Identical subsequent 2d points are not allowed")
            dir = [dx/slen, dy/slen]
            self.directions.append(dir)
            currStat += slen
            self.stations.append(currStat)
        # duplicate last entry for direction (for simplified handling during interpolation)
        self.directions.append(self.directions[-1])

    def __len__(self):
        return len(self.vertices)

    def __getitem__(self, idx):
        "returns vertex and station value based on index"
        return self.vertices[idx], self.stations[idx]

    def min_station(self):
        return self.stations[0]

    def max_station(self):
        return self.stations[-1]

    def get_point(self, station, interpolate_outside=True):
        return self.get_point_and_direction(station, interpolate_outside)[0]

    def get_point_and_direction(self, station, interpolate_outside=True):
        idx = bisect.bisect_left(self.stations, station)
        if idx >= len(self.stations):
            if not interpolate_outside:
                return None, None
            else:
                idx = idx - 1
        elif idx == 0 and station < 0:
            if not interpolate_outside:
                return None, None
            else:
                idx = idx + 1

        # only interpolate station doesn't exactly match linestring vertices
        if station == self.stations[idx]:
            return self.vertices[idx], self.directions[idx]
        else:
            pt = self.vertices[idx - 1]
            dir = self.directions[idx-1]
            s = self.stations[idx - 1]
            ds = station-s
            ptRet = [pt[0]+ds*dir[0], pt[1]+ds*dir[1]]
            return ptRet, dir


class StationCubicSpline2D(StationPolyline2D):
    """2d cubic spline class with station support

    The class is initialized with a list of 2d point vertices. It then computes the corresponding station value
    (accumulated segment length) for each vertex. The class supports cubic spline interpolation function to retrieve
    a point and direction based on a given station value.
    """
    def __init__(self, vertices):
        assert(isinstance(vertices, list))
        self._2d_cubic_spline(vertices)
        super().__init__(self.vertices)

    def _2d_cubic_spline(self, vertices):
        points = np.array(vertices)

        x = points[:, 0]
        y = points[:, 1]

        t = np.arange(len(points))

        cs_x, cs_y = CubicSpline(t, x), CubicSpline(t, y)

        num_pts_between = 10
        t_new = np.linspace(t.min(), t.max(), num_pts_between * (len(points) - 1) + 1)

        x_new, y_new = cs_x(t_new), cs_y(t_new)

        self.vertices = list(np.column_stack((x_new, y_new)))


if __name__ == "__main__":
    pts = [[0,0], [5,0], [5,5]]
    statLine = StationPolyline2D(pts)

    interpolate_outside = False

    print(statLine[0])

    print(statLine.get_point_and_direction(-1, interpolate_outside))
    print(statLine.get_point_and_direction(0, interpolate_outside))
    print(statLine.get_point_and_direction(0.5, interpolate_outside))
    print(statLine.get_point_and_direction(5, interpolate_outside))
    print(statLine.get_point_and_direction(8, interpolate_outside))
    print(statLine.get_point_and_direction(10, interpolate_outside))
    print(statLine.get_point_and_direction(12, interpolate_outside))
