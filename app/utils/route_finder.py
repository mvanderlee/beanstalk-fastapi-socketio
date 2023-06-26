from fastapi import APIRouter, FastAPI
from loguru import logger

from .package_finder import PackageFinder


def dynamically_register_routes(
    app: FastAPI,
    package_name=None,
    routes_package_name='api',
):
    '''
        Dynamically registers all blueprints.

        It does this by searching for the 'routes' package in the caller's parent tree.
        Then finding all modules that have a Blueprint attribute, and registering said attribute.
    '''
    if package_name is None:
        package_name = PackageFinder[APIRouter].get_parent_package()

    for router in PackageFinder[APIRouter].find_attributes_iter(
        package_name=routes_package_name,
        root_package_name=package_name,
        attr_types=(APIRouter,),
    ):
        logger.info(
            "Registering blueprint '{router[name]}' with prefix '{router[prefix]}'",
            router={
                'name': router.__class__.__name__,
                'import_name': router.__class__.__qualname__,
                'prefix': router.prefix,
            },
        )
        app.include_router(router)
