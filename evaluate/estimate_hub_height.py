import os
from pathlib import Path

import dotenv
import pandas as pd
from osgeo import gdal


def main():
    dotenv.load_dotenv(".env")
    dotenv.load_dotenv(".env.secret")

    sites = pd.read_csv("data/site_photo_metadata.csv")
    orthophotos = pd.read_csv("data/orthophoto_metadata.csv")
    test_folder = os.getenv("labelled_hub_shadow_folder")
    label_paths = Path(f"hub_shadow_model/runs/test/{test_folder}/labels").glob("*")

    turbine_list = []
    for label_path in label_paths:
        site = label_path.name.split("_")[0]
        turbine_num = int(label_path.name.split("_")[1])
        resolution = orthophotos.query(f"site=='{site}'").resolution.iloc[0]
        labels = pd.read_csv(
                    label_path,
                    sep=" ",
                    names=["label", "center_x", "center_y", "width", "height"],
                )
        # image_path = Path(f"data/turbine_images/test/{site}_{turbine_num}.png")
        # image = gdal.Open(str(image_path))
        # "src_width": image.RasterXSize,
        # "src_height": image.RasterYSize,



        print("Hello")
        #     .assign(
        #     turbine_num=lambda x: range(len(x)),
        #     center_x_px=lambda x: (x.center_x * x.src_width).astype(int),
        #     center_y_px=lambda x: (x.center_y * x.src_height).astype(int),
        #     width_px=lambda x: (x.width * x.src_width).astype(int),
        #     height_px=lambda x: (x.height * x.src_height).astype(int),
        #     # TODO: Handle overlaps for multiple turbines in a cropped image
        #     max_size=lambda x: (
        #         (x[["width_px", "height_px"]] + 20).assign(size=output_size).max(axis=1)
        #     ),
        #     left_offset=lambda x: x.center_x_px - x.max_size.divide(2),
        #     top_offset=lambda x: x.center_y_px - x.max_size.divide(2),
        # )

    print("Done")


if __name__ == "__main__":
    main()
