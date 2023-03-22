import math
import re
from datetime import datetime
from pathlib import Path

import dotenv
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from osgeo import gdal  # noqa
from pyproj import Transformer
from scipy import stats
from shapely.geometry import Point
from skyfield import api as skyfield_api
from tqdm import tqdm

from evaluate import interpolators
from prep_images.load_photo_metadata import load_photo_metadata


def main(run_name):
    start_time = datetime.now()
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
    elevation_interpolator = interpolators.ElevationInterpolator()

    turbine_regex = re.compile(r"_(\d+)_")
    hub_height_regex = re.compile(r"([0-9]*[.]?[0-9]+)")
    turbine_list = []
    for label_path in tqdm(list(label_paths)):
        name_split = turbine_regex.split(label_path.name)
        site = name_split[0]
        turbine_num = int(name_split[1])
        turbine = turbines.query("site == @site and turbine_num == @turbine_num").iloc[0]
        site_metadata = sites[sites.site.eq(site)].iloc[0]

        # Drop Ourol because the co-ordinates are for the wrong site with an
        # unknown hub height.
        if site in ["ourol"]:
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
        base_point = Point(point_x, point_y)
        area_around_turbine = base_point.buffer(3100)
        nearest_photo = (
            photo_metadata[photo_metadata.within(area_around_turbine)]
            .assign(distance_to_centroid=lambda x: x.distance(base_point))
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
        shadow_height = math.tan(altitude.radians) * shadow_length

        # Include topology correction.
        base_height = elevation_interpolator.get_elevation(base_latitude, base_longitude)
        hub_shadow_height = elevation_interpolator.get_elevation(hub_latitude, hub_longitude)

        height_correction = base_height - hub_shadow_height
        if np.isnan(height_correction):
            height_correction = 0
        estimated_hub_height = round(shadow_height - height_correction, 1)

        turbine_list.append(
            turbine_metadata
            | {
                "actual_hub_height": actual_hub_height,
                "estimated_hub_height": estimated_hub_height,
                "hub_height_diff": estimated_hub_height - actual_hub_height,
                "shadow_height": round(shadow_height, 1),
                "base_height": round(base_height, 1),
                "hub_shadow_height": round(hub_shadow_height, 1),
                "height_correction": round(height_correction, 1),
                "azimuth_diff": abs(int(shadow_azimuth) - int(azimuth.degrees)),
                "shadow_azimuth": round(shadow_azimuth, 1),
                "azimuth": round(azimuth.degrees, 1),
                "shadow_length": round(shadow_length, 1),
                "altitude": round(altitude.degrees, 1),
                "base_latitude": round(base_latitude, 6),
                "base_longitude": round(base_longitude, 6),
                "hub_latitude": round(hub_latitude, 6),
                "hub_longitude": round(hub_longitude, 6),
                "photo_file": nearest_photo.photo_file,
            }
        )
    if len(elevation_interpolator.missing_list) > 0:
        pd.Series(sorted(set(elevation_interpolator.missing_list))).to_csv(
            f"data/digital_elevation/{run_name}_missing_files.csv"
        )
    print(r"Saved list of missing files\n", elevation_interpolator.missing_list)

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
        .round(1)
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
    print(f"Duration: {round(((datetime.now() - start_time).total_seconds() + 61) / 60, 1)} min")


def calculate_coordinates(object_x, object_y, turbine, zone):
    x_coordinate = turbine.turbine_corner_x + (object_x * turbine.resolution * turbine.max_size)
    y_coordinate = turbine.turbine_corner_y - (object_y * turbine.resolution * turbine.max_size)

    transformer = Transformer.from_crs(f"EPSG:258{zone}", "EPSG:4326")
    latitude, longitude = transformer.transform(x_coordinate, y_coordinate)

    return latitude, longitude


if __name__ == "__main__":
    # main("test")
    main("train")
