import os
import redis
import json
import shlex, subprocess
import time
import platform
import signal
SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))


class MANAGER_EXCEPTION(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class RunningProc(object):
     def __init__(self, type, popenobj):
          self.type_ = type
          self.p = popenobj

     def get_type(self):
        return self.type_
     def get_popenobj(self):
        return self.p
     
class Manager(object):
    
    def __init__(self):
         self.config_obj = self.read_config()
         self.r = redis.Redis(host=self.config_obj["redis_ip"], port=self.config_obj["redis_port"])
         self.p=[]
         if "python_path" not in self.config_obj:
              raise MANAGER_EXCEPTION("no python path inside the config file")
         if not os.path.exists(self.config_obj["python_path"]):
              raise MANAGER_EXCEPTION(self.config_obj["python_path"] + " not found")
         
    def read_config(self):
        '''
        read config.json
        return json obj
        '''
        config_fpath = os.path.join(SCRIPT_PATH, "config.json")
        default_config = {
            "word_process_num":1,
            "excel_process_num":0,
            "ppt_process_num":0,
            "hare_process_num":1,
            "process_timeout":180,
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
            if 'process_timeout' not in config_obj:
                config_obj["process_timeout"] = 180
        except Exception as e:
                print("read_config exception:", e)
                config_obj = json.loads(default_config)
        print("[read_config] config:")
        print(config_obj)
        return config_obj
    
    def create_office_process(self, type):
         cmd_line = []
         cmd_line.append(self.config_obj["python_path"])
         officemaster_py = os.path.abspath(os.path.join(SCRIPT_PATH, "officemaster.py"))
         cmd_line.append(officemaster_py)
         cmd_line.append("-t")
         cmd_line.append(type)
         print("[create_office_process]" + str(cmd_line))
         process = subprocess.Popen(cmd_line)
         if process and process.poll() == None:
              print("[create_office_process]" + type +" "+ str(process.pid) + " started")
              #self.p.append(process)
              rp = RunningProc(type, process)
              self.p.append(rp)

    def create_hare_process(self):
         cmd_line = []
         cmd_line.append(self.config_obj["python_path"])
         pdfmaster_py = os.path.abspath(os.path.join(SCRIPT_PATH, "pdfmaster.py"))
         cmd_line.append(pdfmaster_py)
         print("[create_hare_process]" + str(cmd_line))
         process = subprocess.Popen(cmd_line)
         if process and process.poll() == None:
              print("[create_hare_process] hare pdf/ofd"+ str(process.pid) + " started")
              #self.p.append(process)
              rp = RunningProc("pdfofd", process)
              self.p.append(rp)

    def close_subprocess(self):
         for p in self.p:
              p.get_popenobj().kill()

    def create_convert_process(self):
         for i in range(self.config_obj["word_process_num"]):
              print("create_convert_process: word_"+ str(i))
              self.create_office_process("word")
         for i in range(self.config_obj["excel_process_num"]):
              print("create_convert_process: excel_"+ str(i))
              self.create_office_process("excel")
         for i in range(self.config_obj["ppt_process_num"]):
              print("create_convert_process: powerpoint_"+ str(i))
              self.create_office_process("powerpoint")
         for i in range(self.config_obj["hare_process_num"]):
             self.create_hare_process()

    def eat_something(self):
         '''
         对于未创建子进程的队列，如果有人推入了任务如何处理
         '''
         pass
    def handle_expired_process(self, pobj):
        '''
        进程过期，
        redis 相关key要删除，
        officemaster进程要杀一下，以避免残留
        officemaster控制下的office进程要杀一下以避免残留
        '''
        try:
            rkey = "subprocess:" + str(pobj["pid"])
            print("[handle_expired_process] delete key " + rkey )
            self.r.delete(rkey)
            platform_str = platform.system()

            if (platform_str != "Windows"):
                os.kill(pobj["pid"], signal.SIGKILL)
                os.kill(pobj["officepid"], signal.SIGKILL)
            else:            
                if pobj["pid"] != 0:
                    subprocess.Popen("taskkill /F /T /PID " + str(pobj["pid"]) , shell=True)
                if pobj["officepid"] != 0:
                    subprocess.Popen("taskkill /F /T /PID " + str(pobj["officepid"]) , shell=True)            
        except Exception as e:
            print("[handle_expired_process]", e)
    def keep_alive(self):
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
         pass
         while True:
            stored_proc = self.r.keys("subprocess:*")
            print(stored_proc)
            for p in stored_proc:
                #1,判断时间戳是否过期，过期则此进程异常，kill it, 查询此进程的关联进程，杀掉
                #2,时间戳在有效期的，可认为进程正常
                try:
                    v = self.r.get(p)
                    pobj = json.loads(v)
                    print(pobj)
                    now = self.r.time()
                    now = now[0]
                    diff = now - pobj["timestamp"]
                    if diff > self.config_obj["process_timeout"]:
                        self.handle_expired_process(pobj)
                    if "task_timeout" in pobj:
                        if diff > pobj["task_timeout"]:
                            print("task " + pobj["task"] + " convert timeout")
                            self.r.setnx("ConvertResult:" + pobj["task"], -10)
                            self.r.expire("ConvertResult:" + pobj["task"], 60)                            
                            self.handle_expired_process(pobj)

                except Exception as e:
                    print("[keep_alive]stored_proc ", e)
            for p in self.p:
                popenobj = p.get_popenobj()
                if popenobj.poll() != None:
                    #进程已退出
                    #需重建
                    pass
            time.sleep(50)
                           

if __name__ == '__main__':
     
    manager = Manager()
    try:
        manager.create_convert_process()
        manager.keep_alive()
    finally:
         #manager.close_subprocess()
         pass