# -*- coding: utf-8 -*-

from sessioncache import SessionCache
from datetime import datetime, timedelta
import urllib.request
import datetime
import requests
import re
import sys
import json

# {{{
# Exception definitions used below from tapiriik/tapiriik/services/api.py
# https://github.com/cpfair/tapiriik/blob/master/LICENSE
class ServiceExceptionScope:
    Account = "account"
    Service = "service"
    # Unlike Account and Service-level blocking exceptions, these are implemented via ActivityRecord.FailureCounts
    # Eventually, all errors might be stored in ActivityRecords
    Activity = "activity"

class ServiceException(Exception):
    def __init__(self, message, scope=ServiceExceptionScope.Service, block=False, user_exception=None, trigger_exhaustive=True):
        Exception.__init__(self, message)
        self.Message = message
        self.UserException = user_exception
        self.Block = block
        self.Scope = scope
        self.TriggerExhaustive = trigger_exhaustive

    def __str__(self):
        return self.Message + " (user " + str(self.UserException) + " )"

class ServiceWarning(ServiceException):
    pass

class APIException(ServiceException):
    pass

class APIWarning(ServiceWarning):
    pass

# Theoretically, APIExcludeActivity should actually be a ServiceException with block=True, scope=Activity
# It's on the to-do list.

class APIExcludeActivity(Exception):
    def __init__(self, message, activity=None, activity_id=None, permanent=True, user_exception=None):
        Exception.__init__(self, message)
        self.Message = message
        self.Activity = activity
        self.ExternalActivityID = activity_id
        self.Permanent = permanent
        self.UserException = user_exception

    def __str__(self):
        return self.Message + " (activity " + str(self.ExternalActivityID) + ")"

class UserExceptionType:
    # Account-level exceptions (not a hardcoded thing, just to keep these seperate)
    Authorization = "auth"
    RenewPassword = "renew_password"
    Locked = "locked"
    AccountFull = "full"
    AccountExpired = "expired"
    AccountUnpaid = "unpaid" # vs. expired, which implies it was at some point function, via payment or trial or otherwise.
    NonAthleteAccount = "non_athlete_account" # trainingpeaks

    # Activity-level exceptions
    FlowException = "flow"
    Private = "private"
    NoSupplier = "nosupplier"
    NotTriggered = "notrigger"
    Deferred = "deferred" # They've instructed us not to synchronize activities for some time after they complete
    PredatesWindow = "predates_window" # They've instructed us not to synchronize activities before some date
    RateLimited = "ratelimited"
    MissingCredentials = "credentials_missing" # They forgot to check the "Remember these details" box
    NotConfigured = "config_missing" # Don't think this error is even possible any more.
    StationaryUnsupported = "stationary"
    NonGPSUnsupported = "nongps"
    TypeUnsupported = "type_unsupported"
    InsufficientData = "data_insufficient" # Some services demand more data than others provide (ahem, N+)
    DownloadError = "download"
    ListingError = "list" # Cases when a service fails listing, so nothing can be uploaded to it.
    UploadError = "upload"
    SanityError = "sanity"
    Corrupt = "corrupt" # Kind of a scary term for what's generally "some data is missing"
    Untagged = "untagged"
    LiveTracking = "live"
    UnknownTZ = "tz_unknown"
    System = "system"
    Other = "other"

class UserException:
    def __init__(self, type, extra=None, intervention_required=False, clear_group=None):
        self.Type = type
        self.Extra = extra # Unimplemented - displayed as part of the error message.
        self.InterventionRequired = intervention_required # Does the user need to dismiss this error?
        self.ClearGroup = clear_group if clear_group else type # Used to group error messages displayed to the user, and let them clear a group that share a common cause.

class LoginSucceeded(Exception):
    pass

class LoginFailed(Exception):
    pass

# }}}


class GarminConnect(object):
    LOGIN_URL = 'https://connect.garmin.com/signin'
    UPLOAD_URL = 'https://connect.garmin.com/modern/proxy/upload-service/upload/.fit'
    
    _sessionCache = SessionCache(lifetime=timedelta(minutes=30), freshen_on_get=True)
    
    def create_opener(self, cookie):
        this = self
        class _HTTPRedirectHandler(urllib.request.HTTPRedirectHandler):
            def http_error_302(self, req, fp, code, msg, headers):
                if req.get_full_url() == this.LOGIN_URL:
                    raise LoginSucceeded
                return urllib.request.HTTPRedirectHandler.http_error_302(self, req, fp, code, msg, headers)
        return urllib.request.build_opener(_HTTPRedirectHandler, urllib.request.HTTPCookieProcessor(cookie))            
        
    ##############################################
    # From https://github.com/cpfair/tapiriik
    
    def _get_session(self, record=None, email=None, password=None):
        session = requests.Session()
        
        # JSIG CAS, cool I guess.
        # Not quite OAuth though, so I'll continue to collect raw credentials.
        # Commented stuff left in case this ever breaks because of missing parameters...
        data = {
            "username": email,
            "password": password,
            "_eventId": "submit",
            "embed": "true",
            # "displayNameRequired": "false"
        }
        params = {
            "service": "https://connect.garmin.com/modern",
            "redirectAfterAccountLoginUrl": "http://connect.garmin.com/modern",
            "redirectAfterAccountCreationUrl": "http://connect.garmin.com/modern",
            # "webhost": "olaxpw-connect00.garmin.com",
            "clientId": "GarminConnect",
            "gauthHost": "https://sso.garmin.com/sso",
            # "rememberMeShown": "true",
            # "rememberMeChecked": "false",
            "consumeServiceTicket": "false",
            # "id": "gauth-widget",
            # "embedWidget": "false",
            # "cssUrl": "https://static.garmincdn.com/com.garmin.connect/ui/src-css/gauth-custom.css",
            # "source": "http://connect.garmin.com/en-US/signin",
            # "createAccountShown": "true",
            # "openCreateAccount": "false",
            # "usernameShown": "true",
            # "displayNameShown": "false",
            # "initialFocus": "true",
            # "locale": "en"
        }
        
        # I may never understand what motivates people to mangle a perfectly good protocol like HTTP in the ways they do...
        preResp = session.get("https://sso.garmin.com/sso/login", params=params)
        if preResp.status_code != 200:
            raise APIException("SSO prestart error %s %s" % (preResp.status_code, preResp.text))
            
        ssoResp = session.post("https://sso.garmin.com/sso/login", params=params, data=data, allow_redirects=False)
        if ssoResp.status_code != 200 or "temporarily unavailable" in ssoResp.text:
            raise APIException("SSO error %s %s" % (ssoResp.status_code, ssoResp.text))

        if ">sendEvent('FAIL')" in ssoResp.text:
            raise APIException("Invalid login", block=True, user_exception=UserException(UserExceptionType.Authorization, intervention_required=True))
        if ">sendEvent('ACCOUNT_LOCKED')" in ssoResp.text:
            raise APIException("Account Locked", block=True, user_exception=UserException(UserExceptionType.Locked, intervention_required=True))

        if "renewPassword" in ssoResp.text:
            raise APIException("Reset password", block=True, user_exception=UserException(UserExceptionType.RenewPassword, intervention_required=True))

        # self.print_cookies(cookies=session.cookies)

        # ...AND WE'RE NOT DONE YET!
        
        gcRedeemResp = session.get("https://connect.garmin.com/modern", allow_redirects=False)
        if gcRedeemResp.status_code != 302:
            raise APIException("GC redeem-start error %s %s" % (gcRedeemResp.status_code, gcRedeemResp.text))

        url_prefix = "https://connect.garmin.com"

        # There are 6 redirects that need to be followed to get the correct cookie
        # ... :(
        max_redirect_count = 7
        current_redirect_count = 1
        while True:
            url = gcRedeemResp.headers["location"]

            # Fix up relative redirects.
            if url.startswith("/"):
                url = url_prefix + url
            url_prefix = "/".join(url.split("/")[:3])
            gcRedeemResp = session.get(url, allow_redirects=False)

            if current_redirect_count >= max_redirect_count and gcRedeemResp.status_code != 200:
                raise APIException("GC redeem %d/%d error %s %s" % (current_redirect_count, max_redirect_count, gcRedeemResp.status_code, gcRedeemResp.text))
            if gcRedeemResp.status_code == 200 or gcRedeemResp.status_code == 404:
                break
            current_redirect_count += 1
            if current_redirect_count > max_redirect_count:
                break

        self._sessionCache.Set(record.ExternalID if record else email, session.cookies)
        
        # self.print_cookies(session.cookies)

        return session  

    def print_cookies(self, cookies):
            print("Cookies")
            
            for key, value in cookies.items():
                print("Key: " + key + ", " + value)

    def login(self, username, password):

        session = self._get_session(email=username, password=password)
        try:
            res = session.get("https://connect.garmin.com/modern")
            
            userdata_json_str = re.search(r"VIEWER_SOCIAL_PROFILE\s*=\s*JSON\.parse\((.+)\);$", res.text, re.MULTILINE).group(1)
            userdata = json.loads(json.loads(userdata_json_str))
            GCusername = userdata["displayName"]
        except Exception as e:
            raise APIException("Unable to retrieve username: %s" % e, block=True, user_exception=UserException(UserExceptionType.Authorization, intervention_required=True))
            
        sys.stderr.write('Garmin Connect User Name: ' + GCusername + '\n')    
        
        if not len(GCusername):
            raise APIException("Unable to retrieve username", block=True, user_exception=UserException(UserExceptionType.Authorization, intervention_required=True))
        return (session)

    def upload_file(self, f, session):
        files = {"data": ("withings.fit", f)}

        res = session.post(self.UPLOAD_URL,
                           files=files,
                           headers={"nk": "NT"}) 

        try:
            resp = res.json()["detailedImportResult"]
        except ValueError:
            if(res.status_code == 204):   # HTTP result 204 - "no content"
                sys.stderr.write('No data to upload, try to use --fromdate and --todate\n')
            else:
                print("Bad response during GC upload: " + str(res.status_code))
                raise APIException("Bad response during GC upload: %s %s" % (res.status_code, res.text))

        return (res.status_code == 200 or res.status_code == 201 or res.status_code == 204)

