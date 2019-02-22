#!/bin/bash

##
# syncTestFiles.sh
# written by Diego Gutierrez <diego.gutierrez@wexinc.com>
# This will set up a vagrant machine to run ansible tests 
##

# Clean and Copy roles from vagrant mount to ansible location
rm -rf /etc/ansible/roles/*
cp -r /vagrant/roles/* /etc/ansible/roles/

# copy the test master playbooks
rm -f /etc/ansible/*.yml
cp /vagrant/test/playbooks/* /etc/ansible/

# clean and copy the ansible scripts over
rm -rf /root/ansible_scripts
cp -r /vagrant/scripts /root/ansible_scripts
chmod -R 755 /root/ansible_scripts

# copy over the test runner script
rm -f /usr/local/bin/runTest
cp /vagrant/test/utility/runTest.sh /usr/local/bin/runTest
chmod 755 /usr/local/bin/runTest

