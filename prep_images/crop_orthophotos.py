import dotenv
import pandas as pd
from osgeo import gdal  # noqa


def main():
    dotenv.load_dotenv(".env")
    dotenv.load_dotenv(".env.secret")

    # Clip each image to 2km * 2km, centered on the wind site
    clip_width = 2000

    # Load site photo metadata
    site_metadata = pd.read_csv("data/site_photo_metadata.csv")

    # BUGFIX: Coordinates for five sites were updated in February, but images
    # were not regenerated. Use the old values so that the coordinates match the
    # images. This might cause issues for hub height estimation.
    # TODO: Use a merge rather than this loop. If I wasn't on a deadline...
    old_sites = pd.read_csv("data/site_photo_metadata_20221220.csv")
    for site in ["ausine", "serra_outes", "tella", "viudo", "xiabre"]:
        for column in ["latitude", "longitude"]:
            site_metadata.loc[site_metadata.site.eq(site), column] = old_sites.loc[
                old_sites.site.eq(site), column
            ].iloc[0]

    orthophoto_list = []
    for _, site in site_metadata.iterrows():
        print(f"Cropping {site.site}")
        orthophoto = gdal.Open(f"data/orthophotos/{site.orthophoto_name}.ecw")
        source_info = gdal.Info(orthophoto, format="json")
        resolution = source_info["geoTransform"][1]
        left_offset = int(
            (site.site_x - source_info["geoTransform"][0] - (clip_width / 2)) / resolution
        )
        top_offset = int(
            (source_info["geoTransform"][3] - site.site_y - (clip_width / 2)) / resolution
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

        # Save orthophoto metadata
        if resolution != -source_info["geoTransform"][5]:
            raise ValueError(
                f"Orthophoto X resolution ({resolution}) does not match "
                f"Y resolution ({source_info['geoTransform'][5]})"
            )
        orthophoto_list.append(
            {
                "site": site.site,
                "name": site.orthophoto_name,
                "resolution": resolution,
                "zone": site.orthophoto_name[20:22],
                "corner_x": site.site_x - 1000,
                "corner_y": site.site_y + 1000,
            }
        )
    orthophoto_metadata = pd.DataFrame(orthophoto_list)
    orthophoto_metadata.to_csv("data/orthophoto_metadata.csv", index=False)

    print("Done")


if __name__ == "__main__":
    main()
