

#Getting Started

### Dependencies
- Vagrant
- Ansible



#Testing


**testConfig.json**

All Fields Required
- _aws.profile_: String - See aws config for profile configuration
- _aws.ami_: String - [EC2 Console](https://console.aws.amazon.com/ec2/v2/home?region=us-east-1#Images:visibility=private-images;sort=desc:creationDate) - When possible use the AMI that would be deployed to production  
- _aws.instanceType_: String - [Instance types](https://aws.amazon.com/ec2/instance-types/) - Normally the smallest possible, "t2.micro", but should match the desired instance type when setting up new applications 
- _aws.subnetId_: String - [VPC Console](https://console.aws.amazon.com/vpc/home?region=us-east-1#subnets:sort=tag:Name) - Private Subnets should be used under normal circumstances 
- _aws.keypair_: String - [EC2 Console](https://console.aws.amazon.com/ec2/v2/home?region=us-east-1#KeyPairs:sort=keyName) - Needed for Vagrant to communicate with the EC2 instance
- _aws.region_: String - [Regions](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.RegionsAndAvailabilityZones.html) - Needs to match the location of the Subnet
- _aws.securityGroup_: Array of Strings - [EC2 Console](https://console.aws.amazon.com/ec2/v2/home?region=us-east-1#SecurityGroups:sort=tag:Name) - At least one Security Group must be specified, make sure that port 22 from your current location is allowed.
- _sshKeyPath_: String - Full Path string to the KeyPair PEM file on local system

**Example for Dev Account**
```json
{
    "aws": {
        "profile": "mobile-dev",
        "ami": "ami-0ff8a91507f77f867",
        "instanceType": "t2.micro",
        "subnetId": "subnet-95df1dde",
        "keypair": "mwd-devops",
        "region": "us-east-1",
        "securityGroup": ["sg-0f62540f3acc0d894", "sg-e7807c94"]
    },
    "sshKeyPath": "/Users/mlodge-paolini/.ssh/mwd-devops-dev.pem"
}
```
**Example Stage Account**
```json
{
    "aws": {
        "profile": "mobile-stage",
        "ami": "ami-e1bd9f9b",
        "instanceType": "t2.micro",
        "subnetId": "subnet-b25f9df9",
        "keypair": "mwd-devops",
        "region": "us-east-1",
        "securityGroup": ["sg-0f62540f3acc0d894", "sg-e7807c94"]
    },
    "sshKeyPath": "/Users/mlodge-paolini/.ssh/mwd-devops-dev.pem"
}

```
