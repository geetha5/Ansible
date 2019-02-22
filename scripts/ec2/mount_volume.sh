#!/bin/bash

##
# written by Diego Gutierrez <diego.gutierrez@wexinc.com>
# This will mount an attached ebs volume and will create
# a file system if it doesn't already exist
##

# CLI Args
device=$1
mountPoint=$2

# create a file system if the drive is blank
if [[ $( file -s ${device} | grep "${device}: data" ) ]]; then
    echo "No file system present, creating"
    mkfs -t ext4 ${device}

    if [[ $? -ne 0 ]]; then
        echo "Creating filesystem failed"
        exit 1
    fi
else
    echo "Drive is already formatted"
fi

# mount drive
mount ${device} ${mountPoint}

if [[ $? -ne 0 ]]; then
    echo "Failed to mount drive"
    exit 1
fi

exit 0
