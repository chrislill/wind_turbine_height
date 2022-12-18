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
    # with rio.open(f'data/orthophotos/{site.orthophoto_name}.ecw') as orthophoto:
    orthophoto = gdal.Open(f'data/orthophotos/{site.orthophoto_name}.ecw')
    source_info = gdal.Info(orthophoto, format='json')
    translate_options = ' '.join(['-of PNG', '-srcwin 10 -100 4000 4000'])


    print('Done')


if __name__ == '__main__':
    main()
