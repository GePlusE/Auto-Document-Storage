#!/usr/bin/env python3
import os
import credentials as creds
import logging

from datetime import datetime
from time import sleep
from pathlib import Path


############################ Logging Settings ############################
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
# get formats from https://docs.python.org/3/library/logging.html#logrecord-attributes

file_handler = logging.FileHandler(
    "/Users/gepluse/CodeProjects/Auto-Document-Storage/LogFile.log"
)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
##########################################################################


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
    # check if valid origin_filename
    if "__" not in origin_filename:
        pass
    else:
        # create new file name
        file_path = os.path.join(origin_path, origin_filename)
        file_name, file_type = os.path.splitext(origin_filename)
        file_path = os.path.join(origin_path, origin_filename)
        file_prefix = file_name.split("__")[0].capitalize()
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

        date = min(
            file_mdate, file_cdate, file_adate
        )  # use the min date of all three dates
        if len(file_name.split("__")) == 3:
            target_name = date + " " + file_name.split("__")[1]
        else:
            target_name = date + " " + file_name.split("__")[-1]

        # create target directory if neccessary
        directory = os.path.join(target_path, file_prefix)
        Path(directory).mkdir(parents=True, exist_ok=True)

        # create full paths
        full_origin = os.path.join(origin_path, file_name + file_type)
        full_target = os.path.join(target_path, file_prefix, target_name + file_type)

        # check if file exists and increment it if neccessary
        while os.path.exists(full_target):
            file_incremental += 1
            full_target = os.path.join(
                target_path,
                file_prefix,
                target_name + "_" + str(file_incremental) + file_type,
            )

        # move file to target directory
        try:
            os.rename(full_origin, full_target)
            logger.info(f"Moved {full_origin} -> {full_target}")
        except Exception as e:
            logger.error(f"Failed to move {origin_filename}: {e}")

        # logging
        logger.info(f"Moved {full_origin}    ->    {full_target}")


def main():
    # add sleep to wait for downloads in directory_to_clean
    sleep(10)

    # loop through files
    for i in detect_files():
        rename_and_move(i)


if __name__ == "__main__":
    main()
