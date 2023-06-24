#!/usr/bin/python3
import os
import credentials as creds

from datetime import datetime
from time import sleep
from pathlib import Path

types_to_ignore = creds.types_to_ignore


def detect_files(path):
    os.chdir(path)
    files = os.listdir()
    # Create list of files considering the type_to_ignore from credentials
    file_list = [f for f in files if os.path.splitext(f)[-1] not in types_to_ignore]
    return file_list


def rename(origin_filename, path, prefix):
    if origin_filename == ".DS_Store":
        pass
    else:
        # create new file name
        file_path = os.path.join(path, origin_filename)
        file_name, file_type = os.path.splitext(origin_filename)
        file_path = os.path.join(path, origin_filename)
        file_prefix = prefix.capitalize()
        file_incremental = int(0)
        file_cdate = datetime.fromtimestamp(os.path.getctime(file_path)).strftime(
            "%Y-%m-%d"
        )  # create date
        file_mdate = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime(
            "%Y-%m-%d"
        )  # last modified date
        file_adate = datetime.fromtimestamp(os.path.getatime(file_path)).strftime(
            "%Y-%m-%d"
        )  # last accessed date

        date = file_mdate
        if len(file_name.split("__")) == 3:
            target_name = date + " " + file_name.split("__")[1]
        else:
            target_name = date + " " + file_name.split("__")[-1]

        # create full paths
        full_origin = os.path.join(path, file_name + file_type)
        full_target = os.path.join(path, file_prefix + "__" + file_name + file_type)

        # check if file exists and increment it if neccessary
        while os.path.exists(full_target):
            file_incremental += 1
            full_target = os.path.join(
                path,
                file_prefix,
                target_name + "_" + str(file_incremental) + file_type,
            )

        # move file to target directory
        os.rename(full_origin, full_target)
        # print(full_origin, full_target)


def add_prefix_to_files(prefix, path):
    f_list = detect_files(path)
    for i in f_list:
        rename(i, path, prefix)
    print(f"DONE: added {prefix} as prefix for all files in {path}")


add_prefix_to_files(
    "CONSORS", "/Users/gepluse/Downloads/sammeldownload_20230210_194422"
)
