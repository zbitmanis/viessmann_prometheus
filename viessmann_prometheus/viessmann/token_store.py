

import json

from typing import Any, Dict
from pathlib import Path
from .utils import now_ts

class TokenStore:
    MIN_TOKEN_TTL = 5
    path: Path
    access_token: str = ''
    access_updated_at: int = 0
    access_expires_in: int = 0 
    refresh_token: str = ''

    def __init__(self, path):
        if isinstance(path, Path):
            self.path = path
        else:
            self.path = Path(path)
    
    def is_access_valid(self)->bool:
        now = now_ts()
        return  self.access_token and now < (self.access_updated_at+ self.access_expires_in - self.MIN_TOKEN_TTL) 
     
    def local_refresh(self, tokens: Dict[str,Any])->None:
        """
        Refresh local class token values 
        
        :param tokens:  tokens dictionary
        """

        access_updated_at = tokens.get('updated_at', 0)
        access_expires_in = tokens.get('expires_in', 0)
        access_token: str = tokens.get('access_token')

        if access_token is not None:
            if  not self.is_access_valid() and self.access_updated_at < access_updated_at:
                print(f'updating local access token updated: {access_updated_at} expires:{access_expires_in}')
                self.access_token = access_token
                self.access_updated_at = access_updated_at
                self.access_expires_in = access_expires_in
        else:
            self.access_token = ''
            self.access_updated_at = 0
            self.access_expires_in = 0

        refresh_token: str = tokens.get('referesh_token')
        if refresh_token is not None:
            self.refresh_token = refresh_token

    def load(self) -> Dict[str, Any]:
        """
        Load stored token from file and return as dictionary 
        If path does not exists return empty dictionary 
        The token can be stored within the file on the next token renewal 
        """
        if self.path.exists():
            result_json = json.loads(self.path.read_text())
            self.local_refresh(result_json)
            return result_json
        else: 
            return {}

    def save(self, store: Dict[str, Any]) -> None:
        """
        Save token as json file, update local values
        
        :param store: tokens dictionary 
        """
        self.local_refresh(store)
        self.path.write_text(json.dumps(store, indent=2, sort_keys=True))

        
