
"""
curl -sS   -H "Authorization: Bearer ${VIESSMANN_ACCESS_TOKEN}"   -H "Accept: application/json"   "https://api.viessmann-climatesolutions.com/iot/v1/equipment/installations?includeGateways=true" | jq .
"""

from typing import Any, Dict, Tuple

import logging
import httpx

from .utils import now_ts
from .token_store import TokenStore

logger = logging.getLogger(__name__)

class ViessmannClient:
    base_url: str
    token_store: TokenStore
    _status: Dict[str, Any] = {}
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
            'params': {
                'includeGateways': 'true'
                }
            }
         }

    def __init__(self, base_url: str, token_store: TokenStore):
        self._status = {}
        self.base_url = base_url
        self.token_store = token_store

    def build_feature_request(self,
                      inst_id: int, 
                      gateway_serial: str,
                      device_id: int
                      ) ->Tuple[str,Dict[str,str]]:
        """
        Generate api request url for API feature 
        Returns tuple request and dictionary of params
        """

        feature_request = self.REQUESTS.get('features')
        if feature_request is None:
            raise ValueError(f"Cant find the request settings for features")
        
        request = feature_request.get('request')
        
        if request is None:
            raise ValueError('Cant find the request settings for  {}, request {}'.format('features','request'))

        params: dict = feature_request.get('params', {})
        request: dict = request.format(inst_id, gateway_serial, device_id)

        return request, params
    
    def build_installation_request(self) ->Tuple[str,Dict[str,str]]:
        """
        Generate api request url for API installations 
        Returns tuple request and dictionary of params
        """
        installation_request = self.REQUESTS.get('installations')

        if installation_request is None:
            raise ValueError('Cant find the request settings for installation')
        
        request = installation_request.get('request')
        if request is None:
            raise ValueError('Cant find the request settings for installation: request')

        params = installation_request.get('params', {})

        return request, params
    
    async def fetch_features(self, 
                             inst_id: int, 
                             gateway_serial: str, 
                             device_id: int) -> Dict[str, Any]:
        """
        Call Viessmann API and return list of features as json.
        """
        params: Dict[str, str]
        request: str
        
        token = self.token_store.access_token
        
        if not token:
            raise ValueError('No access_token stored')
        
        if self.token_store.is_token_expired(token): 
            at_time: int = self.token_store.access_updated_at
            at_ttl: int = self.token_store.access_expires_in
            md5: str = self.token_store.md5(token)
            raise ValueError(f'Access token issued at:{at_time} md5: {md5}'
                             f'with ttl:{at_ttl} is expired or invalid')

        headers = self.HEADERS.copy()
        headers['Authorization'] = headers['Authorization'].format(token)
        
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
            self._status["last_feature_request_error"] = {"reason": r.text, "time": now_ts()}
            raise ValueError(f"Feature fetch failed: {r.status_code}: {r.text}")

        result_json = r.json()
        return result_json
