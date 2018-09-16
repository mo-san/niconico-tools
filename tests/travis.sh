#!/usr/bin/env bash
prefix=`date "+%Y%m%d_%H%M"`_${TRAVIS_PYTHON_VERSION}
log_file=nicotools.log

cd ~
curl -X POST https://content.dropboxapi.com/2/files/upload\
  --header "Authorization: Bearer ${DROPBOX_TOKEN}"\
  --header "Dropbox-API-Arg: {\"path\": \"/Travis/${prefix}_${log_file}\", \"mode\": \"add\"}"\
  --header "Content-Type: application/octet-stream"\
  --data-binary @${log_file}
