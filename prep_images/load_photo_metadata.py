import os
import pathlib
import re
import shutil
import zipfile

import dotenv
import geopandas as gpd
import pandas as pd
import pyodbc


def main():
    dotenv.load_dotenv(".env")
    dotenv.load_dotenv(".env.secret")

    # Load Spanish wind farm metadata, provided by Aurora Energy Research
    # Some wind farms have multiple turbine configurations
    site_metadata = pd.read_csv(os.getenv("site_metadata_path"))

    # BUGFIX: Coordinates for five sites were updated in February, but images
    # were not regenerated. Use the old values so that the coordinates match the
    # images. This might cause issues for hub height estimation.
    # TODO: Use a merge rather than this loop. If I wasn't on a deadline...
    old_matches = pd.read_csv("data/sites/matches_20221217_120744.csv")
    for site in ["ausine", "serra_outes", "tella", "viudo", "xiabre"]:
        for column in ["latitude", "longitude"]:
            site_metadata.loc[site_metadata.site.eq(site), column] = old_matches.loc[
                old_matches.site.eq(site), column
            ].mean()

    sites = (
        site_metadata.query("selected == True")
        .groupby("site")
        .agg(
            {
                "latitude": "mean",
                "longitude": "mean",
                "num_turbines": lambda x: tuple(x),
                "hub_height": lambda x: tuple(x),
            }
        )
        .sort_index()
        .reset_index()
        .assign(
            geometry=lambda x: gpd.points_from_xy(
                x.longitude, x.latitude, crs="EPSG:4326"
            )
        )
        .set_geometry("geometry")
        .to_crs("EPSG:25830")
        .assign(
            site_x=lambda x: x.geometry.x.round(2),
            site_y=lambda x: x.geometry.y.round(2),
        )
    )

    # Load shape files giving the location of each orthophoto tile
    shutil.unpack_archive(
        "data/photo_metadata/fechas_ortofotos_PNOA_MA.zip",
        "data/photo_metadata/orthophoto_tiles",
    )
    orthophoto_tiles = gpd.read_file(
        "data/photo_metadata/orthophoto_tiles/20220923_Estado_Mosaicos_109_MA"  # noqa
        "/20220923_Estado_Mosaicos_MA_MR.shp"  # noqa
    ).assign(tile_centroid=lambda x: x.geometry.centroid)

    # Join orthophoto tiles to sites. If there are duplicates keep the one where
    # the site is closest to the centroid of the tile
    site_tiles = (
        gpd.sjoin(sites, orthophoto_tiles, how="left", predicate="within")
        .assign(
            distance_to_centroid=lambda x: x.distance(x.tile_centroid),
            orthophoto_name=lambda x: (
                "PNOA_MA_OF_ETRS89_HU"
                + x.HUSO.astype(str)
                + "_H50_"
                + x.HMTN50.astype(str)
            ),
        )
        .sort_values(["site", "distance_to_centroid"])
        .drop_duplicates("site")
        .drop(columns="index_right")
    )

    # The orthophotos actually use three different projections for UTM zones 29, 30 and 31
    # Site coordinates are already in 25830. Fix it for 29 and 31
    # https://epsg.io/25829, https://epsg.io/25830, https://epsg.io/25831
    for zone in [29, 31]:
        zone_tiles = (
            site_tiles.query(f"HUSO == '{zone}'")
            .to_crs(f"EPSG:258{zone}")
            .assign(
                site_x=lambda x: x.geometry.x.round(2),
                site_y=lambda x: x.geometry.y.round(2),
            )
        )
        site_tiles.loc[site_tiles.HUSO.eq(str(zone)), ["site_x", "site_y"]] = zone_tiles[
            ["site_x", "site_y"]
        ]

    # Join with photo metadata to find timestamp of the nearest photo
    photo_metadata = load_photo_metadata()
    site_photos = (
        gpd.sjoin_nearest(
            site_tiles, photo_metadata, how="left", distance_col="photo_distance"
        )
        .query("photo_distance < 3100")
        .reset_index(drop=True)
        .loc[
            :,
            [
                "site",
                "latitude",
                "longitude",
                "num_turbines",
                "hub_height",
                "photo_file",
                "photo_timestamp",
                "orthophoto_name",
                "site_x",
                "site_y",
                "HUSO"
            ],
        ]
    )

    # Load old sites, so that we can identify the new images to be labelled
    old_sites = pd.read_csv("data/site_photo_metadata.csv")
    site_photos["new"] = ~site_photos.site.isin(old_sites.site)

    site_photos.to_csv("data/site_photo_metadata.csv", index=False)
    print("Done")


def load_photo_metadata():
    """Load aerial photo metadata from zipped access database files"""
    metadata_path = pathlib.Path("data/photo_metadata")
    database_files = list(metadata_path.glob("**/PNOA*.mdb"))
    if len(database_files) > 0:
        # TODO: Implement logging
        print("Database files are already unzipped.")
    else:
        zip_files = list(metadata_path.glob("**/*.zip"))
        if len(zip_files) == 0:
            print("Please copy zip files to data/photo_metadata.")
        else:
            # Abbreviation PNOA: Plan Nacional de Ortofotografía Aérea  # noqa
            pnoa_regex = re.compile(".*/PNOA_.*mdb")
            for zip_path in zip_files:
                with zipfile.ZipFile(zip_path, "r") as zp:
                    zipped_files = zipfile.ZipFile.infolist(zp)
                    for zipped_file in zipped_files:
                        if pnoa_regex.match(zipped_file.filename):
                            with open(
                                metadata_path / zipped_file.filename.split("/")[-1],
                                "wb",
                            ) as f:
                                f.write(zp.read(zipped_file.filename))
        database_files = list(metadata_path.glob("**/PNOA*.mdb"))
        print(f"Unzipped {len(database_files)} database files.")

    # Load all photo timestamps into a single dataframe
    photo_list = []
    for database_file in database_files:
        connection_string = (
            r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
            rf"DBQ={str(database_file.resolve())};"
        )
        try:
            with pyodbc.connect(connection_string) as connection:
                cursor = connection.cursor()
                results = pd.DataFrame.from_records(
                    cursor.execute(
                        "SELECT FOTOGRAMA_TIFF, FECHA, HORA, LAT_ETRS89, LONG_ETRS89 "  # noqa
                        "FROM VueloEjecutado"  # noqa
                    ).fetchall(),
                    columns=[
                        "photo_file",
                        "date",
                        "time",
                        "photo_latitude",
                        "photo_longitude",
                    ],
                )

                # There is a mixture of datetime objects and strings. Format them all as strings
                # Then combine
                if pd.api.types.infer_dtype(results.date) == "string":
                    results.date = results.date.str.slice(0, 11)
                else:
                    results.date = results.date.dt.strftime(date_format="%d/%m/%Y")
                if pd.api.types.infer_dtype(results.time) == "string":
                    results.time = (
                        results.time.str.strip()
                        .str.replace("60", "00")
                        .str.replace("1899-12-39 ", "")
                    )
                else:
                    results.time = results.time.dt.strftime(date_format="%X")
                results = results.assign(
                    photo_timestamp=lambda x: pd.to_datetime(
                        x.date + " " + x.time, dayfirst=True, utc=True
                    )
                ).drop(columns=["date", "time"])
                photo_list.append(results)

        # TODO: Can we fix these errors. 16/91 labels are being dropped
        except (pyodbc.ProgrammingError, pyodbc.Error):
            print(f"Skipping {database_file} because the query failed.")
    photos = (
        pd.concat(photo_list)
        .sort_values("photo_file")
        .assign(
            geometry=lambda x: gpd.points_from_xy(
                x.photo_longitude, x.photo_latitude, crs="ETRS89"
            )
        )
        .set_geometry("geometry")
        .to_crs("EPSG:25830")
        .assign(photo_centroid=lambda x: x.geometry)
        .reset_index(drop=True)
    )

    return photos


if __name__ == "__main__":
    main()
