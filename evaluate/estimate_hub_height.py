from datetime import datetime
import math
from pathlib import Path
import re

import dotenv
import numpy as np
import pandas as pd
from osgeo import gdal  # noqa
from scipy import stats
from skyfield import api as skyfield_api


def main(run_name):
    dotenv.load_dotenv(".env")
    dotenv.load_dotenv(".env.secret")

    sites = pd.read_csv("data/site_photo_metadata.csv")
    orthophotos = pd.read_csv("data/orthophoto_metadata.csv")
    label_paths = Path(f"hub_shadow_model/runs/detect/{run_name}/labels").glob("*")

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

        # Drop Ourol because the site co-ordinates are wrong
        if site == "ourol":
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
            "num_hub_shadows": labels.label.eq(1).sum()
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
        estimated_hub_height = round(math.tan(altitude.radians) * shadow_length, 1)

        turbine_list.append(
            turbine_metadata |
            {
                "actual_hub_height": actual_hub_height,
                "estimated_hub_height": estimated_hub_height,
                "hub_height_diff": estimated_hub_height - actual_hub_height,
                "azimuth_diff": abs(int(shadow_azimuth) - int(azimuth.degrees)),
                "shadow_azimuth": round(shadow_azimuth, 1),
                "azimuth": round(azimuth.degrees, 1),
                "shadow_length": round(shadow_length, 1),
                "altitude": round(altitude.degrees, 1),
            }
        )

    turbines = pd.DataFrame(turbine_list).assign(
        missing_labels=lambda x: x.num_bases.eq(0) | x.num_hub_shadows.eq(0),
        multiple_labels=lambda x: (x.num_bases + x.num_hub_shadows).gt(2) & ~x.missing_labels,
        azimuth_mismatch=lambda x: x.azimuth_diff.gt(10) & ~x.multiple_labels,
        good_estimate=lambda x: (
            ~x[["missing_labels", "multiple_labels", "azimuth_mismatch"]].any(axis=1)
        )
    )
    site_results = (
        turbines[turbines.good_estimate]
        .groupby("site")
        .agg({
            "actual_hub_height": "mean",
            "estimated_hub_height": "mean",
            "hub_height_diff": "mean",
            "altitude": "count"
        })
        .rename(columns={"altitude": "valid_estimates"})
        .join(
            turbines[~turbines.good_estimate]
            .groupby("site")
            .agg({
                "missing_labels": "sum",
                "multiple_labels": "sum",
                "azimuth_mismatch": "sum"
            }),
            how="outer"
        )
        .assign(num_turbines=lambda x: x.iloc[:, -4:].sum(axis=1))
    )
    turbines.to_csv(f"data/{run_name}_turbine_predictions.csv", index=False)
    site_results.to_csv(f"data/{run_name}_site_predictions.csv")

    # Carry out a one sample, two-tailed t-test
    # Null hypothesis: Error < -5m or Error > 5m
    _, p_lower = stats.ttest_1samp(
        site_results.hub_height_diff, -5, nan_policy="omit", alternative="greater"
    )
    _, p_upper = stats.ttest_1samp(
        site_results.hub_height_diff, 5, nan_policy="omit", alternative="less"
    )
    p_value = p_lower + p_upper
    summary = f"P-value: {p_value:.3f}\nP-lower: {p_lower:.3f}\nP-upper: {p_upper:.3f}"
    print(summary)
    print("End")


if __name__ == "__main__":
    # main("train")
    main("test")
