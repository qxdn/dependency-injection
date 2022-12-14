# python依赖注入

参考了[nonebot2](https://github.com/nonebot/nonebot2)中参数注入，完整说明见[此]()

对于用户定义的需要通过`Depends()`包含
```python
def provider() -> Dict[str,int]:
    return {"c": 123,"d":999}

def test_func(dep : Dict[str,int] = Depends(provider)):
    print(dep)  # output will be {"c": 123,"d":999}
```


demo如下
```python
from typing import Dict
from dependencies.model import TestObj,Person
from dependencies.params import Depends,Dependent
from colorama import Fore

def provider1(person) -> Dict[str,int]:
    print(Fore.GREEN + "----in provider1-----")
    print(f"person'name :{person.name}")
    print("-------end-------")
    return {"c": 123,"d":999}

def provider2(dep:Dict[str,int]=Depends(provider1)) -> Dict[str,int]:
    print(Fore.RED + "----in provider2-----")
    print(f"in provider 2 dep are:{dep}")
    return_values:Dict[str,int] = {"a": 123,"b":999}
    return_values.update(dep)
    print("-------end-------")
    return return_values

def test_func(test:TestObj,dep : Dict[str,int] = Depends(provider2)):
    '''
    原始函数
    '''
    print(Fore.CYAN + "----in test_func-----")
    print(f"testparam's id:{test.id}")
    print("----print dict-----")
    print(dep)
    print("-------end-------")


def main():
    # 运行前注册
    d = Dependent.parse(call=test_func)
    # 外部参数
    p = Person("test person")
    t = TestObj(6)
    # 省去挑选handler步骤，直接执行原函数
    d(test = t,person=p)


if __name__ == '__main__':
    main()
    
```

运行结果
![result](/assert/result.png)