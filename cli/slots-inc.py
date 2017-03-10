#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time
import re
import tarfile
import datetime
#from sh import ssh

def help():
    print '''
    Usage:
        %s [Service type] [Service name]        -- 需要重启或重载的服务名, 逗号分隔
    '''
    sys.exit(1)

# 需要重启服务打开
# if (len(sys.argv) - 1) != 2 and (not sys.argv[1] is 'restart' or not sys.argv[1] is 'reload'): help()

DIRNAME = os.path.abspath(os.path.dirname(__file__))
svn_dir = DIRNAME + '/repo/branch_slots_20160123'
tar_list = '/mnt/slots_config/update_file_list.txt'
tar_path = '/tmp/slots_package'
tar_name = 'slots_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.tgz'
ver_name = 'date.now'
tar_file = os.path.join(tar_path, tar_name)
ver_file = os.path.join(tar_path, ver_name)
key_file = DIRNAME + '/slots.pem'
slots_push_host = '52.70.28.153'
cdn_url = 'http://download1.ximigame.com/download/slots/push'


# write date to file
with open(ver_file, 'w') as f:
    f.write('%s\n' % datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S'))

# mkdir
if not os.path.exists(tar_path):
    os.system('mkdir -p %s' % tar_path)

# to svn dir
if os.path.exists(svn_dir):
    os.chdir(svn_dir)
else:
    print 'SVN 目录不存在'
    sys.exit(1)

# up svn
os.system('svn up --username=backup --password=svnmi150205 --no-auth-cache')

## del .svn
#os.system('find . -name .svn -exec rm -rf {} \;')
EXCLUDE_FILES = ['.svn']

def filter_function(tarinfo):
    if tarinfo.name in EXCLUDE_FILES:
        return None
    else:
        return tarinfo

# gzip
tar = tarfile.open(tar_file, 'w:gz')

try:
    with open(tar_list, 'rU') as f:
        for _line in f:
            if '\xef\xbb\xbf' in _line:
                line = _line.strip('\xef\xbb\xbf')
            else:
                line = _line
            r = re.match(r'(.+|^)(#.+)\s', line)
            n = re.match(r'(^$|^\s+$)', line)
            if n:
                #print '匹配到空字符和空行,pass'
                continue
            elif r:
                if not '' == r.group(1):
                    print 'ADD', r.group(1).strip(), 'to', tar_file
                    tar.add(r.group(1).strip(), filter=filter_function)
            else:
                print 'ADD', line.replace('\n', ''), 'to', tar_file
                tar.add(line.replace('\n',''), filter=filter_function)
        os.chdir(tar_path)
        tar.add(ver_name, filter=filter_function)
except OSError, e:
    print e
    os.remove(tar_file)
    sys.exit(2)
tar.close()

# to cdn
result = os.system('rsync --port=1888 -azP %s slots-push.ximigame.com::slots-push' %tar_file)

print '稍后'
time.sleep(60)

#result = 0
#tar_name = 'slots_20161203_160044.tgz'

if result == 0: result1 = os.system('chmod 400 %s' %key_file)
else: sys.exit(3)

# 下载更新包
if result1 == 0:
    result2 = 1
    reloadnum = 0
    while not result2 is 0:
        result2 = os.system("ssh -p 13021 -i %s root@%s 'cd /push/pkg/; rm -rf *; wget -t 1 %s/%s'" %(key_file, slots_push_host, cdn_url, tar_name))
        reloadnum+=1
        if reloadnum is 3: break
else: sys.exit(3)

# 解压更新包
if result2 == 0: result3 = os.system('ssh -p 13021 -i %s root@%s "cd /push/pkg/; tar xf %s; rm -f %s"' %(key_file, slots_push_host, tar_name, tar_name))
else: sys.exit(3)

# yn = raw_input('是否关闭报警? (y/n)')
# if yn.strip().lower() == 'y':
#     if result4 == 0: result5 = os.system('ssh -p 13021 -i %s root@%s "/monitor/mediatype.sh stop"' %(key_file, slots_push_host))
# else:
#     result5 = 0
#     print '跳过'

yn = raw_input('是否部署生产服? (y/n)')
if yn.strip().lower() == 'n':
    sys.exit(0)

yn = raw_input('是否阻挡玩家连接游戏? (y/n)')
if yn.strip().lower() == 'y':
    if result3 == 0: result4 = os.system('ssh -p 13021 -i %s root@%s "/monitor/whitelist.sh start"' %(key_file, slots_push_host))
else:
    result4 = 0
    print '跳过'

yn = raw_input('是否开始更新? (y/n)')
if yn.strip().lower() == 'y':
    if result4 == 0: result5 = os.system('ssh -p 13021 -i %s root@%s "cd /push/bin/; ./slots-push.py"' %(key_file, slots_push_host))
else:
    result5 = 0
    print '跳过'

# yn = raw_input('是否重启服务? (y/n)')
# if yn.strip().lower() == 'y':
#     print '开始重启'
#     service_type = 'restart'
#     for service_name in sys.argv[2].strip().split():
#         result7 = os.system('ssh -p 13021 -i %s root@%s "/monitor/service/restart_service.py %s %s"' %(key_file, slots_push_host, service_type, service_name))
# else:
#     result7 = 0
#     print '跳过'

## start zabbix report
# time.sleep(10)
# if result7 == 0: result8 = os.system('ssh -p 13021 -i %s root@%s "/monitor/mediatype.sh start"' %(key_file, slots_push_host))

yn = raw_input('是否关闭白名单? (y/n)')
if yn.strip().lower() == 'y':
    os.system('chmod 400 %s' %key_file)
    os.system('ssh -p 13021 -i %s root@%s "/monitor/whitelist.sh stop"' %(key_file, slots_push_host))
else:
    print '跳过'
