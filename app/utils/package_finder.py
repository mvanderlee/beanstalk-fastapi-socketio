import importlib
import inspect
import pkgutil
from typing import Generator, Generic, Type, TypeVar

from loguru import logger


def rpartitions(value: str, sep: str = '.') -> Generator[str, str, None]:
    '''
        Generator that yields all possible partitions from right to left.
        i.e.: 'a.b.c' => ['a.b.c', 'a.b', 'a']
    '''
    # Yield first partition which is the value as is.
    yield value

    next_partition = value.rpartition(sep)[0]
    while next_partition != '':
        yield next_partition
        next_partition = next_partition.rpartition(sep)[0]


T = TypeVar("T")


class PackageFinder(Generic[T]):
    '''
        Does the same as setuptools's PackageFinder, but at runtime.
        This means that we can't use the os path location, but must instead honor the calling stack.
    '''

    @classmethod
    def get_parent_package(cls) -> str:
        # No package provided, so get the package of the caller's parent.
        # stack[0] is current level, stack[1] is the caller level, and so on.
        stack = inspect.stack()
        logger.debug(f'stack: {stack}')
        return inspect.getmodule(stack[2][0]).__package__

    @classmethod
    def find_packages_iter(
        cls,
        package_name: str,
        root_package_name: str = None,
    ) -> Generator[str, None, None]:
        '''
            Finds all modules by name

            It does this by searching for the package in the caller's parent tree.
        '''
        if root_package_name is None:
            root_package_name = cls.get_parent_package()

        # Find routes module
        for package_part in rpartitions(root_package_name):
            module_to_find = f'{package_part}.{package_name}'

            logger.debug(f'Checking if {module_to_find} exists.')
            module_spec = importlib.util.find_spec(module_to_find)
            if module_spec:
                logger.debug(f'{module_to_find} exists.')

                yield module_to_find

    @classmethod
    def find_attributes_iter(
        cls,
        package_name: str,
        attr_names: tuple[str] = None,
        attr_types: tuple[Type[T]] = None,
        root_package_name: str = None,
        strict_type_check: bool = False,
    ) -> Generator[T, None, None]:
        if root_package_name is None:
            root_package_name = cls.get_parent_package()

        for package in cls.find_packages_iter(package_name, root_package_name):
            yield from cls._find_attributes_in_package_iter(
                package,
                attr_names,
                attr_types,
                strict_type_check,
            )

    @classmethod
    def _find_attributes_in_package_iter(
        cls,
        package_name: str,
        attr_names: tuple[str] = None,
        attr_types: tuple[Type[T]] = None,
        strict_type_check: bool = False,
    ) -> Generator[T, None, None]:
        package = importlib.import_module(package_name)
        for _, mod_name, is_pkg in pkgutil.iter_modules(package.__path__):
            if is_pkg:
                yield from cls._find_attributes_in_package_iter(
                    f'{package_name}.{mod_name}',
                    attr_names,
                    attr_types,
                    strict_type_check,
                )
            else:
                yield from cls._get_module_attributes_iter(
                    f'{package_name}.{mod_name}',
                    attr_names,
                    attr_types,
                    strict_type_check,
                )

    @classmethod
    def _get_module_attributes_iter(
        cls,
        module_name: str,
        attr_names: tuple[str] = None,
        attr_types: tuple[Type[T]] = None,
        strict_type_check: bool = False,
    ) -> Generator[T, None, None]:
        '''
            Get a module's attributes by name, type, or both.

            strict_type_check: Check if type is exact match instead of isinstance
        '''
        mod = importlib.import_module(module_name)

        type_filter = lambda mod, attr: any(isinstance(getattr(mod, attr), atype) for atype in attr_types)
        if strict_type_check:
            # Check for exact type matches
            type_filter = lambda mod, attr: type(getattr(mod, attr)) in attr_types

        # Loop through attributes and yield all those that match.
        for attr in dir(mod):
            if (
                (not attr_names or attr in attr_names)
                and (not attr_types or type_filter(mod, attr))
            ):
                yield getattr(mod, attr)
