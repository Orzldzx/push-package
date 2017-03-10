#!/bin/bash

src_path="/template/slots-usa/branch_slots_20160123"
dst_path="/tmp/slots_tmp"
pkg_path="/tmp/slots_package"

_pkg_name="slots_$(date +%Y%m%d)"
pkg_num=1

[ -d $dst_path ] && { echo "目的路径 $dst_path: 已存在"; exit 1; }
[ -d $pkg_path ] || { echo "mkdir $pkg_path"; mkdir -p $pkg_path; }

while [ -f "${pkg_path}/${_pkg_name}_${pkg_num}.tgz" ]; do
    pkg_num=$(expr $pkg_num + 1)
done

pkg_name="${_pkg_name}_${pkg_num}.tgz"

######

# 复制
echo "1. 复制项目目录"
/bin/cp -rp $src_path $dst_path

# 删源码
echo "2. 删除 源码文件"
find $dst_path -name 'src' -type d -exec rm -rf {} \; 2> /dev/null
find $dst_path -name '.svn' -type d -exec rm -rf {} \; 2> /dev/null
find $dst_path -name '*.go' -type f -exec rm -f {} \; 2> /dev/null
echo "3. 删除 日志文件"
/bin/rm -rf ${dst_path}/service/log/*
/bin/rm -rf ${dst_path}/games/log/*

# 打包
cd $dst_path
echo "4. 打包为: ${pkg_path}/${pkg_name}"
/bin/tar -acf ${pkg_path}/${pkg_name} *

# 清理
/bin/rm -rf $dst_path
if [ $(ls -l $pkg_path|wc -l) -gt 7 ]; then
    echo "5. 清理软件包存放目录"
    echo "    $pkg_path 目录存储软件包数量大于 7 启动清理!"
    read -p "    准备删除 $pkg_path 目录下除当天生成的软件包以外的其他所有软件包,请确认  (default: no [y/n]): " yn
    yn=${yn:=n}
    case $yn in
        y|Y) cd $pkg_path
             if [ $? -eq 0 ]; then
                 /bin/rm $(ls|grep -v $_pkg_name)
                 echo "    清理成功"
             else
                 echo "    清理失败"
             fi ;;
        n|N) echo "    暂不清理" ;;
        *) echo "    pass" ;;
    esac
fi

# 推CDN
cd /tmp
echo "6. 推送 $pkg_name 至 CDN"
read -p "    是否需要推送软件包至 CDN  (default: no [y/n]): " yn2
yn2=${yn2:=n}
echo "${pkg_path}/${pkg_name}"
case $yn2 in
    y|Y)  pgrep rsync &>/dev/null
          if [ $? -ne 0 ]; then
              /usr/bin/rsync --daemon
              /usr/bin/rsync --port=1888 --bwlimit=2000 -azP ${pkg_path}/${pkg_name} slots-push.ximigame.com::slots-push
          else
              /usr/bin/rsync --port=1888 --bwlimit=2000 -azP ${pkg_path}/${pkg_name} slots-push.ximigame.com::slots-push
          fi ;;
    n|N)  echo -n '' ;;
    *) echo "    pass" ;;
esac
