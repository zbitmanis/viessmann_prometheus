
import asyncio
import json
import jwt
import logging
import sys
import hashlib

from typing import Any, Dict
from pathlib import Path
from datetime import datetime, timezone
from .utils import now_ts


logger = logging.getLogger(__name__)

handler = logging.StreamHandler(sys.stdout)
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class TokenStore:
    path: Path
    access_token: str = ''
    access_updated_at: int = 0
    access_expires_in: int = 0 
    refresh_token: str = ''
    

    def __init__(self, path):
        self._lock = asyncio.Lock()
        if isinstance(path, Path):
            self.path = path
        else:
            self.path = Path(path)

    @staticmethod
    def md5(token:str):
        md5 = hashlib.md5(token.encode('utf-8')).hexdigest()
        return md5

    @staticmethod
    def is_token_expired(token: str, updated_at: int = 0,  min_ttl: int = 60) -> bool:
        result:bool = True

        md5: str = TokenStore.md5(token)

        if token: 
            decoded: dict = jwt.decode(token,  
                                       options={"verify_signature": False})
            exp = decoded.get("exp")

            logger.info(f'verifying access token issued: {updated_at} md5: {md5} - expires: {exp}')

            if exp is None:
                raise ValueError("access token does not contains exp claim")
            
            result = exp - min_ttl < now_ts()

        return result

    @classmethod 
    def token_refresh(cls, tokens: Dict[str,Any], old: Dict[str,Any], force: bool = False)->None:
        """
        Refresh local class token values 
        
        :param tokens:  tokens dictionary
        """
        old_access_updated_at = old.get('updated_at', 0)
        old_access_token: str = old.get('access_token')
        old_md5: str  = cls.md5(old_access_token)

        access_updated_at = tokens.get('updated_at', 0)
        access_expires_in = tokens.get('expires_in', 0)
        access_token: str = tokens.get('access_token')

        logger.info(f'initating access token update issued at:{old_access_updated_at} md5: {old_md5}')
        
        if access_token is not None:
            if force or (cls.is_token_expired(old_access_token, old_access_updated_at) and old_access_updated_at < access_updated_at):
                logger.info(f'updating local access token updated: {access_updated_at} expires:{access_expires_in}')
                cls.access_token = access_token
                cls.access_updated_at = access_updated_at
                cls.access_expires_in = access_expires_in
        else:
            cls.access_token = ''
            cls.access_updated_at = 0
            cls.access_expires_in = 0

        refresh_token: str = tokens.get('referesh_token')
        if refresh_token is not None:
            cls.refresh_token = refresh_token

    def load(self) -> Dict[str, Any]:
        """
        Load stored token from file and return as dictionary 
        If path does not exists return empty dictionary 
        The token can be stored within the file on the next token renewal 
        """
        old_store: dict = {
            'access_token': self.access_token,
            'updated_at': self.access_updated_at
        }
        
        if self.path.exists():
            result_json = json.loads(self.path.read_text())
            self.token_refresh(result_json, old_store)
            return result_json
        else: 
            return {}

    def save(self, store: Dict[str, Any]) -> None:
        """
        Save token as json file, update local values
        
        :param store: tokens dictionary 
        """
        old_store: dict = {
            'access_token': self.access_token,
            'updated_at': self.access_updated_at
        }
        self.token_refresh(store, old_store)
        self.path.write_text(json.dumps(store, indent=2, sort_keys=True))

        
