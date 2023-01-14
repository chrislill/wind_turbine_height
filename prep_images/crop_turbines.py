import os
from pathlib import Path

import dotenv
import pandas as pd
from osgeo import gdal


def main():
    dotenv.load_dotenv(".env")
    dotenv.load_dotenv(".env.secret")

    # We will output square images at their natural resolution. They will be at
    # least 640 wide and include 10px of padding. We will use roboflow to resize
    # them to 640px (or smaller)
    output_size = 640
    data_version = os.getenv("labelled_sites_version")

    # for dataset in ["train", "valid", "test"]:
    for dataset in ["valid"]:
        image_paths = Path(f"data/turbine_shadow_data/{data_version}/{dataset}/images").glob("*")
        os.makedirs(f"data/turbine_images/{dataset}", exist_ok=True)
        for image_path in image_paths:
            site = image_path.name.split("_png")[0]
            image = gdal.Open(str(image_path))
            label_path = (
                Path(f"data/turbine_shadow_data/{data_version}/{dataset}/labels") / image_path.name
            ).with_suffix(".txt")
            site_labels = pd.concat(
                [
                    pd.DataFrame(
                        {
                            "site": site,
                            "src_width": image.RasterXSize,
                            "src_height": image.RasterYSize,
                        },
                        index=[0],
                    ),
                    pd.read_csv(
                        label_path,
                        sep=" ",
                        names=["center_x", "center_y", "width", "height"],
                    ),
                ],
                axis=1,
            ).assign(
                turbine_num=lambda x: range(len(x)),
                center_x_px=lambda x: (x.center_x * x.src_width).astype(int),
                center_y_px=lambda x: (x.center_y * x.src_height).astype(int),
                width_px=lambda x: (x.width * x.src_width).astype(int),
                height_px=lambda x: (x.height * x.src_height).astype(int),
                # TODO: Handle overlaps for multiple turbines in a cropped image
                max_size=lambda x: (
                    (x[["width_px", "height_px"]] + 20).assign(size=output_size).max(axis=1)
                ),
                left_offset=lambda x: x.center_x_px - x.max_size.divide(2),
                top_offset=lambda x: x.center_y_px - x.max_size.divide(2),
            )
            for _, label in site_labels.iterrows():
                gdal.Translate(
                    f"data/turbine_images/{dataset}/{label.site}_{label.turbine_num}.png",
                    image,
                    format="PNG",
                    srcWin=[
                        label.left_offset,
                        label.top_offset,
                        label.max_size,
                        label.max_size,
                    ],
                )
            print(f"{label.site}: {len(site_labels)} images created")

    print("Done")


if __name__ == "__main__":
    main()
