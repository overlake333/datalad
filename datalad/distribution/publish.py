# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""High-level interface for dataset (component) publishing

"""

import logging

from datalad.interface.base import Interface
from datalad.interface.utils import filter_unmodified
from datalad.interface.common_opts import annex_copy_opts, recursion_flag, \
    recursion_limit, git_opts, annex_opts
from datalad.support.param import Parameter
from datalad.support.constraints import EnsureStr
from datalad.support.constraints import EnsureNone
from datalad.support.annexrepo import AnnexRepo
from datalad.support.exceptions import InsufficientArgumentsError

from .dataset import EnsureDataset
from .dataset import Dataset
from .dataset import datasetmethod

__docformat__ = 'restructuredtext'

lgr = logging.getLogger('datalad.distribution.publish')

# TODO: make consistent configurable output


def _log_push_info(pi_list):
    from git.remote import PushInfo as PI

    if pi_list:
        for push_info in pi_list:
            if (push_info.flags & PI.ERROR) == PI.ERROR:
                lgr.error(push_info.summary)
            else:
                lgr.info(push_info.summary)
    else:
        lgr.warning("Nothing was pushed.")


def _publish_dataset(ds, remote, refspec, paths, annex_copy_options):
    published, skipped = [], []
    # upstream refspec needed for update (merge) and subsequent push,
    # in case there is no.
    # no tracking refspec yet?
    # TODO what if `to` was given, doesn't have tracking info in this case
    set_upstream = refspec is None

    # check if there are any differences wrt the to-be-published paths,
    # and if not skip this dataset
    if refspec:
        # we have a matching branch on the other side
        diff = ds.repo.repo.commit().diff(
            refspec.replace(
                'refs/heads/',
                'refs/remotes/{}/'.format(remote)),
            paths=paths)
    else:
        # there was no tracking branch, check the push target
        active_branch = ds.repo.get_active_branch()
        refspec = active_branch
        if active_branch in ds.repo.repo.remotes[remote].refs:
            # we know some remote state -> diff
            diff = ds.repo.repo.commit().diff(
                ds.repo.repo.remotes[remote].refs[active_branch],
                paths=paths)
        else:
            # we don't have any remote state, need to push for sure
            diff = True
    if not diff:
        return published, skipped

    # in order to be able to use git's config to determine what to push,
    # we need to annex merge first. Otherwise a git push might be
    # rejected if involving all matching branches for example.
    # Once at it, also push the annex branch right here.
    if isinstance(ds.repo, AnnexRepo):
        ds.repo.fetch(remote=remote)
        ds.repo.merge_annex(remote)
        _log_push_info(ds.repo.push(remote=remote,
                                    refspec="git-annex:git-annex"))

    # publishing of `remote` might depend on publishing other
    # remote(s) first:
    # define config var name for potential publication dependencies
    depvar = 'remote.{}.datalad-publish-depends'.format(remote)
    for d in ds.config.get(depvar, []):
        lgr.info("Dependency detected: '%s'" % d)
        # call this again to take care of the dependency first,
        # but keep the paths the same, as the goal is to publish those
        # to the primary remote, and not anything elase to a dependency
        pblsh, skp = _publish_dataset(ds, d, None, paths)
        published.extend(pblsh)
        skipped.extend(skp)

    lgr.info("Publishing {0} to {1}".format(ds, remote))

    # we now know where to push to:
    # TODO: what to push? default: git push --mirror if nothing configured?
    # consider also: --follow-tags, --tags, --atomic

    # Note: git's push.default is 'matching', which possibly doesn't
    # work for first
    # time publication (a branch, that doesn't exist on remote yet)
    # But if we want to respect remote.*.push entries, etc. we need to
    # not pass a specific refspec (like active branch) to `git push`
    # by default.

    _log_push_info(ds.repo.push(remote=remote,
                                refspec=refspec,
                                set_upstream=set_upstream))

    published.append(ds)

    if (paths or annex_copy_opts) and \
            isinstance(ds.repo, AnnexRepo) and not \
            ds.config.get('remote.{}.annex-ignore', False):
        lgr.info("Publishing data of dataset {0} ...".format(ds))
        pblshd = ds.repo.copy_to(files=paths,
                                remote=remote,
                                options=annex_copy_options)
        published += pblshd

    return published, skipped


class Publish(Interface):
    """Publish a dataset to a known :term:`sibling`.

    This makes the last saved state of a dataset available to a sibling
    or special remote data store of the dataset which must already exist
    and be known to the dataset.

    .. note::
      Power-user info: This command uses :command:`git push`, and :command:`git annex copy`
      to publish a dataset. Publication targets are either configured remote
      Git repositories, or git-annex special remotes (if their support data
      upload).
    """
    # TODO: Figure out, how to tell about tracking branch/upstream
    #      (and the respective remote)
    #      - it is used, when no destination is given
    #      - it is configured to be the given destination, if there was no
    #        upstream set up before, so you can use just "datalad publish" next
    #        time.

    # TODO: Doc!

    _params_ = dict(
        dataset=Parameter(
            args=("-d", "--dataset"),
            metavar='DATASET',
            doc="""specify the dataset to publish. If no dataset is given, an
            attempt is made to identify the dataset based on the current
            working directory""",
            constraints=EnsureDataset() | EnsureNone()),
        to=Parameter(
            args=("--to",),
            metavar='LABEL',
            doc="""sibling name identifying the publication target. If no
            destination is given an attempt is made to identify the target
            based on the dataset's configuration (i.e. a set up tracking
            branch)""",
            # TODO: See TODO at top of class!
            constraints=EnsureStr() | EnsureNone()),
        since=Parameter(
            args=("--since",),
            constraints=EnsureStr() | EnsureNone(),
            doc="""When publishing dataset(s), specifies commit (treeish, tag, etc)
            from which to look for changes
            to decide either updated publishing is necessary for this and which children.
            If empty argument is provided, then we will always run publish command.
            By default, would take from the previously published to that remote/sibling
            state (for the current branch)"""),
        # since: commit => .gitmodules diff to head => submodules to publish

        skip_failing=Parameter(
            args=("--skip-failing",),
            action="store_true",
            doc="skip failing sub-datasets (incombination with `recursive`) "
                "instead of failing altogether"),
        path=Parameter(
            args=("path",),
            metavar='PATH',
            doc="path(s), that may point to file handle(s) to publish including "
                "their actual content or to subdataset(s) to be published. If a "
                "file handle is published with its data, this implicitly means "
                "to also publish the (sub)dataset it belongs to. '.' as a path "
                "is treated in a special way in the sense, that it is passed "
                "to subdatasets in case `recursive` is also given.",
            constraints=EnsureStr() | EnsureNone(),
            nargs='*'),
        recursive=recursion_flag,
        recursion_limit=recursion_limit,
        git_opts=git_opts,
        annex_opts=annex_opts,
        annex_copy_opts=annex_copy_opts
    )

    @staticmethod
    @datasetmethod(name='publish')
    def __call__(
            path=None,
            dataset=None,
            to=None,
            since=None,
            skip_failing=False,
            recursive=False,
            recursion_limit=None,
            git_opts=None,
            annex_opts=None,
            annex_copy_opts=None):

        if since and not dataset:
            raise InsufficientArgumentsError(
                'Modification detection (--since) without a base dataset '
                'is not supported')

        if dataset and not path:
            # act on the whole dataset if nothing else was specified
            path = dataset.path if isinstance(dataset, Dataset) else dataset
        content_by_ds, unavailable_paths = Interface._prep(
            path=path,
            dataset=dataset,
            recursive=recursive,
            recursion_limit=recursion_limit)
        if unavailable_paths:
            raise ValueError(
                'cannot publish content that is not available locally: %s',
                unavailable_paths)
        results = []

        # here is the plan
        # 1. figure out remote to publish to
        # 2. figure out which content needs to be published to this remote
        # 3. look for any pre-publication dependencies of that remote
        #    (i.e. remotes that need to be published to before)
        # 4. publish the content needed to go to the primary remote to
        #    the dependencies first, and to the primary afterwards
        ds_remote_info = {}
        for ds_path in content_by_ds:
            ds = Dataset(ds_path)
            # TODO move detection of publication dependencies into this loop too!
            if to is None:
                # we need an upstream remote, if there's none given. We could
                # wait for git push to complain, but we need to explicitly
                # figure it out for pushing annex branch anyway and we might as
                # well fail right here.
                track_remote, track_refspec = ds.repo.get_tracking_branch()
                if track_remote:
                    ds_remote_info[ds_path] = dict(zip(
                        ('remote', 'refspec'),
                        (track_remote, track_refspec)))
                elif skip_failing:
                    lgr.warning(
                        'Cannot determine target sibling, skipping %s',
                        ds)
                    ds_remote_info[ds_path] = None
                else:
                    # we have no remote given and no upstream => fail
                    raise InsufficientArgumentsError(
                        'Cannot determine target sibling for %s' % (ds,))
            elif to not in ds.repo.get_remotes():
                # unknown given remote
                if skip_failing:
                    lgr.warning(
                        "Unknown target sibling '%s', skipping %s",
                        to, ds)
                    ds_remote_info[ds_path] = None
                else:
                    raise ValueError(
                        "Unknown target sibling '%s' for %s" % (to, ds))
            else:
                # all good: remote given and is known
                ds_remote_info[ds_path] = {'remote': to}
            # TODO more per repo apriori checks here?

        if dataset and since:
            # remove all unmodified components from the spec
            content_by_ds = filter_unmodified(
                content_by_ds, dataset, since)

        published, skipped = [], []
        for ds_path in content_by_ds:
            remote_info = ds_remote_info[ds_path]
            if not remote_info:
                # in case we are skipping
                continue
            # and publish
            ds = Dataset(ds_path)
            pblsh, skp = _publish_dataset(
                ds,
                remote=remote_info['remote'],
                refspec=remote_info.get('refspec', None),
                paths=content_by_ds[ds_path],
                annex_copy_options=annex_copy_opts)
            published.extend(pblsh)
            skipped.extend(skp)
        return published, skipped

    @staticmethod
    def result_renderer_cmdline(results, args):
        from datalad.ui import ui
        for res, res_label in zip(results, ('published', 'skipped')):
            if not res:
                if res_label == 'published':
                    ui.message("Nothing was %s" % res_label)
                continue
            msg = "{n} {obj} {res_label}:\n".format(
                obj='items were' if len(res) > 1 else 'item was',
                n=len(res),
                res_label=res_label)
            for item in res:
                if isinstance(item, Dataset):
                    msg += "Dataset: %s\n" % item.path
                else:
                    msg += "File: %s\n" % item
            ui.message(msg)
