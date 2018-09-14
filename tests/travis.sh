#!/usr/bin/env bash
suffix=`date "+%Y%m%d_%H%M"`_${TRAVIS_PYTHON_VERSION}
log_file=nicotools.log

curl -X POST https://content.dropboxapi.com/2/files/upload\
  --header "Authorization: Bearer ${DROPBOX_TOKEN}"\
  --header 'Dropbox-API-Arg: {"path": "/Travis/${suffix}_${log_file}", "mode": "add"}'\
  --header "Content-Type: application/octet-stream"\
  --data-binary @${log_file}
