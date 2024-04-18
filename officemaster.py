from ctypes import *
import os
import platform
import redis
import json
import sys, getopt

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
OM_PLATFORM_LIB = SCRIPT_PATH + "/officemaster/officemaster.dll"
platform_str = platform.system()
if (platform_str != "Windows"):
    OM_PLATFORM_LIB = SCRIPT_PATH + "/officemaster/libofficemaster.so"


class MASTER_LIBRARY_EXCEPTION(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class TASK_EXCEPTION(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class officemaster(object):
    def __init__(self, master_dll_path=OM_PLATFORM_LIB):
        self.master_obj = None
        if not master_dll_path:
            raise MASTER_LIBRARY_EXCEPTION()
        self.master_obj = CDLL(master_dll_path)
        if not self.master_obj:
            raise MASTER_LIBRARY_EXCEPTION()
        self.convert_type = "word"


    def init_logger(self, log_level, log_path, log_fname):
        '''
        spdlog级别： 0-6 trace, debug, info, warn, error, critical, off
        '''
        if self.master_obj:
            logger_init_fn = self.master_obj.office_master_logger_init
            logger_init_fn.argtypes = [c_int, c_char_p, c_char_p]
            return logger_init_fn(log_level, log_path.encode(), log_fname.encode())
    
    def logger_level(self, log_level):
        '''
        spdlog级别： 0-6 trace, debug, info, warn, error, critical, off
        '''
        logger_level_fn = self.master_obj.office_master_logger_level
        logger_level_fn.argtypes = [c_int]
        return logger_level_fn(log_level)
    
    def logging(self,msg,  log_level=2):
        logger_logging_fn = self.master_obj.office_master_logging
        logger_logging_fn.argtypes = [c_int, c_char_p]
        return logger_logging_fn(log_level, msg.encode())        

    def new_engine(self, machine_code, lic_code, convert_type=1, use_wps=True):
        '''
        convert_type :Word = 1, Excel = 2, PPT= 3
        use_wps : True to use WPS others use MS office
        '''
        new_engine_fn  = self.master_obj.office_master_new
        new_engine_fn.restype = c_int
        new_engine_fn.argtypes = [c_int, c_int, c_int, c_char_p, c_char_p]
        self.convert_type = self.translate_convert_type(convert_type)
        return new_engine_fn(convert_type, use_wps, not use_wps, machine_code.encode(), lic_code.encode())
    
    def translate_convert_type(self, convert_type):
        convert_str = ""
        if convert_type == 1:
            convert_str = "word"
        elif convert_type == 2:
            convert_str = "excel"
        elif convert_type == 3:
            convert_str == "powerpoint"
        else:
            raise MASTER_LIBRARY_EXCEPTION("not support convert type:"+convert_type)
        return  convert_str
    
    def get_convert_type(self):
        return self.convert_type
    
    def delete_engine(self):
        return self.master_obj.office_master_delete()
    
    def get_office_pid(self):
        return self.master_obj.office_master_get_controlled_pid()
    
    def convert(self, src, dst, page_no="*", delete_all_comments=True, accept_all_revisions=True, excel_zoom=0, excel_ori=0, excel_paper_size=2, excel_all=True):
        '''
        char *in_path_file, 
        char *out_path_file, 
        char *page_no_range, 
        char *type, word excel, powerpoint
        bool bDeleteAllComments, 
        bool bAcceptAllRevisions, 
        int nExcelZoom, //              -nExcelZoom 0 :不做缩放转换; 1:逻辑上使用1页宽模式转换;2 :逻辑上
                        //              1页高模式转换; 3
                        // :使用1页宽一页高转换; 10-400 独立的缩放值
        int nExcelOrientation, //              -nExcelOrientation 纸张方向 0 default; 1 : heng ; 2:zhong
        int nExcelPaperSize, //              -nExcelPaperSize 纸张大小 
							if (nExcelPaperSize == 1) {
								pPageSetupPrt->put_PaperSize(MSExcel::XlPaperSize::xlPaperA3);
							}
							else if (nExcelPaperSize == 2) {
								pPageSetupPrt->put_PaperSize(MSExcel::XlPaperSize::xlPaperA4);
							}
							else if (nExcelPaperSize == 3) {
								pPageSetupPrt->put_PaperSize(MSExcel::XlPaperSize::xlPaperA5);
							}
							else if (nExcelPaperSize == 4) {
								pPageSetupPrt->put_PaperSize(MSExcel::XlPaperSize::xlPaperB4);
							}
							else if (nExcelPaperSize == 5) {
								pPageSetupPrt->put_PaperSize(MSExcel::XlPaperSize::xlPaperB5);
							}        
        bool bExcelConvertAll //              -bExcelConvertAll 是否全sheet转换  false 转换激活的sheet
        '''
        convert_file_fn = self.master_obj.office_master_convertFile
        convert_file_fn.restype = c_int
        convert_file_fn.argtypes = [c_char_p, c_char_p, c_char_p,c_char_p,c_int,c_int,c_int,c_int,c_int,c_int]
        convert_type = self.convert_type
        return convert_file_fn(src.encode(), dst.encode(), page_no.encode(), convert_type.encode(), delete_all_comments, accept_all_revisions, excel_zoom, excel_ori, excel_paper_size, excel_all)
        

class Convertor(object):

    def __init__(self, convert_type=1):
        config_obj = self.read_config()
        self.engine = officemaster()
        log_path=""
        try:
            log_path = os.path.join(SCRIPT_PATH, "log", self.engine.translate_convert_type(convert_type))
            if not os.path.exists(log_path):
                os.makedirs(log_path)
        except Exception as e:
            log_path = SCRIPT_PATH
            print("[Convertor] init logger failed")
        self.engine.init_logger(config_obj["log_level"], log_path, str(os.getpid())+".log")
        #import pdb
        #pdb.set_trace()
        lic_path = os.path.join(SCRIPT_PATH, 'officemaster.lic')
        if not os.path.exists(lic_path):
            print("****There are no license file:" + lic_path)
            raise MASTER_LIBRARY_EXCEPTION()
        license_code=None
        with open(lic_path, 'r') as f:
            license_code = f.read()

        self.engine.new_engine("", license_code, convert_type, use_wps=True)
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
        self.engine.logging(msg, 0)

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
            "type":self.convert_type,
            "officepid":self.engine.get_office_pid()
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
                ret = self.engine.convert(task_obj["file_path"], task_obj["target_path"])
                self.r.setnx("ConvertResult:" + task_obj["task_key"], ret)
                self.r.expire("ConvertResult:" + task_obj["task_key"], 60)
                self.printscreen("task:" + task_obj["task_key"] + " result :" + str(self.r.get("ConvertResult:" + task_obj["task_key"])))
                self.keep_alive()
            except Exception as e:
                print("workloop",e)


def test_officemaster():
    test = officemaster(master_dll_path=OM_PLATFORM_LIB)
    test.init_logger(0, SCRIPT_PATH, "test.log")
    test.new_engine()
    test_input = SCRIPT_PATH + "/test.doc"
    test_output = SCRIPT_PATH + "/test.pdf"
    test.convert(test_input, test_output)

def test_convertor():
    convert = Convertor()
    convert.workloop()

if __name__ == '__main__':
    argv = sys.argv[1:]
    try:
        opts, args = getopt.getopt(argv,"ht:",["type="])
    except getopt.GetoptError:
        print("\r\nusage:\r\n")
        print('officemaster.py -t type/*here type can only be word excel powerpoint*/')
        sys.exit(2)
    convert_type = "word"
    for opt, arg in opts:
        if opt == '-h':
            print("\r\nusage:\r\n")
            print('officemaster.py -t type/*here type can only be word excel powerpoint*/')
            print("\r\n")
            sys.exit(0)
        elif opt in ("-t", "--type"):
            convert_type = arg    

    convertor = None
    if convert_type == "word":
        convertor= Convertor(1)
    elif convert_type == "excel":
        convertor= Convertor(2)
    elif convert_type == "powerpoint":
        convertor= Convertor(3)
    else:
        print('here type can only be word excel powerpoint')
        print("\r\n")
        sys.exit(2)
    print("\r\nstartup " + convert_type + " convertor\r\n")
    convertor.workloop()
