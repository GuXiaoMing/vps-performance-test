import requests
import pandas as pd
import logging
import time
import subprocess
import re
import traceback
from subprocess import STDOUT, check_output
from multiprocessing import Process, Value, Lock, TimeoutError
import schedule
from datetime import datetime as dt
import os
import sys
import signal
from multi_proc_log import MultiProcessingLog
import random

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = MultiProcessingLog("main.log", 'a', 1024 * 1024 * 512, 0)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)


class Counter(object):
    def __init__(self, initval=0):
        self.val = Value('i', initval)
        self.lock = Lock()

    def increase(self, incr):
        self.lock.acquire()
        logger.debug("Process {} acquired lock".format(os.getpid()))
        # with self.lock:
        try:
            self.val.value += incr
        finally:
            logger.debug("Process {} releasing lock".format(os.getpid()))
            self.lock.release()

    def value(self):
        with self.lock:
            return self.val.value

def download(file_url, counter):
    logger.debug("process {} start download from {}".format(os.getpid(), file_url))
    r = requests.get(file_url, stream=True)

    # while True:
    #     counter.increase(1024)
    #     time.sleep(random.random())
    chunk_size = 1024
    with r:
        for chunk in r.iter_content(chunk_size=chunk_size):
            logger.debug("Process {} trying to increase".format(os.getpid()))
            counter.increase(chunk_size)

def do_nothing(file_url, counter):
    logger.debug("process {} start doing nothing".format(os.getpid()))
    while True:
        counter.increase(1024)
        time.sleep(random.random())

def getBandwith(file_url, process_cnt=20, duration=10):
    start_time = time.time()
    end_time = -1
    counter = Counter(0)
    procs = [Process(target=download, args=(file_url, counter)) for i in range(process_cnt)]
    # procs = [Process(target=do_nothing, args=(file_url, counter)) for i in range(process_cnt)]

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
    total_size = counter.value() / 1024 / 1024
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
            bandwith = getBandwith(r["test_file"], 20, 5)
            output_dict["bandwith"] = bandwith
        except Exception as e:
            logger.debug("download test file {} failed".format(r["test_file"]))
            logger.debug(traceback.format_exc())
        output_obj.write(",".join([formatValue(output_dict[k]) for k in colnames]) + "\n")

    output_obj.close()
    logger.debug("finished job of {}".format(start_time))


if __name__ == "__main__":
    while True:
        getStatistics()
