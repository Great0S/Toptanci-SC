import json
import math
import os
import random

import requests

from config.settings import settings
from models.category_processor import category_processor
from models.dump_category import check_category
from tasks.translation import translate_text

logger = settings.logger
headers = settings.ecwid_headers
token = settings.ecwid_token
download_headers = {'user-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36'}

# Creates a product and assign the main product image


def create_product(product):
    global response_content, Main, body, seoNameEn
    main_category = main_category_ar = None
    categories = check_category()[0]

    try:
        # Creating variables with ready to use data from telegram message
        link = product["link"]
        name = translate_text(product['name'], 'tr')
        nameAr = translate_text(name, 'en')

        desc = desc_ar = None
        if product['descr']:
            desc = translate_text(product['descr'], 'tr')
            desc_ar = translate_text(desc, 'en')
        pc_quantity = [qty for qty in product['attrs']['stock']]
        pc_price = [math.ceil(float(pc) * 1.3 / 18)
                    for pc in product['attrs']['price']]
        color = [translate_text(co, 'tr') for co in product['attrs']['color']]
        colorAr = [translate_text(coAr, 'en') for coAr in color]
        sku = [sk for sk in product['attrs']['code']]
        true = True

        # Category values
        main_category = translate_text(product['main-category'], 'tr')
        second_category = None
        if product['sub-category']:
            second_category = translate_text(product['sub-category'], 'tr')

        while True:
            
            # Assigning categories using a for loop and a condition to match stored category list
            main_category_ar, second_category_name_ar, categories_ids, main_category_id, categories_json = category_processor(
            main_category, second_category, categories, link)
            
            if main_category_id:
                break
            continue 

        # Create a product request body
        if second_category_name_ar:
            seo_name_ar = main_category_ar + ' / ' + \
                second_category_name_ar + ' / ' + nameAr
        else:
            seo_name_ar = main_category_ar + ' / ' + nameAr

        seo_name = main_category + ' / ' + name

        for attr in sku:
            body = {
                "sku": str(attr),
                "unlimited": False,
                "inStock": true,
                "inStovalue": true,
                "quantity": pc_quantity[sku.index(attr)],
                "name": name,
                "nameTranslated": {
                    "ar": nameAr,
                    "en": name
                },
                "price": pc_price[sku.index(attr)],
                "enabled": true,
                "productClassId": 36317504,
                "description": desc,
                "descriptionTranslated": {
                    "ar": desc_ar,
                    "en": desc
                },
                "categoryIds": categories_ids,
                "categories": categories_json,
                "defaultCategoryId": main_category_id,
                "seoTitle": f'{seo_name}',
                "seoTitleTranslated": {
                    "ar": seo_name_ar,
                    "en": seo_name
                },
                "seoDescription": desc,
                "seoDescriptionTranslated": {
                    "ar": desc_ar,
                    "en": desc
                },
                "attributes": [
                    {
                        "id": 159588021,
                        "name": "UPC",
                        "nameTranslated": {
                            "ar": "رمز المنتج العالمي",
                            "en": "UPC"
                        },
                        "value": f"{attr}",
                        "valueTranslated": {
                            "ar": f"{attr}",
                            "en": f"{attr}"
                        },
                        "show": "DESCR",
                        "type": "UPC"
                    },
                    {
                        "id": 159588022,
                        "name": "Brand",
                        "nameTranslated": {
                            "ar": "ماركة",
                            "en": "Brand"
                        },
                        "value": "Al Beyan Fashion™",
                        "valueTranslated": {
                            "ar": "Al Beyan Fashion™",
                            "en": "Al Beyan Fashion™"
                        },
                        "show": "DESCR",
                        "type": "BRAND"
                    },
                    {
                        "id": 159588025,
                        "name": "Color",
                        "nameTranslated": {
                            "ar": "اللون",
                            "en": "Color"
                        },
                        "value": f"{color[sku.index(attr)]}",
                        "valueTranslated": {
                            "ar": f"{colorAr[sku.index(attr)]}",
                            "en": f"{color[sku.index(attr)]}"
                        },
                        "show": "PRICE",
                        "type": "COLOR"
                    }
                ],
                "googleItemCondition": "NEW",
                "subtitle": "The displayed price is for the full set",
                "subtitleTranslated": {
                    "ar": "السعر المعروض للسيري كامل",
                    "en": "The displayed price is for the full set"
                },
                "googleProductCategory": 167,
                "googleProductCategoryName": "Apparel & Accessories > Clothing Accessories",
                "productCondition": "NEW"
            }

            # Parsing collected data
            response_content, response_code = poster(body)

            # Feedback and returning response and media_path new values
            if response_code == 200:

                # Created product ID
                if 'id' in response_content:
                    product_id = response_content['id']
                    uploading(product, sku, attr, product_id)

                    logger.info(
                        f"Product created successfully with ID: {product_id} | SKU: {attr}")
                else:
                    logger.error(
                        f"Product ID is empty?! | Response: {response_content} | Sku: {attr}")
            elif response_code == 400:
                logger.error(
                    f"New product body request parameters are malformed | Sku: {attr} | Error Message: {response_content['errorMessage']} | Error code: {response_content['errorCode']}"
                )
                break
            elif response_code == 409:
                logger.warning(
                    f"SKU_ALREADY_EXISTS: {attr} | Error Message: {response_content['errorMessage']} | Error code: {response_content['errorCode']}"
                )
            else:
                logger.info(
                    f"Failed to create a new product")
                break

    # Errors handling
    except IndexError as e:
        logger.exception(f'Index Exception: {e} | link: {product["link"]}')
        return
    except KeyError as e:
        logger.exception(f'Key Exception: {e} | link: {product["link"]}')
        return
    except ValueError as e:
        logger.exception(f'Value Exception: {e} | link: {product["link"]}')
        return
    except TypeError as e:
        logger.exception(f'Type Exception: {e} | link: {product["link"]}')
        return

def uploading(product, sku, attr, product_id):
    try:
        file_size = 0
        url = product['images']['link'][sku.index(attr)]
                        
        while True:
            content = requests.get(url, stream=1, headers=download_headers)
            content_size = int(content.headers['Content-Length'])
            main_image_name = f'media/{random.randint(30000, 90000000)}.jpg'
            with open(main_image_name, 'wb') as main_image:
                main_image.write(content.content)
            main_image.close()
            main_image = open(main_image_name, 'rb').read()
            main_image_response = requests.post(f'https://app.ecwid.com/api/v3/63690252/products/{product_id}/image{token}', data=main_image, headers=headers)
                        
            if main_image_response.status_code == 200:
                file_size = os.path.getsize(main_image_name)
                if file_size == content_size:                                    
                    logger.info(f'Main image upload is successful | Status code: {main_image_response.status_code} | Reason: { main_image_response.reason} | Image name: {main_image_name}')
                    break
                else:
                    continue
            elif main_image_response.status_code == 422:
                logger.warning(f"Main image upload is not successful | Reason: {main_image_response.content} | Status: {main_image_response.status_code} | URL: {url}")
                break
    except KeyError as e:
        logger.error(f"Key error: {e} | Link: {url}")

def poster(body):

    # Sending the POST request to create the products
    postData = json.dumps(body)
    response = requests.post(settings.products_url, data=postData, headers=headers)
    response_code = int(response.status_code)
    response = json.loads(response.text.encode('utf-8'))
    logger.info("Body request has been sent")

    return response, response_code
