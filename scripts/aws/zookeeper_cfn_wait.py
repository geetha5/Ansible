##
# zookeeper_cfn_wait.py
# Written by Diego Gutierrez <diego.gutierrez@wexinc.com>
# This will wait till a zookeeper server is up and joined to the
# cluster as a leader or follower before sending a CFN signal to the autoscaling
# group that the server provisioning is complete
##

import argparse
import logging
import sys
from time import sleep
import urllib2
import boto3
from botocore.exceptions import ClientError
import re
from subprocess import Popen,PIPE,STDOUT

# global vars #
logger = logging.getLogger('zookeeper_cfn_wait')
log_file = '/var/log/zookeeper_cfn_wait.log'
accepted_modes = ['standalone', 'leader', 'follower']
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
# get_zookeeper_health_status()
# checks the zookeeper status and returns a healthy/unhealthy and the mode
##
def get_zookeeper_health_status():

    out = Popen(["/opt/zookeeper-active/bin/zkServer.sh", "status"],stderr=STDOUT,stdout=PIPE)
    status_line_out = out.communicate()[0]
    return_code = out.returncode

    if return_code != 0:
        logger.info('zookeeper service is not running')
        return 'unhealthy', 'N/A'
    else:
        mode_match = re.search(r'Mode: (\w+)', status_line_out)
        mode = mode_match.group(1)

        if mode not in accepted_modes:
            return 'unhealthy', mode
        else:
            return 'healthy', mode

# MAIN()
if __name__ == "__main__":

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

    logger.info('Starting zookeeper_cfn_wait')

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

    zookeeper_status, mode = get_zookeeper_health_status()
    logger.info('zookeeper status: %s, mode: %s', zookeeper_status, mode)
    timer = 0

    while zookeeper_status != 'healthy':
        sleep(10)
        timer += 10

        zookeeper_status, mode = get_zookeeper_health_status()
        logger.info('Zookeeper status: %s, Mode: %s', zookeeper_status, mode)

    logger.info('total wait time is %d seconds', timer)

    # send cfn response only if we are not testing
    if not prog_args.test_mode:

        logger.info('sending response %s to cfn stack: %s and resource id: %s', 'SUCCESS', prog_args.stack_name, prog_args.resource_id)
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