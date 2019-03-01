from lxml import etree
import requests
from io import StringIO, BytesIO

def get_hosts():
    url = "https://www.vultr.com/faq/#downloadspeedtests"
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception("vultr server hosts list not available")
    html = r.text
    parser = etree.HTMLParser()
    tree = etree.parse(StringIO(html), parser)
    result = etree.tostring(tree.getroot(),
            pretty_print=True, method="html")
    print(result)


if __name__ == "__main__":
    get_hosts()
