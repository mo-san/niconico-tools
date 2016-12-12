#!/usr/bin/env bash

curl -X PUT -H "Authorization: Bearer $DROPBOX_TOKEN" -T  ~/nicotools_download.log https://content.dropboxapi.com/1/files_put/auto/Travis/
curl -X PUT -H "Authorization: Bearer $DROPBOX_TOKEN" -T  ~/nicotools_mylist.log https://content.dropboxapi.com/1/files_put/auto/Travis/
