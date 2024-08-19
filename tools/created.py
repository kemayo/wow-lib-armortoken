#!/usr/bin/env python

import re
import html
import sys
import argparse

import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import requests
import requests_cache
from requests.adapters import HTTPAdapter, Retry

WOWHEAD_URL = 'https://www.wowhead.com'

session = requests_cache.CachedSession()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 502, 503, 504 ])
session.mount('http://', HTTPAdapter(max_retries=retries))
session.mount('https://', HTTPAdapter(max_retries=retries))
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'})


WOWHEAD_ITEM_TYPES = {
    2: "ALL",  # Weapon
    3: "ALL",  # Relic
    4: {
        1: "CLOTH",
        2: "LEATHER",
        3: "MAIL",
        4: "PLATE",
        -2: "ALL",  # Rings
        -3: "ALL",  # Necklaces
        -4: "ALL",  # Trinkets
        -6: "ALL",  # Cloaks
    },
    "?": "UNKNOWN",
}


def item_type(item):
    if item["classs"] not in WOWHEAD_ITEM_TYPES:
        return "UNKNOWN"
    itype = WOWHEAD_ITEM_TYPES[item["classs"]]
    if type(itype) == dict:
        return itype.get(item["subclass"], "UNKNOWN")
    return itype


def fetch_item(itemid, base):
    url = f"{base}/item={itemid}"
    print("fetch_item", itemid, url)
    r = session.get(url, timeout=5)
    print("fetch completed", r.url)

    item = {"id": itemid, "creates": []}

    if m := re.search(r'<meta property="og:title" content="([^"]+)">', r.text):
        item["name"] = html.unescape(m.group(1))

    # Note to self: can't use yaml.safe_load here because it doesn't let you
    # override the loader, and the default loader is a lot slower.

    # new Listview({
    #     template: 'item',
    #     id: 'creates',
    #     name: WH.TERMS.creates,
    #     tabs: 'tabsRelated',
    #     parent: 'lkljbjkb574',
    #         sort:['name'],
    #     data: [{"appearances":{"0":[111173,""]},"armor":12,"bonustrees":[1518],"classs":4,"displayName":"Cliffbreaker Pauldrons","displayid":111173,"flags2":8192,"id":101796,"level":39,"name":"Cliffbreaker Pauldrons","quality":4,"reqlevel":35,"slot":3,"slotbak":3,"source":[1],"specs":[65,1451,66,250,251,1455,252,70,71,72,1446,73],"subclass":4},{"appearances":{"0":[111186,""]},"armor":12,"bonustrees":[1518],"classs":4,"displayName":"Everbright Pauldrons","displayid":111186,"flags2":8192,"id":101824,"level":39,"name":"Everbright Pauldrons","quality":4,"reqlevel":35,"slot":3,"slotbak":3,"source":[1],"specs":[65,1451,66,250,251,1455,252,70,71,72,1446,73],"subclass":4},{"appearances":{"0":[111202,""]},"armor":12,"bonustrees":[1518],"classs":4,"displayName":"Elder Tortoiseshell Pauldrons","displayid":111202,"flags2":8192,"id":101858,"level":39,"name":"Elder Tortoiseshell Pauldrons","quality":4,"reqlevel":35,"slot":3,"slotbak":3,"source":[1],"specs":[65,1451,66,250,251,1455,252,70,71,72,1446,73],"subclass":4},{"appearances":{"0":[111202,""]},"armor":12,"bonustrees":[1518],"classs":4,"displayName":"Cliffbreaker Pauldrons","displayid":111202,"flags2":8192,"id":101885,"level":41,"name":"Cliffbreaker Pauldrons","namedesc":"Timeless","quality":4,"reqlevel":35,"slot":3,"slotbak":3,"source":[1],"sourcemore":[{"icon":"inv_shoulder_plate_reputation_c_01","n":"Timeless Plate Spaulders","q":4,"t":3,"ti":102268}],"specs":[65,1451,66,250,251,1455,252,70,71,72,1446,73],"subclass":4},{"appearances":{"0":[111186,""]},"armor":12,"bonustrees":[1518],"classs":4,"displayName":"Everbright Pauldrons","displayid":111186,"flags2":8192,"id":101913,"level":41,"name":"Everbright Pauldrons","namedesc":"Timeless","quality":4,"reqlevel":35,"slot":3,"slotbak":3,"source":[1],"sourcemore":[{"icon":"inv_shoulder_plate_reputation_c_01","n":"Timeless Plate Spaulders","q":4,"t":3,"ti":102268}],"specs":[65,1451,66,250,251,1455,252,70,71,72,1446,73],"subclass":4},{"appearances":{"0":[111194,""]},"armor":12,"bonustrees":[1518],"classs":4,"displayName":"Elder Tortoiseshell Pauldrons","displayid":111194,"flags2":8192,"id":101945,"level":41,"name":"Elder Tortoiseshell Pauldrons","namedesc":"Timeless","quality":4,"reqlevel":35,"slot":3,"slotbak":3,"source":[1],"sourcemore":[{"icon":"inv_shoulder_plate_reputation_c_01","n":"Timeless Plate Spaulders","q":4,"t":3,"ti":102268}],"specs":[65,1451,66,250,251,1455,252,70,71,72,1446,73],"subclass":4}],
    # });
    for match in re.findall(r"new Listview\({\n\s*template: 'item'.+?id: '(?:creates|contains)',.+?data: (\[[^\n]+\])", r.text, re.DOTALL):
        data = yaml.load(match, Loader=Loader)
        for citem in data:
            item["creates"].append({
                "id": citem["id"],
                "name": citem["name"],
                "type": item_type(citem),
            })
    return item


def fetch_itemids_from_search(url):
    # assume this is a wowhead search page and pull down everything included on it
    r = session.get(url, timeout=5)
    match = re.search(
        # r'new Listview\({[^{]+?"?data"?:\s*\[(.+?)\]}\);\n', r.text
        r'var listviewitems = \[(.+)\];\n', r.text
    )
    if not match:
        return []
    headermatch = re.search(
        r'<a href="([^"]+)" class="header-logo">', r.text
    )
    return map(int, re.findall(r'"id":(\d+)', match.group(1))), headermatch and headermatch.group(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Strip data out of wowhead")
    parser.add_argument('input', metavar="INPUT", type=str, help="Data source (url or comma-separated item ids)")
    args = parser.parse_args()

    base = WOWHEAD_URL

    if re.match(r"(?:[\d,]|^http)", args.input):
        itemids = []
        if args.input.startswith("http"):
            itemids, sub = fetch_itemids_from_search(args.input)
            if sub and sub != "/wow":
                base = base + sub
        else:
            itemids = map(int, args.input.split(","))

    output = []
    for itemid in itemids:
        item = fetch_item(itemid, base)
        output.extend(("[", str(itemid), "] = { -- ", item["name"], "\n",))
        for itype in ("PLATE", "MAIL", "LEATHER", "CLOTH", "ALL", "UNKNOWN"):
            items = [str(ci["id"]) for ci in item["creates"] if ci["type"] == itype]
            if len(items):
                output.extend(("    ", itype, " = {", ", ".join(items), "},\n"))
            # "    ALL = {", ", ".join(map(lambda c: str(c["id"]), item["creates"])), "},\n",
        output.extend(("},\n",))

    print("".join(output))
