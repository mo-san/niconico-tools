#!/usr/bin/env bash
suffix=`date "+%Y%m%d_%H%M"`_${TRAVIS_PYTHON_VERSION}
log_nd=nicotools.log

curl -X PUT -H "Authorization: Bearer $DROPBOX_TOKEN" -T ~/${log_nd} https://content.dropboxapi.com/1/files_put/auto/Travis/${suffix}/${log_nd}
