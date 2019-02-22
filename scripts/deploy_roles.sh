#!/bin/bash

## Command Line Args ##
# The path to the ansible role zip file
role_zip_path=$1

if [[ -z "${role_zip_path}" ]]; then
    echo "ERROR: you must provide a the role archive path as an arg"
    exit 1
fi

# unzip the role archive
sudo unzip ${role_zip_path} -d /etc/ansible/roles

exit $?
