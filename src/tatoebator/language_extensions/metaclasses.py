import weakref


class TransientSingleton:
    _instances = {}

    def __new__(cls, *args, **kwargs):
        if cls in cls._instances:
            raise RuntimeError(f"Only one instance of {cls.__name__} is allowed.")

        instance = super().__new__(cls)
        cls._instances[cls] = instance

        # Register cleanup function to remove instance when it gets deleted
        weakref.finalize(instance, cls._instances.pop, cls)

        return instance
