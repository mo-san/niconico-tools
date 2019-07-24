[![Build Status](https://travis-ci.org/mo-san/niconico-tools.svg?branch=master)](https://travis-ci.org/mo-san/niconico-tools)
[![Coverage Status](https://coveralls.io/repos/github/mo-san/niconico-tools/badge.svg?branch=master)](https://coveralls.io/github/mo-san/niconico-tools?branch=master)
[![PyPI version](https://badge.fury.io/py/nicotools.svg)](https://pypi.python.org/pypi/nicotools)

[日本語の説明文はこちら (README.md)](./README.md)

# nicotools

a niconico oriented tool.

# Features

This is a command-line tool and python utility module to download videos, comments and thumbnail images on niconico (nicovideo.jp).
And also with this you can handle your Mylists: add, delete, move and copy each items and create or remove new lists.

* Thumbnails: larger and smaller ones.
* Comments: in XML and JSON format.
* Videos: in both types, i.e. of "smile" server (older one) and of "dmc.nico" server (newer one).
* **Concurrent download** (4x faster by default).


# How It Works
![how it works](https://user-images.githubusercontent.com/8792364/45593949-bff87c00-b9cc-11e8-8d51-13a530f7564e.gif)


# Installation

```bash
pip install nicotools
```

### Requirements

* Python >= 3.6


# Usage

By running without any arguments, we will show you a help.

## Usage as a CLI tool

For the first time you will asked your mail address and password.
From the next time on HTTP Cookie will be saved in to your HOME directory, so mail and pass are not needed.
Or you may specify your credentials every time you run this, as this:

```bash
nicotools download -v sm9 --mail "mail@example.com" --pass "password"
```

### Downloading

* To download thumbnails of video ids of sm1, ... sm5:

    ``nicotools download --thumbnail --dest "./Downloads" sm1 sm2 sm3 sm4 sm5``

* To downalod thumbnails, comments and videos of those:

    ``nicotools download --comment --video --thumbnail --dest "./Downloads" sm1 sm2 sm3 sm4 sm5``

* Shorthand commands and how to specify video ids from text file (prepend plus sign):

    ``nicotools download -cvt -d "./Downloads" +ids.txt``

* XML comment ("--dest" is for destination directory):

    ``nicotools download -cvt --xml -dest "./Downloads" sm1``

* to list up whole contents in all LISTS (TAB separated format):

    ``nicotools mylist * --show --everything --out D:/Downloads/all.txt``

----------
### Dealing with Mylists

* to apped videos on MYLIST:

    ``nicotools mylist MYLIST --add sm1 sm2 sm3``

* another way to append: from a text file, in which video id in each lines are written:

    ``nicotools mylist MYLIST --add +C:/Users/Me/Desktop/ids.txt``

* specify the MYLIST by its ID (this is shown in the LIST's URL):

    ``nicotools mylist 12345678 --id --add sm1 sm2 sm3``

* to delete items from MYLIST:

    ``nicotools mylist MYLIST --delete sm1 sm2 sm3``

* to clear the MYLIST:

    ``nicotools mylist MYLIST --delete *``

* to clear the MYLIST without confirmation:

    ``nicotools mylist MYLIST --delete * --yes``

* to move some items in MYLIST to --to:

    ``nicotools mylist MYLIST --to foofoo --move sm1 sm2 sm3``

* to copy entire items in MYLIST to --to:

    ``nicotools mylist MYLIST --to barbar --move *``

* to copy some items in MYLIST to --to:

    ``nicotools mylist MYLIST --to baaboo --copy sm1 sm2 sm3``

* to copy entire items in MYLIST to --to:

    ``nicotools mylist MYLIST --to foobar --copy *``

* to list up all LIST's names:

    ``nicotools mylist * --show``

* to list up whole contents in all LISTS (TAB separated format):

    ``nicotools mylist * --show --everything --out D:/Downloads/all.txt``

* to list up whole contents in all LISTS (TABLE format):

    ``nicotools mylist * --show --show --everything --out D:/Downloads/all.txt``

* to list up items in a single LIST:

    ``nicotools mylist MYLIST --export``

* to list up video ids of whole contents in all LISTS:

    ``nicotools mylist * --export --everything --out D:/Downloads/all.txt``

* to list up the metadata of LISTS:

    ``nicotools mylist * --export --out D:/Downloads/all.txt``

* to create new LIST with name of LISTNAME:

    ``nicotools mylist LISTNAME --create``

* to remove the LIST:

    ``nicotools mylist MYLIST --purge``

* to remove the LIST without cconfirmation:

    ``nicotools mylist MYLIST --purge --yes``

## Usage as a module

```python
from nicotools.download import Video, Comment, Thumbnail

mail = "<your mail address>"
password = "<your password>"
xml = True  # Set to True if you want in XML format, default is JSON

# a list of video ids
video_ids = ["sm1", "sm2", "sm3"]
# directory path to save files in
dir_path = "./downloads/"

Thumbnail(video_ids, dir_path).start()

Comment(video_ids, mail=mail, password=password, save_dir=dir_path, xml=xml).start()

Video(video_ids, save_dir=dir_path, mail=mail, password=password).start()
```
