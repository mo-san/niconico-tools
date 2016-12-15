# coding: utf-8
import os
import sys

from . import nicodown, nicoml
from .utils import Msg, Err, InheritedParser


def main(arguments=None):
    """
    メイン。

    :param arguments: 引数の文字列
    :rtype: bool
    """
    parser = InheritedParser(fromfile_prefix_chars="+")
    parser.add_argument("-l", "--mail", nargs=1, help=Msg.nd_help_mail, metavar="MAIL")
    parser.add_argument("-p", "--pass", nargs=1, help=Msg.nd_help_password, metavar="PASSWORD", dest="password")
    parser.add_argument("-w", "--what", action="store_true", help=Msg.nd_help_what)
    parser.add_argument("--loglevel", type=str.upper, default="INFO",
                        help=Msg.nd_help_loglevel,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    subparsers = parser.add_subparsers()

    parser_nd = subparsers.add_parser("download", aliases=["d"], help=Msg.nd_description)
    parser_nd.set_defaults(func=nicodown.main)
    parser_nd.add_argument("VIDEO_ID", nargs="+", type=str, help=Msg.nd_help_video_id)
    parser_nd.add_argument("-w", "--what", action="store_true", help=Msg.nd_help_what)
    # nargs があるとリストに値が入る。
    parser_nd.add_argument("-l", "--mail", nargs=1, help=Msg.nd_help_mail, metavar="MAIL")
    parser_nd.add_argument("-p", "--pass", nargs=1, help=Msg.nd_help_password, metavar="WORD", dest="password")
    parser_nd.add_argument("-d", "--dest", nargs=1, type=str, default=[os.getcwd()], help=Msg.nd_help_destination)
    parser_nd.add_argument("-c", "--comment", action="store_true", help=Msg.nd_help_comment)
    parser_nd.add_argument("-v", "--video", action="store_true", help=Msg.nd_help_video)
    parser_nd.add_argument("-t", "--thumbnail", action="store_true", help=Msg.nd_help_thumbnail)
    parser_nd.add_argument("-i", "--getthumbinfo", action="store_true", help=Msg.nd_help_info)
    parser_nd.add_argument("-x", "--xml", action="store_true", help=Msg.nd_help_xml)
    parser_nd.add_argument("-o", "--out", nargs=1, help=Msg.nd_help_outfile, metavar="FILE")
    parser_nd.add_argument("--loglevel", type=str.upper, default="INFO",
                        help=Msg.nd_help_loglevel,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

    parser_ml = subparsers.add_parser("mylist", aliases=["m"], help=Msg.ml_description)
    parser_ml.set_defaults(func=nicoml.main)
    parser_ml.add_argument("src", nargs=1, help=Msg.ml_help_src, metavar="マイリスト名")
    parser_ml.add_argument("-w", "--what", action="store_true", help=Msg.nd_help_what)
    parser_ml.add_argument("-l", "--mail", nargs=1, help=Msg.nd_help_mail, metavar="MAIL")
    parser_ml.add_argument("-p", "--pass", nargs=1, help=Msg.nd_help_password, metavar="WORD", dest="password")
    parser_ml.add_argument("-i", "--id", action="store_true", help=Msg.ml_help_id)
    parser_ml.add_argument("-o", "--out", nargs=1, help=Msg.ml_help_outfile, metavar="FILE")
    parser_ml.add_argument("--yes", action="store_true", help=Msg.ml_help_yes)
    parser_ml.add_argument("--loglevel", type=str.upper, default="INFO",
                        help=Msg.nd_help_loglevel,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
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
    if len(sys.argv) <= 1 and not int(os.getenv("PYTHON_TEST")):
        parser.print_help() or sys.exit()
    if args.what:
        print(args) or sys.exit()

    try:
        return args.func(args)
    except KeyboardInterrupt:
        sys.exit(Err.keyboard_interrupt)

if __name__ == "__main__":
    main()
