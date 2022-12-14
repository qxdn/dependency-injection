import inspect
from typing import TypeVar,Callable,Any,Dict,Union,Type,Tuple,TypeVar
from pydantic.typing import ForwardRef,evaluate_forwardref
from pydantic.fields import ModelField
from typing_extensions import get_args, get_origin
from pydantic.typing import is_union, is_none_type
from dependencies.exception import TypeMisMatch

T_Wrapped = TypeVar("T_Wrapped",bound=Callable)
V = TypeVar("V")

def overrides(InterfaceClass:object)-> Callable[[T_Wrapped],T_Wrapped]:
    '''
    检查一个方法是否为父类的实现
    '''

    def decorator(func:T_Wrapped):
        assert func.__name__ in dir(InterfaceClass),f"Error! method:{func.__name__} not in class:{InterfaceClass}"
        return func
    

    return decorator


def get_typed_signature(call: Callable[..., Any]) -> inspect.Signature:
    """获取可调用对象签名"""
    signature = inspect.signature(call)
    globalns = getattr(call, "__globals__", {})
    typed_params = [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=get_typed_annotation(param, globalns),
        )
        for param in signature.parameters.values()
    ]
    typed_signature = inspect.Signature(typed_params)
    return typed_signature


def get_typed_annotation(param: inspect.Parameter, globalns: Dict[str, Any]) -> Any:
    '''
    获得参数的类型注解
    '''
    annotation = param.annotation
    if isinstance(annotation, str):
        annotation = ForwardRef(annotation)
        annotation = evaluate_forwardref(annotation, globalns, globalns)
    return annotation


def generic_check_issubclass(
    cls: Any, class_or_tuple: Union[Type[Any], Tuple[Type[Any], ...]]
) -> bool:
    """检查 cls 是否是 class_or_tuple 中的一个类型子类。

    特别的，如果 cls 是 `typing.Union` 或 `types.UnionType` 类型，
    则会检查其中的类型是否是 class_or_tuple 中的一个类型子类。（None 会被忽略）
    """
    try:
        return issubclass(cls, class_or_tuple)
    except TypeError:
        origin = get_origin(cls)
        if is_union(origin):
            return all(
                is_none_type(type_) or generic_check_issubclass(type_, class_or_tuple)
                for type_ in get_args(cls)
            )
        elif origin:
            return issubclass(origin, class_or_tuple)
        return False

def check_field_type(field: ModelField, value: V) -> V:
    _, errs_ = field.validate(value, {}, loc=())
    if errs_:
        raise TypeMisMatch(field, value)
    return value