"""
Shared helpers for the utility/analyse_*.ipynb notebooks.

Currently just log-file resolution: expanding a glob pattern / list of filenames (optionally
relative to a log_dir) into the concrete rotated driver log files to load. Used identically by
analyse_pec.ipynb and analyse_kf_pid.ipynb, whose own load_pec()/load_kf_pid() differ only in
which log tags (PECLOG vs KFLOG/PIDLOG) they parse out of the resolved files.
"""
import os
import re
from glob import glob


def _has_glob_magic(s: str) -> bool:
    """True if a string contains glob wildcard characters (*, ?, [...])."""
    return any(ch in s for ch in "*?[")


def _join_log_dir(item, log_dir):
    """Join a bare filename/glob onto log_dir, but pass an absolute path through unchanged."""
    return item if os.path.isabs(item) else os.path.join(log_dir, item)


def resolve_log_files(pattern, log_dir='.'):
    """
    Expand a glob pattern (or accept an explicit list) into the set of rotated driver
    logs to load. A multi-hour capture routinely spans several rotated files regardless
    of the configured per-file size cap, so this is the normal path, not a special case.

    Accepts a bare glob string (e.g. 'alpaca.log*' -- filtered to just
    'alpaca.log'/'alpaca.log.<N>', excluding renamed/archived variants like
    'alpaca.mark_*.log' and stray ':Zone.Identifier' sidecar files), or a list where
    each entry is either a literal filename or itself a glob pattern, e.g.
    ['alpaca.soak_nopec_Beta4.3_08_29n*.log'] or a mix of explicit files and globs --
    useful when a soak run's files don't follow the default 'alpaca.log[.N]' rotation
    naming that the bare-glob form filters to. A literal entry with no wildcard is
    passed through unexpanded so a typo'd filename still surfaces as a clear
    FileNotFoundError downstream, rather than silently vanishing the way an unmatched
    glob would.

    Every entry is joined onto log_dir unless it's already absolute, so log_filenames can
    be shortened to bare filenames/globs by pointing log_dir at the session's log
    directory (e.g. log_dir='../logs/logs') instead of repeating it in every entry.
    """
    if isinstance(pattern, str):
        candidates = glob(_join_log_dir(pattern, log_dir))
        return sorted(p for p in candidates if re.search(r"alpaca\.log(\.\d+)?$", os.path.basename(p)))

    paths = []
    for item in pattern:
        full = _join_log_dir(item, log_dir)
        if _has_glob_magic(item):
            paths.extend(sorted(glob(full)))
        else:
            paths.append(full)
    return paths
