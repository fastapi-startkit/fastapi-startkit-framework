class SocialiteException(Exception):
    pass


class InvalidStateException(SocialiteException):
    pass


class DriverMissingConfigurationException(SocialiteException):
    pass
