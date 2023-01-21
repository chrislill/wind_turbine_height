from datetime import datetime
import math
import os
from pathlib import Path
import re

import dotenv
import numpy as np
import pandas as pd
from skyfield import api as skyfield_api
from osgeo import gdal


def main():
    dotenv.load_dotenv(".env")
    dotenv.load_dotenv(".env.secret")

    sites = pd.read_csv("data/site_photo_metadata.csv")
    orthophotos = pd.read_csv("data/orthophoto_metadata.csv")
    test_folder = os.getenv("labelled_hub_shadow_folder")
    label_paths = Path(f"hub_shadow_model/runs/test/{test_folder}/labels").glob("*")

    # Set up skyfield to calculate relative positions of the earth and sun
    ephemeris = skyfield_api.load("de421.bsp")
    earth, sun = ephemeris["earth"], ephemeris["sun"]

    turbine_list = []
    turbine_regex = re.compile(r"_(\d+)_")
    hub_height_regex = re.compile(r"([0-9]*[.]?[0-9]+)")
    for label_path in label_paths:
        name_split = turbine_regex.split(label_path.name)
        site = name_split[0]
        turbine_num = int(name_split[1])
        resolution = orthophotos.query(f"site=='{site}'").resolution.iloc[0]
        site_metadata = sites[sites.site.eq(site)].iloc[0]

        # TODO: Handle multiple hub heights
        hub_heights = hub_height_regex.findall(site_metadata.hub_height)
        if len(hub_heights) >= 1:
            actual_hub_height = float(hub_heights[0])
        else:
            actual_hub_height = np.nan

        # The predicted labels are listed in order of confidence
        labels = pd.read_csv(
            label_path,
            sep=" ",
            names=["label", "center_x", "center_y", "width", "height"],
        )
        if labels.label.eq(0).sum() >= 1 and labels.label.eq(1).sum() >= 1:
            base_x, base_y = labels.query("label == 0").iloc[0, 1:3].values
            hub_x, hub_y = labels.query("label == 1").iloc[0, 1:3].values
        else:
            turbine_list.append(
                {
                    "site": site,
                    "turbine_num": turbine_num,
                    "actual_hub_height": actual_hub_height,
                }
            )
            continue

        # Calculate shadow length and sun azimuth from labels (compass heading of the shadow)
        image_path = next(Path("data/turbine_images").glob(f"**/{site}_{turbine_num}.png"))
        image = gdal.Open(str(image_path))
        x_distance = (base_x - hub_x) * image.RasterXSize * resolution
        y_distance = (base_y - hub_y) * image.RasterYSize * resolution
        shadow_length = (x_distance**2 + y_distance**2) ** 0.5
        if x_distance >= 0:
            shadow_azimuth = 90 + math.atan(y_distance / x_distance) * 180 / math.pi
        else:
            shadow_azimuth = 270 + math.atan(y_distance / x_distance) * 180 / math.pi

        # Calculate the sun altitude and azimuth from the timestamp
        observer = earth + skyfield_api.wgs84.latlon(
            latitude_degrees=site_metadata.latitude, longitude_degrees=site_metadata.longitude
        )
        time = skyfield_api.load.timescale().from_datetime(
            datetime.fromisoformat(site_metadata.photo_timestamp)
        )
        altitude, azimuth, _ = observer.at(time).observe(sun).apparent().altaz()
        estimated_hub_height = math.tan(altitude.radians) * shadow_length

        turbine_list.append(
            {
                "site": site,
                "turbine_num": turbine_num,
                "estimated_hub_height": round(estimated_hub_height, 1),
                "actual_hub_height": actual_hub_height,
                "hub_height_diff": round(estimated_hub_height, 1) - actual_hub_height,
                "azimuth_diff": abs(int(shadow_azimuth) - int(azimuth.degrees)),
                "shadow_azimuth": int(shadow_azimuth),
                "azimuth": int(azimuth.degrees),
                "shadow_length": round(shadow_length, 1),
                "altitude": round(altitude.degrees, 1),
            }
        )

    turbines = pd.DataFrame(turbine_list)
    good_turbines = turbines[turbines.azimuth_diff.le(5) & ~turbines.actual_hub_height.isna()]
    good_sites = good_turbines.groupby("site").agg({
        "turbine_num": "count",
        "actual_hub_height": "mean",
        "estimated_hub_height": "mean",
        "hub_height_diff": "mean",
    }).sort_values("hub_height_diff")

    print("Done")


if __name__ == "__main__":
    main()
