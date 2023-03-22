import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from osgeo import gdal  # noqa
from scipy.interpolate import RegularGridInterpolator
from shapely.geometry import Point


class ElevationInterpolator:
    metadata = None
    filename = None
    interpolator = None
    transformer_to_30n = Transformer.from_crs(f"EPSG:4326", f"EPSG:25830")
    missing_list = []

    def __init__(self):
        # Load elevation metadata from Informacion_auxiliar_LIDAR_2_cobertura.zip
        self.metadata = gpd.read_file(
            "data/digital_elevation/coverage/MDT05.shp"  # noqa
        ).set_geometry(
            "geometry", drop=True
        )

    def check_cache(self, point):
        """Find the nearest Digital Elevation tile and load into cache if it has changed."""
        elevation_tiles = (
            self.metadata[self.metadata.contains(point)]
            .assign(distance_to_centroid=lambda x: x.distance(point))
            .sort_values("distance_to_centroid")
        )
        if len(elevation_tiles) == 0:
            raise ValueError("Elevation tile could not be found in metadata")

        new_filename = elevation_tiles.FICHERO.iloc[0]
        if new_filename != self.filename:
            self.load_elevation_interpolator(new_filename)

    def get_elevation(self, latitude, longitude):
        point = Point(self.transformer_to_30n.transform(latitude, longitude))
        self.check_cache(point)

        if self.interpolator is None:
            return np.nan

        elevation = self.interpolator([point.y, point.x])[0]
        return elevation

    def load_elevation_interpolator(self, filename):
        """Load RegularGridInterpolator from ascii digital elevation file."""
        try:
            elevation_data = pd.read_csv(
                f"data/digital_elevation/files/{filename}",
                skiprows=6,
                skipfooter=1,
                header=None,
                sep=" ",
                engine="python",
            ).iloc[:, :-1]
            metadata = pd.read_csv(
                f"data/digital_elevation/files/{filename}",
                header=None,
                skipfooter=len(elevation_data) + 1,
                index_col=0,
                sep=" ",
                engine="python",
            ).T.iloc[0]
        except FileNotFoundError:
            print(f"Could not load {filename}, please download and add to dataset.")
            self.interpolator = None
            self.filename = filename
            self.missing_list.append(filename)
            return

        # Replace null values
        elevation_data[elevation_data == metadata.NODATA_VALUE] = np.nan

        # Interpolate elevation. Note that 0, 0 is the NW corner of the data.
        x_values = np.linspace(
            metadata.XLLCENTER,
            metadata.XLLCENTER + (metadata.NCOLS - 1) * metadata.CELLSIZE,
            metadata.NCOLS,
        )
        y_values = np.linspace(
            metadata.YLLCENTER + (metadata.NROWS - 1) * metadata.CELLSIZE,
            metadata.YLLCENTER,
            metadata.NROWS,
        )
        self.interpolator = RegularGridInterpolator((y_values, x_values), elevation_data.to_numpy())
        self.filename = filename
        print(f"Loaded {filename}")
