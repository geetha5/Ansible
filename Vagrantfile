# -*- mode: ruby -*-
# vi: set ft=ruby :

### Error checking and Gem Requires ###
plugin_gems = []
plugin_gems.each do |plugin_gem|
  if !Vagrant.has_plugin?(plugin_gem)
    raise "Plugin gem #{plugin_gem} is not installed"
  else
    require plugin_gem
  end  
end

### Error checking for Vagrant Plugins ###
plugins = ['vagrant-aws']
plugins.each do |plugin|
  if !Vagrant.has_plugin?(plugin)
    raise "Plugin #{plugin} is not installed"
  end
end

### other included gems ###
require 'json'

###############################################################
# Functions
###############################################################

##
# read_config(config_file)
# checks for the config file and returns the data hash
##
def read_config(config_file)
  if !File.file?(config_file)
    puts "ERROR: could not find config file"
    exit(1)
  end

  file_json = File.read(config_file)
  config_data =JSON.parse(file_json)

  return config_data
end

## TODO: Add config validation ##

###############################################################
# Initialization
###############################################################

# hash for config file contents
config_data = read_config('testConfig.json')

# aws settings
aws_profile = config_data['aws']['profile']
aws_ami = config_data['aws']['ami'] 
aws_instance = config_data['aws']['instanceType'] 
aws_subnet = config_data['aws']['subnetId'] 
aws_keypair = config_data['aws']['keypair'] 
aws_region = config_data['aws']['region'] 
aws_sgs = config_data['aws']['securityGroup'] 
ssh_key_path = config_data['sshKeyPath'] 

###############################################################
# Vagrant Configuration
###############################################################

Vagrant.configure("2") do |config|
  config.vm.box = "dummy"

  config.vm.provider :aws do |aws, override|

    aws.ami = aws_ami
    aws.aws_profile = aws_profile
    aws.instance_type = aws_instance
    aws.subnet_id = aws_subnet
    aws.region = aws_region
    aws.security_groups = aws_sgs
    aws.keypair_name = aws_keypair
    aws.iam_instance_profile_name = "ansible-test"
    aws.tags = {
      'Name' => 'ansible-test',
      '!Runtime' => 'off=(n/a)'
    }
    aws.block_device_mapping = [{ 'DeviceName' => '/dev/xvda', 'Ebs.VolumeSize' => 30 }]

    config.vm.synced_folder ".", "/vagrant", type: "rsync",
                            rsync__auto: true, rsync__verbose: true

    override.ssh.username = "ec2-user"
    override.ssh.private_key_path = ssh_key_path
    override.nfs.functional = false
  end

  config.vm.provision "bootstrap", type: "shell" do |s|
    s.inline = "chmod 755 /vagrant/scripts/bootstrap.sh && sudo /vagrant/scripts/bootstrap.sh | while IFS= read -r line; do echo \"$(date '+%Y-%m-%d %H:%M:%S') $line\"; done |& tee -a /var/log/bootstrap.log"
  end

  config.vm.provision "testSetup", type: "shell" do |s|
    s.inline = "chmod 755 /vagrant/test/setup/syncTestFiles.sh && sudo /vagrant/test/setup/syncTestFiles.sh"
  end

  config.vm.provision "moduleInstall", type: "shell" do |s|
    s.inline = "sudo /usr/local/bin/ansible-playbook /vagrant/test/setup/ansible_modules.yml"
  end

end
