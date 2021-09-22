import subprocess
import pathlib
import tempfile
import shutil


def git(local_directory, git_repo_url, branch, msg='automata commit'):
    """Make the remote git repo look like the local directory.

    Parameters
    ----------
    local_directory : pathlib.Path
        Path to a local directory whose contents will be pushed to the remote.
    git_repo_url : str
        A URL of a remote git repo. Ideally, starts with `ssh://` and public key
        access is setup so that no password is needed.
    branch : str
        The branch to push to.
    msg : str
        The commit message to write.

    """
    with tempfile.TemporaryDirectory() as tempdir:
        wd = pathlib.Path(tempdir)
        _git(wd, local_directory, git_repo_url, branch, msg)


def _shell_in(cwd, cmd):
    return subprocess.run(cmd, shell=True, cwd=cwd)



def _git(cwd, local_directory, git_repo_url, branch, msg):
    # 1. clone the repo
    _shell_in(cwd, f"git clone {git_repo_url} remote")

    _shell_in(cwd / 'remote', f"git switch {branch} 2>/dev/null || git switch -c {branch}")

    # 2. remove all of the files
    print("Updating files...")
    _shell_in(cwd / 'remote', "rm -rf remote/*")

    # 3. copy all of the files from the local directory
    shutil.copytree(local_directory, cwd / 'remote', dirs_exist_ok=True)

    # 4. add and commit
    _shell_in(cwd / 'remote', "git add .")
    _shell_in(cwd / 'remote', f"git commit -m '{msg}'")

    # 5. push to remote
    _shell_in(cwd / 'remote', f"git push origin {branch}")
