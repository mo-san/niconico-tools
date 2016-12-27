[![Build Status](https://travis-ci.org/mo-san/niconico-tools.svg?branch=master)](https://travis-ci.org/mo-san/niconico-tools)
[![codecov](https://codecov.io/gh/mo-san/niconico-tools/branch/master/graph/badge.svg)](https://codecov.io/gh/mo-san/niconico-tools)
[![Coverage Status](https://coveralls.io/repos/github/mo-san/niconico-tools/badge.svg?branch=master)](https://coveralls.io/github/mo-san/niconico-tools?branch=master)
[![Code Health](https://landscape.io/github/mo-san/niconico-tools/master/landscape.svg?style=flat)](https://landscape.io/github/mo-san/niconico-tools/master)
[![PyPI version](https://badge.fury.io/py/nicotools.svg)](https://pypi.python.org/pypi/nicotools)

Here is a description page written in Japanese.
Not able to read? -> [Read Me (English)](./README_en.md)

# nicotools

a niconico oriented tool.

# Features

ニコニコ動画の動画やコメントやサムネイル画像をダウンロードできる Python 製のコマンドラインツールです。
それだけでなく、マイリストの操作もシンプルな書き方でできるように作ってあります。

できること:

* サムネイル  
    * 小さいほう (130x100) も大きいほう (360x270) も(古いのは小のみ)。

* コメント
    * XML 形式でも JSON でも(古いのはXMLのみ)。

* 動画
    * "smile" サーバー (従来サーバー) でも "dmc.nico" サーバー (いわゆる新サーバー、2016年以降の動画).

* 動画の **分割同時ダウンロード**
    * デフォルトで4分割。分割数に制限なし。

* マイリストの新規作成・削除

* マイリストに動画を追加・削除・移動・コピー

# How It Works
![how it works](https://raw.github.com/wiki/mo-san/niconico-tools/images/nicotools_running_sample.gif)


# Installation

```bash
pip install nicotools
```

### Requirements

* Python >= 3.4
* requests
* prettytable
* bs4 (BeautifulSoup4)
* aiohttp
* tqdm


# Usage

引数なしで実行するとヘルプを表示します。

```
>nicotools
usage: nicotools [-h] [-l MAIL] [-p PASSWORD] [-w]
                 [--loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                 {download,d,mylist,m} ...

nicotools downlaod --help または nicotools mylist --help
で各コマンドのヘルプを表示します。

positional arguments:
  {download,d,mylist,m}
    download (d)        動画のいろいろをダウンロードします。
    mylist (m)          マイリストを扱います。 add, delete, move, copy
                        の引数にはテキストファイルも指定できます。
                        その場合はファイル名の先頭に "+" をつけます。 例:+"C:/ids.txt"

optional arguments:
  -h, --help            show this help message and exit
  -l MAIL, --mail MAIL  メールアドレス
  -p PASSWORD, --pass PASSWORD
                        パスワード
  -w, --what            コマンドの確認用。 引数の内容を書き出すだけです。
  --loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        ログ出力の詳細さ。 デフォルトは INFO です。
```

```
>nicotools mylist --help
usage: nicotools mylist [-h] [--loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                        [-w] [-l MAIL] [-p WORD] [-i] [-o FILE] [--yes]
                        [--each] [-t To] [-a sm... [sm... ...]]
                        [-d sm... [sm... ...]] [-m sm... [sm... ...]]
                        [-c sm... [sm... ...]] [-r] [--purge] [-s] [-e]
                        [--everything]
                        マイリスト名

positional arguments:
  マイリスト名          移動(コピー)元、 あるいは各種の操作対象の、マイリストの名前

optional arguments:
  -h, --help            show this help message and exit
  --loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        ログ出力の詳細さ。 デフォルトは INFO です。
  -w, --what            コマンドの確認用。 引数の内容を書き出すだけです。
  -l MAIL, --mail MAIL  メールアドレス
  -p WORD, --pass WORD  パスワード
  -i, --id              マイリストの指定に、 名前の代わりにそのIDを使います。
  -o FILE, --out FILE   そのファイル名で テキストファイルに出力します。
  --yes                 これを指定すると、マイリスト自体の削除やマイリスト内の
                        全項目の削除の時に確認しません。
  --each                指定すると、登録や削除を、まとめずに一つずつ行います。

リスト中の項目を操作する:
  -t To, --to To        移動(コピー)先のマイリストの名前
  -a sm... [sm... ...], --add sm... [sm... ...]
                        指定したIDの動画を マイリストに追加します。
  -d sm... [sm... ...], --delete sm... [sm... ...]
                        そのマイリストから 指定したIDの動画を削除します。
                        動画IDの代わりに * を指定すると、マイリストを空にします。
  -m sm... [sm... ...], --move sm... [sm... ...]
                        移動元から移動先へと 動画を移動します。
  -c sm... [sm... ...], --copy sm... [sm... ...]
                        コピー元からコピー先へと 動画をコピーします。
                        動画IDの代わりに * を指定すると、マイリスト全体をコピーします。

マイリスト自体を操作する:
  -r, --create          指定した名前で 新しくマイリストを作成します。
  --purge               そのマイリスト自体を削除します。 取り消しはできません。
  -s, --show            登録された動画の情報をタブ区切り形式で出力します。
                        名前の代わりに * を指定するとマイリスト全体のメタデータを
                        出力します。-ss のように2回指定すると表形式で表示します。
  -e, --export          登録された動画IDのみを改行で区切り、出力します。
                        名前の代わりに * を指定すると全マイリストを一覧にします。
  --everything          show や export と同時に指定すると、全てのマイリストの
                        情報をまとめて取得します。
```

```
>nicotools download --help
usage: nicotools download [-h]
                          [--loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                          [-w] [-l MAIL] [-p WORD] [-d DEST] [-c] [-v] [-t]
                          [-i] [-x] [-o FILE] [--smile] [--dmc]
                          [--limit LIMIT] [--nomulti] [--nosieve]
                          VIDEO_ID [VIDEO_ID ...]
   
   positional arguments:
     VIDEO_ID              ダウンロードしたい動画ID。 例: sm12345678
                           テキストファイルも指定できます。その場合はファイル名の
                           先頭に "+" をつけます。 例: +"C:/ids.txt"
   
   optional arguments:
     -h, --help            show this help message and exit
     --loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                           ログ出力の詳細さ。 デフォルトは INFO です。
     -w, --what            コマンドの確認用。 引数の内容を書き出すだけです。
     -l MAIL, --mail MAIL  メールアドレス
     -p WORD, --pass WORD  パスワード
     -d DEST, --dest DEST  ダウンロードしたものを保存する フォルダーへのパス。
     -c, --comment         指定すると、 コメントをダウンロードします。
     -v, --video           指定すると、 動画をダウンロードします。
     -t, --thumbnail       指定すると、 サムネイルをダウンロードします。
     -i, --getthumbinfo    getthumbinfo API から動画の情報のみを ダウンロードします。
     -x, --xml             指定すると、コメントをXML形式でダウンロードします。
                           チャンネル動画の場合は無視されます。
     -o FILE, --out FILE   --getthumbinfo の結果をそのファイル名で テキストファイルに出力します。
     --smile               動画をsmileサーバー(いわゆる従来サーバー)からダウンロードします。
     --dmc                 動画をDMCサーバー(いわゆる新サーバー)からダウンロードします。標準はこちらです。
     --limit LIMIT         サムネイルとコメントについては同時ダウンロードを、
                           動画については1つあたりの分割数をこの数に制限します。標準は 4 です。
     --nomulti             指定すると、プログレスバーを複数行で表示しません。
     --nosieve             指定すると、動画とコメントについて、非公開や削除済みの
                           項目でもダウンロードを試みます。
```


## Usage as a CLI tool

最初に起動したときはメールアドレスとパスワードを聞かれるので入力してください。次回以降は、クッキーが保存されますので入力は要りません。
コマンドで明示的に指定できます。

```bash
nicotools download -v sm9 --mail "mail@example.com" --pass "password"
```

### Downloading

* sm1, ... sm5 のサムネイル:

    ``nicotools downlaod --thumbnail --dest "./Downloads" sm1 sm2 sm3 sm4 sm5``

* それらのサムネイル・コメント・動画:

    ``nicotools download --comment --video --thumbnail --dest "./Downloads" sm1 sm2 sm3 sm4 sm5``

* 動画IDを一行ごとに書いたテキストファイルを読み込ませてダウンロード (ファイル名の前に "+" をつける):

    ``nicotools download -cvt -d "./Downloads" +ids.txt``

* XML 形式のコメント (デフォルトではJSON):
    
    ``--dest`` は保存するディレクトリーのパス。
    ``--comment --video --thumbnail`` はそれぞれ ``-c -v -t``と略記でき、さらにまとめて ``-cvt`` と書けます(順不同)。

    ``nicotools download -cvt --xml -dest "./Downloads" sm1``

* 「まいりすと」という名前のマイリストに登録された動画をすべてダウンロード:

    ```
    nicotools mylist まいりすと --export --out D:/Downloads/all.txt
    nicotools download -v +D:/Downloads/all.txt
    ```

----------
### Dealing with Mylists

* MYLIST に追加する:

    ``nicotools mylist MYLIST --add sm1 sm2 sm3``

* 一行にひとつ動画IDを書いたテキストファイルから追加する:

    ``nicotools mylist MYLIST --add +C:/Users/Me/Desktop/ids.txt``

* 同名のマイリストがある場合は、IDで指定してください。IDはマイリストのURLの末尾にありますし、``--export`` コマンドでも表示されます:

    ``nicotools mylist 12345678 --id --add sm1 sm2 sm3``

* MYLIST から削除する:

    ``nicotools mylist MYLIST --delete sm1 sm2 sm3``

* MYLIST から全て削除し、まっさらにする:

    ``nicotools mylist MYLIST --delete *``

* 確認なしでまっさらにする:

    ``nicotools mylist MYLIST --delete * --yes``

* MYLIST にある動画を foofoo に移動する:

    ``nicotools mylist MYLIST --to foofoo --move sm1 sm2 sm3``

* MYLIST にある全ての動画を barbar に移動する:

    ``nicotools mylist MYLIST --to barbar --move *``

* MYLIST にある動画を barboo にコピーする:

    ``nicotools mylist MYLIST --to baaboo --copy sm1 sm2 sm3``

* MYLIST にある全ての動画を barboo にコピーする:

    ``nicotools mylist MYLIST --to foobar --copy *``

* 全てのマイリストのID、名前、件数、作成日などを表示する:

    ``nicotools mylist * --show``

* 全てのマイリストの全ての動画を表示する(タブ区切りテキスト):

    ``nicotools mylist * --show --everything --out D:/Downloads/all.txt``

* 全てのマイリストの全ての動画を表示する(表形式テキスト):

    ``nicotools mylist * --show --show --everything --out D:/Downloads/all.txt``

* 単独のマイリストの動画IDだけを書き出す:

    ``nicotools mylist MYLIST --export``

* 全てのマイリストの動画IDだけを書き出す:

    ``nicotools mylist * --export --everything --out D:/Downloads/all.txt``

* 全てのマイリストのIDと名前を表示する:

    ``nicotools mylist * --export --out D:/Downloads/all.txt``

* LISTNAME という名前で新規作成する:

    ``nicotools mylist LISTNAME --create``

* マイリスト自体を削除する:

    ``nicotools mylist MYLIST --purge``

* マイリスト自体を確認なしで削除する:

    ``nicotools mylist MYLIST --purge --yes``

## Usage as a module

``_async`` がつかない ``nicodown`` や ``nicoml`` は 非同期処理をしません。

```python
from nicotools.nicodown_async import VideoDmc, VideoSmile
from nicotools.nicodown_async import Comment, Thumbnail

mail = "<your mail address>"
password = "<your password>"
xml = True # True にするとXML形式で取ってくる。指定がなければ JSON。

# 動画IDのリスト
video_ids = ["sm1", "sm2", "sm3"]

# 保存場所
DIR_PATH = "./downloads/"

Thumbnail().start(video_ids, DIR_PATH)

Comment(mail, password).start(video_ids, DIR_PATH, xml)

VideoSmile(mail, password).start(video_ids, DIR_PATH)

VideoDmc(mail, password).start(video_ids, DIR_PATH)
```
