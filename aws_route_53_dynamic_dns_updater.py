import logging
import configparser
import urllib.request

import tldextract # Pypi TLD Extract Package
import boto3 # AWS Boto3 SDK

from datetime import datetime
from urllib.parse import urlparse
from socket import timeout

# Create Config Parser Object to read config objects
config = configparser.ConfigParser(allow_no_value=True)
config.read('aws_ddns_config.ini')

desired_hostname_list = []
if config['hostname_settings']['use_config'] == "True":
        desired_hostname_list = config['hostname_settings']['hostnames'].split(",")
else:
    print("Please fill in required parameters in aws_ddns_config file")
    exit()

#logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
logging.basicConfig(filename='AWS_DDNS_Route_53.log', filemode='a+', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Set Desrired External IP Address Timeout
TIMEOUT_SECONDS = 10.0

# Set Current Time
date = datetime.now()

### Get Current IP using ipify.org API ###
try:
    external_ip = urllib.request.urlopen('https://api.ipify.org', timeout=TIMEOUT_SECONDS).read().decode('utf8')
except timeout:
    print ("Could not obtain IP address in maximum required time of %s" % (TIMEOUT_SECONDS))

# AWS config must be established prior to running this script
# Create object for boto3 Route 53 commands
client = boto3.client('route53')

# Obtains the hosted zone list and domain name 
hosted_zone_and_doamin_list = []
for i in range(len(client.list_hosted_zones()['HostedZones'])):
    for domain in desired_hostname_list:
        domain_parsed = (tldextract.extract(domain))
        domain_root = '.'.join(domain_parsed[1:])
        if domain_root in client.list_hosted_zones()['HostedZones'][i]['Name']:
            hosted_zone_and_doamin_list.append((client.list_hosted_zones()['HostedZones'][i]['Id'], domain_parsed))

# Function to get current IP address of hostnames that match monitored hostnames and change
record_updated = False
def get_hostname_ip(hosted_zone, hostname):
    for i in range(len(client.list_resource_record_sets(HostedZoneId=hosted_zone)['ResourceRecordSets'])):
        aws_hostname = client.list_resource_record_sets(HostedZoneId=hosted_zone)['ResourceRecordSets'][i]['Name']
        aws_ip_address = client.list_resource_record_sets(HostedZoneId=hosted_zone)['ResourceRecordSets'][i]['ResourceRecords'][0]['Value']
        if  hostname in aws_hostname and aws_ip_address != external_ip:
            print("There is an IP Address mismatch for hostname %s, calling the update_hostname_ip function" % (hostname))
            update_hostname_ip(hosted_zone, hostname)
            record_updated = True
        else:
            logging.info('No changes were made to %s at this time' % (hostname))

# Updates hostname with external IP address
def update_hostname_ip(hosted_zone, hostname):
    response = client.change_resource_record_sets(
        HostedZoneId=hosted_zone,
        ChangeBatch={
            'Comment': 'IP Address Updated to %s on %s' % (external_ip, date),
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': hostname,
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [
                            {
                                'Value': external_ip
                            }
                        ]
                    }
                }
            ]
        }
    )
    print(response)
    logging.info('Hostname %s has had its A record IP Address changed to %s' % (hostname, external_ip)) 

# Iterates through hostnames in hostname list and calls get_hostname_ip on each
for item in hosted_zone_and_doamin_list:
    hosted_zone = item[0].split("/")[2]
    hostname = '.'.join(item[1])
    get_hostname_ip(hosted_zone, hostname)