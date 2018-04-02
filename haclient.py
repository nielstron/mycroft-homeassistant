
from requests import get, post
from requests.exceptions import ConnectionError
from fuzzywuzzy import fuzz
import json
from _datetime import datetime

__author__ = 'robconnolly, btotharye, nielstron'

# Timeout time for HA requests
TIMEOUT = 10

class HomeAssistantClient(object):
    """A client for interacting with a home assistant server"""

    def __init__(self, host, password, portnum, ssl=False, verify=True):
        self.ssl = ssl
        self.verify = verify
        if portnum is None or portnum == 0:
            portnum = 8123
        if self.ssl:
            self.url = "https://%s:%d" % (host, portnum)
        else:
            self.url = "http://%s:%d" % (host, portnum)
        self.headers = {
            'x-ha-access': password,
            'Content-Type': 'application/json'
        }
    
    def _get(self, url):
        if self.ssl:
            return get(url, headers=self.headers,
                      verify=self.verify, timeout=TIMEOUT)
        else:
            return get(url, headers=self.headers,
                      timeout=TIMEOUT)
    
    def _post(self, url, data=None):
        if self.ssl:
            return post(url, headers=self.headers, verify=self.verify,
                        data=json.dumps(data), timeout=TIMEOUT)
        else:
            return post(url, headers=self.headers, data=json.dumps(data),
                        timeout=TIMEOUT)
    
    def find_entity(self, entity, types):
        try:
            req = self._get("%s/api/states" % self.url)
        except ConnectionError as e:
            return HomeAssistantEntity(error=e)

        if req.status_code == 200:
            # require a score above 50%
            best_score = 50
            best_entity = None
            for state in req.json():
                try:
                    if state['entity_id'].split(".")[0] in types:
                        # something like temperature outside
                        # should score on "outside temperature sensor"
                        # and repetitions should not count on my behalf
                        score = fuzz.token_sort_ratio(
                            entity,
                            state['attributes']['friendly_name'].lower())
                        if score > best_score:
                            best_score = score
                            best_entity = {
                                "id": state['entity_id'],
                                "dev_name": state['attributes']
                                ['friendly_name'],
                                "state": state['state']}
                        score = fuzz.token_sort_ratio(
                            entity,
                            state['entity_id'].lower())
                        if score > best_score:
                            best_score = score
                            best_entity = {
                                "id": state['entity_id'],
                                "dev_name": state['attributes']
                                ['friendly_name'],
                                "state": state['state']}
                except KeyError:
                    pass
            return HomeAssistantEntity(entity=best_entity)
        return HomeAssistantEntity(error=req.error)
   
    #
    # checking the entity attributes to be used in the response dialog.
    #
    def find_entity_attr(self, entity):
        try:
            req = self._get("%s/api/states/%s" % (self.url, entity))
        except ConnectionError as e:
            return HomeAssistantEntity(error=e)

        if req.status_code == 200:
            return HomeAssistantEntity(req.json())
        return HomeAssistantEntity(error=req.error)

    def execute_service(self, domain, service, data):
        return self._post("%s/api/services/%s/%s" % (self.url, domain, service),
                          data=data)

    def find_component(self, component):
        """Check if a component is loaded at the HA-Server"""
        req = self._get("%s/api/components" % self.url)

        if req.status_code == 200:
            return component in req.json()

    def engage_conversation(self, utterance):
        """Engage the conversation component at the Home Assistant server

        Attributes:
            utterance    raw text message to be processed
        Return:
            Dict answer by Home Assistant server
            { 'speech': textual answer,
              'extra_data': ...,
              'error': non-None if an error occured}
        """
        data = {
             "text": utterance
             }
        try:
            return self._post("%s/api/conversation/process" % (self.url),
                        data=json.dumps(data),
                        ).json()['speech']['plain']
        except ConnectionError as e:
            return {'speech': 
                        "An Error occurred while processing: {}".format(e),
                    'extra_data': None,
                    'error': e}


class HomeAssistantEntity(object):
    """
    An entity received by a Home Assistant server
    Attributes:
        entity_id    Entity id
        state        Entity state
        attributes   Entity attributes
        last_changed
        last_updated
        error        Error when retrieving this entity
        entity       Raw entity parsed from returned json
            If you use this attribute all other attributes except error will be
            ignored
    """
    
    def __init__(self, entity_id=None, state="unknown", attributes={},
                 last_changed=datetime.now, last_updated=datetime.now,
                 error=None, entity=None):
        if entity is None:
            self.entity_id = entity_id
            self.state = state
            self.attributes = attributes
            self.last_changed = last_changed
            self.last_updated = last_updated
        else:
            self.__dict__.update(entity)
        self.error = error

    def friendly_name(self):
        """Returns a suitable name to talk about the entity"""
        if 'friendly_name' in self.attributes.keys():
            return self.attributes['friendly_name']
        else:
            return self.entity_id
    
    def dict(self):
        """Return a dictionary similar to the JSON parsed from the API"""
        owndict = self.__dict__.clone()
        owndict['dev_name'] = self.dev_name()
        return owndict
    
    def get(self, attribute):
        return self.__dict__.get(attribute)