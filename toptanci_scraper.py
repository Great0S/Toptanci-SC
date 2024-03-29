import glob
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry
from rich.progress import Progress, SpinnerColumn, TextColumn
from tqdm import tqdm

from config.settings import settings
from tasks.create_products import create_product

logger = settings.logger

products = []
URL = 'https://toptanci.com/'
headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36'}
json_data = progress = session = main_count = None
links = []


def toptanciScraper():
    global json_data, progress, session, main_count, products

    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True,) as progress:

            # retries = Retry(total=5, backoff_factor=1,
            #                 status_forcelist=[500, 502, 503, 504, 520])
            # session.('https://', HTTPAdapter(max_retries=retries))
            
            session = requests.Session()
            retries = Retry(total=5, backoff_factor=1,
                            status_forcelist=[500, 502, 503, 504, 520])
            session.mount('https://', HTTPAdapter(max_retries=retries))
            session.headers = headers
            page = session.get(URL, headers=headers)
            logger.info(
                f'New page request has been made | Response: {page.status_code}')
            soup = BeautifulSoup(page.content, "html.parser")
            result = soup.find('body')
            navBar = result.find(class_="navbar-nav")
            page_element = navBar.find_all("li", class_='darken-onshow')
            logger.info(f'Categories found count: {len(page_element)}')
            main_count = 0
            
            progress.add_task(description="Exteracting links...", total=None)
            
            if os.path.exists('dumps/unprocessed.json'):
                pass
            else:
                with ThreadPoolExecutor(max_workers=100) as p:
                    result = p.map(get_links, page_element)
                save_data(links, 'unprocessed')

            progress.remove_task(0)
            
            open_json = open('dumps/unprocessed.json', 'r', encoding='utf-8')
            js_data = json.load(open_json)
            main_count = len(js_data)
            logger.info(f'Pulled products links total: {main_count}')
            logger.info("Exteraction done!")
            logger.info(f'Processing links start')
            
            progress.add_task(description="Processing links...", total=None)
            
            if os.path.exists('dumps/data.json'):
                pass
            else:
                with ThreadPoolExecutor(max_workers=5) as p:
                    p.map(get_data, js_data)
                save_data(products, 'data')
                    
            progress.remove_task(1)
            
            logger.info("All data has been processed")
            return
    except requests.exceptions.ChunkedEncodingError:
        time.sleep(1)


def get_links(page_element):
    global links, progress, session

    page_element_count = len(page_element)

    # Category's Title and ID
    main_element = page_element.find('a', class_='nav-link')
    element_title = (main_element.text).strip()
    sub_element = page_element.find('div', class_='list-group')
    sub_categories = sub_element.find_all('a')

    for sub in sub_categories:
        sub_link = URL+sub.attrs['href']
        sub_name = (sub.text).strip()
        ListResponse = session.get(sub_link, headers=headers)
        sub_soup = BeautifulSoup(
            ListResponse.content, "html.parser")
        sub_result = sub_soup.find('body')
        elemen_page_nav_count = int(sub_result.find(
            'div', class_='paging').attrs['data-pagecount'])

        for offset in range(1, elemen_page_nav_count+1, 1):
            ProductListResponse = session.get(
                f'{sub_link}?sayfa={offset}', headers=headers)
            element_sub_soup = BeautifulSoup(
                ProductListResponse.content, "html.parser")
            element_sub_result = element_sub_soup.find('body')
            element_sub = element_sub_result.find(
                class_='col-md-10 col-12')
            element_sub_links = element_sub.contents[7].find_all(
                "div", class_='productCard')
            element_sub_links_count = len(element_sub_links)

            for sub_links in element_sub_links:
                sub_links = URL + \
                    re.sub(
                        '/', '', sub_links.contents[1].attrs['href'])
                links.append(sub_links)


def get_data(item_link):
    global json_data, progress, session, main_count

    try:
        product_link = session.get(item_link)
        product_soup = BeautifulSoup(product_link.content, "html.parser")
        select_sub = product_soup.select('ol.breadcrumb.text-truncate')[0]
        select_sub2 = select_sub.select('li.breadcrumb-item')
        
        if len(select_sub2) == 4:
            main_category = re.sub('\n', '', select_sub2[1].text).strip()
            sub_category = re.sub('\n', '', select_sub2[2].text).strip()
        else:
            main_category = re.sub('\n', '', select_sub2[1].text).strip()
            sub_category = None
            
        product_name = product_soup.find(
            'div', class_='col-10').contents[1].text
        attrs_list = product_soup.select('table.table.table-hover.table-sm')
        atrributes = {"color": [], "price": [], "stock": [], "code": []}
        
        if attrs_list:
            for attr in attrs_list:
                stok_yok = attr.find('div', text=re.compile("Stok Yok"))
                if stok_yok:
                    break
                color_attr = attr.find(
                    'td', attrs={'style': 'width:30%;'}).text
                price_attr = re.sub(',', '.', re.sub('\₺', '', attr.find(
                    'div', text=re.compile(r'\₺')).text).strip())
                stock_attr = int(
                    attr.find('strong', text=re.compile(r'\d+')).text)
                code_attr = int(attr.find('td', class_="",
                                text=re.compile(r'\s\d+\s|\d+')).text)
                atrributes['color'].append(color_attr)
                atrributes['price'].append(price_attr)
                atrributes['stock'].append(stock_attr)
                atrributes['code'].append(code_attr)
            product_desc = re.sub(r'\w+;', '', product_soup.select(
                'div.p-3.bg-white.border.rounded-3')[0].contents[1].contents[0].text).strip()
            product_images = product_soup.select(
                'img.img-fluid.btnVariantSmallImage')
        else:
            attrs_list = product_soup.find(
                'div', class_='col-md-6 p-4 bg-light')
            price_attr = float(re.sub(',', '.', re.sub(
                '\₺', '', attrs_list.find(text=re.compile(r'\₺')).text).strip()))
            stock_attr = int(re.sub('Stok|\:|\s', '', attrs_list.find(
                text=re.compile(r'Stok|\:\d+')).text))
            code_attr = int(re.sub('Barkod|\:|\s', '', attrs_list.find(
                text=re.compile(r'Barkod|\:\d+')).text))
            
            if sub_category:
                product_desc = attrs_list.find(
                    class_='p-3 bg-white border rounded-3').text.strip()
            else:
                product_desc = attrs_list.find(
                    class_='p-3 bg-white border rounded-3').text.strip()
                
            atrributes['color'].append('Not set')
            atrributes['price'].append(price_attr)
            atrributes['stock'].append(stock_attr)
            atrributes['code'].append(code_attr)
            product_images = product_soup.find_all('img', attrs={'width': 1000, 'height': 1000})
            
        images = {"color": [], "link": []}
        
        for image in product_images:
            img_link = image.attrs['data-src']
            img_color = image.attrs['alt']
            images['link'].append(img_link)
            images['color'].append(img_color)
            
        if any(atrributes.values()):
            products_update = {"link": item_link, "main-category": main_category, "sub-category": sub_category,
                               "name": product_name, "images": images, "descr": product_desc, "attrs": atrributes}
            products.append(products_update)
        else:
            logger.info(f"Invalid item | Link: {item_link}")

    except requests.exceptions.ChunkedEncodingError:
        time.sleep(1)
    except (Exception, IndexError) as e:
        logger.error(
            f"Product error: {e} | Status: {product_link.status_code} | Reason: {product_link.reason} | Link: {item_link}")


def save_data(data, files):
    global json_data
    File_path = f'dumps/{files}.json'
    if os.path.exists(File_path):
        pass     
    else:
        with open(File_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False)
        file.close()
        open_json = open(File_path, 'r', encoding='utf-8')
        json_data = json.load(open_json)

    return json_data


def main():
    global json_data
    
    start_time = time.time()
    toptanciScraper()
    logger.info(f"Scraped in {(time.time() - start_time):.2f} seconds")

    open_json_data = open('dumps/data.json', 'r', encoding='utf-8')
    json_data = json.load(open_json_data)
    
    with ThreadPoolExecutor(max_workers=3) as p:            
        result = list(tqdm(p.map(create_product, json_data), total=len(json_data)))
        
    Files = glob.glob('media/*')
    for file in Files:
        os.remove(file)


# clearing the console from unnecessary
def cls(): return os.system("cls")


cls()

logger.info('New TOPTANCI session has been started')

if __name__ == '__main__':
    import time
    s = time.perf_counter()
    main()
    elapsed = time.perf_counter() - s
    logger.info(f"Tasks executed in {elapsed:0.2f} seconds.")