import io
import os

import dotenv
import pandas as pd
import requests
from PIL import Image


def main():
    dotenv.load_dotenv('.env')
    dotenv.load_dotenv('.env.secret')
    sites = pd.read_csv('data/spanish_sites.csv')
    site = sites.iloc[2]

    zoom_level = 19
    url = f'{os.getenv("bing_maps_url")}/{site.latitude},{site.longitude}/{zoom_level}'
    params = {
        'format': 'png',
        'mapSize': "1500,1500",
        'key': os.getenv('bing_maps_key')
    }
    image_request = requests.get(url, params=params)
    if image_request.status_code != 200:
        print(image_request.text[400:])

    i = Image.open(io.BytesIO(image_request.content))
    # i.show()
    i.save(f'data/site_images/{site.site}.png', comment="bob")

    metadata_request = requests.get(
        url, params={'mapMetadata': 1, 'key': os.getenv('bing_maps_key')}
    )
    # py3exiv2

    print("hi")

if __name__ == "__main__":
    main()
