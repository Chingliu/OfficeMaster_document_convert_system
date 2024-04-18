from ctypes import *
import os
import platform
import redis
import json
import sys, getopt
import tempfile
SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
PDF_PLATFORM_LIB = SCRIPT_PATH + "/pdfmaster/hare.dll"
platform_str = platform.system()
if (platform_str != "Windows"):
    PDF_PLATFORM_LIB = SCRIPT_PATH + "/pdfmaster/libhare.so"


class MASTER_LIBRARY_EXCEPTION(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class TASK_EXCEPTION(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class pdfmaster(object):
    def __init__(self, pdf_dll_path=PDF_PLATFORM_LIB):
        self.pdf_obj = None
        if not pdf_dll_path:
            raise MASTER_LIBRARY_EXCEPTION()
        self.pdf_obj = CDLL(pdf_dll_path)
        if not self.pdf_obj:
            raise MASTER_LIBRARY_EXCEPTION()
        self.convert_type = "pdfofd"
    

    def new_engine(self, machine_code, lic_code, load_font = 1):
        '''

        '''
        new_engine_fn  = self.pdf_obj.hare_library_init
        new_engine_fn.argtypes = [c_int, c_char_p, c_char_p]
        return new_engine_fn(load_font, machine_code.encode(), lic_code.encode())
    
    def pdf2ofd(self, pdf_path, ofd_path, page_range = "1-N"):
        pdf2ofd_fn = self.pdf_obj.hare_library_pdf2ofd
        pdf2ofd_fn.restype = c_long
        pdf2ofd_fn.argtypes = [c_char_p, c_char_p, c_char_p]
        return pdf2ofd_fn(pdf_path.encode(), ofd_path.encode(), page_range.encode())
    
    def ofd2pdf(self, ofd_path, pdf_path, page_range="1-N"):
        ofd2pdf_fn = self.pdf_obj.hare_library_ofd2pdf
        ofd2pdf_fn.restype = c_long
        ofd2pdf_fn.argtypes = [c_char_p, c_char_p, c_char_p, c_char_p]
        with tempfile.TemporaryDirectory() as tmpdirname:
            lret = ofd2pdf_fn(ofd_path.encode(), pdf_path.encode(), page_range.encode(), tmpdirname.encode())
        return lret
    def get_convert_type(self):
        return self.convert_type

class Convertor(object):

    def __init__(self):
        config_obj = self.read_config()
        self.engine = pdfmaster()
        #import pdb
        #pdb.set_trace()
        lic_path = os.path.join(SCRIPT_PATH, 'officemaster.lic')
        if not os.path.exists(lic_path):
            print("****There are no license file:" + lic_path)
            raise MASTER_LIBRARY_EXCEPTION()
        license_code=None
        with open(lic_path, 'r') as f:
            license_code = f.read()
        
        self.engine.new_engine(machine_code="", lic_code=license_code)
        self.convert_type = self.engine.get_convert_type()
        self.dump2screen = False
        if config_obj["log_level"] <= 1:
            self.dump2screen = True
        self.r = redis.Redis(host=config_obj["redis_ip"], port=config_obj["redis_port"])

    def read_config(self):
        '''
        read config.json
        return json obj
        '''
        config_fpath = os.path.join(SCRIPT_PATH, "config.json")
        default_config = {
            "log_level":4,
            "redis_ip":"localhost",
            "redis_port":6379
            }
        try:
            with open(config_fpath, 'rb') as f:
                config_obj = json.load(f)
            if 'redis_ip' not in config_obj:
                config_obj["redis_ip"] = "localhost"
            if 'redis_port' not in config_obj:
                config_obj["redis_port"] = 6379
            if 'log_level' not in config_obj:
                config_obj["log_level"] = 4
        except Exception as e:
                print("read_config exception:", e)
                config_obj = json.loads(default_config)
        return config_obj

    def printscreen(self, msg):
        if self.dump2screen:
            print(msg)

    def keep_alive(self, task=None):
         '''
         子进程保活机制：
         子进程创建名为  subprocess:xxx的redis键， xxx为子进程pid
         subprocess:xxx键的值为一个json,
         {
         "timestamp":以 UNIX 时间戳格式表示, redis Time
         "pid":进程本身的pid
         "type": "word", "excel","powerpoint", "pdfofd"...
         "officepid":officemaster控制下的office子进程id
         }
         '''
         time = self.r.time()
         v = {
            "timestamp":time[0],
            "pid":os.getpid(),
            "type":self.convert_type
         }
         if task:
             v["task"] = task["task_key"]
             v["task_timeout"] = task["task_timeout"]
         self.r.set("subprocess:"+str(os.getpid()), json.dumps(v))     
    def workloop(self):
        while True:
            try:
                task = self.r.blpop("Convert:"+self.convert_type, 60)
                if not task:
                    self.keep_alive()
                    continue
                self.printscreen(str(task))
                if b"STOPMONITOR" == task[1]:
                    self.engine.logging("received STOPMONITOR,exit")
                    break
                task_obj = json.loads(task[1])
                if "file_path" not in task_obj:
                    raise TASK_EXCEPTION("no file_path in task_obj")
                if "task_key" not in task_obj:
                    raise TASK_EXCEPTION("no task_key in task_obj")
                if "target_path" not in task_obj:
                    raise TASK_EXCEPTION("no target_path in task_obj")
                if not os.path.exists(task_obj["file_path"]):
                    raise TASK_EXCEPTION("file not found:" + task_obj["file_path"])
                if "task_inqueue_time" in task_obj:
                    #有任务入队时间
                    if "task_inqueue_timeout" in task_obj:
                        now = self.r.time()
                        now = now[0]
                        diff = now - task_obj["task_inqueue_time"]
                        if diff > task_obj["task_inqueue_timeout"]:
                            self.engine.logging("task:"+ task_obj["task_key"]+ "reached inqueue timeout, ignored it", 2)
                            self.keep_alive()
                            continue
                if "task_timeout" not in task_obj:
                    task_obj["task_timeout"] = 60
                #TODO
                #检查源文件类型是否与队列支持的类型相匹配，以防止错误的转换
                target_dir = os.path.abspath(os.path.dirname(task_obj["target_path"]))
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
                #标记任务开始时间
                self.keep_alive(task_obj)
                if task_obj["file_path"].endswith(".pdf"):
                    ret = self.engine.pdf2ofd(task_obj["file_path"], task_obj["target_path"])
                elif task_obj["file_path"].endswith(".ofd"):
                    ret = self.engine.ofd2pdf(task_obj["file_path"], task_obj["target_path"])
                else:
                    continue
                self.r.setnx("ConvertResult:" + task_obj["task_key"], ret)
                self.r.expire("ConvertResult:" + task_obj["task_key"], 60)
                self.printscreen("task:" + task_obj["task_key"] + " result :" + str(self.r.get("ConvertResult:" + task_obj["task_key"])))
                self.keep_alive()
            except Exception as e:
                print("workloop",e)


if __name__ == '__main__': 
    convertor= Convertor()
    print("\r\nstartup pdf/ofd convertor\r\n")
    convertor.workloop()
