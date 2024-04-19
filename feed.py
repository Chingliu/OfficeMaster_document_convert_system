import os
import redis
import json
import uuid

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
WORD_FILES = SCRIPT_PATH + "/TestDoc"
PDF_FILES = SCRIPT_PATH + "/ConvertedPDF"
def word2pdf():
    conn = redis.Redis(host='localhost', port=6379)
    files = os.listdir(WORD_FILES)
    if not os.path.exists(PDF_FILES):
            os.makedirs(PDF_FILES)    
    ongoing_tasks = []
    for file in files:
        file_path = os.path.join(WORD_FILES, file)
        source_type = "word"
        target_path = os.path.join(PDF_FILES, file + ".pdf") #转换后文件绝对路径
        if file.endswith(".doc") or file.endswith(".docx"):
             source_type = "word"
        elif file.endswith(".xls") or file.endswith(".xlsx") or file.endswith(".et"):
             source_type = "excel"
        elif file.endswith(".pdf"):
             source_type = "pdfofd"
             target_path = os.path.join(PDF_FILES, file + ".ofd")
        elif file.endswith(".ofd"):
             source_type = "pdfofd"
             target_path = os.path.join(PDF_FILES, file + ".pdf")
        else:
             continue
        task = {
             "file_path":file_path, #源文件绝对路径
             "target_path": target_path, #转换后文件绝对路径
             "task_key": str(uuid.uuid4()), #任务id, 任务调用方使用此id来轮询结果
             "task_inqueue_time":conn.time()[0], #任务入队时间  以 UNIX 时间戳格式表示, redis Time
             "task_inqueue_timeout":120, #任务在队列中的超时时间
             "task_timeout": 60, #任务转换超时时间，从任务开始被转换开始计时
             "source_type":source_type,
             "target_type":"pdf"
        }
        print(task)
        ongoing_tasks.append(task)
        conn.rpush("Convert:"+source_type, json.dumps(task))
    while len(ongoing_tasks) > 0:
        print(ongoing_tasks)
        print("\r\n")
        for task in ongoing_tasks[:]:
            ret_list = conn.blpop("ConvertResult:" +task["task_key"], 2)
            if not ret_list:
                 continue
            print("\r\n")
            print(task["task_key"]+ ": result->:" + str(ret_list[1]))
            conn.delete("ConvertResult:" +task["task_key"])
            print("\r\n")
            print("convert file saved at:"+ task["target_path"])
            print("\r\n")
            ongoing_tasks.remove(task)
            
         
    
    
if __name__ == '__main__':
    #import pdb
    #pdb.set_trace()
    word2pdf()
