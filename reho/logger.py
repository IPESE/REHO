"""Central logging configuration for the REHO package.

REHO is a library first and a set of scripts second: it must therefore never
write directly to ``stdout`` with :func:`print`, and never configure the root
logger on import. All modules log through the ``reho`` logger hierarchy
(``logging.getLogger(__name__)``), and the *application* — a run script, a test,
or a notebook — decides where those messages go by calling
:func:`configure_logging` once.

Examples
--------
>>> from reho.logger import configure_logging
>>> configure_logging("DEBUG")           # verbose, colored if available
>>> configure_logging(enabled=False)     # silence REHO entirely
"""

import logging
import sys

__all__ = ["configure_logging", "get_logger", "logger"]

#: Root logger of the package. Every REHO module logs below it.
logger = logging.getLogger("reho")

# A library must not emit "No handlers could be found" warnings nor print
# anything when the application did not ask for logs.
logger.addHandler(logging.NullHandler())

DEFAULT_FORMAT = "%(message)s"
VERBOSE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def get_logger(name=None):
    """Return the logger of a REHO module.

    Parameters
    ----------
    name : str, optional
        Usually ``__name__``. When omitted, the package root logger is returned.

    Returns
    -------
    logging.Logger
    """
    if name is None or name == "reho":
        return logger
    if name.startswith("reho."):
        return logging.getLogger(name)
    return logger.getChild(name)


def configure_logging(level=logging.INFO, enabled=True, colored=True, stream=None, verbose_format=False):
    """Route REHO log records to a stream handler.

    This is the single entry point an application should use to control REHO's
    verbosity. Calling it repeatedly is safe: the previous REHO handlers are
    replaced rather than stacked.

    Parameters
    ----------
    level : int or str, optional
        Minimum severity to display, e.g. ``logging.DEBUG`` or ``"WARNING"``.
        Default is ``logging.INFO``.
    enabled : bool, optional
        When False, REHO is silenced (only ``CRITICAL`` gets through).
        Default is True.
    colored : bool, optional
        Use `coloredlogs <https://pypi.org/project/coloredlogs/>`_ when it is
        installed and the stream is a TTY. Default is True.
    stream : file-like, optional
        Where to write. Default is ``sys.stdout``.
    verbose_format : bool, optional
        Prefix records with timestamp, level and module name. Default is False,
        which keeps the terse solver-progress style REHO scripts expect.

    Returns
    -------
    logging.Logger
        The configured package logger.
    """
    stream = sys.stdout if stream is None else stream
    fmt = VERBOSE_FORMAT if verbose_format else DEFAULT_FORMAT

    # Drop handlers installed by a previous call, keeping the NullHandler.
    for handler in list(logger.handlers):
        if not isinstance(handler, logging.NullHandler):
            logger.removeHandler(handler)

    if not enabled:
        logger.setLevel(logging.CRITICAL)
        # Records must not reach the application's root handlers either.
        logger.propagate = False
        return logger

    logger.setLevel(level)
    logger.propagate = False

    if colored:
        try:
            import coloredlogs

            coloredlogs.install(level=level, logger=logger, isatty=True, fmt=fmt, stream=stream)
            return logger
        except ImportError:
            pass

    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
    return logger
