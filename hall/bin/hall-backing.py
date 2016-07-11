#!/usr/bin/env python
# -*- coding: utf-8 -*-

import yaml
import subprocess, paramiko
import logging, logging.config
import sys, os, stat, shutil, time
import threading


def load_yaml(config_file_name):
    '''
    加载配置文件
    '''
    f = open(config_file_name)
    x = yaml.load(f)
    f.close()
    return x

class Backing(object):
    '''
    版本回滚
    '''
    def __init__(self):
        logger_user.debug('初始化Backing类')
        self.service_host = {}
        self.threads = []

    def __err_exit_show_msg(self, msg):
        '''
        发生错误的时候显示相关错误信息并且退出程序
        '''
        logger_user.error(msg)
        sys.exit()

    def ssh(self, cmd, host, arg1='', arg2=''):
        '''
        远程执行命令
        '''
        user='root'
        port=22
        keyfile='/root/.ssh/id_rsa'
        ssh = paramiko.SSHClient()
        key = paramiko.RSAKey.from_private_key_file(keyfile)
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port, user, key)
        try:
            print ">>> %s --- shell | %s %s" %(host, arg1, arg2)
            logger_user.debug('在 %s 执行: %s %s %s' %(host, cmd, arg1, arg2))
            stdin,stdout,stderr = ssh.exec_command('%s %s %s' %(cmd, arg1, arg2))
            print stdout.read(), stderr.read()
            ssh.close()
        except SSHException,e:
            self.__err_exit_show_msg('无法连接目标主机: '+e)

    def myThread(self, tnum, cmd, host, arg1='', arg2=''):
        logger_user.debug('添加 %s 线程到线程池' %tnum)
        tnum = threading.Thread(target=self.ssh, args=(cmd, host, arg1, arg2))
        self.threads.append(tnum)

    def start(self):
        logger_user.debug('执行线程池里的线程')
        for t in self.threads:
            t.setDaemon(True)
            t.start()
        t.join()
        self.threads = []

    def getBackingHost(self, list_file):
        '''
        获取需要回滚主机列表
        '''
        with open(list_file, 'r') as f:
            __backing_host = f.readlines()
        for backing_host in __backing_host:
            logger_user.debug('添加回滚需要的源目录和目的目录到字典')
            self.service_host.setdefault(backing_host.replace('\n',''), []) \
                .append({'src': '/alidata1/backing/', 'dest': '/svndata'})

    def changeService(self, services_options, handle_service_names):
        '''
        对服务执行重启/重载操作
        '''
        for handle_type in [ 'reload', 'restart' ]:
            if not handle_service_names[handle_type]: return
            try:
                logger_user.debug('添加需要操作的服务到字典')
                for handle_service_name in handle_service_names[handle_type]:
                    if handle_service_name == 'all':
                        print '暂不支持对所有服务执行%s操作' %Type
                    if '.' in handle_service_name:
                        _srv = handle_service_name.split('.')
                        host = services_options[_srv[0]][int(_srv[1])-1]['oip']
                        self.service_host.setdefault(host, []) \
                            .append({'type': handle_type, 'srv': handle_service_name})
                    else:
                        options = services_options[handle_service_name]
                        for n in range(len(options)):
                            service_name = '%s.%d' %(handle_service_name, options[n]['num'])
                            host = options[n]['oip']
                            self.service_host.setdefault(host, []) \
                                .append({'type': handle_type, 'srv': service_name})
            except Exception,e:
                self.__err_exit_show_msg('未找到: ' + handle_service_name)

    def run(self):
        logger_user.info('-------------------- | 回滚文件 | --------------------')
        for host, options in self.service_host.items():
            for option in options:
                if option.get('src') and option.get('dest'):
                    tnum = 'rsync'
                    cmd = 'rsync -avP /alidata1/backing/ /svndata'
                    self.myThread(tnum, cmd, host, '>', '/dev/null')
        self.start()
        logger_user.info('-------------------- | 操作服务 | --------------------')
        for host, options in self.service_host.items():
            for option in options:
                if option.get('srv') and option.get('type'):
                    tnum = 'srv'
                    cmd = '/svndata/svr/ServerAdm.sh'
                    self.myThread(tnum, cmd, host, option['type'], option['srv'])
        self.start()


# ----------------------------

if __name__ == '__main__':
    # 加载日志配置
    logging.config.fileConfig("../conf/log.cfg")
    logger_user = logging.getLogger("user")
    # 加载服务列表
    services_options = load_yaml('../conf/ddz-push.yml')
    handle_service_names = load_yaml('../conf/ddz-service.yml')
    # 加载回滚主机列表
    backing_host_list_file = '../backing/backup.list'
    # 开始回滚
    Backing1 = Backing()
    Backing1.changeService(services_options, handle_service_names)
    Backing1.getBackingHost(backing_host_list_file)
    Backing1.run()
