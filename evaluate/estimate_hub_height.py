import math
from pathlib import Path
import re

import dotenv
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from osgeo import gdal  # noqa
from scipy import stats
from scipy.interpolate import RegularGridInterpolator
from shapely.geometry import Point
from skyfield import api as skyfield_api
from prep_images.load_photo_metadata import load_photo_metadata


def main(run_name):
    dotenv.load_dotenv(".env")
    dotenv.load_dotenv(".env.secret")

    sites = pd.read_csv("data/site_photo_metadata.csv")
    turbines = pd.read_csv("data/turbine_image_metadata.csv")
    label_paths = Path(f"hub_shadow_model/runs/detect/{run_name}/labels").glob("*")

    # Set up skyfield to calculate relative positions of the earth and sun
    ephemeris = skyfield_api.load("de421.bsp")
    earth, sun = ephemeris["earth"], ephemeris["sun"]

    # Load aerial photo data to find the nearest photo for each turbine
    photo_metadata = load_photo_metadata()
    transformer_to_30n = Transformer.from_crs(f"EPSG:4326", f"EPSG:25830")

    # Load elevation metadata from Informacion_auxiliar_LIDAR_2_cobertura.zip
    elevation_metadata = gpd.read_file(
        "data/digital_elevation/coverage/MDT05.shp"  # noqa
    ).set_geometry("geometry", drop=True)  # .assign(tile_centroid=lambda x: x.geometry.centroid)

    turbine_regex = re.compile(r"_(\d+)_")
    hub_height_regex = re.compile(r"([0-9]*[.]?[0-9]+)")
    turbine_list = []
    missing_list = []
    for label_path in label_paths:
        name_split = turbine_regex.split(label_path.name)
        site = name_split[0]
        turbine_num = int(name_split[1])
        turbine = turbines.query("site == @site and turbine_num == @turbine_num").iloc[0]
        site_metadata = sites[sites.site.eq(site)].iloc[0]

        # Drop Ourol and Xiabre because the co-ordinates are for the wrong site with an
        # unknown hub height.
        if site in ["ourol", "xiabre"]:
            continue

        # Only Becerril has turbines listed with different heights
        hub_heights = hub_height_regex.findall(site_metadata.hub_height)
        if len(hub_heights) == 0:
            actual_hub_height = np.nan
        elif len(hub_heights) == 1 or hub_heights[0] == hub_heights[1]:
            actual_hub_height = float(hub_heights[0])
        elif len(hub_heights) > 1:
            turbine_counts = hub_height_regex.findall(site_metadata.num_turbines)
            actual_hub_height = np.average(
                [float(h) for h in hub_heights], weights=[float(c) for c in turbine_counts]
            )
        else:
            raise ValueError("Unable to calculate hub height")

        labels = pd.read_csv(
            label_path,
            sep=" ",
            names=["label", "center_x", "center_y", "width", "height", "confidence"],
        )
        turbine_metadata = {
            "site": site,
            "turbine_id": turbine_num,
            "actual_hub_height": actual_hub_height,
            "num_bases": labels.label.eq(0).sum(),
            "num_hub_shadows": labels.label.eq(1).sum(),
        }

        # The predicted labels are listed in order of confidence
        if turbine_metadata["num_bases"] == 1 and turbine_metadata["num_hub_shadows"] == 1:
            base_x, base_y = labels.query("label == 0").iloc[0, 1:3].values
            hub_x, hub_y = labels.query("label == 1").iloc[0, 1:3].values
        else:
            # Models have not detected a base and a hub
            turbine_list.append(turbine_metadata)
            continue

        # Calculate shadow length and sun azimuth from labels (compass heading of the shadow)
        try:
            image_path = next(Path("data/turbine_images").glob(f"**/{site}_{turbine_num}.png"))
        except StopIteration:
            # Images have been removed from dataset (example Almendarache)  # noqa
            turbine_list.append(turbine_metadata)
            continue

        # Calculate label positions within the image
        image = gdal.Open(str(image_path))
        x_distance = (base_x - hub_x) * image.RasterXSize * turbine.resolution
        y_distance = (base_y - hub_y) * image.RasterYSize * turbine.resolution
        shadow_length = (x_distance**2 + y_distance**2) ** 0.5
        if x_distance >= 0:
            shadow_azimuth = 90 + math.atan(y_distance / x_distance) * 180 / math.pi
        else:
            shadow_azimuth = 270 + math.atan(y_distance / x_distance) * 180 / math.pi

        # Calculate label latitude and longitude
        base_latitude, base_longitude = calculate_coordinates(
            base_x, base_y, turbine, site_metadata.HUSO
        )
        hub_latitude, hub_longitude = calculate_coordinates(
            hub_x, hub_y, turbine, site_metadata.HUSO
        )

        # Find the timestamp for the nearest aerial photo
        point_x, point_y = transformer_to_30n.transform(base_latitude, base_longitude)
        turbine_point = Point(point_x, point_y)
        area_around_turbine = turbine_point.buffer(3100)
        nearest_photo = (
            photo_metadata[photo_metadata.within(area_around_turbine)]
            .assign(distance_to_centroid=lambda x: x.distance(turbine_point))
            .sort_values("distance_to_centroid")
        )
        if nearest_photo.shape[0] > 0:
            nearest_photo = nearest_photo.iloc[0]
        else:
            turbine_list.append(turbine_metadata)
            continue

        # Calculate the sun altitude and azimuth from the timestamp
        observer = earth + skyfield_api.wgs84.latlon(
            latitude_degrees=base_latitude, longitude_degrees=base_longitude
        )
        time = skyfield_api.load.timescale().from_datetime(nearest_photo.photo_timestamp)
        altitude, azimuth, _ = observer.at(time).observe(sun).apparent().altaz()
        shadow_height = math.tan(altitude.radians) * shadow_length, 1

        # Include topology correction
        base_height = get_elevation(turbine_point, elevation_metadata)
        hub_point = Point(transformer_to_30n.transform(base_latitude, base_longitude))
        hub_shadow_height = get_elevation(hub_point, elevation_metadata)

        # get_elevation returns the filename if the file is not present on disk
        if isinstance(base_height, str):
            missing_list.append(base_height)
            continue
        if isinstance(hub_shadow_height, str):
            missing_list.append(hub_shadow_height)
            continue

        height_correction = base_height - hub_shadow_height
        estimated_hub_height = round(shadow_height[0] - height_correction, 1)
        # estimated_hub_height = shadow_height[0]

        turbine_list.append(
            turbine_metadata
            | {
                "actual_hub_height": actual_hub_height,
                "estimated_hub_height": estimated_hub_height,
                "hub_height_diff": estimated_hub_height - actual_hub_height,
                "azimuth_diff": abs(int(shadow_azimuth) - int(azimuth.degrees)),
                "shadow_azimuth": round(shadow_azimuth, 1),
                "azimuth": round(azimuth.degrees, 1),
                "shadow_length": round(shadow_length, 1),
                "altitude": round(altitude.degrees, 1),
                "base_latitude": round(base_latitude, 6),
                "base_longitude": round(base_longitude, 6),
                "hub_latitude": round(hub_latitude, 6),
                "hub_longitude": round(hub_longitude, 6),
                "base_height": round(base_height, 1),
                "hub_shadow_height": round(hub_shadow_height, 1),
                "height_correction": round(height_correction, 1),
                "photo_file": nearest_photo.photo_file,
            }
        )
    missing_files = sorted(set(missing_list))
    pd.Series(missing_files).to_csv(f"data/digital_elevation/{run_name}_missing_files.csv")
    print(r"Saved list of missing files\n", missing_files)

    turbines = pd.DataFrame(turbine_list).assign(
        missing_labels=lambda x: x.num_bases.eq(0) | x.num_hub_shadows.eq(0),
        multiple_labels=lambda x: (x.num_bases + x.num_hub_shadows).gt(2) & ~x.missing_labels,
        azimuth_mismatch=lambda x: x.azimuth_diff.gt(10) & ~x.multiple_labels,
        good_estimate=lambda x: (
            ~x[["missing_labels", "multiple_labels", "azimuth_mismatch"]].any(axis=1)
        ),
    )
    site_results = (
        turbines[turbines.good_estimate]
        .groupby("site")
        .agg(
            {
                "actual_hub_height": "mean",
                "estimated_hub_height": "mean",
                "hub_height_diff": "mean",
                "altitude": "count",
            }
        )
        .rename(columns={"altitude": "valid_estimates"})
        .join(
            turbines[~turbines.good_estimate]
            .groupby("site")
            .agg({"missing_labels": "sum", "multiple_labels": "sum", "azimuth_mismatch": "sum"}),
            how="outer",
        )
        .assign(num_turbines=lambda x: x.iloc[:, -4:].sum(axis=1))
    )
    turbines.to_csv(f"data/{run_name}_turbine_predictions.csv", index=False)
    site_results.to_csv(f"data/{run_name}_site_predictions.csv")

    # Plot histogram of hub height errors, using bins of 2m width
    fig, ax = plt.subplots(figsize=(6, 4))
    bins = range(
        (round(site_results.hub_height_diff.min() / 2) * 2) - 1,
        (round(site_results.hub_height_diff.max() / 2) * 2) + 3,
        2,
    )
    site_results.hub_height_diff.plot.hist(bins=bins, ax=ax, label="_remove")
    ax.set_xlabel(f"Hub height errors in the {run_name}ing set (m)")
    ax.axvline(-5, color="green", linestyle="dotted", label="Required accuracy of 5m")
    ax.axvline(5, color="green", linestyle="dotted")
    fig.tight_layout()
    ax.legend()
    fig.savefig(f"data/plots/{run_name}_hub_height_errors.png")

    # Carry out a one sample, two-tailed t-test
    # Null hypothesis: Error < -5m or Error > 5m
    _, p_lower = stats.ttest_1samp(
        site_results.hub_height_diff, -5, nan_policy="omit", alternative="greater"
    )
    _, p_upper = stats.ttest_1samp(
        site_results.hub_height_diff, 5, nan_policy="omit", alternative="less"
    )
    p_value = p_lower + p_upper
    summary = f"{run_name} P-value: {p_value:.3f}\nP-lower: {p_lower:.3f}\nP-upper: {p_upper:.3f}"
    print(summary)
    print(stats.shapiro(site_results.hub_height_diff.dropna()))
    print("End")


def calculate_coordinates(object_x, object_y, turbine, zone):
    x_coordinate = turbine.turbine_corner_x + (object_x * turbine.resolution * turbine.max_size)
    y_coordinate = turbine.turbine_corner_y - (object_y * turbine.resolution * turbine.max_size)

    transformer = Transformer.from_crs(f"EPSG:258{zone}", "EPSG:4326")
    latitude, longitude = transformer.transform(x_coordinate, y_coordinate)

    return latitude, longitude


def get_elevation(point, elevation_metadata):
    """Interpolate the elevation from a Digital Elevation tile

    :param point: Point object with X, Y coordinates in UTM zone 30N
    :param elevation_metadata: Geodataframe of elevation tiles
    :return: height, or filename if it could not be loaded.
    """
    elevation_tiles = (
        elevation_metadata[elevation_metadata.contains(point)]
        .assign(distance_to_centroid=lambda x: x.distance(point))
        .sort_values("distance_to_centroid")
    )
    if len(elevation_tiles) == 0:
        return None
    try:
        elevation_data = pd.read_csv(
            f"data/digital_elevation/files/{elevation_tiles.FICHERO.iloc[0]}",
            skiprows=6,
            skipfooter=1,
            header=None,
            sep=" ",
            engine="python"
        ).iloc[:, :-1]
        metadata = pd.read_csv(
            f"data/digital_elevation/files/{elevation_tiles.FICHERO.iloc[0]}",
            header=None,
            skipfooter=len(elevation_data) + 1,
            index_col=0,
            sep=" ",
            engine="python"
        ).T.iloc[0]
    except FileNotFoundError:
        print(f"Could not load {elevation_tiles.FICHERO.iloc[0]}")
        return elevation_tiles.FICHERO.iloc[0]

    # Replace null values
    elevation_data[elevation_data == metadata.NODATA_VALUE] = np.nan

    # Interpolate elevation
    x_values = np.linspace(
            metadata.XLLCENTER,
            metadata.XLLCENTER + (metadata.NCOLS - 1) * metadata.CELLSIZE,
            metadata.NCOLS
        )
    y_values = np.linspace(
            metadata.YLLCENTER,
            metadata.YLLCENTER + (metadata.NROWS - 1) * metadata.CELLSIZE,
            metadata.NROWS
        )
    interpolator = RegularGridInterpolator((y_values, x_values), elevation_data.to_numpy())
    elevation = interpolator([point.y, point.x])

    return elevation[0]


if __name__ == "__main__":
    main("test")
    # main("train")
