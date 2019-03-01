import requests
from lxml import etree
import lxml
from lxml.html import fromstring
from io import StringIO, BytesIO
import pandas as pd
import threading


url = "https://www.vultr.com/faq/#downloadspeedtests"
r = requests.get(url)
if r.status_code != 200:
    raise Exception("vultr server hosts list not available")
html = r.text

# tree = lxml.html.fromstring(html)
tree = fromstring(html)
table = tree.xpath('//table[@class="table speedtest_table"]')[0]

link_dict = dict()
for tr in table.find("tbody").findall("tr"):
    tds = tr.findall("td")
    name = tds[0].text_content().strip()
    page_link = tds[1].find("a").attrib["href"]
    link_dict[name] = page_link

info_list = []

class GetInfoThread(threading.Thread):
    def __init__(self, name, link):
        threading.Thread.__init__(self)
        self.name = name
        self.link = link
        
    def run(self):
        try:
            sub_r = requests.get(self.link)
            if sub_r.status_code != 200:
                raise Exception("cannot get test info of {}".format(name))
            sub_html = sub_r.text
            sub_tree = lxml.html.fromstring(sub_html)
            addr = sub_tree.xpath('//a[@id="useripv4"]')[0].text_content().strip()
            file = sub_tree.xpath('//a[@id="testfile"]')[0].attrib["href"].strip()
            file = self.link + file
            info_list.append({"name": str(self.name), "addr": str(addr), "test_file": str(file)})
        except Exception as e:
            print(e)

threads = []
for name, link in link_dict.items():
    t = GetInfoThread(name, link);
    threads.append(t)
    t.start()
for t in threads:
    t.join()

pd.DataFrame(info_list)
df = pd.DataFrame(info_list).set_index("name")
df.to_csv("./vultr.csv")
