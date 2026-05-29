import os

def make_directory(directory):
    """Create a directory at the given path for a file if it does not exist"""
    if not os.path.isfile(directory):
        if not os.path.exists(os.path.dirname(directory)):
            # Create the path to the model if it does not exist
            os.makedirs(os.path.dirname(directory))

        return True

    return False
