import os
import credentials as creds

from datetime import datetime
from time import sleep
from pathlib import Path

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
        file_name, file_type = os.path.splitext(origin_filename)
        file_path = os.path.join(origin_path, origin_filename)
        file_prefix = file_name.split("__")[0].capitalize()
        file_incremental = int(0)

        date = datetime.today().strftime("%Y-%m-%d")
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
        os.rename(full_origin, full_target)

        # print("#" * 30)
        # print("file_name: " + file_name)
        # print("file_type: " + file_type)
        # print("file_path: " + file_path)
        # print("file_prefix: " + file_prefix)
        # print("")
        # print("target_name: " + target_name)
        # print("target_path: " + directory)
        # print("")
        # print("origin: " + full_origin)
        # print("new_path: " + full_target)

        pass


for i in detect_files():
    rename_and_move(i)
