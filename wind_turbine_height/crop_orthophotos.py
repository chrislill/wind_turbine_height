import os

import dotenv
import pandas as pd
import rasterio as rio
from osgeo import gdal


def main():
    dotenv.load_dotenv('.env')
    dotenv.load_dotenv('.env.secret')

    # Load site photo metadata
    site_metadata = pd.read_csv('data/site_photo_metadata.csv')

    site = site_metadata[site_metadata.site.eq('brulles')].iloc[0]
    # with gdal.Open(f'data/orthophotos/{site.orthophoto_name}.ecw') as orthophoto:
    orthophoto = gdal.Open(f'data/orthophotos/{site.orthophoto_name}.ecw')
    source_info = gdal.Info(orthophoto, format='json')
    if source_info['geoTransform'][1] != 0.25:
        raise ValueError("Orthophoto resolution is not 0.25m - Implement different resolutions")
    left_offset = int((site.site_x - source_info['geoTransform'][0] - 1000) / 0.25)
    top_offset = int((source_info['geoTransform'][3] - site.site_y - 1000) / 0.25)
    gdal.Translate(
        f'data/site_images/{site.site}.png',
        orthophoto,
        format='PNG',
        srcWin=[left_offset, top_offset, 8000, 8000]
    )

    print('Done')


if __name__ == '__main__':
    main()
