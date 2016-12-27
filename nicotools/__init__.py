# coding: UTF-8
import os
import sys

from . import nicodown, nicoml
from .utils import Msg, Err, InheritedParser

if sys.version_info >= (3, 5):
    from . import nicodown_async, nicoml_async
else:
    nicodown_async, nicoml_async = None, None


def main(arguments=None, async_=True):
    """
    メイン。

    :param arguments: 引数の文字列
    :param bool async_:
    :rtype: bool
    """
    choices = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    parser = InheritedParser(prog="nicotools", fromfile_prefix_chars="+", description=Msg.description)
    # nargs があると値はリストに入る。
    parser.add_argument("-l", "--mail", nargs=1, help=Msg.nd_help_mail, metavar="MAIL")
    parser.add_argument("-p", "--pass", nargs=1, help=Msg.nd_help_password, metavar="PASSWORD", dest="password")
    parser.add_argument("-w", "--what", action="store_true", help=Msg.nd_help_what)
    parser.add_argument("--loglevel", type=str.upper, default="INFO", help=Msg.nd_help_loglevel, choices=choices)
    subparsers = parser.add_subparsers()


    parser_nd = subparsers.add_parser("download", aliases=["d"], help=Msg.nd_description)
    if async_ and nicodown_async is not None:
        parser_nd.set_defaults(func=nicodown_async.main)
    else:
        parser_nd.set_defaults(func=nicodown.main)
    parser_nd.add_argument("VIDEO_ID", nargs="+", type=str, help=Msg.nd_help_video_id)
    parser_nd.add_argument("--loglevel", type=str.upper, default="INFO", help=Msg.nd_help_loglevel, choices=choices)
    parser_nd.add_argument("-w", "--what", action="store_true", help=Msg.nd_help_what)
    parser_nd.add_argument("-l", "--mail", nargs=1, help=Msg.nd_help_mail, metavar="MAIL")
    parser_nd.add_argument("-p", "--pass", nargs=1, help=Msg.nd_help_password, metavar="WORD", dest="password")
    parser_nd.add_argument("-d", "--dest", nargs=1, type=str, default=[os.getcwd()], help=Msg.nd_help_destination)
    parser_nd.add_argument("-c", "--comment", action="store_true", help=Msg.nd_help_comment)
    parser_nd.add_argument("-v", "--video", action="store_true", help=Msg.nd_help_video)
    parser_nd.add_argument("-t", "--thumbnail", action="store_true", help=Msg.nd_help_thumbnail)
    parser_nd.add_argument("-i", "--getthumbinfo", action="store_true", help=Msg.nd_help_info)
    parser_nd.add_argument("-x", "--xml", action="store_true", help=Msg.nd_help_xml)
    parser_nd.add_argument("-o", "--out", nargs=1, help=Msg.nd_help_outfile, metavar="FILE")
    if async_ and nicodown_async is not None:
        parser_nd.add_argument("--smile", action="store_true", help=Msg.nd_help_smile)
        parser_nd.add_argument("--dmc", action="store_true", help=Msg.nd_help_dmc, default=True)
        parser_nd.add_argument("--limit", type=int, help=Msg.nd_help_limit, default=4)
        parser_nd.add_argument("--nomulti", action="store_false", help=Msg.nd_help_nomulti, dest="nomulti")
        parser_nd.add_argument("--nosieve", action="store_false", help=Msg.nd_help_sieve)


    parser_ml = subparsers.add_parser("mylist", aliases=["m"], help=Msg.ml_description)
    if async_ and nicoml_async is not None:
        parser_ml.set_defaults(func=nicoml_async.main)
    else:
        parser_ml.set_defaults(func=nicoml.main)
    parser_ml.add_argument("src", nargs=1, help=Msg.ml_help_src, metavar="マイリスト名")
    parser_ml.add_argument("--loglevel", type=str.upper, default="INFO", help=Msg.nd_help_loglevel, choices=choices)
    parser_ml.add_argument("-w", "--what", action="store_true", help=Msg.nd_help_what)
    parser_ml.add_argument("-l", "--mail", nargs=1, help=Msg.nd_help_mail, metavar="MAIL")
    parser_ml.add_argument("-p", "--pass", nargs=1, help=Msg.nd_help_password, metavar="WORD", dest="password")
    parser_ml.add_argument("-i", "--id", action="store_true", help=Msg.ml_help_id)
    parser_ml.add_argument("-o", "--out", nargs=1, help=Msg.ml_help_outfile, metavar="FILE")
    parser_ml.add_argument("--yes", action="store_true", help=Msg.ml_help_yes)
    if async_ and nicoml_async is not None:
        parser_ml.add_argument("--each", action="store_true", help=Msg.ml_help_each)

    group_one = parser_ml.add_argument_group(Msg.ml_help_group_a)
    group_one.add_argument("-t", "--to", nargs=1, help=Msg.ml_help_to, metavar="To")
    group_one.add_argument("-a", "--add", nargs="+", help=Msg.ml_help_add, metavar="sm...")
    group_one.add_argument("-d", "--delete", nargs="+", help=Msg.ml_help_delete, metavar="sm...")
    group_one.add_argument("-m", "--move", nargs="+", help=Msg.ml_help_move, metavar="sm...")
    group_one.add_argument("-c", "--copy", nargs="+", help=Msg.ml_help_copy, metavar="sm...")

    group_two = parser_ml.add_argument_group(Msg.ml_help_group_b)
    group_two.add_argument("-r", "--create", action="store_true", help=Msg.ml_help_create)
    group_two.add_argument("--purge", action="store_true", help=Msg.ml_help_purge)
    group_two.add_argument("-s", "--show", action="count", help=Msg.ml_help_show)
    group_two.add_argument("-e", "--export", action="count", help=Msg.ml_help_export)
    group_two.add_argument("--everything", action="store_true", help=Msg.ml_help_everything)

    args = parser.parse_args(globals().get("DEBUG_ARGS") or arguments)
    if (len(sys.argv) <= 1 or not hasattr(args, "func")) and not int(os.getenv("PYTHON_TEST", 0)):
        parser.print_help()
        sys.exit()
    if args.what:
        print(args)
        sys.exit()

    try:
        return args.func(args)
    except KeyboardInterrupt:
        sys.exit(Err.keyboard_interrupt)

if __name__ == "__main__":
    main()
