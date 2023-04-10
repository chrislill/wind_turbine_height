# Data-centric estimation of wind turbine height using aerial imagery

This solution estimates the hub height of wind turbines from aerial photograph and their timestamps. It is the basis of the final project for my MSc in Data Science and includes my [final project report](Data-centric estimation of wind turbine hub height using aerial imagery.pdf).

## Abstract
Data-centric AI is the systematic engineering of data to improve performance, and is a mindset that is actively promoted in the data science community. This project measures the benefit of different data-centric techniques. It focuses on a novel task to estimate wind turbine hub height from aerial imagery in Spain, using computer vision models to measure the turbine shadow and the image timestamp to calculate the turbine height. 

This project demonstrates that different data-centric techniques are optimal for each use cases, even when using the same images. Effective data-centric tooling is needed, not only in Machine Learning Operations (ML Ops) platforms but also embedded in computer vision models. Computer vision frameworks such as YOLOv7 contain many data-centric transformations in their training code by default, and this contributes significantly to their performance.

We demonstrate that good results can be gained from a small dataset of 76 wind farms, with 70% of wind farms having an hub height error of less than 5m. To achieve these results, additional functionality was required to account for elevation differences between the base and hub shadow, and to ensure the correct timestamp was being used for each turbine.

## Pre-requisites
1. Python 3.9
2. YOLOv7 - https://github.com/WongKinYiu/yolov7
3. Pytorch, ideally with CUDA installed to enable GPU processing

## Data
This solution has been implemented to work directly with data from [Centro de Descargas](https://centrodedescargas.cnig.es/CentroDescargas/locale?request_locale=en) in Spain. The easiest approach is to reuse the prepared images which are shared on Roboflow at https://universe.roboflow.com/windturbineheight

Alternatively the following data will need to be prepared.
1. `data/sites/sites.csv` - Collection of sites with latitude and longitude
2. `data/orthophotos` - Aerial imagery, ideally in `.ecw` format. 
3. `data/photo_metadata` - Database files with photo timestamps.
4. `data/digital_elevation` - Digital elevation files to correct for site topography

## Steps
Steps 1, 2 and 4 can be skipped if the prepared data is loaded from Roboflow.
1. `prep_images/load_photo_metadata.py`
2. `prep_images/crop_orthophotos.py`
3. `turbine_shadow_model/026_additional_labels_mixup.cmd` (best model)
4. `prep_images/crop_turbines.py`
5. `hub_shadow_model/015_active_learning.cmd` (best model)
6. `hub_shadow_model/test_hub_shadows.cmd`
7. `evaluate/estimate_hub_height.py`
