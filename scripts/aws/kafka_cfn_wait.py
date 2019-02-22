##
# kafka_cfn_wait.py
# Written by Diego Gutierrez <diego.gutierrez@wexinc.com>
# This will watch the output from the kafka-health-check
# and will wait for the kafka broker to by in sync before
# sending a signal to cloudformation that the instance is
# healthy
##

import argparse
import boto3
from botocore.exceptions import ClientError
import logging
import sys
import json
import re
from time import sleep
import urllib2
from urllib2 import HTTPError

# global vars #
logger = logging.getLogger('kafka_cfn_wait')
log_file = '/var/log/kafka_cfn_wait.log'
metadata_url_base = 'http://169.254.169.254/latest/meta-data/'
kafka_health_check_url_base = 'http://localhost:8000/'

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
# get_broker_health_status()
# gets the broker health status from a lookup from kafka-health-check and returns a health/unhealthy
# and the status that is output from the health check
##
def get_broker_health_status():

    try:
        response = json.load(urllib2.urlopen(kafka_health_check_url_base))
        status = response['status']

        if status == 'sync':
            return 'healthy', status
        else:
            return 'unhealthy', status

    except HTTPError:
        return 'unhealthy', 'nook'


# MAIN()
if __name__=="__main__":

    # parse command line args
    arg_parser = argparse.ArgumentParser(description='Wait for zookeeper to be stable before sending cfn signal')
    arg_parser.add_argument('-e', '--environment', help='The environment that being deployed to', dest='environment')
    arg_parser.add_argument('-s', '--stack-name', help='The stack name the instance will report to', required=True,
                            dest='stack_name')
    arg_parser.add_argument('--resource-id', help='The logical resource id that the instance belongs to in the stack',
                            required=True, dest='resource_id')
    arg_parser.add_argument('--test-mode', help='A flag to set test mode where no cfn signal will be sent', action='store_true',
                            dest='test_mode', default=False)

    prog_args = arg_parser.parse_args()

    # set up logging
    fh = logging.FileHandler(log_file)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)

    if prog_args.environment == 'prod':
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)

    logger.info('Starting kafka_cfn_wait')

    logger.debug('environment: %s', prog_args.environment)
    logger.debug('stack_name: %s', prog_args.stack_name)
    logger.debug('resource_id: %s', prog_args.resource_id)
    logger.debug('test_mode: %r', prog_args.test_mode)

    # get instance information from metadata
    instance_id = get_instance_id()
    logger.debug('instance_id: %s', instance_id)
    instance_region = get_instance_region()
    logger.debug('aws region: %s', instance_region)

    # create boto3 client for cloudformation
    cfn_client = boto3.client('cloudformation', region_name=instance_region)

    broker_health, broker_status = get_broker_health_status()
    logger.info('broker health: %s, status: %s', broker_health, broker_status)
    timer = 0

    while broker_health != 'healthy':
        sleep(10)
        timer += 10

        broker_health, broker_status = get_broker_health_status()
        logger.info('broker health: %s, status: %s', broker_health, broker_status)

    logger.info('Total wait time is %d seconds', timer)

    # send cfn response only if we are not testing
    if not prog_args.test_mode:

        logger.info('Sending response %s to cfn stack %s and resource id %s', 'SUCCESS', prog_args.stack_name, prog_args.resource_id)
        try:
            response = cfn_client.signal_resource(
                StackName=prog_args.stack_name,
                LogicalResourceId=prog_args.resource_id,
                UniqueId=instance_id,
                Status='SUCCESS'
            )
            logger.info('cfn signal to stack %s is successful', prog_args.stack_name)
        except ClientError as e:
            logger.fatal('could not send cfn signal to stack %s, reason: %s', prog_args.stack_name, e)

    sys.exit(0)