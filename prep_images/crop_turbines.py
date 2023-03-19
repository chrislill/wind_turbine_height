import os
from pathlib import Path

import dotenv
import pandas as pd
from osgeo import gdal


def main():
    dotenv.load_dotenv(".env")
    dotenv.load_dotenv(".env.secret")
    full_labels = os.getenv("full_site_labels")
    orthophotos = pd.read_csv("data/orthophoto_metadata.csv")

    # We will output square images at their natural resolution. They will be at
    # least 640 wide and include 10px of padding. We will use roboflow to resize
    # them to 640px (or smaller)
    output_size = 640

    turbine_list = []
    for dataset in ["train", "valid", "test"]:
        image_paths = Path(f"data/turbine_shadow_data/{full_labels}/{dataset}/images").glob("*")
        os.makedirs(f"data/turbine_images/{dataset}", exist_ok=True)
        for image_path in image_paths:
            site = image_path.name.split("_png")[0]
            orthophoto = orthophotos[orthophotos.site.eq(site)].iloc[0]
            image = gdal.Open(str(image_path))
            label_path = (
                Path(f"data/turbine_shadow_data/{full_labels}/{dataset}/labels") / image_path.name
            ).with_suffix(".txt")
            turbine_labels = (
                pd.concat(
                    [
                        pd.DataFrame(
                            {
                                "site": site,
                                "src_width": int(2000 / orthophoto.resolution),
                                "src_height": int(2000 / orthophoto.resolution),
                                "resolution": orthophoto.resolution,
                                "site_corner_x": orthophoto.corner_x,
                                "site_corner_y": orthophoto.corner_y,
                                "image_file": image_path.name
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
                )
                .dropna()
                .assign(
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
                    turbine_corner_x=lambda x: x.site_corner_x + (x.left_offset * x.resolution),
                    turbine_corner_y=lambda x: x.site_corner_y - (x.top_offset * x.resolution),
                )
            )
            turbine_list.append(turbine_labels)
            for _, label in turbine_labels.iterrows():
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
            print(f"{label.site}: {len(turbine_labels)} images created")
    turbine_metadata = pd.concat(turbine_list)
    turbine_metadata.to_csv("data/turbine_image_metadata.csv", index=False)
    print("Done")


if __name__ == "__main__":
    main()
