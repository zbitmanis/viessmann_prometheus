

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import asyncio
import logging
import httpx

from .utils import now_ts
from .token_store import TokenStore


"""
curl -sS   -H "Authorization: Bearer ${VIESSMANN_ACCESS_TOKEN}"   -H "Accept: application/json"   "https://api.viessmann-climatesolutions.com/iot/v2/features/installations/${VIESSMANN_INSTALLATION_ID}/gateways/${VIESSMANN_GATEWAY_SERIAL}/devices/${VIESSMANN_DEVICE_ID}/features" | tee -a features.json
curl -sS   -H "Authorization: Bearer ${VIESSMANN_ACCESS_TOKEN}"   -H "Accept: application/json"   "https://api.viessmann-climatesolutions.com/iot/v1/equipment/installations?includeGateways=true" | jq .
curl -sS   -H "Authorization: Bearer ${VIESSMANN_ACCESS_TOKEN}"   -H "Accept: application/json"   "https://api.viessmann-climatesolutions.com/iot/v2/equipment/installations" | jq .
"""
class ViessmannClient:
    base_url: str
    token_store: TokenStore
    _status: dict = {}
    TIMEOUT = 20

    HEADERS = {
        'Accept': 'application/json',
        'Authorization': 'Bearer {}'
    }  

    REQUESTS = {
        'features': {
            'request': '/features/installations/{}/gateways/{}/devices/{}/features',
            'params': {}
            },
        'installations': {
            'request': '/equipment/installations',
            'params':{
                'includeGateways': 'true'
                }
            }
         }
    def __init__(self, base_url: str, token_store: TokenStore):
        self._status ={}
        self.base_url=base_url
        self.token_store=token_store

    def build_feature_request(self,
                      inst_id: int, 
                      gateway_serial: str,
                      device_id: int
                      ) ->Tuple[str,Dict[str,str]]:
        """
        Generate api request url for API feature 
        Returns tuple request and dictionary of params
        """
        feature_request: dict

        feature_request = self.REQUESTS.get('features')
        if feature_request is None:
            raise ValueError(f"Cant find the request settings for features")
        
        request = feature_request.get('request')
        
        if request is None:
            raise ValueError('Cant find the request settings for  {}, request {}'.format('features','request'))

        params = feature_request.get('params', {})

        # store = self.token_store.load()
        # str(httpx.URL(self.authorize_url).copy_merge_params(params))
        request = request.format(inst_id, gateway_serial, device_id)

        return request, params
    
    def build_installation_request(self) ->Tuple[str,Dict[str,str]]:
        """
        Generate api request url for API installations 
        Returns tuple request and dictionary of params
        """
        installation_request: dict[str, Any]
        
        installation_request = self.REQUESTS.get('installations')

        if installation_request is None:
            raise ValueError('Cant find the request settings for installations')
        request = installation_request.get('request')
        if request is None:
            raise ValueError('Cant find the request settings for installations: request')

        params = installation_request.get('params', {})

        # url = httpx.URL(self.base_url + request).copy_merge_params(params)
        return request, params
    
    async def fetch_features(self, 
                             inst_id: int, 
                             gateway_serial: str, 
                             device_id: int) -> Dict[str, Any]:
        """
        Implement: call Viessmann API and return list of features as json.
        """
        # raise NotImplementedError
        params: Dict[str, str]
        request: str
        
        # store = self.token_store.load()

        at = self.token_store.access_token
        # at = store.get('access_token')
        if not at:
            raise ValueError('No access_token stored')
        
        if self.token_store.is_access_expired(): 
            at_time:int = self.token_store.access_updated_at
            at_ttl:int = self.token_store.access_expires_in
            raise ValueError(f'Access token issued at:{at_time} with ttl:{at_ttl} is expired or invalid')

        
        headers = self.HEADERS
        headers['Authorization'] = headers['Authorization'].format(at)
        
        #ANCHOR - TBD add access token ttl validation and renewal section  

        request, params = self.build_feature_request(inst_id=inst_id,
                                                     gateway_serial=gateway_serial,
                                                     device_id=device_id)

        async with httpx.AsyncClient(base_url=self.base_url,
                                     timeout=self.TIMEOUT) as client:
            r = await client.get(
                request,
                headers=headers,
                params=params
            )

        if r.status_code != 200:
            #ANCHOR -  TBD add logging
            self._status["last_feature_request_error"] = {"reason": r.text, "time": now_ts()}
            print(f'Feature fetch failed at {now_ts()} with status code: {r.status_code} reason: {r.text}')
            raise ValueError(f"Feature fetch failed: {r.status_code}")

        result_json = r.json()
        return result_json

