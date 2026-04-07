# tools/file.py
# Gives Kairos the ability to read, write, create and delete files & folders.

import os
from dataclasses import dataclass

@dataclass
class FileResult:
    """
    Holds the result of a file operation.

    content → the file content (only used when reading)
    message → a human readable status message
    success → True if the operation succeeded
    """
    content : str
    message : str
    success : bool

def read_file(path: str) -> FileResult:
    """
    Read and return the contents of a file.

    Example:
        result = read_file("hello.txt")
        print(result.content)
    """
    try:
        with open(path, "r") as f:
            content = f.read()
        return FileResult(
            content = content,
            message = f"Successfully read {path}",
            success = True,
        )
    except FileNotFoundError:
        return FileResult(
            content = "",
            message = f"File not found: {path}",
            success = False,
        )
    except Exception as e:
        return FileResult(
            content = "",
            message = f"Unexpected error reading {path}: {str(e)}",
            success = False,
        )

def write_file(path: str, content: str) -> FileResult:
    """
    Write content to a file. Creates the file if it doesn't exist.
    Also creates any missing parent folders automatically.

    Example:
        result = write_file("notes/hello.txt", "Hello World!")
    """
    try:
        # Create parent folders if they don't exist
        # e.g. if path is "notes/hello.txt", creates the "notes" folder
        os.makedirs(os.path.dirname(path), exist_ok = True) if os.path.dirname(path) else None

        with open(path , "w") as f:
            f.write(content)
        return FileResult(
            content = "",
            message = f"Successfully wrote to {path}",
            success = True,
            )
    except Exception as e:
        return FileResult(
            content = "",
            message = f"Unexpected error writing {path}: {str(e)}",
            success = False,
        )

def delete_file(path: str)-> FileResult:
    """
    Delete a file.

    Example:
        result = delete_file("hello.txt")
    """
    try:
        os.remove(path)
        return FileResult(
            content = "",
            message = f"Successfully deleted {path}",
            success = True,
        )
    except FileNotFoundError:
        return FileResult(
            content = "",
            message = f"File not found: {path}",
            success = False,
        )
    except Exception as e:
        return FileResult(
            content = "",
            message = f"Unexpected error deleting {path}: {str(e)}",
            success = False,
        )

def list_folder(path: str)-> FileResult:
    """
    List all files and folders inside a directory.

    Example:
        result = list_folder(".")
        print(result.content)
    """
    try:
        items = os.listdir(path)
        content = "\n".join(sorted(items))
        return FileResult(
            content = content,
            message = f"Successfully listed {path}",
            success = True,
        )
    except FileNotFoundError:
        return FileResult(
            content = "",
            message = f"Folder not found: {path}",
            success = False,
        )
    except Exception as e:
        return FileResult(
            content = "",
            message = f"Unexpected error listing {path}: {str(e)}",
            success = False,
        )