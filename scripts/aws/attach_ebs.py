##
# mount_ebs.py
# Written by Diego Gutierrez <diego.gutierrez@wexinc.com>
# This is a script to mount a secondary ebs volume to the Ec2 instance
# that is running this script. This will check the status of the ebs volume
# and wait till its available before mounting it, making it suitable for use in
# autoscaling groups of one to mount a static ebs volume upon machine creation.
##

import argparse
import boto3
import logging
import sys
from time import sleep
import urllib2
import re

# global vars #
logger = logging.getLogger('ebs_attach')
log_file = '/var/log/ebs_attach.log'
metadata_url_base = 'http://169.254.169.254/latest/meta-data/'

##
# get_instance_id()
# gets the instance id from the ec2 instance metadata
##
def get_instance_id():
    return urllib2.urlopen( metadata_url_base + 'instance-id').read()

##
# get_instance_region()
# gets the instance regipn from the ec2 instance metadata
##
def get_instance_region():
    availability_zone = urllib2.urlopen(metadata_url_base + 'placement/availability-zone').read()
    return re.match(r"(^[a-z]*-[a-z]*-\d).*$", availability_zone).group(1)

##
# wait_for_available_volume(vol_id)
# waits for the volume to be available in case it is still connected to an old instance
##
def wait_for_volume(vol_id, desired_state):

    timer = 0
    volume_state = ec2_client.describe_volumes(
        VolumeIds = [
            vol_id
        ]
    )['Volumes'][0]['State']

    while volume_state != desired_state:
        sleep(10)
        timer += 10

        volume_state = ec2_client.describe_volumes(
            VolumeIds = [
                vol_id
            ]
        )['Volumes'][0]['State']

        logger.debug('EBS volume status is %s', volume_state)

    logger.info('Total wait time in %d seconds', timer)

    return 'SUCCESS'




# MAIN()
if __name__== "__main__":

    # parse command line args
    arg_parser = argparse.ArgumentParser(description='Wait for a EBS Volume to be available and then mount')
    arg_parser.add_argument('--vol-id', help='The id of the volume to watch and mount', required=True, dest='vol_id')
    arg_parser.add_argument('--device', help='The device mount (default: /dev/xvdb)', default='/dev/xvdb', dest='device')

    prog_args = arg_parser.parse_args()


    # set up logging
    fh = logging.FileHandler(log_file)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.setLevel(logging.DEBUG)

    logger.info('Starting EBS watch mounter')

    logger.debug('vol_id: %s', prog_args.vol_id)
    logger.debug('device: %s', prog_args.device)


    # get instance information from metadata
    instance_id = get_instance_id()
    logger.debug('instance_id: %s', instance_id)
    instance_region = get_instance_region()
    logger.debug('aws region: %s', instance_region)

    # create boto3 client for ec2
    ec2_client = boto3.client('ec2', region_name=instance_region)

    detach_status = wait_for_volume(prog_args.vol_id, 'available')

    if detach_status != 'SUCCESS':
        logger.error('The EBS volume %s failed to detach', prog_args.vol_id)
        sys.exit(1)

    ec2_client.attach_volume(
        Device=prog_args.device,
        VolumeId=prog_args.vol_id,
        InstanceId=instance_id
    )

    attach_status = wait_for_volume(prog_args.vol_id, 'in-use')

    if attach_status != 'SUCCESS':
        logger.error('The EBS volume %s failed to attach', prog_args.vol_id)
        sys.exit(1)

    sleep(30)

    sys.exit(0)