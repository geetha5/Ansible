##
# health_check_topics.py
# Written by Diego Gutierrez <diego.gutierrez@wexinc.com>
# This will create/update the kafka topics needed by the
# kafka health check program to monitor broker health
##

import argparse
import logging
import sys
import re
import json
from exceptions import Exception
import os
from time import sleep
from subprocess import Popen,PIPE,STDOUT
from kazoo.client import KazooClient

# global vars #
logger = logging.getLogger('kafka_health_topics')
log_file = '/var/log/health_check_topics.log'
kafka_bin_path = '/opt/kafka-active/bin'
kafka_change_path = '/var/kafka-changes'

##
# create_broker_health_topic(broker_id, zookeepers)
# This will create the health check topic for this broker
##
def create_broker_health_topic(broker_id, zookeepers):

    topic_name = 'broker-' + str(broker_id) + '-health-check'

    # create the topic if it doesn't exist
    if not topic_exists(topic_name, zookeepers):
        logger.info('creating broker health topic %s', topic_name)
        status = create_topic(topic_name, 1, 1, zookeepers)

        if status:
            logger.info('broker health topic creation successful')
        else:
            logger.fatal('broker health topic creation failed')
            sys.exit(1)
    else:
        logger.info('broker health topic %s already exists', topic_name)

##
# ensure_proper_broker_health_topic_leader(broker_id, zookeepers)
# This will ensure that the leader of the broker health topic
# is the broker that the health topic belongs to
##
def ensure_proper_broker_health_topic_leader(broker_id, zookeepers):

    topic_name = 'broker-' + str(broker_id) + '-health-check'

    topic_leader = get_topic_leader(topic_name, zookeepers)

    if topic_leader == broker_id:
        logger.info('broker %d is already the leader of broker health topic %s', broker_id, topic_name)
        return

    logger.info('broker %d is not the leader of broker health topic %s, updating...', broker_id, topic_name)

    # create change set to move broker health topic to current broker
    move_topic = {
        'partitions': [
            {
                'topic': topic_name,
                'partition': 0,
                'replicas': [broker_id]
            }
        ]
    }

    move_topic_filename = 'broker-health-topic-nonrep-move-to-broker-' + str(broker_id) + '.json'

    # write change set to file
    with open(kafka_change_path + '/' + move_topic_filename, 'w') as f:
        json.dump(move_topic, f)

    # run change on topic
    logger.debug('running leader change set for topic %s', topic_name)

    out = Popen([kafka_bin_path + '/kafka-reassign-partitions.sh', '--zookeeper', zookeepers,
                 '--reassignment-json-file', kafka_change_path + '/' + move_topic_filename,
                 '--execute'], stderr=STDOUT,stdout=PIPE)

    out.wait()

    output = out.communicate()[0]

    if out.returncode != 0:
        logger.fatal('error running change set to move topic %s to broker %d, output: %s', topic_name, broker_id, output)
        sys.exit(1)

    # wait for topic leader to change
    logger.info('starting wait for broker %d to become leader of topic %s', broker_id, topic_name)
    wait_timer = 0
    leader_id = get_topic_leader(topic_name, zookeepers)

    while leader_id != broker_id:

        logger.debug('waiting for broker to become leader')
        sleep(10)
        wait_timer += 10
        leader_id = get_topic_leader(topic_name, zookeepers)

    logger.info('broker %d is now the leader of its own broker health topic, wait time %d', broker_id, wait_timer)
##
# broker_0_create_rep_topic(rep_topic_name, zookeepers)
# This will only be run by broker 0 this is to create the
# replication health check topic
##
def broker_0_create_rep_topic(rep_topic_name, zookeepers):

    # create the replication health check topic if it doesn't exist
    if not topic_exists(rep_topic_name, zookeepers):
        logger.info('creating replication health topic %s', rep_topic_name)
        status = create_topic(prog_args.rep_topic_name, 1, 1, zookeepers)

        if status:
            logger.info('replication health topic creation successful')
        else:
            logger.fatal('replication health topic creation failed')
            sys.exit(1)
    else:
        logger.info('replication health topic %s already exists', rep_topic_name)

##
# wait_for_rep_topic(rep_topic_name, zookeepers)
# This will wait for broker 0 to create the replication
# health check topic incase another broker comes up first
##
def wait_for_rep_topic(rep_topic_name, zookeepers):

    wait_timer = 0

    # Loop until the replication topic exists
    rep_topic_status = topic_exists(rep_topic_name, zookeepers)

    if not rep_topic_status:
        logger.info('replication health topic not present, starting wait for broker 0 to create it')
    else:
        logger.debug('replication health topic already exists')
        return True

    while not rep_topic_status:
        logger.debug('waiting for replication topic to be created ...')
        sleep(10)
        wait_timer += 10
        rep_topic_status = topic_exists(rep_topic_name, zookeepers)

    logger.info('replication topic created by broker 0')
    return True


##
# add_broker_to_rep_topic()
# This will be run by any broker that is not broker 0 and
# will add itself to the replication list for the replication
# health check topic if it is not already on the list
##
def add_broker_to_rep_topic(rep_topic_name, broker_id, zookeepers):

    # get replica list
    replicas = get_topic_replica_list(rep_topic_name, zookeepers)

    if broker_id not in replicas:
        logger.info('broker %d not in replica list for topic %s, adding...', broker_id, rep_topic_name)

        # add broker id to replica list and create replica change set
        replicas.append(broker_id)

        replica_change = {
            'partitions': [
                {
                    'topic': rep_topic_name,
                    'partition': 0,
                    'replicas': replicas
                }
            ]
        }

        replica_change_filename = 'broker-heath-replication-topic-add-broker-' + str(broker_id) + '.json'

        # write topic change set to file
        with open(kafka_change_path + '/' + replica_change_filename, 'w') as f:
            json.dump(replica_change, f)

        # run change on topic
        logger.debug('running change set for topic')
        out = Popen([kafka_bin_path + '/kafka-reassign-partitions.sh', '--zookeeper', zookeepers,
                     '--reassignment-json-file', kafka_change_path + '/' + replica_change_filename,
                     '--execute'], stderr=STDOUT,stdout=PIPE)

        out.wait()

        output = out.communicate()[0]

        if out.returncode != 0:
            logger.fatal('error running change set to add broker %d as replica for topic %s, output: %s', broker_id, rep_topic_name, output)
            sys.exit(1)

        # wait for broker to be added to the list of replicas
        logger.info('starting wait till broker is added to the replica list')
        replca_list = get_topic_replica_list(rep_topic_name, zookeepers)
        wait_timer = 0

        while broker_id not in replca_list:
            logger.debug('waiting for broker %d to be a replica', broker_id)
            sleep(10)
            wait_timer += 10
            replca_list = get_topic_replica_list(rep_topic_name, zookeepers)

    else:
        logger.info('broker %d is already present in replica list for topic %s', broker_id, rep_topic_name)

##
# get_topic_replica_list(topic_name, zookeepers)
# This will get the list of replicas for a given topic
##
def get_topic_replica_list(topic_name, zookeepers):

    logger.debug('getting replica list for topic %s', topic_name)

    out = Popen([kafka_bin_path + '/kafka-topics.sh',
                 '--describe',
                 '--zookeeper', zookeepers,
                 '--topic', topic_name], stderr=STDOUT,stdout=PIPE)

    out.wait()

    output = out.communicate()[0]

    if out.returncode != 0:
        logger.fatal('failed to get replica list for topic %s, output: %s', topic_name, output)
        sys.exit(1)

    logger.debug('topic detail line: %s', output.splitlines()[1])

    replica_match = re.search(r'Replicas: (\d*((,\d*)+)?)', output.splitlines()[1])

    if replica_match is None:
        logger.fatal('failed to get replica list')
        sys.exit(1)

    replica_str = replica_match.group(1)
    logger.debug('replicas for topic %s are %s', topic_name, replica_str)

    temp_replica_list = replica_str.split(',')
    int_replica_list = []

    for replica in temp_replica_list:
        int_replica_list.append(int(replica))

    return int_replica_list

##
# wait_for_broker_to_be_active(broker_id, zookeepers)
# This will wait for the broker to be active in zookeeper before
# letting the broker create or update topics
##
def wait_for_broker_to_be_active(broker_id, zookeepers):

    wait_timer = 0

    logger.info('starting wait for broker to be added to the cluster')
    # create kazoo Client and prime the broker list
    zk = KazooClient(hosts=zookeepers)
    zk.start()
    brokers = zk.get_children('/brokers/ids')
    zk.stop()
    #broker_found = False

    # loop and wait for broker id to be available
    while str(broker_id) not in brokers:

        sleep(10)
        wait_timer += 10
        zk.start()
        brokers = zk.get_children('/brokers/ids')
        logger.debug('broker list is %s', ','.join(brokers))
        zk.stop()
        #for broker in brokers:
        #    logger.debug('checking broker in list %d', int(broker))
        #if int(broker_id) is int(broker):
        #    logger.debug('broker found')
        #    broker_found = True
        #else:
        #   logger.debug('broker not found')
        #    broker_found = False


    logger.info('broker is available in the cluster, wait time was %d', wait_timer)

##
# get_topic_leader(topic_name, zookeepers)
# This will get the current leader of the topic and
# return its id
##
def get_topic_leader(topic_name, zookeepers):

    logger.debug('getting the leader for topic %s, partition 0', topic_name)

    out = Popen([kafka_bin_path + '/kafka-topics.sh',
                 '--describe',
                 '--zookeeper', zookeepers,
                 '--topic', topic_name], stderr=STDOUT,stdout=PIPE)

    out.wait()

    output = out.communicate()[0]

    if out.returncode != 0:
        logger.fatal('failed to get leader for partition 0 for topic %s, output: %s', topic_name, output)
        sys.exit(1)

    leader_match = re.search(r'Leader: (\d*)', output.splitlines()[1])
    leader_id = int(leader_match.group(1))

    logger.debug('leader for topic %s partition 0 is %d', topic_name, leader_id)

    return leader_id

##
# topic_exists(topic_name, zookeepers)
# This will check if the topic already exists and will return True
# if it does and False if it doesn't
##
def topic_exists(topic_name, zookeepers):

    # start zookeeper client, get topic list and stop client
    logger.info('checking if topic %s exists', topic_name)
    logger.debug('trying to connect to zookeeper with zookeeper list %s', zookeepers)
    try:
        zk = KazooClient(hosts=zookeepers)
        zk.start()
        topics = zk.get_children('/brokers/topics')
        logger.debug('topics found: %s', ','.join(topics))
        zk.stop()
    except Exception as e:
        logger.exception("exception getting info from zookeeper")

    # check for topic in list
    if topic_name in topics:
        logger.info('topic %s is found', topic_name)
        return True
    else:
        logger.info('topic %s not found', topic_name)
        return False

##
# create_topic(name, rep_factor. partitions)
# This will create a topic with defined settings
# it will return True if the operation was successful
# and False if the operation failed
##
def create_topic(name, rep_factor, partitions, zookeepers):

    logger.info('creating topic %s with replication %d and partitions %d', name, rep_factor, partitions)

    out = Popen([kafka_bin_path + '/kafka-topics.sh',
                 '--create',
                 '--zookeeper', zookeepers,
                 '--replication-factor', str(rep_factor),
                 '--partitions',  str(partitions),
                 '--topic', name], stderr=STDOUT,stdout=PIPE)

    out.wait()

    line_out = out.communicate()[0]

    if out.returncode == 0:
        logger.info('topic creation successful')
        return True
    else:
        logger.error('topic creation failed %s', line_out)
        return False

# MAIN()
if __name__ == "__main__":

    # parse command line args
    arg_parser = argparse.ArgumentParser(description='Create and update the kafka health check topics')
    arg_parser.add_argument('-e', '--environment', help='The environment the server is in', dest='environment',
                            default='dev')
    arg_parser.add_argument('-b', '--broker-id', help='The id of this broker', dest='broker_id')
    arg_parser.add_argument('-z', '--zookeepers', help='The list of zookeeper servers', dest='zookeepers')
    arg_parser.add_argument('--rep-topic-name', help='The replication heath topic name', dest='rep_topic_name')

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

    logger.info('Starting the kafka health check topic creation/update')

    logger.debug('environment: %s', prog_args.environment)
    logger.debug('broker_id: %d', int(prog_args.broker_id))
    logger.debug('zookeepers: %s', prog_args.zookeepers)
    logger.debug('rep_topic_name: %s', prog_args.rep_topic_name)

    if not os.path.exists(kafka_change_path):
        logger.debug('creating /var/kafka_changes directory')
        os.mkdir(kafka_change_path)

    # wait for the broker to be added to the cluster
    wait_for_broker_to_be_active(int(prog_args.broker_id), prog_args.zookeepers)

    # create the broker health topic
    create_broker_health_topic(int(prog_args.broker_id), prog_args.zookeepers)
    ensure_proper_broker_health_topic_leader(int(prog_args.broker_id), prog_args.zookeepers)

    # if this is broker 0 create the replication topic if needed
    if int(prog_args.broker_id) == 0:
        broker_0_create_rep_topic(prog_args.rep_topic_name, prog_args.zookeepers)

    # else wait for the replication topic and ensure this broker id is in the replica list
    else:
        wait_for_rep_topic(prog_args.rep_topic_name, prog_args.zookeepers)
        add_broker_to_rep_topic(prog_args.rep_topic_name, int(prog_args.broker_id), prog_args.zookeepers)

    sys.exit(0)




