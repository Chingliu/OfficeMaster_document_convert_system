# OfficeMaster_document_convert_system  
多格式（word/excel/ppt转pdf/ofd, pdf/ofd相互转换）文档转换系统  

# 已支持的转换类型
1. word转pdf word转ofd  
2. excel转pdf excel转ofd   
3. ppt转pdf ppt转ofd  
4. pdf转ofd ofd转pdf  

# 待支持类型  
1. pdf转jpg pdf转png  
2. ofd转jpg ofd转png  
3. 图片转pdf 图片转ofd   
4. pdf转txt ofd转txt  
5. txt转pdf txt转ofd  
6. pdf转docx ofd转docx  

# 已支持的接口
fastapi的http接口  
CLI的feed.py  

# 授权文件  
授权文件放在另一个项目中： 
https://github.com/Chingliu/XilouReader/tree/main/OfficeMaster_document_convert_system  
https://gitee.com/chingliu/XilouReader/tree/main/OfficeMaster_document_convert_system  

word/excel/ppt转pdf/ofd考虑到版面效果，需要依赖wps/office软件，需要wps/office有com接口支持  
pdf/ofd互转 详见另一项目https://gitee.com/chingliu/XilouReader  

# 用法
1. 下载最新版本redis服务端,将redis 地址端口更新到config.json
2. 将python程序绝对路径配置到config.json文件中
3. 根据机器性能配置word,excel, ppt,hare进程的数量
4. 现在默认使用的是wps所以需要安装wps专业版，只有wps专业版本才有com接口
5. pdfmaster目录下的hare库用于pdf/ofd互转
6. python manager.py启动转换后台服务， python 应该安装redis客户端 pip install redis
7. python feed.py就可以将指定目录的文件送到转换服务去转换
8. 如果需要使用HTTP接口，需要按full-stack-fastapi-template-master目录中fastapi的依赖来配置

