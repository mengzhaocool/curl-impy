import warnings


class CurlImpyWarning(UserWarning, RuntimeWarning):
    pass


def config_warnings(on: bool = False):
    if on:
        warnings.simplefilter("default", category=CurlImpyWarning)
    else:
        warnings.simplefilter("ignore", category=CurlImpyWarning)


def is_pro():
    return False
