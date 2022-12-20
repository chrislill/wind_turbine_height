import dotenv
import pandas as pd
from osgeo import gdal


def main():
    dotenv.load_dotenv(".env")
    dotenv.load_dotenv(".env.secret")

    # Clip each image to 2km * 2km, centered on the wind site
    clip_width = 2000

    # Load site photo metadata
    site_metadata = pd.read_csv("data/site_photo_metadata.csv")

    for _, site in site_metadata.iterrows():
        print(f"Cropping {site.site}")
        orthophoto = gdal.Open(f"data/orthophotos/{site.orthophoto_name}.ecw")
        source_info = gdal.Info(orthophoto, format="json")
        resolution = source_info["geoTransform"][1]
        left_offset = int(
            (site.site_x - source_info["geoTransform"][0] - (clip_width / 2))
            / resolution
        )
        top_offset = int(
            (source_info["geoTransform"][3] - site.site_y - (clip_width / 2))
            / resolution
        )
        gdal.Translate(
            f"data/site_images/{site.site}.png",
            orthophoto,
            format="PNG",
            srcWin=[
                left_offset,
                top_offset,
                int(clip_width / resolution),
                int(clip_width / resolution),
            ],
        )

    print("Done")


if __name__ == "__main__":
    main()
