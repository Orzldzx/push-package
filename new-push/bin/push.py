#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 1un
# 2016-08-15

'''
    Python version: 2.7.3
        install: paramiko
'''

# --------------模块------------

import yaml
import logging, logging.config      # 脚本直接配置不用加载 logging.config 模块
import os, sys, shutil, subprocess, commands, paramiko
import threading

# --------------变量------------

# 定义各类目录路径
pwd_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pkg_path = pwd_path + '/pkg'
tmp_path = pwd_path + '/work'
bak_path = pwd_path + '/backing'
remoteBakDir  = '/data/backing'
remoteWorkDir = '/svndata'
# 定义各类文件路径
config_file = pwd_path + '/conf/config-services.yml'
exclude_file = pwd_path + '/conf/exclude-service-list.txt'
bakListFile = bak_path + '/backup.list'
# 定义各类文件名
remote_bak_file = '/tmp/XimiHallPushFileList.txt'
# 加载日志配置(配置文件)
logging.config.fileConfig(pwd_path + '/conf/logs.cfg')
logger_user = logging.getLogger("user")
# 脚本直接配置
#logging.basicConfig(level=logging.DEBUG,
#                     format='%(asctime)s %(levelname)-6s %(message)s',
#                     datefmt='%Y-%m-%d %X',
#                     filename='../log/push.log',
#                     filemode='a')
#console = logging.StreamHandler()
#console.setLevel(logging.DEBUG)
#formatter = logging.Formatter('%(asctime)s %(levelname)-6s %(message)s')
#console.setFormatter(formatter)
#logging.getLogger('').addHandler(console)
# 限制同时进行的线程数量
threading_sum = threading.Semaphore(5)

# ------------装饰器------------

def log(msg):
    def _log(func):
        def wrapper(*args, **kw):
            try:
                print_Show_Msg('{0:-<80}'.format(''), 'debug')
                print_Show_Msg('正在执行: {0:*<70}'.format(msg), 'debug')
                return func(*args, **kw)
            except Exception,e:
                print_Show_Msg('执行失败: {0:x<70}'.format(e), 'debug')
                print_Show_Msg('{0:-<80}'.format(''), 'debug')
                #err_Exit_Show_Msg('执行失败: {0:x<70}'.format(msg))
            else:
                print_Show_Msg('执行完成: {0:+<70}'.format(msg), 'debug')
                print_Show_Msg('{0:-<80}'.format(''), 'debug')
        return wrapper
    return _log

# -------------函数-------------

def err_Exit_Show_Msg(msg):
    '''
    发生错误的时候显示相关错误信息并且退出程序
    '''
    logger_user.error(msg)
    sys.exit()

def print_Show_Msg(msg, level='info'):
    '''显示信息,并记录日志'''
    if level == 'info': logger_user.info(msg)
    elif level == 'debug': logger_user.debug(msg)

@log('Load config file ')
def select_Config(config_file):
    '''加载配置文件'''
    f    = open(config_file)
    conf = yaml.load(f)
    f.close()
    return conf

@log('Copy file ')
def sync(src, dest=None, exclude=False, include=False, host=False, remote=False, mod=None, **kw):
    '''传输文件到指定位置'''
    # ---------
    try:
        if not os.path.exists(src): return False
        src = src+'/' if os.path.isdir(src) else src
        # ---------
        exclude = '' if not exclude else '--exclude-from={0}'.format(exclude_file)
        # ---------
        include = '' if not include else '--files-from={0}'.format(include)
        # ---------
        if not remote:
            cmd = '/usr/bin/rsync -aqP {0} {1} {2} {3}'.format(include, exclude, src, dest)
            ChangeDir.check_dir_exists(os.path.dirname(dest), 'touch')
        else:
            CheckHost.ping(host)
            dest = '{0}:{1}'.format(host, mod) if '/' in mod else '{0}::{1}'.format(host, mod)
            cmd = '/usr/bin/rsync --port=1888 -azP {0} {1} {2} {3}'.format(include, exclude, src, dest)
        # ---------
        ps = subprocess.Popen(cmd ,shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ps.wait()
        stdout, stderr = ps.communicate()
        print_Show_Msg('执行完成: \n\nstdout: {0} \nstderr: {1}'.format(stdout, stderr), 'debug')
        print_Show_Msg('复制完成: {0} >> {1}'.format(src,dest), 'debug')
    except Exception,e:
        err_Exit_Show_Msg('复制失败: {0}'.format(e))

@log('Exec SSH ')
def ssh(cmd,host,user='root',port=22,keyfile='/root/.ssh/id_rsa'):
    '''远程执行命令'''
    ssh = paramiko.SSHClient()
    key = paramiko.RSAKey.from_private_key_file(keyfile)
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port, user, key)
    # ---------
    try:
        print_Show_Msg('正在执行: {0} - "{1}"'.format(host, cmd), 'debug')
        stdin,stdout,stderr = ssh.exec_command(cmd)
        print_Show_Msg('执行完成: \n\nstdout: {0} \nstderr: {1}'.format(stdout.read(), stderr.read()), 'debug')
        ssh.close()
    except SSHException,e: err_Exit_Show_Msg('无法连接目标主机: '+e)

@log('Loop list ')
def loop(func,conf,file_name=False,exclude=False,include=False):
    '''循环读取配置文件'''
    for Type,services_names in conf.items():
        if isinstance(services_names, dict):
            for service_name,service_opts in services_names.items():
                for service_opt in service_opts:
                    # ---------
                    _name,_num      = service_name, service_opt['num']
                    _lanip, _wlanip = service_opt['lip'], service_opt['oip']
                    _port, _deplist = service_opt['port'], service_opt['dep']
                    # --------
                    src  = pkg_path
                    dest = '{0}/{1}'.format(tmp_path, _lanip)
                    exclude_text = '{0}/{1}'.format(Type, service_name)
                    # --------
                    func(Type=Type,service_name=_name,file_name=file_name,src=src,dest=dest,WLANIP=_wlanip,host=_lanip,exclude=exclude,include=include,service_num=str(_num),text=exclude_text,port=_port,deplist=_deplist)

@log('Write text to the file ')
def write_File(file_name, text, **kw):
    '''写文本文件'''
    ChangeFile.check_file_exists(file_name, 'touch')
    print_Show_Msg('正在写入: {0:30} 到文件 {1}'.format(text.strip('\n'),file_name), 'debug')
    try:
        with open(file_name, 'a+') as f:
            f.write('{0}\n'.format(text))
    except Exception,e:
        err_Exit_Show_Msg('写入失败: {0} - {1}'.format(file_name,e))

@log('Edit text file ')
def change_Test_file(select_file_name, select, text):
    '''修改文件内容'''
    try:
        print_Show_Msg('正在替换: {0} 的内容为 - {1}'.format(select_file_name, text), level='debug')
        with open(select_file_name, 'r') as f:
            lines = f.readlines()
        for num in range(len(lines)):
            if select in lines[num]:
                lines[num]='{0}\n'.format(text)
        with open(select_file_name, 'w+') as f:
            f.write(''.join(lines))
    except Exception,e:
        err_Exit_Show_Msg('替换失败: '+e)

@log('Config service ')
def change_Service_config(Type,service_name,host,service_num,port,WLANIP,deplist, **kw):
    '''根据服务类型选择配置方式'''
    try:
        print_Show_Msg('准备配置: {0:15} {1}'.format(service_name,'-'*10), 'info')
        # ---------
        src = pkg_path+'/'+Type+'/'+service_name
        if service_name == 'cfgcenter':
            serviceNameNum = service_name
            dest = tmp_path+'/'+host+'/'+Type+'/'+service_name
            path = '{0}/{1}/bin/{1}'.format(Type, service_name)
        else:
            serviceNameNum = service_name+'.'+service_num.split('.')[1]
            dest = tmp_path+'/'+host+'/'+Type+'/'+serviceNameNum
            path = '{0}/{1}/bin/{1}'.format(Type, service_name)
        # ---------
    except KeyError,e:
        err_Exit_Show_Msg('准备错误: 变量错误 - %s' %e)
    try:
        print_Show_Msg('正在复制: {0} 服务相关文件和配置'.format(service_name), 'info')
        ChangeFile.clearFile(exclude_file)
        excludeList = '/'.join(path.split('/')[-2:])
        write_File(exclude_file, excludeList)
        sync(src, dest, exclude=True)
        sync('{0}/bin/{1}'.format(src, service_name), '{0}/bin/{2}'.format(dest, service_name,serviceNameNum))
    except Exception,e:
        err_Exit_Show_Msg('复制失败: '+e)
    # ---------
    try:
        if service_name == 'cfgcenter': return
        elif Type == 'games':
            change_GAMES_Service_config(Type,service_name,host,service_num,dest,port,WLANIP)
        elif Type == 'service':
            change_SERVICE_Service_config(Type,service_name,host,service_num,dest,port,WLANIP,deplist)
    except Exception,e:
        err_Exit_Show_Msg('类型错误: {0}, {1}'.format(Type,e))

@log('Edit config file ')
def change_GAMES_Service_config(Type,service_name,host,service_num,dest,port,WLANIP):
    '''配置local'''
    print_Show_Msg('修改配置: {0} to local'.format(service_name), 'info')
    # ---------
    cfg_game = '{0}/config/game.cfg'.format(dest)
    dep_srv = '{0}/deploy/server.cfg'.format(dest)
    dep_cli = '{0}/deploy/clients/robot.cfg'.format(dest)
    # ---------
    gw_lan_ip      = conf['service']['gamegw'][0]['lip']
    gw_app_port    = conf['service']['gamegw'][0]['port'][0]
    # ---------
    robot_all_id   = conf['games']['robot'][0]['num']
    robot_lan_ip   = conf['games']['robot'][0]['lip']
    robot_app_port = conf['games']['robot'][0]['port'][0]
    # ---------
    srv_wlan_ip, srv_lan_ip     = WLANIP, host
    srv_app_port, srv_http_port = port[0], port[1]
    srv_id, srv_id_num          = service_num.split('.')[0], service_num.split('.')[1]
    # ---------
    # 修改服务配置
    files = [cfg_game,dep_srv,dep_cli] if service_name != 'robot' else [dep_srv]
    try:
        for f in files:
            if ChangeFile.check_file_exists(f, 'pass'):
                print_Show_Msg('正在配置: {0} 服务 {1} 配置'.format(service_name,f),'info')
                if f == dep_srv:
                    change_Test_file(f, 'Id', 'Id: "{0}.{1}"'.format(srv_id,srv_id_num))
                    change_Test_file(f, 'Addrs', 'Addrs: "0.0.0.0:{0}"'.format(srv_app_port))
                    change_Test_file(f, 'HttpAddr', 'HttpAddr: "{0}:{1}"'.format(srv_lan_ip,srv_http_port))
                if f == cfg_game:
                    change_Test_file(f, 'GameGW', 'GameGW: "{0}:{1}"'.format(gw_lan_ip,gw_app_port))
                    change_Test_file(f, 'ServerAddr', 'ServerAddr: "{0}:{1}"'.format(srv_wlan_ip,srv_app_port))
                if f == dep_cli:
                    change_Test_file(f, 'Id', 'Id: "{0}"'.format(robot_all_id))
                    change_Test_file(f, 'Addrs', 'Addrs: "{0}:{1}"'.format(robot_lan_ip,robot_app_port))
            else: return False
    except Exception,e:
        err_Exit_Show_Msg('修改失败: '+e)

@log('Edit config file ')
def change_SERVICE_Service_config(Type,service_name,host,service_num,dest,port,WLANIP,deplist):
    '''配置cfgcenter'''
    print_Show_Msg('修改配置: {0} to cfgcenter'.format(service_name), 'info')
    # ---------
    serviceName, serviceNum, serviceType = service_name, service_num, Type
    serviceLanIpAddr, serviceWLanIpAddr  = host, WLANIP
    serviceAppPort, serviceHttpPort      = port[0], port[1]
    serviceCfgPath, serviceSyncPath      = dest+'/deploy/server.cfg', dest+'/deploy/cfgsync.cfg'
    # ---------
    centerConf = conf['service']['cfgcenter'][0]
    centerCfgdir = tmp_path+'/'+centerConf['lip']+'/service/cfgcenter/config'
    CfgToService = centerCfgdir+'/'+serviceNum.replace('.','/')
    # ---------
    # 修改cfgcenter连接配置
    if ChangeFile.check_file_exists(serviceSyncPath, 'pass'): change_Test_file(serviceSyncPath, 'Addr:', 'Addr: "{0}:{1}"'.format(centerConf['lip'],centerConf['port'][0]))
    # 修改server.cfg
    if ChangeFile.check_file_exists(serviceCfgPath, 'pass'):
        change_Test_file(serviceCfgPath, 'Id', 'Id: "{0}"'.format(serviceNum))
        change_Test_file(serviceCfgPath, 'Addrs', 'Addrs: "0.0.0.0:{0}"'.format(serviceAppPort))
        change_Test_file(serviceCfgPath, 'HttpAddr', 'HttpAddr: "{0}:{1}"'.format(serviceLanIpAddr,serviceHttpPort))
        # 修改cfgcenter/server.cfg
        print_Show_Msg('正在配置: {0} 服务 server 配置'.format(serviceName,CfgToService+'/server.cfg'),'info')
        ChangeDir.check_dir_exists(CfgToService,'touch')
        msg = '''Id: "%s"
Addrs: "0.0.0.0:%d"
IsGateway: false
SendLimit: 1000
RecvLimit: 1000
HttpAddr: "%s:%d"
        ''' %(serviceNum,serviceAppPort,serviceLanIpAddr,serviceHttpPort)
        ChangeFile.writeText(CfgToService+'/server.cfg','w+',msg)
        # 修改cfgcenter/依赖配置
        if type(deplist) == list:
            for dep in deplist:
                ChangeDir.check_dir_exists(CfgToService+'/clients','touch')
                print_Show_Msg('正在配置: {0} 服务 依赖项 {1}'.format(serviceName,dep),'info')
                if dep == 'corelogic':
                    msg = '''ServerEntries {
    Id : "%s"
    Addrs : "%s:%d"
}
RouteEntries {
    HashBegin : 0
    HashEnd : 511
    ServerIdx : 0
}
SendLimit : 10
RecvLimit : 10\n''' %(conf['service']['coredata_logic'][0]['num'],
                      conf['service']['coredata_logic'][0]['lip'],
                      conf['service']['coredata_logic'][0]['port'][0])
                elif dep == 'oplog':
                    msg = '''ServerEntries {
    Id : "%s"
    Addrs : "%s:%d"
}
RouteEntries {
    HashBegin : 0
    HashEnd : 511
    ServerIdx : 0
}
SendLimit : 10
RecvLimit : 10\n''' %(conf['service']['oplogs'][0]['num'],
                      conf['service']['oplogs'][0]['lip'],
                      conf['service']['oplogs'][0]['port'][0])
                else:
                    msg = '''ServerEntries {
    Id : "%s"
    Addrs : "%s:%d"
}
RouteEntries {
    HashBegin : 0
    HashEnd : 511
    ServerIdx : 0
}
SendLimit : 10
RecvLimit : 10\n''' %(conf['service'][dep][0]['num'],
                      conf['service'][dep][0]['lip'],
                      conf['service'][dep][0]['port'][0])
                ChangeFile.writeText(CfgToService+'/clients/'+dep+'.cfg','w+',msg)

@log('Backup remote host the files ')
def bak_Remote_Files(remoteBakDir,remoteWorkDir):
    try: hosts = ChangeDir.printDir(tmp_path)
    except Exception,e: err_Exit_Show_Msg('获取失败: {0} '.format(e))
    else: print_Show_Msg('获取成功: 目录列表', 'debug')
    try:
        for host in hosts:
            src = bak_path + '/' + host
            dest = remote_bak_file
            ChangeDir.PathFilesList(tmp_path + '/' + host,src)
            print_Show_Msg('正在执行: 推送本次发布相关文件列表到 {0}'.format(host), 'info')
            sync(src,host=host,mod=dest,remote=True)
            write_File(bakListFile, '%s\n' %host)
            print_Show_Msg('执行完成: 文件列表推送成功 - {0}'.format(host), 'info')
    except Exception,e:
        err_Exit_Show_Msg('执行失败: {0}'.format(e))
        # ---------
    try:
        for host in hosts:
            cmd = 'rm -rf {0}/* && rsync -avP --files-from={2} {1}/ {0}/'.format(remoteBakDir,remoteWorkDir,remote_bak_file)
            print_Show_Msg('正在执行: 备份 {0} 相关文件'.format(host), 'info')
            t = MyThreadSSH(threading_sum,cmd,host)
            t.start()
        t.join()
    except Exception,e:
        err_Exit_Show_Msg('推送失败: {0} '.format(e))

@log('push files to servers ')
def push_files_to_servers():
    try: hosts = ChangeDir.printDir(tmp_path)
    except Exception,e: err_Exit_Show_Msg('获取失败: {0} '.format(e))
    else: print_Show_Msg('获取成功: 远程主机列表获取成功', 'debug')
    try:
        for host in hosts:
            print_Show_Msg('正在执行: 推送文件到 {0} 主机'.format(host), 'info')
            src = tmp_path+'/'+host
            t = MyThreadSYNC(threading_sum,src,None,host,remote=True,mod='svn')
            t.start()
        t.join()
    except Exception,e:
        err_Exit_Show_Msg('推送失败: {0} '.format(e))
    else:
        print_Show_Msg('执行完成: 发布完成'.format(host), 'info')

# --------------类--------------

class ChangeFile(object):
    '''操作文件'''
    @staticmethod
    def check_file_exists(file_name, mode='exit'):
        '''检测指定的文件是否存在'''
        print_Show_Msg('正在检查: {0}是否存在'.format(file_name), 'debug')
        if not os.path.exists(file_name):
            if mode == 'exit': err_Exit_Show_Msg('{0} 不存在'.format(file_name))
            elif mode == 'touch': ChangeFile.touchFile(file_name)
            elif mode == 'pass': return False
        else: return True
    @staticmethod
    def touchFile(file_name):
        '''创建文件'''
        if not os.path.exists(os.path.dirname(file_name)):
            print_Show_Msg('正在创建: {0}'.format(os.path.dirname(file_name)), 'debug')
            os.makedirs(os.path.dirname(file_name))
        try:
            print_Show_Msg('正在创建: {0}'.format(file_name), 'debug')
            os.mknod(file_name)
        except Exception,e:
            err_Exit_Show_Msg('创建失败: {0}'.format(e))
        else:
            print_Show_Msg('创建完成: {0}'.format(file_name), 'debug')
    @staticmethod
    def clearFile(fileName):
        '清空文件内容'
        with open(fileName, 'w') as f:
            f.truncate()
    @staticmethod
    def writeText(fileName,mode,msg):
        try:
            with open(fileName,mode) as f:
                f.write(msg)
        except Exception,e:
            err_Exit_Show_Msg('写入失败:',e)

class ChangeDir(object):
    '''操作目录'''
    @staticmethod
    def check_dir_exists(dir_name, mode='exit'):
        '''检测指定的目录是否存在'''
        print_Show_Msg('正在检查: {0} 是否存在'.format(dir_name), 'debug')
        if not os.path.exists(dir_name):
                if mode == 'exit': err_Exit_Show_Msg('检查完成: {0} 不存在'.format(dir_name))
                elif mode == 'touch': ChangeDir.touchFile(dir_name)
                elif mode == 'pass': return False
        else:
            if not os.path.isdir(dir_name): print_Show_Msg('检查完成: {0} 不是一个目录'.format(dir_name))
            return True
    @staticmethod
    def touchFile(dir_name):
        '''创建目录'''
        try:
            print_Show_Msg('正在创建: {0}'.format(dir_name), 'debug')
            os.makedirs(dir_name)
        except Exception,e:
            err_Exit_Show_Msg('创建失败: {0}'.format(e))
        else: print_Show_Msg('创建完成: {0}'.format(dir_name), 'debug')
    @staticmethod
    def printDir(dir_name):
        '''获取指定目录下子目录列表'''
        if os.path.exists(dir_name):
            print_Show_Msg('正在获取: 目录列表'.format(dir_name), 'info')
            return [d for d in os.listdir(dir_name) if os.path.isdir('{0}/{1}'.format(dir_name,d))]
        else: err_Exit_Show_Msg('获取失败: {0} 目录不存在'.format(dir_name))
    @staticmethod
    def PathFilesList(dir_name,files_list_file):
        '''
        获取目录下面所有的文件(包括子目录以及其中包含的文件).
        '''
        try:
            print_Show_Msg('正在写入: {0} 目录下所有文件列表到 {1}'.format(dir_name,files_list_file), 'info')
            with open(files_list_file,'w+') as f:
                for (dirpath, dirnames, filenames) in os.walk(dir_name):
                    for filename in filenames:
                        __file = os.path.join(dirpath, filename).split('/')[5:]
                        File = '/'.join(__file)
                        f.write(File + '\n')
                f.close()
        except IOError,e:
            err_Exit_Show_Msg('写入失败: 创建文件失败 ' + files_list_file)
        else:
            print_Show_Msg('写入完成: 获取文件列表成功', 'info')
    @staticmethod
    def clearDir(dirName):
        shutil.rmtree(dirName)

class CheckHost(object):
    '''检测网络状况'''
    @staticmethod
    def checkIp(host):
        '''
        IP地址合法性检测
        '''
        ipaddr = host.split('.')
        print_Show_Msg('正在执行: ip地址[%s]合法性检测' %host, 'debug')
        check = len(ipaddr) == 4 and len(filter(lambda x: x >= 0 and x <= 255, map(int, filter(lambda x: x.isdigit(), ipaddr)))) == 4
        if check: print_Show_Msg('执行成功: ip地址[%s]合法性检测' %host, 'debug')
        else: err_Exit_Show_Msg('执行失败: ip地址[%s]合法性检测' %host)
    @staticmethod
    def ping(host):
        '''IP地址连通性检测'''
        CheckHost.checkIp(host)
        print_Show_Msg('正在执行: ip地址 %s 连通性检测检测' %host, 'debug')
        status, output = commands.getstatusoutput('ping -c 2 -w 3 -i 1 {0}'.format(host))
        if 0 == status: print_Show_Msg('执行成功: %s 通信正常' %host, 'debug')
        else: err_Exit_Show_Msg('执行失败: %s 通信失败' %host)

class MyThreadSSH(threading.Thread):
    def __init__(self, Sum, cmd, host):
        threading.Thread.__init__(self)
        self.sum  = Sum
        self.cmd  = cmd
        self.host = host
        self.lock = threading.Lock()
    def run(self):
        with self.sum:
            if self.lock.acquire():
                ssh(self.cmd,self.host)
                self.lock.release()

class MyThreadSYNC(threading.Thread):
    def __init__(self,Sum,src,dest,host=False,exclude=False,include=False,remote=False,mod=None):
        threading.Thread.__init__(self)
        self.sum  = Sum
        self.src  = src
        self.mod  = mod
        self.dest = dest
        self.host = host
        self.remote  = remote
        self.exclude = exclude
        self.include = include
        self.lock = threading.Lock()
    def run(self):
        with self.sum:
            if self.lock.acquire():
                sync(self.src,self.dest,self.exclude,self.include,self.host,self.remote,self.mod)
                self.lock.release()

# --------------准备------------

def main():
    print_Show_Msg('\n\n\n{0} {1} {0}\n'.format('#'*30,'准备发布环境'),'info')
    global conf
    # 清空exclude文件
    ChangeFile.clearFile(exclude_file)
    # 清空工作目录
    ChangeDir.check_dir_exists(tmp_path,'touch')
    ChangeDir.clearDir(tmp_path)
    # 加载配置
    conf = select_Config(config_file)
    # 写排除列表
    loop(write_File, conf, exclude_file)
    # 复制通用目录
    print_Show_Msg('\n\n\n{0} {1} {0}\n'.format('#'*30,'准备通用配置'),'info')
    loop(sync, conf, exclude=True)
    # 独立配置
    print_Show_Msg('\n\n\n{0} {1} {0}\n'.format('#'*30,'准备独立配置'),'info')
    loop(change_Service_config, conf)
    # 备份远程主机文件
    print_Show_Msg('\n\n\n{0} {1} {0}\n'.format('#'*30,'备份远端配置'),'info')
    bak_Remote_Files(remoteBakDir,remoteWorkDir)
    # 推送文件
    print_Show_Msg('\n\n\n{0} {1} {0}\n'.format('#'*30,'开始发布'),'info')
    push_files_to_servers()

# --------------开始------------

if __name__ == '__main__':

    # ---------
    main()
