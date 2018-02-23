# nokia-to-garmin-weight
Get weight from Nokia Health update in Garmin Connect

![nokia-to-garmin-weight-logo](logo.png)

## Installation

1. Download / clone the repository.

2. Satisfy the following requirements:

    - Python 3.X
    - Python libraries: arrow, requests, requests-oauthlib
    
3. [Register](https://developer.health.nokia.com/partner/add) an application with Nokia Health and obtain a consumer key and secret.

## Usage

1. On first run you need to set-up your Nokia Health consumer key and secret:

        ./nokia-to-garmin-weight.py -k CONSUMER_KEY -s CONSUMER_SECRET last
        
2. Following the instructions and enter your oauth_verifier.

3. Verify that your last measurement group is being displayed and your Nokia credentials are saved to ```config.ini```.

4. Now register your Garmin Connect credentials and sync your last measurement (provide GC password when asked):

        ./nokia-to-garmin-weight.py -g user@example.com synclast
        
5. Repeate synchronization when new measurements are made:

        ./nokia-to-garmin-weight.py synclast
        
**Important** both Nokia Health API credentials and Garmin Connect credentials are stored in ```config.ini```. If this file is compromised your entire Garmin account and personal health data from both providers are at risk.
        
## Advanced

See ```./nokia-to-garmin-weight.py --help``` for more information.

## Notice

nokia-to-garmin-weight includes components the following open-source projects:

* ```fit.py``` from [ikasamah/withings-garmin](https://github.com/ikasamah/withings-garmin), MIT License (c) 2013 Masayuki Hamasaki, adapted for Python 3.
* ```garmin.py``` from [jaroslawhartman/withings-garmin-v2](https://github.com/jaroslawhartman/withings-garmin-v2), MIT License (c) 2013 Masayuki Hamasaki, adapted for Python 3.
* ```nokia.py``` from [python-nokia](https://github.com/orcasgit/python-nokia), MIT License (c) 2012 Maxime Bouroumeau-Fuseau, 2017 ORCAS, unmodified.
* ```sessioncache.py``` from [cpfair/tapiriik](https://github.com/cpfair/tapiriik/blob/187d1b97ce73cc35b5e2194eb4631ceff20499e3/tapiriik/services/sessioncache.py), Apache License 2.0, unmodified.
* ```smashrun.py``` from [campbellr/smashrun-client](https://github.com/campbellr/smashrun-client), Apache License 2.0, several fixes.

## Support

Please [open an issue](https://github.com/magnific0/nokia-to-garmin-weight/issues/new) for support.

## Contributing

Please contribute using [Github Flow](https://guides.github.com/introduction/flow/). Create a branch, add commits, and [open a pull request](https://github.com/magnific0/nokia-to-garmin-weight/compare/).
