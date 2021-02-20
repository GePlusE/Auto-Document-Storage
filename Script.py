import os
import credentials as creds
from time import sleep

directory_to_clean = creds.input_folder
os.chdir(directory_to_clean)
files = os.listdir()

print(files)
