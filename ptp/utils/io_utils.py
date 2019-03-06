# Copyright (C) tkornuta, IBM Corporation 2019
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = "Tomasz Kornuta"

import os
import sys
import time
import errno
import csv
import urllib
from pathlib import Path



def save_list_to_txt_file(folder, filename, data):
    """ 
    Writes data to txt file.
    """
    # Make sure directory exists.
    os.makedirs(os.path.dirname(folder +'/'), exist_ok=True)

    # Write elements in separate lines.        
    with open(folder+'/'+filename, mode='w+') as txtfile:
        txtfile.write('\n'.join(data))


def load_list_from_txt_file(folder, filename):
    """
    Loads data from txt file.
    """
    data = []
    with open(folder+'/'+filename, mode='rt') as txtfile:
        for line in txtfile:
            # Remove next line char.
            if line[-1] == '\n':
                line = line[:-1]
            data.append(line)
    return data


def load_dict_from_csv_file(folder, filename):
    """
    Loads data from csv file.

    .. warning::
            There is an assumption that file will contain key:value pairs (no content checking for now!)

    :param filename: File with encodings (absolute path + filename).
    :return: dictionary with word:index keys
    """        
    file_path = os.path.expanduser(folder) + "/" + filename

    with open(file_path, mode='rt') as csvfile:
        # Check the presence of the header.
        sniffer = csv.Sniffer()
        first_bytes = str(csvfile.read(256))
        has_header = sniffer.has_header(first_bytes)
        # Rewind.
        csvfile.seek(0)  
        reader = csv.reader(csvfile)
        # Skip the header row.
        if has_header:
            next(reader)  
        # Read the remaining rows.
        ret_dict = {rows[0]:int(rows[1]) for rows in reader}
    return ret_dict


def save_dict_to_csv_file(folder, filename, word_to_ix, fieldnames = []):
    """
    Saves dictionary to a file.

    :param filename: File with encodings (absolute path + filename).
    :param word_to_ix: dictionary with word:index keys
    """
    # Make sure directory exists.
    os.makedirs(os.path.dirname(folder +'/'), exist_ok=True)

    file_path = os.path.expanduser(folder) + "/" + filename

    with open(file_path, mode='w+') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        # Create header.
        writer.writeheader()

        # Write word-index pairs.
        for (k,v) in word_to_ix.items():
            #print("{} : {}".format(k,v))
            writer.writerow({fieldnames[0]:k, fieldnames[1]: v})


def get_project_root() -> Path:
    """
    Returns project root folder.
    """
    return Path(__file__).parent.parent


def check_file_existence(directory, filename):
    """
    Checks if file exists.

    :param directory: Relative path to to folder.
    :type directory: str

    :param filename: Name of the file.
    :type directory: str
    """
    file_to_check = os.path.expanduser(directory) + '/' + filename
    if os.path.isdir(directory) and os.path.isfile(file_to_check):
        return True
        #self.logger.info('Dataset found at {}'.format(file_folder_to_check))
    else:
        return False

def check_files_existence(directory, filenames):
    """
    Checks if all files in the list exist.

    :param directory: Relative path to to folder.
    :type directory: str

    :param filename: List of files
    :type directory: List of strings or a single string with filenames separated by spaces)
    """
    # Check directory existence.
    if not os.path.isdir(directory):
        return False

    # Process list of files.
    if type(filenames) == str:
        filenames = filenames.split(" ")

    # Check files one by one.
    for file in filenames:
        file_to_check = os.path.expanduser(directory) + '/' + file
        if not os.path.isfile(file_to_check):
            return False
    # Ok.
    return True
    

def download(directory, filename, url):
    """
    Checks whether a file or folder exists at given path (relative to storage folder), \
    otherwise downloads files from the given URL.

    :param directory: Relative path to to folder.
    :type directory: str

    :param filename: Name of the file.
    :type directory: str

    :param url: URL to download the file from.
    :type url: str
    """
    if check_file_existence(directory, filename):
        return True
    
    # Download.
    #self.logger.info('Downloading {}'.format(url))
    urllib.request.urlretrieve(url, os.path.expanduser(directory), reporthook)

def reporthook(count, block_size, total_size):
    """
    Progress bar function.
    """
    global start_time
    if count == 0:
            start_time = time.time()
            return
    duration = time.time() - start_time
    progress_size = int(count * block_size)
    speed = int(progress_size / (1024 * duration))
    percent = int(count * block_size * 100 / total_size)
    sys.stdout.write("\r...%d%%, %d MB, %d KB/s, %d seconds passed" %
                     (percent, progress_size / (1024 * 1024), speed, duration))
    sys.stdout.flush()
