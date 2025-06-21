"""
GATF Serialization Utilities

This module provides serialization and deserialization functionality
for various data types used within the GATF framework.
"""

import json
import pickle
import yaml
import msgpack
import datetime
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Union, Optional, Type, Callable
from enum import Enum
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict, is_dataclass


class SerializationError(Exception):
    """Raised when serialization/deserialization fails"""
    pass


class SerializationFormat(Enum):
    """Supported serialization formats"""
    JSON = "json"
    YAML = "yaml"
    PICKLE = "pickle"
    MSGPACK = "msgpack"


class GATFJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for GATF data types"""
    
    def default(self, obj):
        """Handle custom data types"""
        # Handle datetime objects
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        
        # Handle UUID objects
        if isinstance(obj, uuid.UUID):
            return str(obj)
        
        # Handle Decimal objects
        if isinstance(obj, Decimal):
            return float(obj)
        
        # Handle Path objects
        if isinstance(obj, Path):
            return str(obj)
        
        # Handle numpy arrays
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        
        # Handle pandas DataFrames
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')
        
        # Handle pandas Series
        if isinstance(obj, pd.Series):
            return obj.to_dict()
        
        # Handle Enum objects
        if isinstance(obj, Enum):
            return obj.value
        
        # Handle dataclasses
        if is_dataclass(obj):
            return asdict(obj)
        
        # Handle sets
        if isinstance(obj, set):
            return list(obj)
        
        # Handle bytes
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        
        # Default to string representation
        try:
            return str(obj)
        except:
            return super().default(obj)


def serialize(
    data: Any,
    format: Union[SerializationFormat, str] = SerializationFormat.JSON,
    **kwargs
) -> bytes:
    """
    Serialize data to bytes using specified format
    
    Args:
        data: Data to serialize
        format: Serialization format
        **kwargs: Additional arguments for the serializer
    
    Returns:
        Serialized data as bytes
    """
    if isinstance(format, str):
        format = SerializationFormat(format)
    
    try:
        if format == SerializationFormat.JSON:
            return _serialize_json(data, **kwargs)
        elif format == SerializationFormat.YAML:
            return _serialize_yaml(data, **kwargs)
        elif format == SerializationFormat.PICKLE:
            return _serialize_pickle(data, **kwargs)
        elif format == SerializationFormat.MSGPACK:
            return _serialize_msgpack(data, **kwargs)
        else:
            raise SerializationError(f"Unsupported format: {format}")
    except Exception as e:
        raise SerializationError(f"Serialization failed: {str(e)}")


def deserialize(
    data: bytes,
    format: Union[SerializationFormat, str] = SerializationFormat.JSON,
    **kwargs
) -> Any:
    """
    Deserialize data from bytes using specified format
    
    Args:
        data: Serialized data
        format: Serialization format
        **kwargs: Additional arguments for the deserializer
    
    Returns:
        Deserialized data
    """
    if isinstance(format, str):
        format = SerializationFormat(format)
    
    try:
        if format == SerializationFormat.JSON:
            return _deserialize_json(data, **kwargs)
        elif format == SerializationFormat.YAML:
            return _deserialize_yaml(data, **kwargs)
        elif format == SerializationFormat.PICKLE:
            return _deserialize_pickle(data, **kwargs)
        elif format == SerializationFormat.MSGPACK:
            return _deserialize_msgpack(data, **kwargs)
        else:
            raise SerializationError(f"Unsupported format: {format}")
    except Exception as e:
        raise SerializationError(f"Deserialization failed: {str(e)}")


def _serialize_json(data: Any, **kwargs) -> bytes:
    """Serialize to JSON"""
    json_str = json.dumps(
        data,
        cls=GATFJSONEncoder,
        ensure_ascii=False,
        **kwargs
    )
    return json_str.encode('utf-8')


def _deserialize_json(data: bytes, **kwargs) -> Any:
    """Deserialize from JSON"""
    json_str = data.decode('utf-8')
    return json.loads(json_str, **kwargs)


def _serialize_yaml(data: Any, **kwargs) -> bytes:
    """Serialize to YAML"""
    yaml_str = yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        **kwargs
    )
    return yaml_str.encode('utf-8')


def _deserialize_yaml(data: bytes, **kwargs) -> Any:
    """Deserialize from YAML"""
    yaml_str = data.decode('utf-8')
    return yaml.safe_load(yaml_str)


def _serialize_pickle(data: Any, **kwargs) -> bytes:
    """Serialize to Pickle"""
    protocol = kwargs.get('protocol', pickle.HIGHEST_PROTOCOL)
    return pickle.dumps(data, protocol=protocol)


def _deserialize_pickle(data: bytes, **kwargs) -> Any:
    """Deserialize from Pickle"""
    return pickle.loads(data)


def _serialize_msgpack(data: Any, **kwargs) -> bytes:
    """Serialize to MessagePack"""
    return msgpack.packb(data, use_bin_type=True, **kwargs)


def _deserialize_msgpack(data: bytes, **kwargs) -> Any:
    """Deserialize from MessagePack"""
    return msgpack.unpackb(data, raw=False, **kwargs)


def to_json(data: Any, pretty: bool = False, **kwargs) -> str:
    """
    Convert data to JSON string
    
    Args:
        data: Data to convert
        pretty: Whether to pretty-print the JSON
        **kwargs: Additional arguments for json.dumps
    
    Returns:
        JSON string
    """
    if pretty:
        kwargs.setdefault('indent', 2)
        kwargs.setdefault('sort_keys', True)
    
    return json.dumps(data, cls=GATFJSONEncoder, ensure_ascii=False, **kwargs)


def from_json(json_str: str, **kwargs) -> Any:
    """
    Parse JSON string to data
    
    Args:
        json_str: JSON string
        **kwargs: Additional arguments for json.loads
    
    Returns:
        Parsed data
    """
    return json.loads(json_str, **kwargs)


def save_to_file(
    data: Any,
    file_path: Union[str, Path],
    format: Optional[Union[SerializationFormat, str]] = None,
    **kwargs
):
    """
    Save data to file
    
    Args:
        data: Data to save
        file_path: Path to save file
        format: Serialization format (auto-detected from extension if not provided)
        **kwargs: Additional arguments for the serializer
    """
    file_path = Path(file_path)
    
    # Auto-detect format from file extension if not provided
    if format is None:
        ext = file_path.suffix.lower()
        if ext == '.json':
            format = SerializationFormat.JSON
        elif ext in ['.yaml', '.yml']:
            format = SerializationFormat.YAML
        elif ext in ['.pickle', '.pkl']:
            format = SerializationFormat.PICKLE
        elif ext == '.msgpack':
            format = SerializationFormat.MSGPACK
        else:
            format = SerializationFormat.JSON
    
    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Serialize and save
    serialized_data = serialize(data, format, **kwargs)
    file_path.write_bytes(serialized_data)


def load_from_file(
    file_path: Union[str, Path],
    format: Optional[Union[SerializationFormat, str]] = None,
    **kwargs
) -> Any:
    """
    Load data from file
    
    Args:
        file_path: Path to load file
        format: Serialization format (auto-detected from extension if not provided)
        **kwargs: Additional arguments for the deserializer
    
    Returns:
        Loaded data
    """
    file_path = Path(file_path)
    
    # Auto-detect format from file extension if not provided
    if format is None:
        ext = file_path.suffix.lower()
        if ext == '.json':
            format = SerializationFormat.JSON
        elif ext in ['.yaml', '.yml']:
            format = SerializationFormat.YAML
        elif ext in ['.pickle', '.pkl']:
            format = SerializationFormat.PICKLE
        elif ext == '.msgpack':
            format = SerializationFormat.MSGPACK
        else:
            format = SerializationFormat.JSON
    
    # Load and deserialize
    serialized_data = file_path.read_bytes()
    return deserialize(serialized_data, format, **kwargs)


class DataSerializer:
    """Advanced serializer with type registration and custom handlers"""
    
    def __init__(self):
        self._type_handlers: Dict[Type, Tuple[Callable, Callable]] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default type handlers"""
        # Register numpy array handler
        self.register_type(
            np.ndarray,
            lambda arr: {'_type': 'numpy.ndarray', 'data': arr.tolist(), 'dtype': str(arr.dtype), 'shape': arr.shape},
            lambda obj: np.array(obj['data'], dtype=obj['dtype']).reshape(obj['shape'])
        )
        
        # Register pandas DataFrame handler
        self.register_type(
            pd.DataFrame,
            lambda df: {'_type': 'pandas.DataFrame', 'data': df.to_dict('records'), 'columns': list(df.columns)},
            lambda obj: pd.DataFrame(obj['data'], columns=obj['columns'])
        )
        
        # Register datetime handler
        self.register_type(
            datetime.datetime,
            lambda dt: {'_type': 'datetime', 'value': dt.isoformat()},
            lambda obj: datetime.datetime.fromisoformat(obj['value'])
        )
    
    def register_type(self, type_class: Type, serializer: Callable, deserializer: Callable):
        """
        Register custom type handler
        
        Args:
            type_class: Type to handle
            serializer: Function to serialize the type
            deserializer: Function to deserialize the type
        """
        self._type_handlers[type_class] = (serializer, deserializer)
    
    def serialize(self, data: Any) -> Dict[str, Any]:
        """
        Serialize data with custom type handling
        
        Args:
            data: Data to serialize
        
        Returns:
            Serialized data
        """
        # Check for registered type handlers
        for type_class, (serializer, _) in self._type_handlers.items():
            if isinstance(data, type_class):
                return serializer(data)
        
        # Handle built-in types
        if isinstance(data, dict):
            return {k: self.serialize(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return [self.serialize(item) for item in data]
        elif is_dataclass(data):
            return {'_type': 'dataclass', 'class': type(data).__name__, 'data': asdict(data)}
        else:
            return data
    
    def deserialize(self, data: Any) -> Any:
        """
        Deserialize data with custom type handling
        
        Args:
            data: Serialized data
        
        Returns:
            Deserialized data
        """
        if isinstance(data, dict):
            # Check for type marker
            if '_type' in data:
                type_name = data['_type']
                
                # Look for registered handler
                for type_class, (_, deserializer) in self._type_handlers.items():
                    if f"{type_class.__module__}.{type_class.__name__}" == type_name or type_class.__name__ == type_name:
                        return deserializer(data)
                
                # Handle dataclass
                if type_name == 'dataclass':
                    # Note: This requires the dataclass to be importable
                    return data['data']
            
            # Recursively deserialize dict values
            return {k: self.deserialize(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.deserialize(item) for item in data]
        else:
            return data


# Global data serializer instance
_data_serializer = DataSerializer()


def get_data_serializer() -> DataSerializer:
    """Get the global data serializer instance"""
    return _data_serializer