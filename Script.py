import os
import credentials as creds
from time import sleep

directory_to_clean = creds.directory_to_clean
target_directory = creds.target_directory
types_to_ignore = creds.types_to_ignore


def detect_files(path=directory_to_clean):
    os.chdir(path)
    files = os.listdir()
    # Create list of files considering the type_to_ignore from credentials
    file_list = [f for f in files if os.path.splitext(f)[-1] not in types_to_ignore]
    return file_list


def rename_and_move(
    origin_filename, origin_path=directory_to_clean, target_path=target_directory
):

    pass


rename_files()
