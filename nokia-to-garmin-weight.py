#!/usr/bin/env python3
"""
Nokia Health to Garmin Connect Weight Updater
"""

__author__ = "Jacco Geul"
__version__ = "0.1.0"
__license__ = "GPLv3"

from optparse import OptionParser
import configparser
from fit import FitEncoder_Weight
from garmin import GarminConnect
import os.path
import nokia
import sys
import time
import getpass
import base64

parser = OptionParser()
parser.add_option('-k', '--consumer-key', dest='consumer_key', help="Consumer Key")
parser.add_option('-s', '--consumer-secret', dest='consumer_secret', help="Consumer Secret")
parser.add_option('-a', '--access-token', dest='access_token', help="Access Token")
parser.add_option('-t', '--access-token-secret', dest='access_token_secret', help="Access Token Secret")
parser.add_option('-g', '--garmin-username', dest='garmin_username', help="Garmin Connect Username")
parser.add_option('-p', '--garmin-password', dest='garmin_password', help="Garmin Connect Password")
parser.add_option('-u', '--userid', dest='user_id', help="User ID")
parser.add_option('-c', '--config', dest='config', help="Config file")

(options, args) = parser.parse_args()

options.last_sync = None
options.last_run = None

if len(args) == 0:
    print("Missing command!")
    print("Available commands: saveconfig, userinfo, last, synclast, subscribe, unsubscribe, list_subscriptions")
    sys.exit(1)
command = args.pop(0)

def read_config( options ):
    """Add configuration files to options, not overriding any commandline arguments"""
    if options.config is None or not os.path.exists(options.config):
        options.config = 'config.ini'
    config = configparser.ConfigParser(vars(options))
    config.read(options.config)
    if options.consumer_key is None and config.has_option('nokia', 'consumer_key'):
        options.consumer_key = config.get('nokia', 'consumer_key')
    if options.consumer_secret is None and config.has_option('nokia', 'consumer_secret'):
        options.consumer_secret = config.get('nokia', 'consumer_secret')
    if options.access_token is None and config.has_option('nokia', 'access_token'):
        options.access_token = config.get('nokia', 'access_token')
    if options.access_token_secret is None and config.has_option('nokia', 'access_token_secret'):
        options.access_token_secret = config.get('nokia', 'access_token_secret')
    if options.user_id is None and config.has_option('nokia', 'user_id'):
        options.user_id = config.get('nokia', 'user_id')
    if config.has_section('garmin'):
        if options.garmin_username is None and config.has_option('garmin', 'username'):
            options.garmin_username = config.get('garmin', 'username')
        if options.garmin_password is None and config.has_option('garmin', 'password'):
            options.garmin_password = base64.b64decode(config.get('garmin', 'password').encode('ascii')).decode('ascii')
            
    # Read GC password from console now
    if options.garmin_username and options.garmin_password is None:
        options.garmin_password = getpass.getpass('Please enter your Garmin Connect password: ')
            
    if config.has_section('sync'):
        if config.has_option('sync', 'last'):
            options.last_sync = config.get('sync', 'last')
        if config.has_option('sync', 'run'):
            options.last_run = config.get('sync', 'last')
    return options
            
options = read_config( options )

def nokia_credentials( options ):
    if options.consumer_key is None or options.consumer_secret is None:
        raise Exception("You must provide a consumer key and consumer secret from https://developer.health.nokia.com/en/partner/add.")

    if options.access_token is None or options.access_token_secret is None or options.user_id is None:
        print("Missing authentification information!")
        print("Starting authentification process...")
        auth = nokia.NokiaAuth(options.consumer_key, options.consumer_secret)
        authorize_url = auth.get_authorize_url()
        print("Go to %s allow the app and copy your oauth_verifier" % authorize_url)
        oauth_verifier = input('Please enter your oauth_verifier: ')
        creds = auth.get_credentials(oauth_verifier)
        options.access_token = creds.access_token
        options.access_token_secret = creds.access_token_secret
        options.user_id = creds.user_id
        print("")
    else:
        creds = nokia.NokiaCredentials(options.access_token, options.access_token_secret,
                                    options.consumer_key, options.consumer_secret,
                                    options.user_id)
    return creds

creds = nokia_credentials( options )

client = nokia.NokiaApi(creds)

def save_config( options ):
    config = configparser.ConfigParser()
    
    # Nokia Health options
    config.add_section('nokia')
    config.set('nokia', 'consumer_key', options.consumer_key)
    config.set('nokia', 'consumer_secret', options.consumer_secret)
    config.set('nokia', 'access_token', options.access_token)
    config.set('nokia', 'access_token_secret', options.access_token_secret)
    config.set('nokia', 'user_id', options.user_id)
    
    # Garmin Connect options
    if options.garmin_username:
        config.add_section('garmin')
        config.set('garmin', 'username', options.garmin_username)
        config.set('garmin', 'password', base64.b64encode(options.garmin_password.encode('ascii')).decode('ascii'))

    if options.last_sync:        
        config.add_section('sync')
        config.set('sync', 'last', options.last_sync)
        config.set('sync', 'run', options.last_run)

    with open(options.config, 'w') as f:
        config.write(f)
        f.close()
    print("Config file saved to %s" % options.config)

if command == 'userinfo':
    print(client.get_user())

elif command == 'last':
    m = client.get_measures(limit=1)[0]
    
    print(m.date)
    if len(args) == 1:
        for n, t in nokia.NokiaMeasureGroup.MEASURE_TYPES:
            if n == args[0]:
                print(m.get_measure(t))
    else:
        for n, t in nokia.NokiaMeasureGroup.MEASURE_TYPES:
            print("%s: %s" % (n.replace('_', ' ').capitalize(), m.get_measure(t)))

elif command == 'synclast':    
    # Get weight as before    
    m = client.get_measures(limit=1)[0]
    
    for n, t in nokia.NokiaMeasureGroup.MEASURE_TYPES:
        if n == 'weight':
            weight = m.get_measure(t)            
    
    print("Last weight from Nokia Health: %s kg taken at %s" % (weight, m.date))
    
    # create fit file
    print('generating fit file...\n')
    fit = FitEncoder_Weight()
    fit.write_file_info()
    fit.write_file_creator()
    fit.write_device_info(timestamp=m.date.timestamp)
    fit.write_weight_scale(timestamp=m.date.timestamp, weight=weight)
        
    fit.finish()
    
    options.last_run  = str(time.time())
        
    # Do not repeatidly sync the same value
    if options.last_sync:
        if m.date.timestamp == int(options.last_sync):
            print('Last measurement was already synced')
            save_config( options )
            sys.exit(0)
    
    garmin = GarminConnect()
    session = garmin.login(options.garmin_username, options.garmin_password)
    r = garmin.upload_file(fit.getvalue(), session)
    if r:
        print('FIT has been successfully uploaded to Garmin!\n')
        options.last_sync = str(m.date.timestamp)

elif command == 'subscribe':
    client.subscribe(args[0], args[1])
    print("Subscribed %s" % args[0])

elif command == 'unsubscribe':
    client.unsubscribe(args[0])
    print("Unsubscribed %s" % args[0])

elif command == 'list_subscriptions':
    l = client.list_subscriptions()
    if len(l) > 0:
        for s in l:
            print(" - %s " % s['comment'])
    else:
        print("No subscriptions")
        
else:
    
    print("Unknown command")
    print("Available commands: saveconfig, userinfo, last, synclast, subscribe, unsubscribe, list_subscriptions")
    sys.exit(1)        

save_config( options )
sys.exit(0)



