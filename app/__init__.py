__version__ = "1.20.1"  # x-release-please-version
__display_version__ = "v1.21parity"
__all__ = ["app", "__display_version__", "__version__"]


def __getattr__(name: str):
    if name == "app":
        from app.main import app as fastapi_app

        return fastapi_app
    raise AttributeError(name)
