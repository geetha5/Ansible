#!/bin/bash

##
# bootstrap_logs.sh
# written by Diego Gutierrez <diego.gutierrez@wexinc.com>
# This will install cloudwatch logs or sumo agent and provision the config
# only enough to log for the bootstrap and provisioning, the config will
# be updated with the application logs later in the provisioning
##

## Global Vars ##
AWS_METADATA_URL="http://169.254.169.254/latest/meta-data"

## Generic CLI ARGS ##
log_agent_type=$1

if [[ "${log_agent_type}" == "sumo" ]]; then

    ## Agent Specific ARGS ##
    environment=$2
    hostPurpose=$3
    lob=$4
    collectorS3Url=$5

    ## Read AWS info out of metadata ##
    region=$(curl -s ${AWS_METADATA_URL}/placement/availability-zone | grep -o "[a-z]*-[a-z]*-[0-9]")
    normalized_ip_address=$(curl -s ${AWS_METADATA_URL}/local-ipv4 | tr . _)

    aws_hostname="aws-${hostPurpose}-${environment}-${normalized_ip_address}"

    accessId=$(aws ssm get-parameter --name "${environment}.sumologic.accessid" --query 'Parameter.Value' --output text --region ${region})
    accessKey=$(aws ssm get-parameter --name "${environment}.sumologic.accesskey" --with-decryption --query 'Parameter.Value' --output text --region ${region})

    aws s3 cp ${collectorS3Url} /root/sumologic_collector.rpm --region ${region}

cat << EOF > /etc/sumo.conf
name=${aws_hostname}
accessid=${accessId}
accesskey=${accessKey}
sources=/etc/sumo_sources.json
ephemeral=true
EOF

cat << EOF > /etc/sumo_sources.json
{
    "api.version": "v1",
    "sources": [
        {
            "automaticDateParsing": true,
            "sourceType": "LocalFile",
            "hostName": "${aws_hostname}",
            "name": "bootstrap",
            "category": "${lob}/${region}/${hostPurpose}/${environment}/bootstrap",
            "multilineProcessingEnabled": true,
            "pathExpression": "/var/log/bootstrap.log",
            "timeZone": "UTC",
            "forceTimeZone": true,
            "useAutolineMatching": true
        },
        {
            "automaticDateParsing": true,
            "sourceType": "LocalFile",
            "hostName": "${aws_hostname}",
            "name": "ansible",
            "category": "${lob}/${region}/${hostPurpose}/${environment}/ansible",
            "multilineProcessingEnabled": true,
            "pathExpression": "/var/log/ansible.log",
            "timeZone": "UTC",
            "forceTimeZone": true,
            "useAutolineMatching": true
        }
    ]
}
EOF

    yum -y install /root/sumologic_collector.rpm

    /etc/init.d/collector start

elif [[ "${log_agent_type}" == "awslogs" ]]; then

    ## Agent Specific ARGS ##
    log_group_name_prefix=$2
    region=$3

    ## Read AWS info out of metadata ##
    region=$(curl -s ${AWS_METADATA_URL}/placement/availability-zone | grep -o "\w*-\w*-\d")

    if [[ -z "${log_group_name_prefix}" ]]; then
        echo "ERROR: you must provide a log group prefix"
        exit 1
    fi

    if [[ -z "${region}" ]]; then
        echo "ERROR: you must provide a region"
        exit 1
    fi

cat << EOF > /etc/awslogs/awscli.conf
[default]
region = ${region}
EOF

    yum -y install awslogs

    mkdir /var/awslogs

cat << EOF > /etc/awslogs/awslogs.conf
[general]
state_file = /var/awslogs/agent-state
logging_config_file = /etc/awslogs/awslogs.conf
use_gzip_http_content_encoding = true

[${log_group_name_prefix}-bootstrap]
log_group_name = ${log_group_name_prefix}-bootstrap
log_stream_name = {instance_id}_{ip_address}
datetime_format = "%Y-%m-%d %H:%M:%S"
time_zone = UTC
file = /var/log/bootstrap.log

[${log_group_name_prefix}-ansible]
log_group_name = ${log_group_name_prefix}-ansible
log_stream_name = {instance_id}_{ip_address}
datetime_format = "%Y-%m-%d %H:%M:%S"
time_zone = UTC
file = /var/log/ansible.log

EOF

    service awslogs restart

else

    echo "ERROR: unknown log_agent_type"
    exit 1

fi
