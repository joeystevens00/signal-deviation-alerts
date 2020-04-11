import json

from pydantic import BaseModel as PyDanticBaseModel
from util import DB

from c import redis_handle

class BaseModel(PyDanticBaseModel):
    def to_file(self, path):
        with open(path, 'w') as f:
            json.dump(json.loads(self.json()), f)

    def save(self):
        dbo = DB(redis_handle(), model=self)
        dbo.save()
        return dbo

    def to_dict(self):
        """Fixes serialization of dict()"""
        d = json.loads(self.json(by_alias=True))
        return d

    def get_safe(self, v):
        try:
            return self.__getattribute__(v)
        except AttributeError:
            pass
