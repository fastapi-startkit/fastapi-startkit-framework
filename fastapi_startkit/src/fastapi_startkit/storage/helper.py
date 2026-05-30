import mimetypes
import os
import pathlib


def get_module_dir(module_file):
    return os.path.dirname(os.path.realpath(module_file))


mimetypes.init([os.path.join(get_module_dir(__file__), "data/mime.types")])

KNOWN_MIME_TYPES = mimetypes.types_map.keys()


def get_extension(filepath: str, without_dot=False) -> str:
    """Get a file extension from a filepath. If without_dot= True, the prefix will be removed from
    the extension."""
    extension_parts = pathlib.Path(filepath).suffixes
    extension = ""
    if extension_parts:
        # try to join all the parts until only one part to check if it's a known extension
        for i in range(len(extension_parts)):
            try_extension = "".join(extension_parts[i:])
            if try_extension in KNOWN_MIME_TYPES:
                extension = try_extension
                break
        # if no known extension found, return the last part as the extension
        if not extension:
            extension = extension_parts[-1]

        if without_dot:
            extension = extension[1:]
    return extension
