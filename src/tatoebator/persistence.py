# TODO wait, this turns tuples into lists
#  we'll probably just have to write our on crappy serializer at some point
#  add support for a little bit of recursion

import json
import os
from dataclasses import dataclass, is_dataclass, asdict as dataclass_asdict
from inspect import signature, currentframe
from json import JSONDecodeError
from typing import List, Any, Optional, Tuple, Dict, Union, Protocol

_BASIC_TYPES = (str, int, float, bool) #+NoneType (not in 3.9...?)
_COLLECTION_TYPES = (set, dict, list, tuple)
_ALL_DEFAULT_TYPES = _BASIC_TYPES + _COLLECTION_TYPES
_ANY_DEFAULT_TYPE = Union[_ALL_DEFAULT_TYPES]


class _EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if is_dataclass(o):
            data = dataclass_asdict(o)
            # class name goes in a reserved attr
            data["__dataclass_name__"] = o.__class__.__name__
            return data
        return super().default(o)


class _EnhancedJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        if "__dataclass_name__" in obj:
            cls_name = obj.pop("__dataclass_name__")
            # this is very silly but it will work
            caller_frame = currentframe()
            try:
                while cls_name not in caller_frame.f_globals:
                    caller_frame = caller_frame.f_back
            except:
                return obj
            cls = caller_frame.f_globals.get(cls_name, None)
            if cls and is_dataclass(cls):
                return cls(**obj)
        return obj


def _verify_jsonifiable(obj: Any, record: Optional[List[str]]) -> bool:
    if isinstance(obj, _BASIC_TYPES) or obj is None:
        return True
    elif isinstance(obj, dict):
        return (
            all((_verify_jsonifiable(item, record) for item in obj.keys()))
            and all((_verify_jsonifiable(item, record) for item in obj.values()))
        )
    elif is_dataclass(obj):
        return _verify_jsonifiable(dataclass_asdict(obj), record)
    elif isinstance(obj, _COLLECTION_TYPES):
        return all((_verify_jsonifiable(item, record) for item in obj))
    else:
        if record is not None:
            record.append(type(obj))
        return False


class Persistable(Protocol):

    default_filepath = None
    """
    persists only the attributes which have the same name as params to __init__

    in principle should only be used for classes that 'look like' dataclasses (or are dataclasses), e.g.

    class Person:
        def __init__(self, name: str, age: int):
            self.name = name
            self.age = age
            ...

        ...

    -> Person.load will create a file storing name and age
    """
    def _jsonify(self) -> Tuple[str, Dict]:
        attr_dict = {attr_name: getattr(self, attr_name) for attr_name in self._get_init_params()}
        unjsonifiable_types = []
        if not _verify_jsonifiable(attr_dict, unjsonifiable_types):
            raise Exception(f"Attempted to jsonify an instance of {self.__class__.__name__} with non-jsonifiable types in its attributes: {unjsonifiable_types}")
        return (self.__class__.__name__, attr_dict)

    @classmethod
    def _get_init_params(cls) -> List[str]:
        init_signature = signature(cls.__init__)
        if any((param.startswith("*") for param in map(str, init_signature.parameters.values()))):
            raise Exception("Attempted to load Persistable class from json but __init__ has wildcard parameters")
        return list(init_signature.parameters.keys())[1:]  # remove 'self'

    @classmethod
    def _from_jsonified(cls, json_data: Tuple[str, Dict]):
        name, attr_data = json_data
        if name != cls.__name__:
            raise Exception(f"Attempted to load a saved instance of {name} into an instance of {cls.__name__}")
        saved_attr_names = list(attr_data.keys())
        class_attr_names = cls._get_init_params()
        different_attr_names = set(saved_attr_names) ^ set(class_attr_names)
        if different_attr_names:
            raise Exception(f"Attempted to load a saved instance of {name}, but saved attributes do not match with class attributes. Differences: {different_attr_names}")
        init_attrs = [attr_data[attr_name] for attr_name in class_attr_names]
        return cls(*init_attrs)

    # would be good to use json here but best to preserve information about what is and isn't a tuple

    def save(self, filepath: Optional[str] = None):
        filepath = filepath or self.default_filepath
        if filepath is None:
            raise Exception("Need to provide Persistable.save with a filepath (or the class with a default filepath)")
        with open(filepath, 'w') as f:
            f.write(json.dumps(self._jsonify(), cls=_EnhancedJSONEncoder))

    @classmethod
    def load(cls, filepath: Optional[str] = None):
        filepath = filepath or cls.default_filepath
        if filepath is None:
            raise Exception("Need to provide Persistable.load with a filepath (or the class with a default filepath)")
        with open(filepath, 'r') as f:
            try:
                json_data = json.loads(f.read(), cls=_EnhancedJSONDecoder)
            except JSONDecodeError:
                raise Exception(f"Attempted to read {cls.__name__} object from {filepath} but data was corrupted")
            return cls._from_jsonified(json_data)


class PossiblyEmptyPersistable(Persistable, Protocol):

    @classmethod
    def empty(cls):
        ...

    @classmethod
    def load_or_create(cls):
        if os.path.exists(cls.default_filepath):
            return cls.load()
        else:
            return cls.empty()

