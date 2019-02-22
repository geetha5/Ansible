##
# instance_cloudwatch_alarms.py
# Written by Diego Gutierrez <diego.gutierrez@wexinx.com>
# This will take a json config file (from s3) and will
# configure cloudwatch alarms for the instance at start up
##

from lib import common
import json
import sys
import logging
import argparse
import boto3
from botocore.exceptions import ClientError
from exceptions import Exception
from exceptions import ValueError

## Global Vars ##
logger = logging.getLogger('cloudwatch_alarm_setup')
log_file = '/var/log/cloudwatch_instance_alarm.log'
metadata_url_base = 'http://169.254.169.254/latest/meta-data/'
alarm_config_local_loc = '/root/cloudwatch-alarm-config.json'

# config settings
# Default Options for optional settings
alarm_default_settings = {
    'EvaluationPeriods': 1,
    'Statistic': 'Average',
    'Period': 60,
    'Enabled': True
}

# A list of allowed options
required_alarm_options = ['Name', 'MetricName', 'Unit', 'ComparisonOperator', 'Threshold', 'SnsTopics', 'Namespace', 'Dimensions']

# A list of allowed units for the Unit option
allowed_units = ['Seconds', 'Microseconds', 'Bytes', 'Kilobytes', 'Megabytes', 'Gigabytes',
                 'Terabytes', 'Bits', 'Kilobits', 'Megabits', 'Gigabits', 'Terabits', 'Percent',
                 'Count', 'Bytes/Second', 'Kilobytes/Second', 'Megabytes/Second', 'Gigabyte/Second',
                 'Terabytes/Second', 'Bits/Second', 'Kilobits/Second', 'Megabits/Second', 'Gigabits/Second',
                 'Terabits/Second', 'Count/Second', 'None']

# A list of allowed comparison operators
allowed_comparison_operators = ['GreaterThanOrEqualToThreshold', 'GreaterThanThreshold', 'LessThanThreshold',
                                'LessThanOrEqualToThreshold']

# A list of allowed statistics for the Statistic option
allowed_statistics = ['SampleCount', 'Average', 'Sum', 'Minimum', 'Maximum']

# Classes #
# Config - A class to hold the entire configuration
class Config(object):
    def __init__(self):
        self.alarms = []

    def add_alarm(self, alarm):
        self.alarms.append(alarm)

    def __getitem__(self, item):
        return getattr(self, item)

class Alarm(object):
    def __init__(self, name, description, enabled, metric_name, unit, comparison_operator, threshold, period,
                 eval_periods, statistic, sns_topics, namespace, dimensions):
        self.name = name
        self.description = description
        self.enabled = bool(enabled)
        self.metric_name = metric_name
        self.unit = unit
        self.comparison_operator = comparison_operator
        self.threshold = float(threshold)
        self.period = int(period)
        self.eval_periods = int(eval_periods)
        self.statistic = statistic
        self.sns_topics = sns_topics
        self.namespace = namespace
        self.dimensions = dimensions

    @property
    def unit(self):
        return self._unit

    @unit.setter
    def unit(self, unit):
        if unit not in allowed_units:
            raise ValueError('unit type is not allowed')
        self._unit = unit

    @property
    def comparison_operator(self):
        return self._comparison_operator

    @comparison_operator.setter
    def comparison_operator(self, comparison_operator):
        if comparison_operator not in allowed_comparison_operators:
            raise ValueError('comparison operator is not allowed')
        self._comparison_operator = comparison_operator

    @property
    def statistic(self):
        return self._statistic

    @statistic.setter
    def statistic(self, statistic):
        if statistic not in allowed_statistics:
            raise ValueError('statistic value is not allowed')
        self._statistic = statistic

##
# download_alarm_config(bucket, key)
# This will download the alarm config json file from s3
##
def download_alarm_config(bucket, key, region):

    logger.info('downloading alarm config from s3://%s', bucket + '/' + key)

    try:
        s3_client = boto3.client('s3', region_name=region)
        s3_client.download_file(bucket, key, alarm_config_local_loc)
    except ClientError as e:
        logger.fatal('error getting alarm config from s3: %s', e)

##
# load_alarm_config()
# This will load the alarm config into an object and error and type
# check
def load_alarm_config(instance_id, instance_name):

    logger.info('loading alarms from alarm config')

    # try to load the alarm config json file and run some basic checks on the file
    try:
        config_data = json.load(open(alarm_config_local_loc))
    except Exception as e:
        logger.fatal('there is an error loading config, %s', e)

    if 'Alarms' not in config_data.keys():
        logger.fatal('there is no Alarms section in the config')

    if len(config_data['Alarms']) == 0:
        logger.info('there are no alarms in the config')
        sys.exit(1)

    # create the config object and start loading alarms
    config_obj = Config()

    # loop through all the alarms in the config
    for alarm_dict in config_data['Alarms']:

        # Ensure all required options are present
        logger.debug('checking required alarm options')
        for required_opt in required_alarm_options:
            logger.debug('checking required option %s', required_opt)
            if required_opt not in alarm_dict.keys():
                logger.fatal('%s required alarm option missing from config', required_opt)

        # get the required and known to be provided options
        name = alarm_dict['Name']
        metric_name = alarm_dict['MetricName']
        unit = alarm_dict['Unit']
        comparison_operator = alarm_dict['ComparisonOperator']
        threshold = alarm_dict['Threshold']
        sns_topics = alarm_dict['SnsTopics']
        namespace = alarm_dict['Namespace']

        # check for optional options and use either the provided or default value
        if 'Description' not in alarm_dict.keys():
            description = ''
        else:
            description = alarm_dict['Description']

        if 'Period' not in alarm_dict.keys():
            period = alarm_default_settings['Period']
        else:
            period = alarm_dict['Period']

        if 'EvaluationPeriods' not in alarm_dict.keys():
            eval_periods = alarm_default_settings['EvaluationPeriods']
        else:
            eval_periods = alarm_dict['EvaluationPeriods']

        if 'Enabled' not in alarm_dict.keys():
            enabled = alarm_default_settings['Enabled']
        else:
            enabled = alarm_dict['Enabled']

        if 'Statistic' not in alarm_dict.keys():
            statistic = alarm_default_settings['Statistic']
        else:
            statistic = alarm_dict['Statistic']


        # process the demenions
        dimensions = []

        for config_dimension in alarm_dict['Dimensions']:
            # error check the dimensions dictionary
            if ("Name" not in config_dimension.keys()) or ("Value" not in config_dimension.keys()):
                logger.fatal('error on of the dimension dictionaries is malformed missing Name or Value')

            # add the dimension to the list
            if config_dimension['Name'] == 'InstanceId':
                dimensions.append({
                    "Name": "InstanceId",
                    "Value": instance_id
                })

            elif config_dimension['Name'] == 'InstanceName':
                dimensions.append({
                    "Name": "InstanceName",
                    "Value": instance_name
                })

            else:
                dimensions.append({
                    "Name": config_dimension['Name'],
                    "Value": config_dimension['Value']
                })

        logger.debug('alarm name: %s', name)
        logger.debug('alarm description %s', description)
        logger.debug('alarm enabled: %s', str(enabled))
        logger.debug('alarm metric name: %s', metric_name)
        logger.debug('alarm unit type %s', unit)
        logger.debug('alarm comparison operator: %s', comparison_operator)
        logger.debug('alarm threshold: %s', str(threshold))
        logger.debug('alarm period: %s', str(period))
        logger.debug('alarm eval periods: %s', str(eval_periods))
        logger.debug('alarm statistic: %s', statistic)
        logger.debug('alarm sns topics: %s', ','.join(sns_topics))
        logger.debug('alarm namespace: %s', str(namespace))
        logger.debug('alarm dimensions: %s', ','.join(str(dimensions)))

        try:
            logger.info('loading alarm %s', name)
            alarm = Alarm(name, description, enabled, metric_name, unit, comparison_operator, threshold,
                      period, eval_periods, statistic, sns_topics, namespace, dimensions)

            config_obj.add_alarm(alarm)
        except ValueError as e:
            logger.fatal('could not load alarm %s: %s', name, e)

    return config_obj

##
# create_alarms(config, region, instance_id, instance_name)
# This will create all the alarms from the config file
##
def create_alarms(config, region, instance_name):

    cw_client = boto3.client('cloudwatch', region_name=region)

    # loop through the alarms in the configs
    for alarm in config.alarms:

        try:
            logger.info('creating instance cloudwatch alarm %s', alarm.name + '-' + instance_name)
            cw_client.put_metric_alarm(
                AlarmName = alarm.name + '-' + instance_name,
                AlarmDescription = alarm.description + ' ' + instance_name,
                MetricName = alarm.metric_name,
                ComparisonOperator = alarm.comparison_operator,
                EvaluationPeriods = alarm.eval_periods,
                Namespace = alarm.namespace,
                Unit = alarm.unit,
                Threshold = alarm.threshold,
                Period = alarm.period,
                Statistic = alarm.statistic,
                ActionsEnabled = alarm.enabled,
                OKActions = alarm.sns_topics,
                AlarmActions = alarm.sns_topics,
                Dimensions = alarm.dimensions
            )
            logger.info('alarm %s successfully created', alarm.name + '-' + instance_name)
        except ClientError as e:
            logger.fatal('alarm %s creation failed: %s', alarm.name + '-' + instance_name, e)

##
# write_alarm_list_to_s3(region, instance_id, instance_name, output_bucket, output_key_prefix,
# output_bucket_encryption, output_kms_key)
# This will write out the list of alarm names that were created to a
# json file with the instance id as the name. This will be used by
# the cleanup program so it can easily know what alarms need to be
# removed
##
def write_alarm_list_to_s3(region, instance_id, instance_name, output_bucket, output_key_prefix,
                           output_bucket_encryption, output_kms_key):

    alarm_name_list = []

    for alarm in config.alarms:

        logger.debug('writting alarm %s to alarm list', alarm.name + '-' + instance_name)
        alarm_name_list.append(alarm.name + '-' + instance_name)

    alarm_name_dict = {
        "InstanceAlarms": alarm_name_list
    }

    logger.info('writing %d alarms to alarm list file', len(alarm_name_list))
    with open('/tmp/instance_alarms.json', 'w') as f:
        json.dump(alarm_name_dict, f)

    logger.info('uploading alarm name list to s3 s3://%s', output_bucket + '/' + output_key_prefix + '/' + instance_id + '.json')

    s3_client = boto3.client('s3', region_name=region)

    if output_bucket_encryption == 'no':
        try:
            logger.debug('uploading to non encrypted bucket')
            s3_client.upload_file('/tmp/instance_alarms.json', output_bucket, output_key_prefix + '/' + instance_id + '.json')
        except ClientError as e:
            logger.fatal('could not upload alarm list to s3, %s', e)

    elif output_bucket_encryption == 'aws:kms':
        try:
            logger.debug('uploading to kms encrypted bucket with key %s', output_kms_key)
            s3_client.upload_file('/tmp/instance_alarms.json', output_bucket, output_key_prefix + '/' + instance_id + '.json',
                                 ExtraArgs={"ServerSideEncryption": "aws:kms", "SSEKMSKeyId":output_kms_key})
        except ClientError as e:
            logger.fatal('could not upload alarm list to s3, %s', e)
    else:
        logger.fatal('unknown output bucket encryption option %s', output_bucket_encryption)

# MAIN()
if __name__ == '__main__':

    # parse command line args
    arg_parser = argparse.ArgumentParser(description='Create instance cloudwatch alarms')
    arg_parser.add_argument('-e', '--environment', help='The environment the server is in', dest='environment',
                            default='dev')
    arg_parser.add_argument('--config-bucket', help='The s3 bucket for the alarm config', dest='config_bucket')
    arg_parser.add_argument('--config-key', help='The s3 key for the alarm config', dest='config_key')
    arg_parser.add_argument('--output-bucket', help='The s3 bucket for the alarm list output', dest='output_bucket')
    arg_parser.add_argument('--output-key-prefix', help='The s3 key prefix for the alarm output files', dest='output_key_prefix')
    arg_parser.add_argument('--output-bucket-encrypted', help='If the output bucket is encrypted, allowed values are no and aws:kms',
                            choices=['no', 'aws:kms'], dest='output_bucket_encrypted', default='no')
    arg_parser.add_argument('--output-key-id', help='The kms key for the config bucket', dest='output_kms_key_id', default='none')

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

    logger.info('Starting cloudwatch instance alarm setup')

    logger.debug('environment: %s', prog_args.environment)
    logger.debug('config_bucket: %s', prog_args.config_bucket)
    logger.debug('config_key: %s', prog_args.config_key)
    logger.debug('output_bucket: %s', prog_args.output_bucket)
    logger.debug('output_key_prefix: %s', prog_args.output_key_prefix)
    logger.debug('output_bucket_encrypted: %s', prog_args.output_bucket_encrypted)
    logger.debug('output_kms_key_id: %s', prog_args.output_kms_key_id)

    # get instance information from metadata
    instance_id = common.get_instance_id()
    logger.debug('instance_id: %s', instance_id)
    instance_region = common.get_instance_region()
    logger.debug('aws region: %s', instance_region)
    instance_name = common.get_instance_name_tag(instance_region, instance_id)
    logger.info('instance_name: %s', instance_name)

    # error check for missing kms key id using kms s3 encryption
    if prog_args.output_bucket_encrypted == 'aws:kms':
        if prog_args.output_kms_key_id == 'none':
            logger.fatal('missing kms key id using aws:kms for the output bucket')

    download_alarm_config(prog_args.config_bucket, prog_args.config_key, instance_region)

    config = load_alarm_config(instance_id, instance_name)

    create_alarms(config, instance_region, instance_name)

    write_alarm_list_to_s3(instance_region, instance_id, instance_name, prog_args.output_bucket,
                           prog_args.output_key_prefix, prog_args.output_bucket_encrypted, prog_args.output_kms_key_id)

    sys.exit(0)
