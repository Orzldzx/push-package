#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 1un
# 2016-03-16

import ConfigParser, yaml
import logging, logging.config
import sys, os, stat, shutil, time
import subprocess, paramiko
import threading
import MySQLdb


def __err_exit_show_msg(msg):
    '''
    发生错误的时候显示相关错误信息并且退出程序
    '''
    logger_user.error(msg)
    sys.exit()

def __check_file_exists(file_name):
    '''
    检测指定的文件是否存在
    '''
    if not os.path.exists(file_name):
        __err_exit_show_msg(file_name + ' 不存在')

def load_yaml(file_name):
    '''
    加载配置文件
    '''
    f = open(file_name)
    x = yaml.load(f)
    f.close()
    return x

def setup_section(file_name, section, option, value):
    '''
    修改配置文件项
    '''
    # 检测文件是否存在
    __check_file_exists(file_name)
    # 修改配置项
    class myconf(ConfigParser.ConfigParser):
        def __init__(self,defaults=None):
            ConfigParser.ConfigParser.__init__(self,defaults=None)
        def optionxform(self, optionstr):
            return optionstr
    conf = myconf()
    #conf = ConfigParser.ConfigParser()
    conf.read(file_name)
    try:
        if not option in conf.options(section): return
        conf.set(section, option, value)
    except ConfigParser.NoSectionError,e:
        print e
    conf.write(open(file_name, 'w'))
    # 记录日志
    logger_user.debug('正在修改: %s | %-17s  %-11s = %s' %(file_name, '[%s]' %section, option, value))

def get_service_dir_list():
    '''
    获取独立配置列表
    '''
    service_names = ['svr/' + i for i in x.keys()]
    # 将列表写入文件,推送通用配置文件时排除列表里的目录
    with open('../conf/tex_exclude_path.txt','w') as f:
        for i in range(0, len(service_names)):
            f.write(service_names[i] + '\n')
        f.write('svr/tcpsvrd' + '\n')
        f.write('svr/mod.txt' + '\n')
        f.close()

def make_dir(Dir):
    '''
    创建目录
    '''
    if not os.path.exists(Dir):
        logger_user.debug('正在创建目录: ' + Dir)
        os.makedirs(Dir)

def get_dir_list(Dir):
    '''
    获取指定目录下子目录列表
    '''
    make_dir(Dir)
    os.chdir(Dir)
    try:
        _workDir = os.listdir(Dir)
        return [ _workDir[i] for i in range(len(_workDir)) if os.path.isdir(_workDir[i]) ]
    except OSError,e:
        __err_exit_show_msg('目录不存在: ' + Dir)

def Get_Zip_Nmae(Dir):
    '''
    获取zip文件名
    '''
    make_dir(Dir)
    os.chdir(Dir)
    try:
        _zipfile = os.listdir(Dir)
        zipfile = [ i for i in _zipfile if os.path.isfile(i) if 'zip' in i ]
        if len(zipfile) == 1:
            return Dir+'/'+''.join(zipfile)
    except OSError,e:
        __err_exit_show_msg('目录不存在: ' + Dir)

def __select_file(rdir, sfn):
    '''
    获取指定路径下的指定文件,返回列表
    rdir = rootdir, sfn = select_file_name, dp = dirpath, dns = dirnames, fns = filenames, fn = filename
    '''
    return [ os.path.join(dp, fn) for (dp,dns,fns) in os.walk(rdir) for fn in fns if fn == sfn ]

def change_dbenv(select_file_names, sql_user, sql_pass):
    '''
    修改文件指定字符
    '''
    for select_file_name in select_file_names:
        logger_user.info('修改%s文件的数据库连接帐号' %select_file_name)
        with open(select_file_name, 'r') as f:
            lines = f.readlines()
        for num in range(len(lines)):
            if 'DBUSER' in lines[num]:
                lines[num]='export DBUSER=%s\n' %sql_user
            elif 'DBPASS' in lines[num]:
                lines[num]='export DBPASS=%s\n' %sql_pass
        with open(select_file_name, 'w+') as f:
            f.write(''.join(lines))

def chmod_file(rootdir, f):
    '''
    给指定扩展名文件增加权限
    '''
    logger_user.info(f + '文件授权')
    for (dirpath, dirnames, filenames) in os.walk(rootdir):
        for filename in filenames:
            if os.path.splitext(filename)[1] == f:
                os.chmod(os.path.join(dirpath, filename), stat.S_IRWXU+stat.S_IRGRP+stat.S_IROTH)

def change_zabbix_report(on_off, msg):
    '''
    开/关zabbix监控报警
    '''
    # on_off = 0 > 发送短信; on_off = 1 > 关闭短信
    print '%szabbix短信告警' %msg
    # 打开数据库连接
    db = MySQLdb.connect(host="127.0.0.1",user="zabbix",passwd='zabbixREPORT',db="zabbix",charset="utf8")
    # 使用cursor()方法获取操作游标
    cursor = db.cursor()
    sql = "UPDATE media_type SET status=%s WHERE mediatypeid=7" %on_off
    try:
        # 使用execute方法执行SQL语句
        cursor.execute(sql)
        # 提交更改到数据库
        db.commit()
    except:
        # 回滚操作
        db.rollback()
    db.close()

def rsync_local(src, dest, Type='all'):
    '''
    调用bash执行rsync,本地复制
    '''
    service_name  = src.split('/')[-2]
    service_num   = dest.split('/')[-1]
    cmd           = '/usr/bin/rsync'
    options       = '-avP'
    exclude       = '--exclude-from=../conf/tex_exclude_path.txt'
    exclude_srv   = "--exclude=bin/%s" %service_name
    src           = src
    dest          = dest

    if Type == 'all':
        try:
            logger_user.info('正在复制通用文件到' + dest)
            make_dir(dest)
            ps = subprocess.Popen([cmd, options, exclude, '%s/'%src, dest], stdout=open(r'/dev/null','w'))
            ps.wait()
        except Exception,e:
            __err_exit_show_msg('复制通用文件失败 %s' % e)
    elif Type == 'srv':
        try:
            if os.path.exists(src):
                logger_user.info('正在复制 %s 配置文件' %service_num)
                make_dir(dest)
                ps = subprocess.Popen([cmd, options, exclude_srv, src, dest], stdout=open(r'/dev/null','w'))
                ps.wait()
            if os.path.exists(src + '/bin/' + service_name):
                make_dir(dest)
                ps = subprocess.Popen([cmd, options, src + '/bin/' + service_name, dest + '/bin/' + service_num], stdout=open(r'/dev/null','w'))
                ps.wait()
                os.chmod(dest + '/bin/' + service_num, stat.S_IRWXU+stat.S_IRGRP+stat.S_IROTH)
        except Exception,e:
            __err_exit_show_msg('复制 %s 配置文件失败: %s' %(service_num, e))
    elif Type == 'tcp':
        try:
            if os.path.exists(src):
                logger_user.info('正在复制 %s.tcp 配置文件' %service_num)
                make_dir(dest)
                ps = subprocess.Popen([cmd, options, src, dest], stdout=open(r'/dev/null','w'))
                ps.wait()
            else: return
            if os.path.exists(src + '/bin/tcpsvrd'):
                make_dir(dest)
                ps = subprocess.Popen([cmd, options, src + '/bin/tcpsvrd', '%s/bin/%s.tcpsvrd.%s' %(dest, k[:-4], v[i]['num'])], stdout=open(r'/dev/null','w'))
                ps.wait()
                os.chmod('%s/bin/%s.tcpsvrd.%s' %(dest, k[:-4], v[i]['num']), stat.S_IRWXU+stat.S_IRGRP+stat.S_IROTH)
            else: return
        except Exception,e:
            __err_exit_show_msg('复制 %s.tcp 配置文件失败: %s' %(service_num, e))

def change_proxy_cfg():
    '''
    修改各个服务路由表
    '''
    if not os.path.exists('%s/svr/proxysvrd' %packagedir): return
    for key in x.keys():
        file_name = '%s/%s/svr/%s.%s/deploy/%ssvrs.ini' %(temp_dir, v[i]['lip'], k, v[i]['num'],x[key][0]['type'].lower())
        #file_name = file_name.lower()
        if x[key][0]['type'] == '-':
            continue
        else:
            if os.path.exists(os.path.dirname(file_name)):
                ps = subprocess.Popen(['echo','/dev/null'], stdin=open(file_name, 'w+'), stdout=open('/dev/null', 'w+'))
                ps.wait()
        if os.path.exists(os.path.dirname(file_name)):
            for n in range(len(x[key])):
                service_ip = x[key][n]['lip']
                service_num = x[key][n]['num']
                with open(file_name, 'a') as f:
                    logger_user.debug('正在修改 %-20s 配置路由表' %key)
                    f.write('%s %s\n' %(service_num, service_ip))

def change_route_cfg(file_name):
    '''
    修改每个服务的个数
    '''
    if not os.path.exists(file_name): return
    with open(file_name, 'r+') as f:
        lines = f.readlines()
        for Type in x.keys():
            number = len(x[Type])
            logger_user.debug('正在修改 %-20s 数目为: %s' %(Type, number))
            for line in lines:
                _Type = x[Type][0]['type']
                if _Type + 'Server' + 'Number' in line:
                    line='%sServerNumber  %s\n' %(_Type, number)
                elif _Type == 'Control' or _Type == 'PanicBuy':
                    if _Type + 'Svr' + 'Number' in line:
                        line='%sSvrNumber  %s\n' %(_Type, number)
                elif 'ProxyServerID' in line:
                    line='ProxyServerID  ' + str(len(x['proxysvrd']))
                elif 'ProxyPort' in line:
                    line='ProxyPort  ' + str(x['proxysvrd'][0]['port'][0])
                #else: print line
    with open(file_name, 'w+') as f:
        f.writelines(lines)

def change_service_proxy_cfg(file_name):
    setup_section(file_name, 'PROXYSVRD', 'PROXYSVRDNUM', len(x['proxysvrd']))
    for proxy_num in range(len(x['proxysvrd'])):
        __proxy_num = x['proxysvrd'][proxy_num]
        setup_section(file_name, 'PROXYSVRD.' + str(__proxy_num['num']), 'SERVERID', __proxy_num['num'])
        setup_section(file_name, 'PROXYSVRD.' + str(__proxy_num['num']), 'SERVICEIP', __proxy_num['lip'])
        setup_section(file_name, 'PROXYSVRD.' + str(__proxy_num['num']), 'SERVICEPORT', __proxy_num['port'][0])

def change_service_logsvrd_cfg(service_name, service_sum):
    file_name = '%s/%s/svr/%s.%s/deploy/%s.cfg' %(temp_dir, service_sum['lip'], service_name, service_sum['num'], service_name)
    if not os.path.exists(file_name): return
    # 日志配置
    setup_section(file_name, 'logsvrd', 'ip', '0.0.0.0')
    setup_section(file_name, 'logsvrd', 'port', x['logsvrd'][0]['port'][0])
    setup_section(file_name, 'logsvrd', 'uri', x['logsvrd'][0]['db'][0])

def change_service_httpsvrd_cfg(service_name, service_sum):
    file_name = '%s/%s/svr/%s.%s/deploy/%s.cfg' %(temp_dir, service_sum['lip'], service_name, service_sum['num'], service_name)
    if not os.path.exists(file_name): return
    # 服务信息配置
    setup_section(file_name, service_name.upper(), 'ServerID', service_sum['num'])
    setup_section(file_name, service_name.upper(), 'ServerIP', '127.0.0.1')
    setup_section(file_name, service_name.upper(), 'ServerPort', service_sum['port'][0])
    # 日志配置
    setup_section(file_name, 'logsvrd', 'ip', x['logsvrd'][0]['lip'])
    setup_section(file_name, 'logsvrd', 'port', x['logsvrd'][0]['port'][0])
    # key配置
    setup_section(file_name, 'SHM', 'CoreKey', service_sum['key'][0])
    # 路由配置
    change_service_proxy_cfg(file_name)

def change_service_base_dbsvrd_cfg(service_name, service_sum):
    file_name = '%s/%s/svr/%s.%s/deploy/%s.cfg' %(temp_dir, service_sum['lip'], service_name, service_sum['num'], service_name)
    if not os.path.exists(file_name): return
    # 服务信息配置
    setup_section(file_name, 'dbsvrd', 'DBServerID', service_sum['num'])
    setup_section(file_name, 'dbsvrd', 'corekey', service_sum['key'][0])
    setup_section(file_name, 'dbsvrd', 'DBIP', service_sum['db'][0])
    setup_section(file_name, 'dbsvrd', 'DBPort', service_sum['db'][1])
    # 路由配置
    change_service_proxy_cfg(file_name)

def change_service_auth_dbsvrd_cfg(service_name, service_sum):
    file_name = '%s/%s/svr/%s.%s/deploy/%s.cfg' %(temp_dir, service_sum['lip'], service_name, service_sum['num'], service_name)
    if not os.path.exists(file_name): return
    # 服务信息配置
    setup_section(file_name, service_name, 'DBServerID', service_sum['num'])
    setup_section(file_name, service_name, 'DBIP', service_sum['db'][0])
    setup_section(file_name, service_name, 'DBPort', service_sum['db'][1])
    # key配置
    setup_section(file_name, service_name, 'corekey', service_sum['key'][0])
    # 路由配置
    change_service_proxy_cfg(file_name)

def change_service_authsvrd_cfg(service_name, service_sum):
    file_name = '%s/%s/svr/%s.%s/deploy/%s.cfg' %(temp_dir, service_sum['lip'], service_name, service_sum['num'], service_name)
    if not os.path.exists(file_name): return
    # 服务信息配置
    setup_section(file_name, service_name.upper(), 'ServerID', service_sum['num'])
    setup_section(file_name, service_name.upper(), 'ServerIP', service_sum['lip'])
    setup_section(file_name, service_name.upper(), 'ServerPort', service_sum['port'][0])
    # 日志配置
    setup_section(file_name, 'logsvrd', 'ip', x['logsvrd'][0]['lip'])
    setup_section(file_name, 'logsvrd', 'port', x['logsvrd'][0]['port'][0])
    # key配置
    setup_section(file_name, 'SHM', 'CoreKey', service_sum['key'][0])
    setup_section(file_name, 'SHM', 'CSPipeKey', service_sum['key'][1])
    setup_section(file_name, 'SHM', 'SCPipeKey', service_sum['key'][2])
    # 路由配置
    change_service_proxy_cfg(file_name)

def change_service_thirdsvrd_cfg(service_name, service_sum):
    file_name = '%s/%s/svr/%s.%s/deploy/%s.cfg' %(temp_dir, service_sum['lip'], service_name, service_sum['num'], service_name)
    if not os.path.exists(file_name): return
    # 服务信息配置
    setup_section(file_name, service_name.upper(), 'ServerID', service_sum['num'])
    setup_section(file_name, service_name.upper(), 'ServerIP', '127.0.0.1')
    setup_section(file_name, service_name.upper(), 'ServerPort', service_sum['port'][0])
    # 日志配置
    setup_section(file_name, 'logsvrd', 'ip', x['logsvrd'][0]['lip'])
    setup_section(file_name, 'logsvrd', 'port', x['logsvrd'][0]['port'][0])
    # redis配置
    setup_section(file_name, 'REDIS', 'IP', service_sum['db'][0])
    setup_section(file_name, 'REDIS', 'PORT', service_sum['db'][1])
    # key配置
    setup_section(file_name, 'SHM', 'CoreKey', service_sum['key'][0])
    # 路由配置
    change_service_proxy_cfg(file_name)

def change_service_public_cfg(service_name, service_sum):
    file_name = '%s/%s/svr/%s.%s/deploy/%s.cfg' %(temp_dir, service_sum['lip'], service_name, service_sum['num'], service_name)
    if not os.path.exists(file_name): return
    # 服务信息配置
    setup_section(file_name, 'SVR', 'SERVERID', service_sum['num'])
    setup_section(file_name, 'SVR', 'SERVERIP', service_sum['oip'])
    setup_section(file_name, 'SVR', 'SERVERPORT', service_sum['port'][0])
    # 日志配置
    setup_section(file_name, 'LOGSVRD', 'ip', x['logsvrd'][0]['lip'])
    setup_section(file_name, 'LOGSVRD', 'port', x['logsvrd'][0]['port'][0])
    # key配置
    setup_section(file_name, 'SHM', 'corekey', service_sum['key'][0])
    setup_section(file_name, 'SHM', 'cspipekey', service_sum['key'][1])
    setup_section(file_name, 'SHM', 'scpipekey', service_sum['key'][2])
    # redis配置
    setup_section(file_name, 'REDIS', 'IP', service_sum['db'][0])
    setup_section(file_name, 'REDIS', 'PORT', service_sum['db'][1])
    setup_section(file_name, 'REDIS', 'SERVERIP', service_sum['db'][1])
    setup_section(file_name, 'REDIS', 'SERVERPORT', service_sum['db'][1])

    # 路由配置
    change_service_proxy_cfg(file_name)

def chage_service_cfg(service_name, service_sum):
    '''
    整合/调用服务配置项修改
    '''
    # 路由设置
    if service_name == 'proxysvrd':
        file_name = '%s/%s/svr/%s.%s/deploy/%s.cfg' %(temp_dir, service_sum['lip'], service_name, service_sum['num'], service_name)
        change_route_cfg(file_name)
        change_proxy_cfg()
    # 修改配置
    elif service_name == 'logsvrd':
        change_service_logsvrd_cfg(service_name, service_sum)
    elif service_name == 'httpsvrd':
        change_service_httpsvrd_cfg(service_name, service_sum)
    elif service_name == 'base_dbsvrd':
        change_service_base_dbsvrd_cfg(service_name, service_sum)
    elif service_name == 'auth_dbsvrd':
        change_service_auth_dbsvrd_cfg(service_name, service_sum)
    elif service_name == 'authsvrd':
        change_service_authsvrd_cfg(service_name, service_sum)
    elif service_name == 'thirdsvrd':
        change_service_thirdsvrd_cfg(service_name, service_sum)
    elif service_name == 'shopsvrd':
		change_service_public_cfg(service_name, service_sum)
    else:
        change_service_public_cfg(service_name, service_sum)

def change_tcpsvrd_cfg(service_name, service_sum, tcp_dir_path):
    '''
    修改tcp服务
    '''
    tcp_cfg = 'tcpsvrd_%s' %service_name
    # 没有配置文件则复制模板
    try:
        if not os.path.exists('%s/deploy/%s.cfg' %(tcp_dir_path,tcp_cfg)):
			if not os.path.exists('%s/deploy/tcpsvrd_gamesvrd.cfg' %tcp_dir_path): return
			else: shutil.copyfile('%s/deploy/tcpsvrd_gamesvrd.cfg' %tcp_dir_path, '%s/deploy/%s.cfg' %(tcp_dir_path,tcp_cfg))
    except IOError,e:
        logger_user.debug(e)
        return
    # 配置端口
    setup_section('%s/deploy/%s.cfg' %(tcp_dir_path,tcp_cfg), 'tcpsvrd', 'ListenPortNum', len(service_sum['port']))
    for i in range(len(service_sum['port'])):
        port_num = int(i) + 1
        setup_section('%s/deploy/%s.cfg' %(tcp_dir_path,tcp_cfg), 'tcpsvrd', 'ListenPort%s' %port_num, service_sum['port'][i])
    # 配置key
    setup_section('%s/deploy/%s.cfg' %(tcp_dir_path,tcp_cfg), 'shm', 'corekey', service_sum['key'][0])
    setup_section('%s/deploy/%s.cfg' %(tcp_dir_path,tcp_cfg), 'shm', 'cspipekey', service_sum['key'][1])
    setup_section('%s/deploy/%s.cfg' %(tcp_dir_path,tcp_cfg), 'shm', 'scpipekey', service_sum['key'][2])
    # 配置输出地址
    setup_section('%s/deploy/%s.cfg' %(tcp_dir_path,tcp_cfg), 'output', 'word', tcp_cfg)
    # 修改启动脚本
    with open('%s/bin/start_tcpsvrd.sh' %tcp_dir_path, 'w+') as f:
        f.write('./%s.tcpsvrd.%s ../deploy/%s.cfg \n' %(service_name.replace('svrd',''), service_sum['num'], tcp_cfg))
        f.close()

def change_modTxt():
    print '写入mod.txt配置'
    for service_name, service_opts in x.items():
        for opt in range(len(service_opts)):
            modFile = '%s/%s/svr/mod.txt' %(temp_dir, service_opts[opt]['lip'])
            if service_opts[opt]['tcp'] == 'True':
                startName = '%s.%d\n%s.tcpsvrd.%d start_tcpsvrd.sh' %(service_name, service_opts[opt]['num'], service_name[:-4], service_opts[opt]['num'])
            elif service_opts[opt]['tcp'] == 'False':
                startName = '%s.%d' %(service_name, service_opts[opt]['num'])
            __change_mod_text(modFile, startName)

def __change_mod_text(modFile, startName):
    logger_user.debug('正在写入 %s 到 %s' %(startName, modFile))
    try:
        with open(modFile, 'a+') as f:
            f.write('%s\n' %startName)
    except Exception,e:
        __err_exit_show_msg('写入失败: %s' %e)

def get_pathFile_list(rootdir):
    '''
    获取目录下面所有的文件(包括子目录以及其中包含的文件).
    '''
    try:
        file_list = '../backing/' + rootdir.split('/')[-1]
        with open(file_list,'wa+') as f:
            for (dirpath, dirnames, filenames) in os.walk(rootdir):
                for filename in filenames:
                    __file = os.path.join(dirpath, filename).split('/')[6:]
                    File = '/'.join(__file)
                    f.write(File + '\n')
            f.close()
    except IOError,e:
        __err_exit_show_msg('创建文件失败: ' + file_list)

def rsync_remote(ip):
    '''
    调用bash执行rsync,远程复制
    '''
    cmd     = '/usr/bin/rsync'
    options = '-azP'
    src     = '%s/' %ip
    dest    = '%s::svn' %ip
    port    = '--port=1888'
    try:
        logger_user.debug('发布文件到 %s 服务器' %ip)
        ps = subprocess.Popen([cmd, options, port, src, dest], stdout=open(r'/dev/null','w'))
        ps.wait()
        logger_user.info('%s 发布完成' %ip)
    except Exception,e:
        print e
        __err_exit_show_msg('发布到 %s 失败: %s' %(ip,e))

def connect_to_srv(cmd, ip, port, keyfile, avge1='', avge2=''):
    '''
    连接远端服务器执行命令,打印返回值
    '''
    user = 'root'
    ssh = paramiko.SSHClient()
    key = paramiko.RSAKey.from_private_key_file(keyfile)
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, port, user, key)
    print ">>> %s --- shell | %s %s" %(ip, avge1, avge2)
    stdin,stdout,stderr = ssh.exec_command('%s %s %s' %(cmd, avge1, avge2))
    print stdout.read(), stderr.read()
    ssh.close()

def connect_upload(ip, port, keyfile, localfile, remotefile):
    '''
    连接远端服务器上传文件,打印返回值
    '''
    user = 'root'
    up = paramiko.Transport((ip, port))
    key = paramiko.RSAKey.from_private_key_file(keyfile)
    up.connect(username=user, pkey=key)
    print ">>> %s --- upload | %s %s" %(ip, localfile, remotefile)
    sftp = paramiko.SFTPClient.from_transport(up)
    sftp.put(localfile, remotefile)
    up.close()

def copy_all_file():
    '''
    复制通用配置
    '''
    all_ip = [ var[i]['lip'] for k,var in x.items() for i in range(len(var))]
    all_ip = sorted(set(all_ip))
    for i in range(len(all_ip)):
        rsync_local(packagedir, '%s/%s' %(temp_dir, all_ip[i]), 'all')

def copy_service_file():
    '''
    复制独立配置
    '''
    global k, v, i
    for k,v in x.items():
        for i in range(len(v)):
            src = '%s/svr/%s/' %(packagedir, k)
            dest = '%s/%s/svr/%s.%s' %(temp_dir, v[i]['lip'], k, v[i]['num'])
            # 复制服务文件
            rsync_local(src, dest, 'srv')
            # 修改配置
            chage_service_cfg(k, v[i])
            # tcp配置
            if v[i]['tcp'] == 'True':
                src = '%s/svr/tcpsvrd/' %packagedir
                dest = '%s/%s/svr/%s.tcpsvrd.%s' %(temp_dir, v[i]['lip'], k[:-4], v[i]['num'])
                rsync_local(src, dest, 'tcp')
                change_tcpsvrd_cfg(k, v[i], dest)

def backup_remote_file(workDir):
    '''
    备份远端关联主机
    '''
    global threads
    threads = []
    print '备份远程主机文件'
    os.chdir(scriptDir)
    for ip in range(len(workDir)):
        logger_user.debug('传输发布文件列表到 %s 主机' %workDir[ip])
        get_pathFile_list('%s/%s' %(temp_dir, workDir[ip]))
        localfile = '../backing/' + workDir[ip]
        remotefile = '/tmp/XimiPushBackingList.txt'
        Thread = 'myThreadUpload%d' %ip
        Thread = myThreadUpload(ip + 1, workDir[ip], ssh_port, keyfile, localfile, remotefile)
        Thread.start()
        threads.append(Thread)
    for t in threads:
        t.join()
    ssh_cmd = 'rm -rf /alidata1/backing/* ; rsync -avP --files-from=/tmp/XimiPushBackingList.txt /svndata/ /alidata1/backing/ >/dev/null'
    for ip in range(len(workDir)):
        logger_user.debug('备份 %s 主机' %workDir[ip])
        Thread = 'myThreadSSH%d' %ip
        Thread = myThreadSSH(ip + 1, ssh_cmd, workDir[ip], ssh_port, keyfile)
        Thread.start()
        threads.append(Thread)
    with open('../backing/backup.list', 'w+') as f:
        for ip in range(len(workDir)):
            f.write(workDir[ip] + '\n')
        f.close()
    for t in threads:
        t.join()

def sync_to_remote_file(workDir):
    '''
    传输文件到远端主机
    '''
    global threads
    threads = []
    print '推送文件到服务器'
    # 切换工作目录
    os.chdir(temp_dir)
    for var in range(len(workDir)):
        Thread = 'myThreadSync%d' %var
        Thread = myThreadSync(var + 1, workDir[var])
        Thread.start()
        threads.append(Thread)
    for t in threads:
        t.join()

def change_service(Type):
    '''
    编辑需要操作的服务
    '''
    ssh_cmd = '/svndata/svr/ServerAdm.sh'
    global threads
    threads = []
    if not s[Type]: return
    for i in range(len(s[Type])):
        if s[Type][i] == 'all':
            print '暂不支持对所有服务执行%s操作' %Type
        if '.' in s[Type][i]:
            try:
                _srv = s[Type][i].split('.')
                ip = x[_srv[0]][int(_srv[1])-1]['lip']
                service_name = s[Type][i]
                Thread = 'myThreadSSH%d' %i
                Thread = myThreadSSH(i + 1, ssh_cmd, ip, ssh_port, keyfile, Type, service_name)
                Thread.start()
                threads.append(Thread)
            except IndexError,e:
                __err_exit_show_msg('未找到: ' + s[Type][i])
        else:
            _srv = x[s[Type][i]]
            for n in range(len(_srv)):
                service_name = '%s.%d' %(s[Type][i],  _srv[n]['num'])
                ip = _srv[n]['lip']
                Thread = 'myThreadSSH%d' %i
                Thread = myThreadSSH(i + 1, ssh_cmd, ip, ssh_port, keyfile, Type, service_name)
                Thread.start()
                threads.append(Thread)
    for t in threads:
        t.join()

class myThreadSync(threading.Thread):
    '''
    多线程执行传输
    '''
    def __init__(self, threadID, ip):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ip = ip
    def run(self):
        rsync_remote(self.ip)

class myThreadSSH(threading.Thread):
    '''
    多线程执行命令
    '''
    def __init__(self, threadID, ssh_cmd, ip, ssh_port, keyfile, avge1='', avge2=''):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ssh_cmd = ssh_cmd
        self.ip = ip
        self.ssh_port = ssh_port
        self.keyfile = keyfile
        self.avge1 = avge1
        self.avge2 = avge2
    def run(self):
        connect_to_srv(self.ssh_cmd, self.ip, self.ssh_port, self.keyfile, self.avge1, self.avge2)

class myThreadUpload(threading.Thread):
    '''
    多线程执行上传
    '''
    def __init__(self, threadID, ip, ssh_port, keyfile, localfile, remotefile):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ip = ip
        self.ssh_port = ssh_port
        self.keyfile = keyfile
        self.localfile = localfile
        self.remotefile = remotefile
    def run(self):
        connect_upload(self.ip, self.ssh_port, self.keyfile, self.localfile, self.remotefile)

# ----------------------------------------

if __name__ == '__main__':
    # 加载日志配置
    logging.config.fileConfig("../conf/log.cfg")
    logger_user = logging.getLogger("user")
    # 目录
    scriptDir = os.getcwd()
    packagedir = '/xyj/ximi-push/tex-tw/pkg'
    temp_dir = '/xyj/ximi-push/tex-tw/workDir'
    # ssh
    ssh_port = 13021
    keyfile = '/root/.ssh/id_rsa'
    # 加载配置文件
    x = load_yaml('../conf/tex-push.yml')
    s = load_yaml('../conf/tex-service.yml')
    # 获取服务目录列表
    get_service_dir_list()
    # 删除历史临时目录
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.system('rm -f ../backing/*')
    # 对so文件授权
    chmod_file(packagedir, '.so')
    # 修改db.env
    change_dbenv(__select_file(packagedir, 'db.env'), 'dbaroot', 'ximiRlave20141751')
    print '准备发布文件'
    if not os.listdir(packagedir):
        __err_exit_show_msg('程序目录为空或者不存在')
    # 复制通用文件
    copy_all_file()
    # 配置/复制服务文件
    copy_service_file()
    # 配置mod.txt
    change_modTxt()
    # 备份远程主机文件
    backup_remote_file(get_dir_list(temp_dir))
    # 传输文件到远程主机
    sync_to_remote_file(get_dir_list(temp_dir))
#   # 关闭zabbix报警
#   change_zabbix_report(1, '关闭')
#   # 重启服务
#   print '重启/重载服务'
#   change_service('reload')
#   change_service('restart')
#   # 开启zabbix报警
#   change_zabbix_report(0, '开启')
