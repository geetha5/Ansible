##
# common.py
# Written by Diego Gutierrez <diego.gutierrez@wexinc.com>
# This is a common library for functions that will need to
# be used by the majority of the AWS related scripts
##

import logging
import urllib2
import boto3
from botocore.exceptions import ClientError
import re

logger = logging.getLogger(__name__)
metadata_url_base = 'http://169.254.169.254/latest/meta-data/'

## Instance Metadata ##

##
# get_instance_id()
# Gets the instance id from the ec2 instance metadata
##
def get_instance_id():
    return urllib2.urlopen( metadata_url_base + 'instance-id').read()

##
# get_instance_region()
# Gets the instance regipn from the ec2 instance metadata
##
def get_instance_region():
    availability_zone = urllib2.urlopen(metadata_url_base + 'placement/availability-zone').read()
    return re.match(r"(^[a-z]*-[a-z]*-\d).*$", availability_zone).group(1)

##
# get_instance_name_tag(region, instance_id)
# This will get the name tag for the instance to be used when creating alarms
##
def get_instance_name_tag(region, instance_id):

    ec2_client = boto3.client('ec2', region_name=region)

    try:
        instance_metadata = ec2_client.describe_instances(
            InstanceIds=[instance_id]
        )
    except ClientError as e:
        logger.fatal('could not get instance metadata, %s', e)

    tags = instance_metadata['Reservations'][0]['Instances'][0]['Tags']

    for tag in tags:
        logger.debug('instance tag %s is %s', tag['Key'], tag['Value'])
        if tag['Key'] == 'Name':
            return tag['Value']
