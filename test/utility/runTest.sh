#!/bin/bash

##
# runTest.sh
# written by Diego Gutierrez <diego.gutierrez@wexinc.com>
# This will run a ansible test that is based on the name that is 
# passed to it 
##

# CLI ARGS #
# test_name: the name of the test to run
test_name=$1
# debug flag: weither to run in debug
debug_flag=$2

if [[ -z "${test_name}" ]]; then 
    echo "ERROR: you must supply a test name"
    exit 1
elif [[ "${test_name}" == "debug" ]]; then
   echo "ERROR: you must supply a test name"
   exit 1 
fi

if [[ ${test_name} == "nexus_artifact-latest" ]]; then
    env_var="APP_VERSION=1.0.0-latest"
elif [[ ${test_name} == "nexus_artifact-release" ]]; then
    env_var="APP_VERSION=4.4.10-release"
elif [[ ${test_name} == "nexus_artifact-snapshot" ]]; then
    env_var="APP_VERSION=1.0.0-20180112.190014-75"
elif [[ ${test_name} == "nexus_artifact-s3" ]]; then
    env_var="APP_VERSION=s3://wex-mobile-artifacts/mobile-gateway/oauth-service-3.4.3.jar"
elif [[ ${test_name} == "zookeeper-cluster" ]]; then
    env_var="ZOOKEEPER_INSTANCE_NUMBER=1"
else
    env_var=""
fi

if [[ ! -z "${debug_flag}" ]]; then
   sudo ${env_var} /usr/local/bin/ansible-playbook -vvv /etc/ansible/${test_name}-test.yml
else 
   sudo ${env_var} /usr/local/bin/ansible-playbook /etc/ansible/${test_name}-test.yml
fi

exit 0