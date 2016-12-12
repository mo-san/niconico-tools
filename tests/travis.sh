#!/usr/bin/env bash
suffix=`date "+%Y%m%d"`_${TRAVIS_PYTHON_VERSION}
curl -X PUT -H "Authorization: Bearer $DROPBOX_TOKEN" -T  ~/nicotools_download.log https://content.dropboxapi.com/1/files_put/auto/Travis/${suffix}
curl -X PUT -H "Authorization: Bearer $DROPBOX_TOKEN" -T  ~/nicotools_mylist.log https://content.dropboxapi.com/1/files_put/auto/Travis/${suffix}
