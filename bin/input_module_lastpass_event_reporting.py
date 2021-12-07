
# encoding = utf-8

import re
import os
import sys
import time
import json
import copy
import requests
import datetime
import traceback
import pytz

LASTPASS_TIMEFORMAT = '%Y-%m-%d %H:%M:%S'
LP_CHECKPOINT_KEY = 'LastPass_reporting'
CMD_KEY = 'reporting'
STR_TSTART = 'time_start'
STR_TEND = 'time_end'
STR_TCURR = 'time_curr'

'''
    IMPORTANT
    Edit only the validate_input and collect_events functions.
    Do not edit any other part in this file.
    This file is generated only once when creating the modular input.
'''
'''
# For advanced users, if you want to create single instance mod input, uncomment this method.
def use_single_instance_mode():
    return True
'''


def validate_input(helper, definition):
    """Implement your own validation logic to validate the input stanza configurations"""
    # This example accesses the modular input variable
    # global_account = definition.parameters.get('global_account', None)
    # lastpass_api_url = definition.parameters.get('lastpass_api_url', None)
    # time_start = definition.parameters.get('time_start', None)
    url = definition.parameters.get('lastpass_api_url', None)
    if 'https://' in url:
        return
    # replace if http but not https
    elif 'http' in url and 'https://' not in url:
        helper.log_error(f'"HTTP" protocol not allowed. Please update for HTTPS.')
        raise ValueError(f'"HTTP" protocol not allowed. Please update for HTTPS.')
    elif '.' not in url:
        helper.log_error(f'URL submission invalid. Please validate domain.')
        raise ValueError(f'URL submission invalid. Please validate domain.')
    elif 'https://' not in url:
        # add proper url
        definition.parameters['lastpass_api_url'] = 'https://'+url

    time_start = definition.parameters.get(STR_TSTART, None)
    try:
        if str(time_start).isdigit():
            time_dt = datetime.datetime.fromtimestamp(int(time_start))

            diff = datetime.datetime.now() - time_dt
            # check for within last 4y or if time is ahead
            if diff.days > (365*4) or diff.days < 0:
                helper.log_warning(f'Validating time format. out of range. time_val="{time_start}"')
                raise ValueError(f'Validating time format. out of range. time_val="{time_start}"')
        elif time_start == None: # if not specified, just reset in input definition
            pass
        else:
            datetime.datetime.strptime(str(time_start), LASTPASS_TIMEFORMAT)
    except Exception as e:
        raise ValueError(f'{e.__class__.__name__}: LastPass http input configuration failed: {e}')
        helper.log_error(f'{e.__class__.__name__}: LastPass http input configuration failed: {e}')
        return None


def get_time_lp(time_val, tz):
    ''' return time value for date format suitable for lastpass API 
    @param time_val: epoch time or datetime object

    :return: '%Y-%m-%d %H:%M:%S'
    '''

    if isinstance(time_val, datetime.datetime):
        return time_val.strftime(LASTPASS_TIMEFORMAT)

    return datetime.datetime.fromtimestamp(int(time_val), tz).strftime(LASTPASS_TIMEFORMAT)


def check_datetime(val):
    '''
        verify time value is a datetime object
        @param val: time value
        @type val: datetime or other
    '''

    try:
        return isinstance(val, datetime.datetime)
    except (TypeError, ValueError):
        return False
        

def check_digit(val):
    '''
        verify time value is a digit for epoch format
        @param val: time value
        @type val: int or other
    '''

    try:
        check = int(val)
        return True
    except (TypeError, ValueError):
        return False
        

def check_float(val):
    '''
        verify time value is a float for epoch format
        @param val: time value
        @type val: float or other
    '''

    try:
        return float(str(val)) > 0
    except (TypeError, ValueError):
        return False


def prepare_time_value(helper, val, field_name):
    '''
        prepare the time value for consistent epoch-friendly format
        @param val: time value to be stored into checkpoint
        @type val: some format for time
        @param field_name: checkpoint field name
        @type field_name: str

        :return: formatted time value
    '''
    
    try:
        if check_digit(val):
            helper.log_debug(f'Verifying time value format. {field_name} is: DIGIT')
        elif check_datetime(val):
            helper.log_debug(f'Verifying time value format. {field_name} is: DATETIME')
            val = val.timestamp()
        elif float(str(val)):
            helper.log_debug(f'Verifying time value format. {field_name} is: FLOAT')
            val = float(str(val))
        else:
            raise Exception(f'Unknown value type for time format.')
    except Exception as e:
        raise IOError(f'Invalid time format for checkpointing LastPass activity input. {field_name}="{val}" type={type(val)} reason="{repr(e)}"')

    return str(val)
    

def save_checkpoint(helper, time_curr, time_start, time_end):
    ''' 
        update checkpoint with time value as epoch
        @param time_curr: epoch time or datetime object
        @type time_curr: datetime
        @param time_start: epoch time or datetime object
        @type time_start: datetime
        @param time_end: epoch time or datetime object
        @type time_end: datetime
    '''

    state_payload = {}

    try:
        state_payload[STR_TCURR] = prepare_time_value(helper, time_curr, STR_TCURR)
        state_payload[STR_TSTART] = prepare_time_value(helper, time_start, STR_TSTART)
        state_payload[STR_TEND] = prepare_time_value(helper, time_end, STR_TEND)

        helper.log_debug(f'Saving checkpoint. state_payload={repr(state_payload)}')
        helper.save_check_point(LP_CHECKPOINT_KEY, state_payload)
    except Exception as e:
        raise IOError(f'Save checkpoint failed. time_curr="{time_curr}" time_start="{time_start}" time_end="{time_end}" reason="{repr(e)}"')


def get_checkpoint(helper):
    ''' 
        extract checkpoint payload, which includes time value
        :return: epoch time or None
    '''

    # if checkpoint corrupted or not readable, consider empty
    try:
        state_payload = helper.get_check_point(LP_CHECKPOINT_KEY)
    except Exception as e:
        helper.log_warning(f'Loading checkpoint. Unable to load checkpoint. reason="{repr(e)}"') 
        return None

    helper.log_debug(f'checkpoint: type={type(state_payload)} value={repr(state_payload)}')
    # if nothing found, return empty
    if state_payload == None:
        helper.log_debug(f'checkpoint payload is empty. nothing to get.')
        return None

    # handle old checkpoint and just flush out other fields
    if check_digit(state_payload) or check_float(state_payload):
        helper.log_warning(f'Old checkpoint found. Pushing to new model with time start, end, and current values.')
        return None
        return {STR_TCURR: None, STR_TSTART: state_payload, STR_TEND: None}

    # validate if checkpoint payload of time values are formatted in float value for epoch
    try:
        if not (state_payload.get(STR_TCURR) and prepare_time_value(helper, state_payload.get(STR_TCURR), STR_TCURR)):
            raise Exception(f'valid time_curr field not found in checkpoint payload')
        if not (state_payload[STR_TSTART] and prepare_time_value(helper, state_payload[STR_TSTART], STR_TSTART)):
            raise Exception(f'valid time_start field not found in checkpoint payload')
        if not (state_payload[STR_TEND] and prepare_time_value(helper, state_payload[STR_TEND], STR_TEND)):
            raise Exception(f'valid time_end field not found in checkpoint payload')

    except Exception as e:
        helper.log_warning(f'Save checkpoint failed. time_curr=\"{state_payload.get(STR_TCURR)}\" time_start=\"{state_payload.get(STR_TSTART)}\" time_end=\"{state_payload.get(STR_TEND)}\" reason=\"{e}\"')
        #raise Exception(f'Save checkpoint failed. time_curr=\"{state_payload.get(STR_TCURR)}\" time_start=\"{state_payload.get(STR_TSTART)}\" time_end=\"{state_payload.get(STR_TEND)}\" reason=\"{e}\"')
        # return None
        return None
    

    helper.log_debug(f'Extracted checkpoint time values. time_curr=\"{state_payload.get(STR_TCURR)}\" time_start=\"{state_payload.get(STR_TSTART)}\" time_end=\"{state_payload.get(STR_TEND)}\"')
    return state_payload


def validate_checkpoint(payload_checkpoint):
    ''' evaluates if there's enough events have been collected from LastPass based on time range captured in checkpoint
        uses golden ratio as start time may not have events and curr cursor only captures from event timestamps
    @param payload_checkpoint: JSON checkpoint payload

    @return bool: captured enough events to consider complete
    '''

    # dynamically base acceptable range against start and end time range from checkpoint
    range_full = abs(float(payload_checkpoint.get(STR_TSTART)) - float(payload_checkpoint.get(STR_TEND)))
    range_threshold = range_full *.618

    return (abs(float(payload_checkpoint.get(STR_TCURR)) - float(payload_checkpoint.get(STR_TEND))) > range_threshold)


def get_time_dt(helper, time_val):
    ''' evaluates time format and returns datetime. None if error.
    @param time_val: timestamp value to check

    @return time_dt: datetime or None
    '''

    if not time_val:
        return None

    try:
        time_dt = None
        if check_digit(time_val):
            time_dt = datetime.datetime.fromtimestamp(int(time_val))
        elif check_float(time_val):
            time_dt = datetime.datetime.fromtimestamp(float(time_val))
        else:
            time_dt = datetime.datetime.strptime(str(time_val), LASTPASS_TIMEFORMAT)

    except Exception as e:
        helper.log_warning(f'Validating time format. Time conversion failed. time_val="{time_val}" reason="{e}"')
        return None

    diff = datetime.datetime.now() - time_dt
    # check for within last 4y or if time is ahead
    if diff.days > (365*4) or diff.days < 0:
        helper.log_warning(f'Validating time format. out of range. time_val="{time_val}"')
        return None

    return time_dt


def convert_time(time_val):
    ''' convert time to datetime
    @param time_val: epoch or YYYY-mm-dd HH:MM:SS format

    @return datetime
    '''
    try:
        if check_digit(time_val):
            temp = datetime.datetime.fromtimestamp(int(time_val))
        elif check_float(time_val):
            temp = datetime.datetime.fromtimestamp(float(time_val))
        else:
            temp = datetime.datetime.strptime(str(time_val), LASTPASS_TIMEFORMAT)
    except:
        return None

    return temp


def collect_events(helper, ew):
    """Implement your data collection logic here

    # The following examples get the arguments of this input.
    # Note, for single instance mod input, args will be returned as a dict.
    # For multi instance mod input, args will be returned as a single value.
    opt_global_account = helper.get_arg('global_account')
    opt_lastpass_api_url = helper.get_arg('lastpass_api_url')
    opt_time_start = helper.get_arg('time_start')
    # In single instance mode, to get arguments of a particular input, use
    opt_global_account = helper.get_arg('global_account', stanza_name)
    opt_lastpass_api_url = helper.get_arg('lastpass_api_url', stanza_name)
    opt_time_start = helper.get_arg('time_start', stanza_name)

    # get input type
    helper.get_input_type()

    # The following examples get input stanzas.
    # get all detailed input stanzas
    helper.get_input_stanza()
    # get specific input stanza with stanza name
    helper.get_input_stanza(stanza_name)
    # get all stanza names
    helper.get_input_stanza_names()

    # The following examples get options from setup page configuration.
    # get the loglevel from the setup page
    loglevel = helper.get_log_level()
    # get proxy setting configuration
    proxy_settings = helper.get_proxy()
    # get account credentials as dictionary
    account = helper.get_user_credential_by_username("username")
    account = helper.get_user_credential_by_id("account id")
    # get global variable configuration
    global_cid = helper.get_global_setting("cid")
    global_provhash = helper.get_global_setting("provhash")

    # The following examples show usage of logging related helper functions.
    # write to the log for this modular input using configured global log level or INFO as default
    helper.log("log message")
    # write to the log using specified log level
    helper.log_debug("log message")
    helper.log_info("log message")
    helper.log_warning("log message")
    helper.log_error("log message")
    helper.log_critical("log message")
    # set the log level for this modular input
    # (log_level can be "debug", "info", "warning", "error" or "critical", case insensitive)
    helper.set_log_level(log_level)

    # The following examples send rest requests to some endpoint.
    response = helper.send_http_request(url, method, parameters=None, payload=None,
                                        headers=None, cookies=None, verify=True, cert=None,
                                        timeout=None, use_proxy=True)
    # get the response headers
    r_headers = response.headers
    # get the response body as text
    r_text = response.text
    # get response body as json. If the body text is not a json string, raise a ValueError
    r_json = response.json()
    # get response cookies
    r_cookies = response.cookies
    # get redirect history
    historical_responses = response.history
    # get response status code
    r_status = response.status_code
    # check the response status, if the status is not sucessful, raise requests.HTTPError
    response.raise_for_status()

    # The following examples show usage of check pointing related helper functions.
    # save checkpoint
    helper.save_check_point(key, state)
    # delete checkpoint
    helper.delete_check_point(key)
    # get checkpoint
    state = helper.get_check_point(key)

    # To create a splunk event
    helper.new_event(data, time=None, host=None, index=None, source=None, sourcetype=None, done=True, unbroken=True)
    """

    '''
    # The following example writes a random number as an event. (Multi Instance Mode)
    # Use this code template by default.
    import random
    data = str(random.randint(0,100))
    event = helper.new_event(source=helper.get_input_type(), index=helper.get_output_index(), sourcetype=helper.get_sourcetype(), data=data)
    ew.write_event(event)
    '''

    '''
    # The following example writes a random number as an event for each input config. (Single Instance Mode)
    # For advanced users, if you want to create single instance mod input, please use this code template.
    # Also, you need to uncomment use_single_instance_mode() above.
    import random
    input_type = helper.get_input_type()
    for stanza_name in helper.get_input_stanza_names():
        data = str(random.randint(0,100))
        event = helper.new_event(source=input_type, index=helper.get_output_index(stanza_name), sourcetype=helper.get_sourcetype(stanza_name), data=data)
        ew.write_event(event)
    '''

    rest_url = helper.get_arg('lastpass_api_url')
    time_zone = helper.get_arg('time_zone')
    local_tz = pytz.timezone(time_zone)
    tz = local_tz.tzname(datetime.datetime.now())

    if not rest_url:
        rest_url = 'https://lastpass.com/enterpriseapi.php'
    # pre-fix domain to proper URL
    elif 'https://' not in rest_url:
        rest_url = f'https://{rest_url}'

    # expected time format: epoch
    payload_checkpoint = get_checkpoint(helper)

    # expected time format: datetime
    time_start = get_time_dt(helper, helper.get_global_setting(STR_TSTART))
    time_end = None
    time_now = datetime.datetime.now(tz=local_tz)

    if time_start:
        time_start = time_start.astimezone(local_tz)
    
    helper.log_debug(f'LastPass parameter check: rest_url={rest_url} time_checkpoint={repr(payload_checkpoint)} time_start="{time_start}" time_zone="{time_zone}"')
    headers = {}

    # build data params
    data = {}
    data['data'] = {}
    data['cid'] = helper.get_global_setting('cid')
    data['provhash'] = helper.get_global_setting('provhash')
    data['cmd'] = CMD_KEY
    data['apiuser'] = 'splunk.collector'
    data['user'] = 'allusers'

    ''' algorithm w checkpointing:
        no time input and no checkpoint => last 24h
        no time input and checkpoint exists => valid checkpoint time
        time input and no checkpoint => time input
        time input and checkpoint both set => valid checkpoint time

        for valid checkpoint time, need to review checkpoint time values:
        if curr approx eq to start time, successful collection
            set new start time as checkpoint end
            set new end time as now
        if there's gap from collecting full checkpoint time range:
            SKIP gap and flag
            set new start time as checkpoint end
            set new end time as now
    '''

    time_default = (time_now - datetime.timedelta(days=1)).replace(microsecond=0)
    start = end = None

    # validate checkpoint entries
    if payload_checkpoint:
        if not validate_checkpoint(payload_checkpoint):
            # TODO won't do anything with the identified data gap for now, just emit warning message
            helper.log_error(f'Checkpoint validation error: based on checkpoint data, data collection for events did not complete.' \
                f'time_start=\"{payload_checkpoint.get(STR_TSTART)}\" time_end=\"{payload_checkpoint.get(STR_TEND)}\" curr_time=\"{payload_checkpoint.get(STR_TCURR)}\"')
            chk_start_gap = get_time_dt(helper, payload_checkpoint[STR_TSTART])
            chk_end_gap = get_time_dt(helper, payload_checkpoint[STR_TCURR])

        # prepare to collect from latest successful event time based from checkpoint        
        chk_start = get_time_dt(helper, payload_checkpoint[STR_TEND]).astimezone(local_tz) + datetime.timedelta(seconds=1)
        chk_end = time_now

    if not time_start and not payload_checkpoint:
        helper.log_debug(f'time_start check: not time_start and not payload_checkpoint')
        # set earliest time for collection = -24h
        time_start = time_default

    elif not time_start and payload_checkpoint:
        # increment to collect after last checkpoint timestamp
        # WARNING: may lose events if happened at the same per second as the last collected event but wasn't collected in a previous pull
        time_start = chk_start
        end = chk_end
        helper.log_debug(f'time_start check: not time_start and payload_checkpoint')

    elif time_start and not payload_checkpoint:
        helper.log_debug(f'time_start check: time_start and not payload_checkpoint')
        # use specified time input
        pass

    # force collection from last known collected event
    elif (time_start and payload_checkpoint) and (payload_checkpoint.get(STR_TCURR) - time_start) > 0:
        helper.log_debug(f'time_start check: (time_start and payload_checkpoint) and (payload_checkpoint - time_start) > 0')
        time_start = chk_start
        end = chk_end

    else:
        time_start = time_default

    # increase interval in case backfill is extensive
    diff = time_now - time_start
    # increase increment for pull by date if a large range
    day_incr = 1 if diff.days < 7 else 3

    if day_incr > 1:
        helper.log_info(f'LastPass event report collection. large date range. start="{time_start}"\tend="{time_now}"')

    for i in range(0, diff.days+1, day_incr):
        # need to update start time for multiple pulls
        start = time_start + datetime.timedelta(days=i) if start is None else time_start
        end = start + datetime.timedelta(days=day_incr) - datetime.timedelta(seconds=1) if end is None else end
        end = time_now if time_now < end else end
        event_time = None

        # update query dates
        data['data']['from'] = get_time_lp(start, local_tz)
        data['data']['to'] = get_time_lp(end, local_tz)

        helper.log_debug(f'LastPass event report collection. Tracking event pulling: time_start=\"{data["data"]["from"]}\" time_end=\"{data["data"]["to"]}\"')

        try:
            resp_ev = requests.post(rest_url, headers=headers, data=json.dumps(data))
            
            if resp_ev.status_code != 200:
                helper.log_exception(f'LastPass event report collection. request data failed.')                
            elif re.search(r"(Authorization Error)", resp_ev.text):
                helper.log_exception(f'LastPass event report collection. request data failed. 401: Unauthorized. Verify cid/provhash.')

            resp_ev_json = resp_ev.json()

            if 'OK' not in resp_ev_json['status']:
                helper.log_error(f'LastPass event report collection. REST call successful, but query is bad. Validate request params. Terminating script')
                sys.exit(1)
            else:
                helper.log_debug(f'LastPass event report collection. REST response dump check: status={resp_ev_json.get("status")} next={str(resp_ev_json.get("next"))} data_count={len(resp_ev_json.get("data"))}')
            
            chk_ptr = 0

            # WARNING: data is returned most recent or latest (Event1) to oldest or earliest (Event<Max>)
            for ev_id in resp_ev_json['data']:

                ev_payload = copy.deepcopy(resp_ev_json['data'][ev_id])

                # add additional fields for better event data quality
                ev_payload['event_id'] = ev_id

                # capture event time from lp event
                event_time = convert_time(ev_payload['Time'])

                # add timezone to data event for tracking
                ev_payload['Time'] += f" {tz}"
                ev_payload['time_zone'] = f"{time_zone}"

                # if no proper timestamp extracted from event, default to current
                # if timestamp has milliseconds, then extraction unsuccessful as lastpass limited to seconds
                # need to convert to UTC as Splunk doesn't recognize non-UTC timezone for data collection via modinput
                if not event_time:
                    event_time = datetime.datetime.now(tz=local_tz).timestamp()
                else:
                    event_time = local_tz.localize(event_time).timestamp()
                    # .strftime('%s.%f') will not properly adjust for timezone

                ev_payload['time_collected'] = datetime.datetime.now(tz=local_tz).timestamp()
                ev_payload['time_epoch'] = float(event_time)

                event = helper.new_event(data=json.dumps(ev_payload), time=float(event_time), source=helper.get_input_type(), index=helper.get_output_index(), sourcetype=helper.get_sourcetype())
                ew.write_event(event)

                # checkpoint timestamp every 1000 messages
                chk_ptr += 1
                if chk_ptr % 1000 == 0:
                    save_checkpoint(helper, event_time, time_start, time_now)
                    helper.log_debug(f'LastPass event report collection. Updating checkpoint to date: chk_ptr={chk_ptr} time_start=\"{data["data"]["from"]}\" time_end=\"{data["data"]["to"]}\" curr_time={event_time}')

            # checkpoint finally when done
            if not resp_ev_json.get('next'):
                helper.log_debug(f'LastPass event report collection. Updating checkpoint to date: time_start=\"{data["data"]["from"]}\" time_end=\"{data["data"]["to"]}\" curr_time={event_time} chk_ptr={chk_ptr}')
                if chk_ptr:
                    save_checkpoint(helper, event_time, time_start, time_now)

            # iterate time cursor
            if type(event_time) is datetime.datetime:
                time_start = event_time
            else:
                time_start = get_time_dt(helper, event_time)
            helper.log_debug(f'LastPass event report collection. Updating time cursor time_curr={event_time} chk_ptr={chk_ptr}')

        except Exception as e:
            helper.log_critical(f'LastPass event report collection. Error in forwarding data: {traceback.format_exc()}')
            raise e                
