##
# cfn_lb_wait.py
# Written by Diego Gutierrez <diego.gutierrez@wexinc.com>
# This is meant to run in place of just a plain CFN signal on
# machines that are connected to a load balancer. This will
# monitor the status in the load balancer and only send the
# cfn signal when the machine shows as healthy in the load
# balancer
##

import argparse
import boto3
import logging
import sys
from time import sleep
import urllib2
import re

# global vars #
supported_elb_versions = ['v2']
logger = logging.getLogger('cfn_lb_wait')
log_file = '/var/log/cfn_lb_wait.log'
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
# wait_v2(target_group_arn, instance_port, instance_id)
# This will wait and check for the health of an instance in a target group based
# load balancer
##
def wait_v2(target_group_arn, instance_port, instance_id):

    instance_state = 'unhealthy'
    timer = 0

    while instance_state != 'healthy':
        sleep(10)
        timer += 10

        response = elb_client.describe_target_health(
            TargetGroupArn=target_group_arn,
            Targets=[
                {
                    'Id': instance_id,
                    'Port': int(instance_port)
                }
            ]
        )


        instance_state = response['TargetHealthDescriptions'][0]['TargetHealth']['State']
        logger.debug('Instance state is %s', instance_state)

    logger.info('Total wait time is %d seconds', timer)

    return 'SUCCESS'

# MAIN()
if __name__== "__main__":

    # parse command line args
    arg_parser = argparse.ArgumentParser(description='Wait for LB health to send CFN instance signal')
    arg_parser.add_argument('--lb-version', help='The version of load balancer (ex: v1 or v2)', required=True, dest='lb_version')
    arg_parser.add_argument('--lb-name', help='The name of the load blancer (if classic elb)', dest='lb_name')
    arg_parser.add_argument('--target-group-arn',
                            help='The arn of the target group for target group based load balancers',
                            dest='target_group_arn')
    arg_parser.add_argument('--instance-port',
                            help='The port the instance is listening on for target group based load balancers',
                            dest='instance_port')
    arg_parser.add_argument('-e', '--environment', help='The environment that being deployed to', dest='environment')
    arg_parser.add_argument('-s', '--stack-name', help='The stack name the instance will report to', required=True,
                            dest='stack_name')
    arg_parser.add_argument('--resource-id', help='The logical resource id that the instance belongs to in the stack',
                            required=True, dest='resource_id')


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

    logger.info('Starting cfn_lb_wait')

    logger.debug('lb_version: %s', prog_args.lb_version)
    logger.debug('lb_name: %s', prog_args.lb_name)
    logger.debug('target_group_arn: %s', prog_args.target_group_arn)
    logger.debug('instance_port: %s', prog_args.instance_port)
    logger.debug('environment: %s', prog_args.environment)
    logger.debug('stack_name: %s', prog_args.stack_name)
    logger.debug('resource_id: %s', prog_args.resource_id)

    # validate args
    if prog_args.lb_version not in supported_elb_versions:
        logger.fatal('load balancer type is not supported')
        sys.exit(1)

    if (prog_args.target_group_arn is None) or (prog_args.instance_port is None):
        logger.fatal('target-group-arn or instance-port is not passed and are required')
        sys.exit(2)


    # get instance information from metadata
    instance_id = get_instance_id()
    logger.debug('instance_id: %s', instance_id)
    instance_region = get_instance_region()
    logger.debug('aws region: %s', instance_region)

    # create boto3 client for cloudformation
    cfn_client = boto3.client('cloudformation', region_name=instance_region)

    # create ELB client and run the wait function
    elb_client = boto3.client('elbv2', region_name=instance_region)
    logger.info('Starting the elb watcher for v2 load balancer')
    cfn_status = wait_v2(
        prog_args.target_group_arn,
        prog_args.instance_port,
        instance_id
    )

    logger.info('Sending response %s to cfn stack %s and resource id %s', cfn_status, prog_args.stack_name, prog_args.resource_id)
    response = cfn_client.signal_resource(
        StackName=prog_args.stack_name,
        LogicalResourceId=prog_args.resource_id,
        UniqueId=instance_id,
        Status=cfn_status
    )

    sys.exit(0)