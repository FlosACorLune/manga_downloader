import utils, config
import re, requests, os, json
from bs4 import BeautifulSoup

parameters = "?fields[]=background&fields[]=moderated&fields[]=manga_status_id&fields[]=chap_count&fields[]=status_id"
api_url = "https://api.cdnlibs.org/api/manga/"
server_one = "https://img2.imglib.info"
server_compression = "https://img3.mixlib.me"

def get_slug_url(url):
    match = re.search(r'/manga/([^/?]+)', url)
    if match:
        return match.group(1)
    return None

def get_json(url):
    response = requests.get(url)
    data = response.json()
    #new = json.dumps(data, indent=2)
    #print(new)
    return data

def get_num_vol(query_result, max_item_count):
    result = ()
    for i in range(0,max_item_count):
        vol = query_result["data"][i]['volume']
        num = query_result["data"][i]['number']
        result += ((vol, num),)
    return result

def get_chapter_images_url(query_result):
    result=[]
    for i in range(0,len(query_result['data']['pages'])):
        result.append(query_result['data']['pages'][i]['url'])
    return

def get_titile_name(query_result):
    return query_result["data"]['rus_name']

def get_scanlateStatus(query_result):
    return query_result["data"]['scanlateStatus']['label']

def get_status(query_result):
    return query_result["data"]['status']['label']

def get_items_count(query_result):
    return query_result["data"]['items_count']['uploaded']



def get_number_to_url(result_num_vol, result_slug_url):
    result = []
    for vol,num in result_num_vol:
        result.append(f"{api_url}{result_slug_url}/chapter?number={num}&volume={vol}")
    return result

def init(url):
    result_slug_url = get_slug_url(url)
    query_num = f"{api_url}{result_slug_url}/chapter?number={1}&volume={1}"
    query_chapters = f'{api_url}{result_slug_url}/chapters'
    query_fields = f'{api_url}{result_slug_url}{parameters}'
    

    result_query_num = get_json(query_num)
    result_query_chapters = get_json(query_chapters)
    result_query_fields = get_json(query_fields)

    max_count_item = get_items_count(result_query_fields)

    result_num_vol = get_num_vol(result_query_chapters, max_count_item)

    get_chapter_images_url(result_query_num)
    t = get_number_to_url(result_num_vol,result_slug_url)
    
    print(t)
    
    return

init("https://mangalib.me/ru/manga/183349--mankitsu-shitai-jouren-san?section=chapters")