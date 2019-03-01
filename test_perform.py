import requests
import pandas as pd
import logging
import time
import subprocess
import re
import traceback
from subprocess import STDOUT, check_output
from multiprocessing import Process, Value, Lock, TimeoutError, RawValue
import schedule
from datetime import datetime as dt
import os
import sys
import signal
# import logging
from multi_proc_log import MultiProcessingLog

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = MultiProcessingLog("main.log", 'a', 1024 * 1024 * 512, 0)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)


def ping(ip, count=100):
    cmd = ["ping", ip, "-c{}".format(count), "-i0.1"]
    out = check_output(cmd, stderr=STDOUT, timeout=count + 60)
    out = out.decode("utf8").strip('\n')
    lines = out.split('\n')
    stat_dict = dict()
    m = re.search("(\d+) packets transmitted, (\d+) packets received", lines[-2])
    trans, rev = m.groups()
    fields = list(lines[-1].strip().split(" "))
    equal_index = fields.index("=")
    names = fields[equal_index - 1].split('/')
    values = [float(x) for x in fields[equal_index + 1].split('/')]
    kvs = zip(names, values)
    stat_dict = {
        "transmitted": int(trans),
        "received": int(rev),
        "loss_rate": (float(trans) - float(trans)) / float(trans)
    }
    for k, v in kvs:
        stat_dict[k] = v
    return stat_dict


class Counter(object):
    def __init__(self, initval=0):
        # self.val = Value('i', initval)
        self.val = RawValue('i', initval)
        self.lock = Lock()

    def increase(self, incr):
        with self.lock:
            self.val.value += incr

    @property
    def value(self):
        return self.val.value

def download(file_url, counter):
    logger.debug("process {} start download from {}".format(os.getpid(), file_url))
    r = requests.get(file_url, stream=True)
    # counter.increase(1024)
    # r = requests.get(file_url)

    # def sigterm_handler(signal, frame):
    #     logger.debug("sigterm captured by process {}".format(os.getpid()))
    #     raise Exception("received sigterm")

    # signal.signal(signal.SIGTERM, sigterm_handler)
    chunk_size = 1024
    with r:
        for chunk in r.iter_content(chunk_size=chunk_size):
            counter.increase(chunk_size)

def getBandwith(file_url, process_cnt=20, duration=10):
    start_time = time.time()
    end_time = -1
    counter = Counter(0)
    procs = [Process(target=download, args=(file_url, counter)) for i in range(process_cnt)]

    for p in procs:
        p.start()
    while True:
        secs = time.time() - start_time
        if secs > duration:
            for p in procs:
                p.terminate()
                # p.kill()
                p.join()
            logger.debug("All process killed")
            break
        time.sleep(1)
    # total_size = counter.value() / 1024 / 1024
    total_size = counter.value / 1024 / 1024
    bandwith = total_size / secs;
    logger.debug("{}M / {:.02f}s = {:.02f}Mbps".format(total_size, secs, bandwith))
    return bandwith

def formatValue(value):
    if type(value) is str:
        return '"{}"'.format(value)
    if type(value) is float:
        return '{:.2f}'.format(value)
    return str(value)


def getStatistics():
    start_time = dt.now().strftime("%Y-%m-%d %H:%M")
    logger.debug("start to get status of {}".format(start_time))
    df = pd.read_csv("./vultr.csv")
    output_path = "./vultr_statistics.csv"
    output_obj = open(output_path, "a", buffering=1)
    colnames = ["time", "name", "loss_rate", "avg_rtt", "stddev_rtt", "bandwith"]
    # output_obj.write(",".join(colnames) + "\n")

    for index, r in df.iterrows():
        logger.debug("Testing {}".format(r["name"]))
        output_dict = {
                "time": start_time,
                "name": r["name"],
                "loss_rate": -1.0,
                "avg_rtt": -1.0,
                "stddev_rtt": -1.0,
                "bandwith": -1.0
            }
        try:
            ping_stat = ping(r["addr"], 50)
            output_dict["loss_rate"] = ping_stat["loss_rate"]
            output_dict["avg_rtt"] = ping_stat["avg"]
            output_dict["stddev_rtt"] = ping_stat["stddev"]
        except Exception as e:
            logger.debug("ping {} failed".format(r["addr"]))
            logger.debug(traceback.format_exc())
        try:
            bandwith = getBandwith(r["test_file"], 20, 10)
            output_dict["bandwith"] = bandwith
        except Exception as e:
            logger.debug("download test file {} failed".format(r["test_file"]))
            logger.debug(traceback.format_exc())
        output_obj.write(",".join([formatValue(output_dict[k]) for k in colnames]) + "\n")

    output_obj.close()
    logger.debug("finished job of {}".format(start_time))


if __name__ == "__main__":
    # for hour in range(0, 24):
    #     for minute in range(0, 60, 5):
    #         time_str = "{:02}:{:02}".format(hour, minute)
    #         schedule.every().day.at(time_str).do(getStatistics)
    # schedule.every(5).minutes.do(getStatistics)
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)
    while True:
        getStatistics()
