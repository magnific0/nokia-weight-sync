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
from oauthlib.oauth2 import MobileApplicationClient
import urllib.parse
import nokia
import os.path
import sys
import time
import getpass
import base64

# Do command processing
class MyParser(OptionParser):
    def format_epilog(self, formatter):
        return self.epilog

usage = "usage: %prog [options] command [service]"
epilog = """
Commands:
  setup, sync, last, userinfo, subscribe, unsubscribe, list_subscriptions

Services:
  nokia, garmin, smashrun, smashrun_code (setup only)

Copyright (c) 2018 by Jacco Geul <jacco@geul.net>
Licensed under GNU General Public License 3.0 <https://github.com/magnific0/nokia-weight-sync/LICENSE>
"""
parser = MyParser(usage=usage,epilog=epilog,version=__version__)

parser.add_option('-k', '--key', dest='key', help="Key/Username")
parser.add_option('-s', '--secret', dest='secret', help="Secret/Password")
parser.add_option('-u', '--callback', dest='callback', help="Callback/redirect URI")
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
    """ Setup the Nokia Health API
    """
    if options.key is None:
        print("To set a connection with Nokia Health you must have registered an application at https://account.health.nokia.com/partner/add_oauth2 .")
        options.key = input('Please enter the client id: ')

    if options.secret is None:
        options.secret = input('Please enter the consumer secret: ')
        
    if options.callback is None:
        options.callback = input('Please enter the callback url known by Nokia: ')

    auth = nokia.NokiaAuth(options.key, options.secret, options.callback)
    authorize_url = auth.get_authorize_url()
    print("Visit: %s\nand select your user and click \"Allow this app\"." % authorize_url)
    print("Afterwards you will be redirected to your callback url with some additional parameters.")
    print("Example: https://your_original_callback?code=[code]&state=[state]")
    callback_url = input('Please enter the full callback response url: ')
    # auth.extract_access_code(callback_url)
    creds = auth.get_credentials(callback_url)


    if not config.has_section('nokia'):
        config.add_section('nokia')

    config.set('nokia', 'consumer_key', options.key)
    config.set('nokia', 'consumer_secret', options.secret)
    config.set('nokia', 'callback_uri', options.callback)
    config.set('nokia', 'access_token', creds.access_token)
    config.set('nokia', 'token_expiry', creds.token_expiry)
    config.set('nokia', 'token_type', creds.token_type)
    config.set('nokia', 'refresh_token', creds.refresh_token)
    config.set('nokia', 'user_id', creds.user_id)

def setup_garmin( options, config ):
    """ Setup the Garmin Connect credentials
    """

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
    """ Setup Smashrun API implicit user level authentication
    """
    mobile = MobileApplicationClient('client') # implicit flow
    client = Smashrun(client_id='client',client=mobile,client_secret='my_secret',redirect_uri='https://httpbin.org/get')
    auth_url = client.get_auth_url()
    print("Go to '%s' and log into Smashrun. After redirection, copy the access_token from the url." % auth_url[0])
    print("Example url: https://httpbin.org/get#access_token=____01234-abcdefghijklmnopABCDEFGHIJLMNOP01234567890&token_type=[...]")
    print("Example access_token: ____01234-abcdefghijklmnopABCDEFGHIJLMNOP01234567890")
    token = input("Please enter your access token: " )
    if not config.has_section('smashrun'):
        config.add_section('smashrun')
    config.set('smashrun', 'token', urllib.parse.unquote(token))
    config.set('smashrun', 'type', 'implicit')

def setup_smashrun_code( options, config ):
    """ Setup Smashrun API explicit code flow (for applications)
    """
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
    config.set('smashrun', 'type', 'code')


def auth_nokia( config ):
    """ Authenticate client with Nokia Health
    """
    creds = nokia.NokiaCredentials(config.get('nokia', 'access_token'), 
                                   config.get('nokia', 'token_expiry'),
                                   config.get('nokia', 'token_type'),
                                   config.get('nokia', 'refresh_token'),
                                   config.get('nokia', 'user_id'),
                                   config.get('nokia', 'consumer_key'),
                                   config.get('nokia', 'consumer_secret')
                                   )
    client = nokia.NokiaApi(creds)
    return client

def auth_smashrun( config ):
    """ Authenticate client with Smashrun
    """

    if config.get('smashrun', 'type') == 'code':
        client = Smashrun(client_id=config.get('smashrun', 'client_id'),
                        client_secret=config.get('smashrun', 'client_secret'))
        client.refresh_token(refresh_token=config.get('smashrun', 'refresh_token'))
    else:
        mobile = MobileApplicationClient('client') # implicit flow
        client = Smashrun(client_id='client', client=mobile,
                        token={'access_token':config.get('smashrun', 'token'),'token_type':'Bearer'})
    return client

client_nokia = None
if command != 'setup':
    client_nokia = auth_nokia( config )

if command == 'setup':

    if len(args) == 1:
        service = args[0]
    else:
        print("You must provide the name of the service to setup. Available services are: nokia, garmin, smashrun, smashrun_code.")
        sys.exit(1)

    if service == 'nokia':
        setup_nokia( options, config )
    elif service == 'garmin':
        setup_garmin( options, config )
    elif service == 'smashrun':
        setup_smashrun( options, config )
    elif service == 'smashrun_code':
        setup_smashrun_code( options, config )
    else:
        print('Unknown service (%s), available services are: nokia, garmin, smashrun, smashrun_code.')
        sys.exit(1)

elif command == 'userinfo':
    print(client_nokia.get_user())

elif command == 'last':
    m = client_nokia.get_measures(limit=1)[0]

    print(m.date)
    if len(args) == 1:
        types = dict(nokia.NokiaMeasureGroup.MEASURE_TYPES)
        print(m.get_measure(types[args[0]]))
    else:
        for n, t in nokia.NokiaMeasureGroup.MEASURE_TYPES:
            print("%s: %s" % (n.replace('_', ' ').capitalize(), m.get_measure(t)))

elif command == 'lastn':
    if len(args) != 1:
        print("You must supply the number of measurement groups to fetch.")
        sys.exit(1)

    # Get n last measurements
    mall = client_nokia.get_measures(limit=args[0])

    for n, m in enumerate(mall):
        # Print clear header and date for each group
        print("--Group %i" % n)
        print(m.date)

        # Print all types one by one
        for n, t in nokia.NokiaMeasureGroup.MEASURE_TYPES:
            print("%s: %s" % (n.replace('_', ' ').capitalize(), m.get_measure(t)))
        print("")

elif command == 'sync-preview':
    if len(args) == 1:
        service = args[0]
    else:
        print("You must provide the name of the service to sync. Available services are: garmin, smashrun.")
        sys.exit(1)

    # Get next measurements
    last_sync = int(config.get(service,'last_sync')) if config.has_option(service, 'last_sync') else 0
    mall = client_nokia.get_measures(lastupdate=last_sync)

    for n, m in enumerate(mall):
        # Print clear header and date for each group
        print("--Group %i" % n)
        print(m.date)

        # Print all types one by one
        for n, t in nokia.NokiaMeasureGroup.MEASURE_TYPES:
            print("%s: %s" % (n.replace('_', ' ').capitalize(), m.get_measure(t)))
        print("")

elif command == 'sync':

    if len(args) == 1:
        service = args[0]
    else:
        print("You must provide the name of the service to sync. Available services are: garmin, smashrun.")
        sys.exit(1)

    # Get next measurements
    last_sync = int(config.get(service,'last_sync')) if config.has_option(service, 'last_sync') else 0
    groups = client_nokia.get_measures(lastupdate=last_sync)
    types = dict(nokia.NokiaMeasureGroup.MEASURE_TYPES)

    if len(groups) == 0:
        print("Their is no new measurement to sync.")
        sys.exit(0);

    if service == 'garmin':

        next_sync = groups[-1].date.timestamp

        # Do not repeatidly sync the same value
        if next_sync == last_sync:
            print('Last measurement was already synced')
            sys.exit(0)

        # create fit file
        fit = FitEncoder_Weight()
        fit.write_file_info()
        fit.write_file_creator()
        fit.write_device_info(timestamp=next_sync)
        for m in groups:
            weight = m.get_measure(types['weight']);
            if weight:
                fit.write_weight_scale(timestamp=m.date.timestamp, weight=weight, percent_fat=m.get_measure(types['fat_ratio']),
                    percent_hydration=m.get_measure(types['hydration']), bone_mass=m.get_measure(types['bone_mass']), muscle_mass=m.get_measure(types['muscle_mass']))

        fit.finish()

        garmin = GarminConnect()
        session = garmin.login(config.get('garmin','username'), config.get('garmin','password'))
        r = garmin.upload_file(fit.getvalue(), session)
        if r:
            print("%d weights has been successfully updated to Garmin!" % (len(groups)))
            config.set('garmin','last_sync', str(next_sync))

    elif service == 'smashrun':

        for m in reversed(groups):
            t = types['weight']
            weight = m.get_measure(t)
            if weight:
                break

        print("Last weight from Nokia Health: %s kg taken at %s" % (weight, m.date))


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
    print("Available commands: setup, sync, sync-preview, last, userinfo, subscribe, unsubscribe, list_subscriptions")
    sys.exit(1)

# If Nokia API client was used in this session, get the token (might have been refreshed
if client_nokia:
    creds = client_nokia.get_credentials()    
    config.set('nokia', 'access_token', creds.access_token)
    config.set('nokia', 'token_expiry', creds.token_expiry)
    config.set('nokia', 'refresh_token', creds.refresh_token)
    

# Encode the Garmin password
if config.has_section('garmin'):
    if config.has_option('garmin', 'password'):
        config.set('garmin', 'password', base64.b64encode( config.get('garmin', 'password').encode('ascii') ).decode('ascii'))

with open(options.config, 'w') as f:
    config.write(f)
    f.close()

print("Config file saved to %s" % options.config)

sys.exit(0)
