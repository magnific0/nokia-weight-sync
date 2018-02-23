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
from smashrun import Smashrun
import nokia
import os.path
import sys
import time
import getpass
import base64

# Do command processing
parser = OptionParser()
parser.add_option('-k', '--key', dest='key', help="Key/Username")
parser.add_option('-s', '--secret', dest='secret', help="Secret/Password")
parser.add_option('-c', '--config', dest='config', default='config.ini', help="Config file")

(options, args) = parser.parse_args()

if len(args) == 0:
    print("Missing command!")
    print("Available commands: setup, sync, last, userinfo, subscribe, unsubscribe, list_subscriptions")
    sys.exit(1)
    
command = args.pop(0)

config = configparser.ConfigParser()
config.read(options.config)

# Decode the Garmin password
if config.has_section('garmin'):
    if config.has_option('garmin', 'password'):
        config.set('garmin', 'password', base64.b64decode(config.get('garmin', 'password').encode('ascii')).decode('ascii'))

def setup_nokia( options, config ):   
           
    if options.key is None:
        print("To set a connection with Nokia Health you must have registered an application at https://developer.health.nokia.com/en/partner/add .")
        options.key = input('Please enter the consumer key: ')
        
    if options.secret is None:
        options.secret = input('Please enter the consumer secret: ')
        
    auth = nokia.NokiaAuth(options.consumer_key, options.consumer_secret)
    authorize_url = auth.get_authorize_url()
    print("Go to %s allow the app and authorize the application." % authorize_url)
    oauth_verifier = input('Please enter your oauth_verifier: ')
    creds = auth.get_credentials(oauth_verifier)
    
    
    if not config.has_section('nokia'):
        config.add_section('nokia')
    
    config.set('nokia', 'consumer_key', options.key)
    config.set('nokia', 'consumer_secret', options.secret)
    config.set('nokia', 'access_token', creds.access_token)
    config.set('nokia', 'access_token_secret', creds.access_token_secret)
    config.set('nokia', 'user_id', creds.user_id)

def setup_garmin( options, config ):
    
    if options.key is None:
        options.key = input('Please enter your Garmin Connect username: ')
        
    if options.secret is None:
        options.secret = getpass.getpass('Please enter your Garmin Connect password: ')
        
    # Test out our new powers
    garmin = GarminConnect()
    session = garmin.login(options.key, options.secret)
    
    if not config.has_section('garmin'):
        config.add_section('garmin')
        
    config.set('garmin', 'username', options.key)
    config.set('garmin', 'password', options.secret)

def setup_smashrun( options, config ):
    
    if options.key is None:
        print("To set a connection with Smashrun you need to request an API key at https://api.smashrun.com/register .")
        options.key = input('Please the client id: ')
        
    if options.secret is None:
        options.secret = input('Please enter the client secret: ')
        
    client = Smashrun(client_id=options.key,client_secret=options.secret,redirect_uri='urn:ietf:wg:oauth:2.0:auto')
    auth_url = client.get_auth_url()
    print("Go to '%s' and authorize this application." % auth_url[0])
    code = input('Please enter your the code provided: ')
    resp = client.fetch_token(code=code)
    
    if not config.has_section('smashrun'):
        config.add_section('smashrun')
    
    config.set('smashrun', 'client_id', options.key)
    config.set('smashrun', 'client_secret', options.secret)
    config.set('smashrun', 'refresh_token', resp['refresh_token'])
    

def auth_nokia( config ):
    creds = nokia.NokiaCredentials(config.get('nokia', 'access_token'), config.get('nokia', 'access_token_secret'),
                                   config.get('nokia', 'consumer_key'), config.get('nokia', 'consumer_secret'),
                                   config.get('nokia', 'user_id'))
    client = nokia.NokiaApi(creds)
    return client

def auth_smashrun( config ):
    
    client = Smashrun(client_id=config.get('smashrun', 'client_id'), 
                      client_secret=config.get('smashrun', 'client_secret'))
    client.refresh_token(refresh_token=config.get('smashrun', 'refresh_token'))
    return client

    
client_nokia = auth_nokia( config )


if command == 'setup':   
  
    if len(args) == 1:
        service = args[0]
    else:
        print("You must provide the name of the service to setup. Available services are: nokia, garmin, smashrun.")
        sys.exit(1)
        
    if service == 'nokia':
        setup_nokia( options, config )
    elif service == 'garmin':
        setup_garmin( options, config )
    elif service == 'smashrun':
        setup_smashrun( options, config )
    else:
        print('Unknown service (%s), available services are: nokia, garmin, smashrun.')
        sys.exit(1)

elif command == 'userinfo':
    print(client_nokia.get_user())

elif command == 'last':
    m = client_nokia.get_measures(limit=1)[0]
    
    print(m.date)
    if len(args) == 1:
        for n, t in nokia.NokiaMeasureGroup.MEASURE_TYPES:
            if n == args[0]:
                print(m.get_measure(t))
    else:
        for n, t in nokia.NokiaMeasureGroup.MEASURE_TYPES:
            print("%s: %s" % (n.replace('_', ' ').capitalize(), m.get_measure(t)))

elif command == 'sync':    
    # Get weight as before    
    m = client_nokia.get_measures(limit=1)[0]
    
    for n, t in nokia.NokiaMeasureGroup.MEASURE_TYPES:
        if n == 'weight':
            weight = m.get_measure(t)
    
    print("Last weight from Nokia Health: %s kg taken at %s" % (weight, m.date))
    
    if len(args) == 1:
        service = args[0]
    else:
        print("You must provide the name of the service to setup. Available services are: nokia, garmin, smashrun.")
        sys.exit(1)
    
    if service == 'garmin':
                
        # Do not repeatidly sync the same value
        if config.has_option('garmin', 'last_sync'):
            if m.date.timestamp == int(config.get('garmin','last_sync')):
                print('Last measurement was already synced')
                sys.exit(0)
        
        # create fit file
        fit = FitEncoder_Weight()
        fit.write_file_info()
        fit.write_file_creator()
        fit.write_device_info(timestamp=m.date.timestamp)
        fit.write_weight_scale(timestamp=m.date.timestamp, weight=weight)
            
        fit.finish()           
        
        garmin = GarminConnect()
        session = garmin.login(config.get('garmin','username'), config.get('garmin','password'))
        r = garmin.upload_file(fit.getvalue(), session)
        if r:
            print('Weight has been successfully updated to Garmin!')
            config.set('garmin','last_sync', str(m.date.timestamp))
            
    elif service == 'smashrun':
                
        # Do not repeatidly sync the same value
        if config.has_option('smashrun', 'last_sync'):
            if m.date.timestamp == int(config.get('smashrun','last_sync')):
                print('Last measurement was already synced')
                sys.exit(0)
        
        client_smashrun = auth_smashrun( config )
        
        resp = client_smashrun.create_weight( weight, m.date.format('YYYY-MM-DD') )
        
        if resp.status_code == 200:
            print('Weight has been successfully updated to Smashrun!')
            config.set('smashrun','last_sync', str(m.date.timestamp))
        
    else:
        print('Unknown service (%s), available services are: nokia, garmin, smashrun')
        sys.exit(1)

elif command == 'subscribe':
    client_nokia.subscribe(args[0], args[1])
    print("Subscribed %s" % args[0])

elif command == 'unsubscribe':
    client_nokia.unsubscribe(args[0])
    print("Unsubscribed %s" % args[0])

elif command == 'list_subscriptions':
    l = client_nokia.list_subscriptions()
    if len(l) > 0:
        for s in l:
            print(" - %s " % s['comment'])
    else:
        print("No subscriptions")
        
else:
    
    print("Unknown command")
    print("Available commands: setup, sync, last, userinfo, subscribe, unsubscribe, list_subscriptions")
    sys.exit(1)
    

# Encode the Garmin password
if config.has_section('garmin'):
    if config.has_option('garmin', 'password'):
        config.set('garmin', 'password', base64.b64encode( config.get('garmin', 'password').encode('ascii') ).decode('ascii'))

with open(options.config, 'w') as f:
    config.write(f)
    f.close()
    
print("Config file saved to %s" % options.config)

sys.exit(0)
