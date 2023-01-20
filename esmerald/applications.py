from datetime import timezone
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Type,
    Union,
)

from openapi_schemas_pydantic.v3_1_0 import License, SecurityRequirement, Server
from openapi_schemas_pydantic.v3_1_0.open_api import OpenAPI
from starlette.applications import Starlette
from starlette.middleware import Middleware as StarletteMiddleware  # noqa

from asyncz.contrib.esmerald.scheduler import EsmeraldScheduler
from esmerald.conf import settings as esmerald_settings
from esmerald.conf.global_settings import EsmeraldAPISettings
from esmerald.config import CORSConfig, CSRFConfig, SessionConfig, TemplateConfig
from esmerald.config.application import AppConfig
from esmerald.config.openapi import OpenAPIConfig
from esmerald.config.static_files import StaticFilesConfig
from esmerald.datastructures import State
from esmerald.exception_handlers import (
    improperly_configured_exception_handler,
    validation_error_exception_handler,
)
from esmerald.exceptions import ImproperlyConfigured, ValidationErrorException
from esmerald.interceptors.types import Interceptor
from esmerald.middleware.asyncexitstack import AsyncExitStackMiddleware
from esmerald.middleware.cors import CORSMiddleware
from esmerald.middleware.csrf import CSRFMiddleware
from esmerald.middleware.exceptions import EsmeraldAPIExceptionMiddleware, ExceptionMiddleware
from esmerald.middleware.sessions import SessionMiddleware
from esmerald.middleware.trustedhost import TrustedHostMiddleware
from esmerald.permissions.types import Permission
from esmerald.protocols.template import TemplateEngineProtocol
from esmerald.routing import gateways
from esmerald.routing.router import HTTPHandler, Include, Router, WebSocketHandler
from esmerald.types import (
    APIGateHandler,
    ASGIApp,
    Dependencies,
    ExceptionHandlers,
    LifeSpanHandler,
    Middleware,
    ParentType,
    Receive,
    ResponseCookies,
    ResponseHeaders,
    ResponseType,
    RouteParent,
    SchedulerType,
    Scope,
    Send,
)
from esmerald.utils.helpers import is_class_and_subclass

if TYPE_CHECKING:
    from openapi_schemas_pydantic.v3_1_0 import SecurityRequirement

    from esmerald.types import SettingsType


def get_app_settings(app: Type["Esmerald"]) -> "SettingsType":
    """
    Returns the application settings object.
    """
    return app.settings_config if app.settings_config else esmerald_settings


class Esmerald(Starlette):
    """
    Creates a Esmerald application instance.
    """

    __slots__ = (
        "title",
        "app_name",
        "summary",
        "description",
        "version",
        "contact",
        "terms_of_service",
        "license",
        "servers",
        "secret",
        "allowed_hosts",
        "allow_origins",
        "interceptors",
        "permissions",
        "dependencies",
        "middleware",
        "exception_handlers",
        "openapi_schema",
        "scheduler_tasks",
        "scheduler_configurations",
        "csrf_config",
        "openapi_config",
        "cors_config",
        "static_files_config",
        "template_config",
        "session_config",
        "response_class",
        "response_cookies",
        "response_headers",
        "scheduler_class",
        "scheduler",
        "tags",
        "root_path",
        "deprecated",
        "security",
        "include_in_schema",
        "redirect_slashes",
        "enable_scheduler",
        "enable_openapi",
        "timezone",
        "parent",
    )

    def __init__(
        self,
        *,
        settings_config: Optional["SettingsType"] = None,
        debug: Optional[bool] = None,
        app_name: Optional[str] = None,
        title: Optional[str] = None,
        version: Optional[str] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        contact: Optional[Dict[str, Union[str, Any]]] = None,
        terms_of_service: Optional[str] = None,
        license: Optional[License] = None,
        security: Optional[List[SecurityRequirement]] = None,
        servers: Optional[List[Server]] = None,
        secret_key: Optional[str] = None,
        allowed_hosts: Optional[List[str]] = None,
        allow_origins: Optional[List[str]] = None,
        permissions: Optional[List["Permission"]] = None,
        interceptors: Optional[List["Interceptor"]] = None,
        dependencies: Optional["Dependencies"] = None,
        csrf_config: Optional["CSRFConfig"] = None,
        openapi_config: Optional["OpenAPIConfig"] = None,
        cors_config: Optional["CORSConfig"] = None,
        static_files_config: Optional["StaticFilesConfig"] = None,
        template_config: Optional["TemplateConfig"] = None,
        session_config: Optional["SessionConfig"] = None,
        response_class: Optional["ResponseType"] = None,
        response_cookies: Optional["ResponseCookies"] = None,
        response_headers: Optional["ResponseHeaders"] = None,
        scheduler_class: Optional["SchedulerType"] = None,
        scheduler_tasks: Optional[Dict[str, str]] = None,
        scheduler_configurations: Optional[Dict[str, Union[str, Dict[str, str]]]] = None,
        enable_scheduler: Optional[bool] = None,
        timezone: Optional[timezone] = None,
        routes: Optional[List["APIGateHandler"]] = None,
        root_path: Optional[str] = None,
        middleware: Optional[Sequence["Middleware"]] = None,
        exception_handlers: Optional["ExceptionHandlers"] = None,
        on_startup: Optional[List["LifeSpanHandler"]] = None,
        on_shutdown: Optional[List["LifeSpanHandler"]] = None,
        lifespan: Optional[Callable[["Esmerald"], "AsyncContextManager"]] = None,
        tags: Optional[List[str]] = None,
        include_in_schema: Optional[bool] = None,
        deprecated: Optional[bool] = None,
        enable_openapi: Optional[bool] = None,
        redirect_slashes: Optional[bool] = None,
    ) -> None:
        self.settings_config = None

        if settings_config:
            if not isinstance(settings_config, EsmeraldAPISettings) or not is_class_and_subclass(
                settings_config, EsmeraldAPISettings
            ):
                raise ImproperlyConfigured(
                    "settings_config must be a subclass of EsmeraldSettings"
                )
            elif isinstance(settings_config, EsmeraldAPISettings):
                self.settings_config = settings_config
            elif is_class_and_subclass(settings_config, EsmeraldAPISettings):
                self.settings_config = settings_config()

        assert lifespan is None or (
            on_startup is None and on_shutdown is None
        ), "Use either 'lifespan' or 'on_startup'/'on_shutdown', not both."

        if allow_origins and cors_config:
            raise ImproperlyConfigured("It can be only allow_origins or cors_config but not both.")

        app_settings = get_app_settings(self)
        app_config = AppConfig(
            debug=debug or app_settings.debug,
            title=title or app_settings.title,
            app_name=app_name or app_settings.app_name,
            description=description or app_settings.description,
            version=version or app_settings.version,
            summary=summary or app_settings.summary,
            contact=contact or app_settings.contact,
            terms_of_service=terms_of_service or app_settings.terms_of_service,
            license=license or app_settings.license,
            servers=servers or app_settings.servers,
            secret_key=secret_key or app_settings.secret_key,
            allowed_hosts=allowed_hosts or app_settings.allowed_hosts,
            allow_origins=allow_origins or app_settings.allow_origins,
            permissions=(permissions or app_settings.permissions) or [],
            interceptors=(interceptors or app_settings.interceptors) or [],
            dependencies=(dependencies or app_settings.dependencies) or {},
            csrf_config=csrf_config or app_settings.csrf_config,
            cors_config=cors_config or app_settings.cors_config,
            openapi_config=openapi_config or app_settings.openapi_config,
            template_config=template_config or app_settings.template_config,
            static_files_config=static_files_config or app_settings.static_files_config,
            session_config=session_config or app_settings.session_config,
            response_class=response_class or app_settings.response_class,
            response_cookies=response_cookies or app_settings.response_cookies,
            response_headers=response_headers or app_settings.response_headers,
            scheduler_class=scheduler_class or app_settings.scheduler_class,
            scheduler_tasks=scheduler_tasks or app_settings.scheduler_tasks or {},
            scheduler_configurations=scheduler_configurations
            or app_settings.scheduler_configurations
            or {},
            enable_scheduler=enable_scheduler or app_settings.enable_scheduler,
            timezone=timezone or app_settings.timezone,
            root_path=root_path or app_settings.root_path,
            middleware=(middleware or app_settings.middleware) or [],
            exception_handlers=exception_handlers or app_settings.exception_handlers,
            on_startup=on_startup or app_settings.on_startup,
            on_shutdown=on_shutdown or app_settings.on_shutdown,
            lifespan=lifespan or app_settings.lifespan,
            tags=tags or app_settings.tags,
            include_in_schema=include_in_schema or app_settings.include_in_schema,
            enable_openapi=enable_openapi or app_settings.enable_openapi,
            redirect_slashes=redirect_slashes or app_settings.redirect_slashes,
            security=security or app_settings.security,
        )

        self._debug = app_config.debug
        self.title = app_config.title
        self.app_name = app_config.app_name
        self.description = app_config.description
        self.version = app_config.version
        self.summary = app_config.summary
        self.contact = app_config.contact
        self.terms_of_service = app_config.terms_of_service
        self.license = app_config.license
        self.servers = app_config.servers
        self.secret_key = app_config.secret_key
        self.allowed_hosts = app_config.allowed_hosts
        self.allow_origins = app_config.allow_origins
        self.permissions = app_config.permissions
        self.interceptors = app_config.interceptors
        self.dependencies = app_config.dependencies
        self.csrf_config = app_config.csrf_config
        self.cors_config = app_config.cors_config
        self.openapi_config = app_config.openapi_config
        self.template_config = app_config.template_config
        self.static_files_config = app_config.static_files_config
        self.session_config = app_config.session_config
        self.response_class = app_config.response_class
        self.response_cookies = app_config.response_cookies
        self.response_headers = app_config.response_headers
        self.scheduler_class = app_config.scheduler_class
        self.scheduler_tasks = app_config.scheduler_tasks
        self.scheduler_configurations = app_config.scheduler_configurations
        self.enable_scheduler = app_config.enable_scheduler
        self.timezone = app_config.timezone
        self.root_path = app_config.root_path
        self.middleware = app_config.middleware
        self.exception_handlers = (
            {} if app_config.exception_handlers is None else dict(app_config.exception_handlers)
        )
        self.on_startup = app_config.on_startup
        self.on_shutdown = app_config.on_shutdown
        self.lifespan = app_config.lifespan
        self.tags = app_config.tags
        self.include_in_schema = app_config.include_in_schema
        self.security = app_config.security
        self.enable_openapi = app_config.enable_openapi
        self.redirect_slashes = app_config.redirect_slashes

        self.openapi_schema: Optional["OpenAPI"] = None
        self.state = State()
        self.async_exit_config = esmerald_settings.async_exit_config
        self.parent: Optional[Union["ParentType", "Esmerald", "ChildEsmerald"]] = None

        self.router: "Router" = Router(
            on_shutdown=self.on_shutdown,
            on_startup=self.on_startup,
            routes=routes,
            app=self,
            lifespan=self.lifespan,
            deprecated=deprecated,
            security=security,
            redirect_slashes=self.redirect_slashes,
        )

        self.get_default_exception_handlers()
        self.user_middleware = self.build_user_middleware_stack()
        self.middleware_stack = self.build_middleware_stack()
        self.template_engine = self.get_template_engine(self.template_config)

        if self.static_files_config:
            for config in (
                self.static_files_config
                if isinstance(self.static_files_config, list)
                else [self.static_files_config]
            ):
                static_route = Include(path=config.path, app=config.to_app())
                self.router.validate_root_route_parent(static_route)
                self.router.routes.append(static_route)

        if self.enable_scheduler:
            self.scheduler = EsmeraldScheduler(
                app=self,
                scheduler_class=self.scheduler_class,
                tasks=self.scheduler_tasks,
                timezone=self.timezone,
                configurations=self.scheduler_configurations,
            )

        # self.resolve_settings()
        self.activate_openapi()

    def activate_openapi(self) -> None:
        if self.openapi_config and self.enable_openapi:
            self.openapi_schema = self.openapi_config.create_openapi_schema_model(self)
            gateway = gateways.Gateway(handler=self.openapi_config.openapi_apiview)
            self.router.add_apiview(value=gateway)

    def get_template_engine(
        self, template_config: "TemplateConfig"
    ) -> Optional["TemplateEngineProtocol"]:
        """
        Returns the template engine for the application.
        """
        if not template_config:
            return

        engine = template_config.engine(template_config.directory)
        return engine

    def add_route(
        self,
        path: str,
        handler: "HTTPHandler",
        router: Optional["Router"] = None,
        dependencies: Optional["Dependencies"] = None,
        exception_handlers: Optional["ExceptionHandlers"] = None,
        interceptors: Optional[List["Interceptor"]] = None,
        permissions: Optional[List["Permission"]] = None,
        middleware: Optional[List["Middleware"]] = None,
        name: Optional[str] = None,
        include_in_schema: bool = True,
    ) -> None:
        router = router or self.router
        route = router.add_route(
            path=path,
            handler=handler,
            dependencies=dependencies,
            exception_handlers=exception_handlers,
            interceptors=interceptors,
            permissions=permissions,
            middleware=middleware,
            name=name,
            include_in_schema=include_in_schema,
        )

        self.activate_openapi()
        return route

    def add_websocket_route(
        self,
        path: str,
        handler: "HTTPHandler",
        router: Optional["Router"] = None,
        dependencies: Optional["Dependencies"] = None,
        exception_handlers: Optional["ExceptionHandlers"] = None,
        interceptors: Optional[List["Interceptor"]] = None,
        permissions: Optional[List["Permission"]] = None,
        middleware: Optional[List["Middleware"]] = None,
        name: Optional[str] = None,
    ) -> None:
        router = router or self.router
        return router.add_websocket_route(
            path=path,
            handler=handler,
            dependencies=dependencies,
            exception_handlers=exception_handlers,
            interceptors=interceptors,
            permissions=permissions,
            middleware=middleware,
            name=name,
        )

    def add_router(self, router: "Router"):
        """
        Adds a router to the application.
        """
        for route in router.routes:
            if isinstance(route, Include):
                self.router.routes.append(
                    Include(
                        path=route.path,
                        app=route.app,
                        dependencies=route.dependencies,
                        exception_handlers=route.exception_handlers,
                        name=route.name,
                        middleware=route.middleware,
                        interceptors=route.interceptors,
                        permissions=route.permissions,
                        routes=route.routes,
                        parent=self.router,
                    )
                )
                continue

            gateway = (
                gateways.Gateway
                if not isinstance(route.handler, WebSocketHandler)
                else gateways.WebSocketGateway
            )

            if self.on_startup:
                self.on_startup.extend(router.on_startup)
            if self.on_shutdown:
                self.on_shutdown.extend(router.on_shutdown)

            self.router.routes.append(
                gateway(
                    path=route.path,
                    dependencies=route.dependencies,
                    exception_handlers=route.exception_handlers,
                    name=route.name,
                    middleware=route.middleware,
                    interceptors=route.interceptors,
                    permissions=route.permissions,
                    handler=route.handler,
                    parent=self.router,
                    is_from_router=True,
                )
            )

        self.activate_openapi()

    def get_default_exception_handlers(self) -> None:
        """
        Default exception handlers added to the application.
        Defaulting the HTTPException and ValidationError handlers to JSONResponse.

        The values can be overritten by calling the self.add_event_handler().

        Example:
            app = Esmerald()

            app.add_event_handler(HTTPException, my_new_handler)
            app.add_event_handler(ValidationError, my_new_422_handler)

        """
        self.exception_handlers.setdefault(
            ImproperlyConfigured, improperly_configured_exception_handler
        )
        self.exception_handlers.setdefault(
            ValidationErrorException, validation_error_exception_handler
        )

    def build_routes_middleware(
        self, route: "RouteParent", middlewares: Optional[List["Middleware"]] = None
    ):
        """
        Builds the middleware stack from the top to the bottom of the routes.

        The includes are anm exception as they are treated as an independent ASGI
        application and therefore handles their own middlewares independently.
        """
        if not middlewares:
            middlewares = []

        if isinstance(route, Include):
            app = getattr(route, "app", None)
            if app and isinstance(app, (Esmerald, ChildEsmerald)):
                return middlewares

        if isinstance(route, (gateways.Gateway, gateways.WebSocketGateway)):
            middlewares.extend(route.middleware)
            if route.handler.middleware:
                middlewares.extend(route.handler.middleware)

        return middlewares

    def build_routes_exception_handlers(
        self,
        route: "RouteParent",
        exception_handlers: Optional["ExceptionHandlers"] = None,
    ):
        """
        Builds the exception handlers stack from the top to the bottom of the routes.
        """
        if not exception_handlers:
            exception_handlers = {}

        if isinstance(route, Include):
            exception_handlers.update(route.exception_handlers)
            app = getattr(route, "app", None)
            if app and isinstance(app, (Esmerald, ChildEsmerald)):
                return exception_handlers

            for _route in route.routes:
                exception_handlers = self.build_routes_exception_handlers(
                    _route, exception_handlers
                )

        if isinstance(route, (gateways.Gateway, gateways.WebSocketGateway)):
            exception_handlers.update(route.exception_handlers)
            if route.handler.exception_handlers:
                exception_handlers.update(route.handler.exception_handlers)

        return exception_handlers

    def build_user_middleware_stack(self) -> List["StarletteMiddleware"]:
        """
        Configures all the passed settings
        and wraps inside an exception handler.

        CORS, CSRF, TrustedHost and JWT are provided to the __init__ they will wapr the
        handler as well.

        It evaluates the middleware passed into the routes from bottom up
        """
        user_middleware = []
        handlers_middleware = []

        if self.allowed_hosts:
            user_middleware.append(
                StarletteMiddleware(TrustedHostMiddleware, allowed_hosts=self.allowed_hosts)
            )
        if self.cors_config:
            user_middleware.append(StarletteMiddleware(CORSMiddleware, **self.cors_config.dict()))
        if self.csrf_config:
            user_middleware.append(StarletteMiddleware(CSRFMiddleware, config=self.csrf_config))

        if self.session_config:
            user_middleware.append(
                StarletteMiddleware(SessionMiddleware, **self.session_config.dict())
            )

        handlers_middleware += self.router.middleware
        for route in self.routes or []:
            handlers_middleware.extend(self.build_routes_middleware(route))

        self.middleware += handlers_middleware

        for middleware in self.middleware or []:
            if isinstance(middleware, StarletteMiddleware):
                user_middleware.append(middleware)
            else:
                user_middleware.append(StarletteMiddleware(middleware))
        return user_middleware

    def build_middleware_stack(self) -> "ASGIApp":
        """
        Esmerald uses the [esmerald.protocols.MiddlewareProtocol] (interfaces) and therefore we
        wrap the StarletteMiddleware in a slighly different manner.

        Overriding the default build_middleware_stack will allow to control the initial
        middlewares that are loaded by Esmerald. All of these values can be updated.

        For each route, it will verify from top to bottom which exception handlers are being passed
        and called them accordingly.

        For APIViews, since it's a "wrapper", the handler will update the current list to contain
        both.
        """
        debug = self.debug
        error_handler = None
        exception_handlers = {}

        for key, value in self.exception_handlers.items():
            if key in (500, Exception):
                error_handler = value
            else:
                exception_handlers[key] = value

        for route in self.routes or []:
            exception_handlers.update(self.build_routes_exception_handlers(route))

        middleware = (
            [
                StarletteMiddleware(
                    EsmeraldAPIExceptionMiddleware,
                    exception_handlers=exception_handlers,
                    error_handler=error_handler,
                    debug=debug,
                ),
            ]
            + self.user_middleware
            + [
                StarletteMiddleware(
                    ExceptionMiddleware,
                    handlers=exception_handlers,
                    debug=debug,
                ),
                StarletteMiddleware(AsyncExitStackMiddleware, config=self.async_exit_config),
            ]
        )

        app: "ASGIApp" = self.router
        for cls, options in reversed(middleware):
            app = cls(app=app, **options)

        return app

    def resolve_settings(self) -> None:
        """
        Make sure the settings are aligned with the application parameters.
        Request, local, app and global have the same values
        """
        object_setattr = object.__setattr__

        for key in dir(self):
            if key == "_debug":
                setattr(esmerald_settings, "debug", self._debug)

            if (
                hasattr(esmerald_settings, key)
                and not key.startswith("__")
                and not key.endswith("__")
            ):
                value = getattr(self, key, None)
                if value:
                    object_setattr(esmerald_settings, key, value)

    @property
    def settings(self) -> esmerald_settings:
        """
        Returns the Esmerald settings object for easy access.
        """
        return esmerald_settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = self
        if scope["type"] == "lifespan":
            await self.router.lifespan(scope, receive, send)
            return
        if self.root_path:
            scope["root_path"] = self.root_path
        scope["state"] = {}
        await super().__call__(scope, receive, send)

    def mount(self, path: str, app: ASGIApp, name: Optional[str] = None) -> None:
        raise ImproperlyConfigured("`mount` is not supported by Esmerald. Use Include() instead.")

    def host(self, host: str, app: ASGIApp, name: Optional[str] = None) -> None:
        raise ImproperlyConfigured(
            "`host` is not supported by Esmerald. Use Starlette Host() instead."
        )

    def route(
        self,
        path: str,
        methods: Optional[List[str]] = None,
        name: Optional[str] = None,
        include_in_schema: bool = True,
    ) -> Callable:
        raise ImproperlyConfigured("`route` is not valid. Use Gateway instead.")

    def websocket_route(self, path: str, name: Optional[str] = None) -> Callable:
        raise ImproperlyConfigured("`websocket_route` is not valid. Use WebSocketGateway instead.")


class ChildEsmerald(Esmerald):
    """
    A simple visual representation of an Esmerald application, exactly like Esmerald
    but for organisation purposes it might be preferred to use this class.
    """

    ...
