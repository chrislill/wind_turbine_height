import math
import os
from pathlib import Path

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
    ephemeris = skyfield_api.load('de421.bsp')
    earth, sun = ephemeris['earth'], ephemeris['sun']

    turbine_list = []
    for label_path in label_paths:
        site = label_path.name.split("_")[0]
        turbine_num = int(label_path.name.split("_")[1])
        resolution = orthophotos.query(f"site=='{site}'").resolution.iloc[0]
        site_metadata = sites[sites.site.eq(site)].iloc[0]

        # The predicted labels are listed in order of confidence
        labels = pd.read_csv(
                    label_path,
                    sep=" ",
                    names=["label", "center_x", "center_y", "width", "height"],
                )
        if labels.label.eq(0).sum() >= 1:
            base_x, base_y = labels.query("label == 0").iloc[0, 1:3].values
        else:
            base_x, base_y = None
        if labels.label.eq(0).sum() >= 1:
            hub_x, hub_y = labels.query("label == 1").iloc[0, 1:3].values
        else:
            hub_x, hub_y = None

        # Calculate shadow length and sun azimuth from labels (compass heading of the shadow)
        image_path = Path(f"data/turbine_images/test/{site}_{turbine_num}.png")
        image = gdal.Open(str(image_path))
        x_distance = (base_x - hub_x) * image.RasterXSize * resolution
        y_distance = (base_y - hub_y) * image.RasterYSize * resolution
        shadow_length = (x_distance ** 2 + y_distance ** 2) ** 0.5
        if x_distance >= 0:
            shadow_azimuth = 90 + math.atan(y_distance / x_distance) * 180 / math.pi
        else:
            shadow_azimuth = 270 + math.atan(y_distance / x_distance) * 180 / math.pi

        # Calculate the sun altitude and azimuth from the timestamp
        observer = earth + skyfield_api.wgs84.latlon(
            latitude_degrees=site_metadata.latitude, longitude_degrees=site_metadata.longitude
        )
        time = skyfield_api.load.timescale().from_datetime(site_metadata.photo_timestamp)
        altitude, azimuth, _ = observer.at(time).observe(sun).apparent().altaz()
        estimated_hub_height = math.tan(altitude.radians) * shadow_length

        # Check that the azimuth of the sun matches the shadow
        # if abs(shadow_azimuth - azimuth.degrees) > 5:
        #     raise ValueError(
        #         f"Shadow azimuth {shadow_azimuth:.0f} does not match "
        #         f"sun azimuth {azimuth.degrees:.0f}"
        #     )

        turbine_list.append({
            "site": site,
            "turbine_num": turbine_num,
            "shadow_length": round(shadow_length, 1),
            "altitude": round(altitude.degrees, 1),
            "estimated_hub_height": round(estimated_hub_height, 1),
            "shadow_azimuth": int(shadow_azimuth),
            "azimuth": int(azimuth.degrees)
        })
        print("Hello")

    turbines = pd.DataFrame(turbine_list)
    print("Done")


if __name__ == "__main__":
    main()
