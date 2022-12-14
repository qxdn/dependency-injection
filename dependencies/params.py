from pydantic.fields import FieldInfo, ModelField, Required, Undefined
from pydantic.schema import get_annotation_from_field_info
from pydantic import BaseConfig
import abc
from typing import (
    TYPE_CHECKING,
    Optional,
    Callable,
    Any,
    List,
    Type,
    Dict,
    cast,
)
from dependencies.utils import (
    get_typed_signature,
    overrides,
    generic_check_issubclass,
    check_field_type,
)
from dependencies.exception import TypeMisMatch
import inspect

if TYPE_CHECKING:
    from dependencies.model import TestObj, Person


class CustomConfig(BaseConfig):
    arbitrary_types_allowed = True


class Param(abc.ABC, FieldInfo):
    """
    依赖注入单元 参数
    继承自 `pydantic.fields.FieldInfo`，用于描述参数信息（不包括参数名）。
    """

    ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.default})"

    @classmethod
    def _check_param(
        cls, dependent: "Dependent", name: str, param: inspect.Parameter
    ) -> Optional["Param"]:
        """
        解析出Param
        """
        return None

    @abc.abstractmethod
    def _solve(self, **kwargs: Any) -> Any:
        """
        从**kwargs中提取出Param对应value
        """
        raise NotImplementedError


class TestParam(Param):
    """
    TestObj对应的包装
    """

    @classmethod
    def _check_param(
        cls, dependent: "Dependent", name: str, param: inspect.Parameter
    ) -> Optional["Param"]:
        from dependencies.model import TestObj

        if param.default == param.empty:
            if generic_check_issubclass(param.annotation, TestObj):
                # 可以加子类检查，按照类型注入
                return cls(Required)
            elif param.annotation == param.empty and name == "test":
                # 没有标注但是变量名是test，按照名字注入
                return cls(Required)
        return None

    @overrides(Param)
    def _solve(self, test: "TestObj", **kwargs: Any) -> Any:
        return test


class PersonParam(Param):
    """
    Person对应的包装
    """

    @classmethod
    def _check_param(
        cls, dependent: "Dependent", name: str, param: inspect.Parameter
    ) -> Optional["Param"]:
        from dependencies.model import Person

        if param.default == param.empty:
            if generic_check_issubclass(param.annotation, Person):
                # 可以加子类检查，按照类型注入
                return cls(Required)
            elif param.annotation == param.empty and name == "person":
                # 没有标注但是变量名是person，按照名字注入
                return cls(Required)
        return None

    @overrides(Param)
    def _solve(self, person: "Person", **kwargs: Any) -> Any:
        return person


class DependsInner:
    """
    对用户自定义依赖的包装
    """

    def __init__(self, dependency: Optional[Callable[..., Any]]) -> None:
        self.dependency = dependency


class DependParam(Param):
    """
    子依赖参数
    """

    @classmethod
    def _check_param(
        cls, dependent: "Dependent", name: str, param: inspect.Parameter
    ) -> Optional["Param"]:
        if isinstance(param.default, DependsInner):
            dependency: Callable[..., Any]
            if param.default.dependency is None:
                assert param.annotation is not param.empty, "Dependency cannot be empty"
                dependency = param.annotation
            else:
                dependency = param.default.dependency
            sub_dependent = Dependent.parse(call=dependency)
            return cls(Required, dependent=sub_dependent)
        return None

    @overrides(Param)
    def _solve(self, **kwargs: Any) -> Any:
        # 子依赖
        sub_dependent: Dependent = self.extra["dependent"]
        sub_dependent.call = cast(Callable[..., Any], sub_dependent.call)
        call = sub_dependent.call

        # 解析出嵌套依赖的返回值
        sub_values = sub_dependent.solve(**kwargs)

        # 解析当前的返回值
        solved = call(**sub_values)
        return solved


class Dependent:
    """
    依赖注入容器
    """

    ALL_TYPES: List[Type[Param]] = [TestParam, PersonParam, DependParam]

    def __init__(
        self,
        call: Optional[Callable[..., Any]],
        *,
        params: Optional[List[ModelField]] = None,
    ) -> None:
        self.call = call
        self.params = params or []

    def parse_param(self, name: str, param: inspect.Parameter) -> Param:
        """
        将未知参数转为依赖注入Param
        """
        for types in self.ALL_TYPES:
            field_info = types._check_param(self, name, param)
            if field_info:
                return field_info
        else:
            raise ValueError(
                f"Unknown parameter {name} for function {self.call} with type {param.annotation}"
            )

    @classmethod
    def parse(cls, *, call: Callable[..., Any]) -> "Dependent":
        """
        对Callable解析出容器
        """
        signature = get_typed_signature(call=call)  # 获取函数签名
        params = signature.parameters  # 获取函数参数信息
        dependent = cls(call=call)  # 创建容器

        for param_name, param in params.items():
            default_value = Required
            if param.default != param.empty:
                default_value = param.default

            if isinstance(default_value, Param):
                # param 本身就是FieldInfo
                field_info = default_value
                default_value = field_info.default
            else:
                # 不是 Param 类型的需要打包成Param
                field_info = dependent.parse_param(param_name, param)
                default_value = field_info.default

            annotation: Any = Any
            required = default_value == Required
            if param.annotation != param.empty:
                annotation = param.annotation
            annotation = get_annotation_from_field_info(  # 验证annotation
                annotation, field_info, param_name
            )
            dependent.params.append(  # 将解析出的Param添加到容器的依赖中
                ModelField(
                    name=param_name,
                    type_=annotation,
                    class_validators=None,
                    model_config=CustomConfig,
                    default=None if required else default_value,
                    required=required,
                    field_info=field_info,
                )
            )

        return dependent

    def solve(
        self,
        **params: Any,
    ) -> Dict[str, Any]:
        values: Dict[str, Any] = {}  # 解析出的 name:param_value

        for field in self.params:
            field_info = field.field_info
            assert isinstance(field_info, Param), "Params must be subclasses of Param"
            value = field_info._solve(**params)  # 解析出当前参数对应的值
            if value is Undefined:
                value = field.get_default()

            try:
                values[field.name] = check_field_type(field, value) # 检查类型和值是否对应，并添加到字典中
            except TypeMisMatch:
                print(
                    f"{field_info} "
                    f"type {type(value)} not match depends {self.call} "
                    f"annotation {field._type_display()}, ignored"
                )
                raise

        return values

    def __call__(self, **kwargs: Any) -> Any:
        values = self.solve(**kwargs) # 解析出函数的需要的值 字典形式

        return self.call(**values) # 注入参数计算返回

    def __repr__(self) -> str:
        return f"Dependent {self.__class__.__name__} call={self.call.__name__}"


def Depends(dependency: Optional[Callable[..., Any]] = None) -> Any:  # noqa: N802
    '''
    对用户依赖进行包装
    '''
    return DependsInner(dependency=dependency) 
